"""Firecrawl search and scrape providers."""

from __future__ import annotations

import asyncio

import httpx

from providers import http as http_settings
from providers.base import ProviderError, dedupe_search_results
from providers.http import get_client

FIRECRAWL_SEARCH_URL = "https://api.firecrawl.dev/v2/search"
FIRECRAWL_SCRAPE_URL = "https://api.firecrawl.dev/v2/scrape"

_TBS_MAP = {
    "day": "qdr:d",
    "week": "qdr:w",
    "month": "qdr:m",
    "year": "qdr:y",
}


def _auth_headers(api_key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}


class FirecrawlSearchProvider:
    name = "firecrawl"

    def __init__(self, credential: str = "") -> None:
        self._api_key = (credential or "").strip()

    def is_configured(self) -> bool:
        return bool(self._api_key)

    async def search(
        self,
        query: str,
        num_results: int,
        categories: str,
        language: str,
        time_range: str | None,
    ) -> dict:
        del categories, language
        source: dict = {"type": "web"}
        if time_range and time_range in _TBS_MAP:
            source["tbs"] = _TBS_MAP[time_range]
        body: dict = {
            "query": query,
            "limit": num_results,
            "sources": [source],
        }

        try:
            resp = await get_client().post(
                FIRECRAWL_SEARCH_URL,
                json=body,
                headers=_auth_headers(self._api_key),
                timeout=http_settings.REQUEST_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPStatusError as e:
            raise ProviderError(f"firecrawl search returned HTTP {e.response.status_code}") from e
        except httpx.HTTPError as e:
            raise ProviderError("firecrawl search request failed") from e

        if not data.get("success", True):
            raise ProviderError("firecrawl search returned success=false")

        raw_results = []
        web = (data.get("data") or {}).get("web") or []
        for item in web:
            url = item.get("url")
            if not url:
                continue
            raw_results.append(
                {
                    "title": item.get("title", ""),
                    "url": url,
                    "snippet": item.get("description", ""),
                    "engine": "firecrawl",
                    "score": item.get("position"),
                }
            )

        return {
            "query": query,
            "results": dedupe_search_results(raw_results, num_results),
            "answers": [],
            "suggestions": [],
            "number_of_results": len(raw_results),
        }


class FirecrawlExtractProvider:
    name = "firecrawl"

    def __init__(self, credential: str = "") -> None:
        self._api_key = (credential or "").strip()

    def is_configured(self) -> bool:
        return bool(self._api_key)

    def supports_mode(self, mode: str) -> bool:
        return mode in {"fit", "raw"}

    async def extract(
        self,
        urls: list[str],
        mode: str,
        query: str | None,
        bypass_cache: bool,
    ) -> dict:
        del query, bypass_cache
        sem = asyncio.Semaphore(http_settings.MAX_CONCURRENCY)
        results = await asyncio.gather(*[self._extract_one(sem, u, mode) for u in urls])
        return {"results": list(results)}

    async def _extract_one(self, sem: asyncio.Semaphore, url: str, mode: str) -> dict:
        formats = ["rawHtml"] if mode == "raw" else ["markdown"]
        body = {"url": url, "formats": formats}

        async with sem:
            try:
                resp = await get_client().post(
                    FIRECRAWL_SCRAPE_URL,
                    json=body,
                    headers=_auth_headers(self._api_key),
                    timeout=http_settings.EXTRACT_TIMEOUT,
                )
                resp.raise_for_status()
                data = resp.json()
            except httpx.HTTPStatusError as e:
                return {
                    "url": url,
                    "status": "error",
                    "error": f"firecrawl scrape returned HTTP {e.response.status_code}",
                    "markdown": "",
                    "word_count": 0,
                }
            except httpx.HTTPError as e:
                return {
                    "url": url,
                    "status": "error",
                    "error": f"firecrawl scrape request failed: {e}",
                    "markdown": "",
                    "word_count": 0,
                }

        if not data.get("success", True):
            return {
                "url": url,
                "status": "error",
                "error": "firecrawl scrape returned success=false",
                "markdown": "",
                "word_count": 0,
            }

        page = data.get("data") or {}
        markdown = page.get("markdown") or page.get("rawHtml") or page.get("html") or ""
        return {
            "url": page.get("url", url),
            "status": "ok" if markdown else "empty",
            "markdown": markdown,
            "word_count": len(markdown.split()) if markdown else 0,
        }
