"""Core implementations for web_search and web_extractor.

Single source of truth for SearXNG / Crawl4AI logic, caching, and URL policy.
Transport layers (`server.py` for MCP, `api.py` for HTTP) delegate here.
"""

import asyncio
import os
from urllib.parse import urlsplit, urlunsplit

import httpx
from cachetools import TTLCache
from url_policy import validate_fetch_url

SEARXNG_URL = os.environ.get("SEARXNG_URL", "http://localhost:8080").rstrip("/")
CRAWL4AI_URL = os.environ.get("CRAWL4AI_URL", "http://localhost:11235").rstrip("/")
CRAWL4AI_API_TOKEN = os.environ.get("CRAWL4AI_API_TOKEN", "").strip()

REQUEST_TIMEOUT = float(os.environ.get("REQUEST_TIMEOUT", "30"))
EXTRACT_TIMEOUT = float(os.environ.get("EXTRACT_TIMEOUT", "60"))
MAX_CONCURRENCY = int(os.environ.get("MAX_CONCURRENCY", "5"))
MAX_URLS_PER_CALL = 20

SEARCH_CACHE_TTL = int(os.environ.get("MCP_CACHE_TTL", "300"))
EXTRACT_CACHE_TTL = int(os.environ.get("EXTRACT_CACHE_TTL", "1800"))

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


async def web_search_impl(
    query: str,
    num_results: int = 10,
    categories: str = "general",
    language: str = "auto",
    time_range: str | None = None,
) -> dict:
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
    except Exception:  # noqa: BLE001 - keep broad handling, but do not expose internals to clients
        return {"query": query, "results": [], "error": "searxng request failed"}

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
    validation_error = validate_fetch_url(url)
    if validation_error:
        return {
            "url": url,
            "status": "error",
            "error": validation_error,
            "markdown": "",
            "word_count": 0,
        }
    if mode in {"bm25", "llm"} and not (query or "").strip():
        return {
            "url": url,
            "status": "error",
            "error": f"query is required for {mode} mode",
            "markdown": "",
            "word_count": 0,
        }

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


async def web_extractor_impl(
    urls: str | list[str],
    mode: str = "fit",
    query: str | None = None,
    bypass_cache: bool = False,
) -> dict:
    url_list = [urls] if isinstance(urls, str) else list(urls)
    url_list = [u.strip() if isinstance(u, str) else "" for u in url_list]
    if not url_list:
        return {"results": [], "error": "no urls provided"}
    if len(url_list) > MAX_URLS_PER_CALL:
        url_list = url_list[:MAX_URLS_PER_CALL]

    sem = asyncio.Semaphore(MAX_CONCURRENCY)
    results = await asyncio.gather(
        *[_extract_one(sem, u, mode, query, bypass_cache) for u in url_list]
    )
    return {"results": list(results)}
