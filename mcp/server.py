"""MCP server exposing two web tools backed by SearXNG and Crawl4AI.

Tools:
  - web_search(query, ...)     -> ranked search results from a self-hosted SearXNG
  - web_extractor(urls, ...)   -> clean markdown for one or more URLs via Crawl4AI
"""

import asyncio
import os
from urllib.parse import urlsplit, urlunsplit

import httpx
from cachetools import TTLCache
from fastmcp import FastMCP

SEARXNG_URL = os.environ.get("SEARXNG_URL", "http://localhost:8080").rstrip("/")
CRAWL4AI_URL = os.environ.get("CRAWL4AI_URL", "http://localhost:11235").rstrip("/")
CRAWL4AI_API_TOKEN = os.environ.get("CRAWL4AI_API_TOKEN", "").strip()

REQUEST_TIMEOUT = float(os.environ.get("REQUEST_TIMEOUT", "30"))
EXTRACT_TIMEOUT = float(os.environ.get("EXTRACT_TIMEOUT", "60"))
MAX_CONCURRENCY = int(os.environ.get("MAX_CONCURRENCY", "5"))
MAX_URLS_PER_CALL = 20

SEARCH_CACHE_TTL = int(os.environ.get("MCP_CACHE_TTL", "300"))
EXTRACT_CACHE_TTL = int(os.environ.get("EXTRACT_CACHE_TTL", "1800"))

MCP_TRANSPORT = os.environ.get("MCP_TRANSPORT", "http").lower()
MCP_HOST = os.environ.get("MCP_HOST", "0.0.0.0")
MCP_PORT = int(os.environ.get("MCP_PORT", "8000"))

mcp = FastMCP("web-tool")

_search_cache = TTLCache(maxsize=512, ttl=SEARCH_CACHE_TTL) if SEARCH_CACHE_TTL > 0 else None
_extract_cache = TTLCache(maxsize=1024, ttl=EXTRACT_CACHE_TTL) if EXTRACT_CACHE_TTL > 0 else None

_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(
            follow_redirects=True,
            headers={"User-Agent": "mcp-web-tool/1.0"},
        )
    return _client


def _normalize_url(url: str) -> str:
    try:
        parts = urlsplit(url.strip())
        path = parts.path.rstrip("/") or "/"
        return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, parts.query, ""))
    except Exception:
        return url.strip()


def _coerce_markdown(value) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return value.get("fit_markdown") or value.get("raw_markdown") or value.get("markdown") or ""
    return ""


@mcp.tool
async def web_search(
    query: str,
    num_results: int = 10,
    categories: str = "general",
    language: str = "auto",
    time_range: str | None = None,
) -> dict:
    """Search the web via a self-hosted SearXNG instance and return ranked results.

    Args:
        query: The search query.
        num_results: Maximum number of results to return (clamped to 1-50).
        categories: SearXNG category, e.g. "general", "news", "science", "it", "images".
        language: Language code such as "en" or "vi", or "auto" to let SearXNG decide.
        time_range: Optional recency filter: "day", "week", "month", or "year".

    Returns:
        A dict with keys: query, results (list of {title, url, snippet, engine, score}),
        answers, suggestions, number_of_results. On failure, includes an "error" key.
    """
    query = (query or "").strip()
    if not query:
        return {"query": query, "results": [], "error": "empty query"}
    num_results = max(1, min(int(num_results), 50))

    cache_key = (query, num_results, categories, language, time_range)
    if _search_cache is not None and cache_key in _search_cache:
        return _search_cache[cache_key]

    params = {"q": query, "format": "json", "categories": categories, "pageno": 1}
    if language and language != "auto":
        params["language"] = language
    if time_range:
        params["time_range"] = time_range

    try:
        resp = await _get_client().get(
            f"{SEARXNG_URL}/search", params=params, timeout=REQUEST_TIMEOUT
        )
        resp.raise_for_status()
        data = resp.json()
    except httpx.HTTPStatusError as e:
        return {
            "query": query,
            "results": [],
            "error": f"searxng returned HTTP {e.response.status_code} "
            f"(is the 'json' format enabled in searxng/settings.yml?)",
        }
    except Exception as e:  # noqa: BLE001 - surface any transport/parse error to the agent
        return {"query": query, "results": [], "error": f"searxng request failed: {e}"}

    seen: set[str] = set()
    results: list[dict] = []
    for item in data.get("results", []):
        url = item.get("url")
        if not url:
            continue
        key = _normalize_url(url)
        if key in seen:
            continue
        seen.add(key)
        results.append(
            {
                "title": item.get("title", ""),
                "url": url,
                "snippet": item.get("content", ""),
                "engine": item.get("engine", ""),
                "score": item.get("score"),
            }
        )
        if len(results) >= num_results:
            break

    out = {
        "query": query,
        "results": results,
        "answers": data.get("answers", []),
        "suggestions": (data.get("suggestions") or [])[:5],
        "number_of_results": data.get("number_of_results"),
    }
    if _search_cache is not None:
        _search_cache[cache_key] = out
    return out


async def _extract_one(
    sem: asyncio.Semaphore, url: str, mode: str, query: str | None, bypass_cache: bool
) -> dict:
    norm = _normalize_url(url)
    cache_key = (norm, mode, query)
    if not bypass_cache and _extract_cache is not None and cache_key in _extract_cache:
        return _extract_cache[cache_key]

    payload: dict = {"url": url, "f": mode}
    if query:
        payload["q"] = query
    if bypass_cache:
        payload["c"] = "0"

    headers: dict[str, str] = {}
    if CRAWL4AI_API_TOKEN:
        headers["Authorization"] = f"Bearer {CRAWL4AI_API_TOKEN}"

    async with sem:
        try:
            resp = await _get_client().post(
                f"{CRAWL4AI_URL}/md", json=payload, headers=headers, timeout=EXTRACT_TIMEOUT
            )
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPStatusError as e:
            return {
                "url": url,
                "status": "error",
                "error": f"crawl4ai returned HTTP {e.response.status_code}",
                "markdown": "",
                "word_count": 0,
            }
        except Exception as e:  # noqa: BLE001
            return {
                "url": url,
                "status": "error",
                "error": f"crawl4ai request failed: {e}",
                "markdown": "",
                "word_count": 0,
            }

    markdown = _coerce_markdown(data.get("markdown"))
    result = {
        "url": data.get("url", url),
        "status": "ok" if markdown else "empty",
        "markdown": markdown,
        "word_count": len(markdown.split()) if markdown else 0,
    }
    if not bypass_cache and _extract_cache is not None and markdown:
        _extract_cache[cache_key] = result
    return result


@mcp.tool
async def web_extractor(
    urls: str | list[str],
    mode: str = "fit",
    query: str | None = None,
    bypass_cache: bool = False,
) -> dict:
    """Fetch one or more URLs via Crawl4AI and return clean markdown.

    Args:
        urls: A single URL string, or a list of URL strings (max 20 per call).
        mode: Markdown filter: "fit" (pruned main content), "raw" (full page),
              or "bm25"/"llm" (relevance-filtered; requires `query`).
        query: Focus query, used when mode is "bm25" or "llm".
        bypass_cache: If true, skip this server's cache and ask Crawl4AI to re-fetch.

    Returns:
        A dict with key "results": a list of {url, status, markdown, word_count, error?}
        in the same order as the input URLs.
    """
    url_list = [urls] if isinstance(urls, str) else list(urls)
    url_list = [u.strip() for u in url_list if u and u.strip()]
    if not url_list:
        return {"results": [], "error": "no urls provided"}
    if len(url_list) > MAX_URLS_PER_CALL:
        url_list = url_list[:MAX_URLS_PER_CALL]

    sem = asyncio.Semaphore(MAX_CONCURRENCY)
    results = await asyncio.gather(
        *[_extract_one(sem, u, mode, query, bypass_cache) for u in url_list]
    )
    return {"results": list(results)}


if __name__ == "__main__":
    if MCP_TRANSPORT == "stdio":
        mcp.run()
    else:
        mcp.run(transport="http", host=MCP_HOST, port=MCP_PORT)
