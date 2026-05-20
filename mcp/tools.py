"""Core implementations for web_search and web_extractor.

Delegates to YAML-configured provider fallback chains. Transport layers delegate here.
"""

from __future__ import annotations

import os

from cachetools import TTLCache

from providers.base import coerce_markdown, normalize_url
from providers.chain import run_extract_chain, run_extract_provider, run_search_chain, run_search_provider
from providers.http import MAX_URLS_PER_CALL
from url_policy import validate_fetch_url

SEARCH_CACHE_TTL = int(os.environ.get("MCP_CACHE_TTL", "300"))
EXTRACT_CACHE_TTL = int(os.environ.get("EXTRACT_CACHE_TTL", "1800"))

_search_cache = TTLCache(maxsize=512, ttl=SEARCH_CACHE_TTL) if SEARCH_CACHE_TTL > 0 else None
_extract_cache = TTLCache(maxsize=1024, ttl=EXTRACT_CACHE_TTL) if EXTRACT_CACHE_TTL > 0 else None


def _normalize_url(url: str) -> str:
    return normalize_url(url)


def _coerce_markdown(value) -> str:
    return coerce_markdown(value)


def _normalize_provider(provider: str | None) -> str | None:
    if provider is None:
        return None
    value = provider.strip().lower()
    return value or None


async def web_search_impl(
    query: str,
    num_results: int = 10,
    categories: str = "general",
    language: str = "auto",
    time_range: str | None = None,
    provider: str | None = None,
) -> dict:
    query = (query or "").strip()
    if not query:
        return {"query": query, "results": [], "error": "empty query"}
    num_results = max(1, min(int(num_results), 50))
    provider_id = _normalize_provider(provider)

    cache_key = (query, num_results, categories, language, time_range, provider_id)
    if _search_cache is not None and cache_key in _search_cache:
        return _search_cache[cache_key]

    if provider_id:
        out = await run_search_provider(
            provider_id, query, num_results, categories, language, time_range
        )
    else:
        out = await run_search_chain(query, num_results, categories, language, time_range)
    if _search_cache is not None and "error" not in out:
        _search_cache[cache_key] = out
    return out


def _extract_validation_error(url: str, mode: str, query: str | None) -> dict | None:
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
    return None


async def web_extractor_impl(
    urls: str | list[str],
    mode: str = "fit",
    query: str | None = None,
    bypass_cache: bool = False,
    provider: str | None = None,
) -> dict:
    url_list = [urls] if isinstance(urls, str) else list(urls)
    url_list = [u.strip() if isinstance(u, str) else "" for u in url_list]
    if not url_list:
        return {"results": [], "error": "no urls provided"}
    if len(url_list) > MAX_URLS_PER_CALL:
        url_list = url_list[:MAX_URLS_PER_CALL]

    provider_id = _normalize_provider(provider)

    results: list[dict] = []
    fetch_urls: list[str] = []
    fetch_positions: list[int] = []

    for url in url_list:
        invalid = _extract_validation_error(url, mode, query)
        if invalid:
            results.append(invalid)
            continue

        norm = normalize_url(url)
        cache_key = (norm, mode, query, provider_id)
        if not bypass_cache and _extract_cache is not None and cache_key in _extract_cache:
            results.append(_extract_cache[cache_key])
            continue

        fetch_positions.append(len(results))
        results.append({})
        fetch_urls.append(url)

    if not fetch_urls:
        return {"results": results}

    if provider_id:
        fetched = await run_extract_provider(provider_id, fetch_urls, mode, query, bypass_cache)
    else:
        fetched = await run_extract_chain(fetch_urls, mode, query, bypass_cache)
    for pos, url, item in zip(
        fetch_positions, fetch_urls, fetched.get("results", []), strict=False
    ):
        results[pos] = item
        if not bypass_cache and _extract_cache is not None and item.get("markdown") and item.get(
            "status"
        ) == "ok":
            _extract_cache[(normalize_url(url), mode, query, provider_id)] = item

    out: dict = {"results": results}
    if "provider" in fetched:
        out["provider"] = fetched["provider"]
    if "fallback_attempts" in fetched:
        out["fallback_attempts"] = fetched["fallback_attempts"]
    if "error" in fetched and not any(r.get("status") == "ok" for r in results):
        out["error"] = fetched["error"]
    return out
