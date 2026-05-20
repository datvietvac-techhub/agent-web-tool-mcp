"""Tavily search and extract providers."""

from __future__ import annotations

import httpx

from providers.base import ProviderError, coerce_markdown, dedupe_search_results
from providers import http as http_settings
from providers.http import get_client

TAVILY_SEARCH_URL = "https://api.tavily.com/search"
TAVILY_EXTRACT_URL = "https://api.tavily.com/extract"

_TOPIC_MAP = {
    "general": "general",
    "news": "news",
    "science": "general",
    "it": "general",
    "images": "general",
}

_TIME_RANGE_MAP = {
    "day": "day",
    "week": "week",
    "month": "month",
    "year": "year",
}


def _auth_headers(api_key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}


class TavilySearchProvider:
    name = "tavily"

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
        body: dict = {
            "query": query,
            "max_results": num_results,
            "topic": _TOPIC_MAP.get(categories, "general"),
            "search_depth": "basic",
        }
        if language and language != "auto":
            body["include_answer"] = False
        if time_range and time_range in _TIME_RANGE_MAP:
            body["time_range"] = _TIME_RANGE_MAP[time_range]

        try:
            resp = await get_client().post(
                TAVILY_SEARCH_URL,
                json=body,
                headers=_auth_headers(self._api_key),
                timeout=http_settings.REQUEST_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPStatusError as e:
            raise ProviderError(f"tavily search returned HTTP {e.response.status_code}") from e
        except httpx.HTTPError as e:
            raise ProviderError("tavily search request failed") from e

        raw_results = []
        for item in data.get("results", []):
            url = item.get("url")
            if not url:
                continue
            raw_results.append(
                {
                    "title": item.get("title", ""),
                    "url": url,
                    "snippet": item.get("content", ""),
                    "engine": "tavily",
                    "score": item.get("score"),
                }
            )

        suggestions = []
        answer = data.get("answer")
        if answer:
            suggestions.append(str(answer)[:200])

        return {
            "query": query,
            "results": dedupe_search_results(raw_results, num_results),
            "answers": [answer] if answer else [],
            "suggestions": suggestions[:5],
            "number_of_results": len(raw_results),
        }


class TavilyExtractProvider:
    name = "tavily"

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
        del mode, query, bypass_cache
        body = {"urls": urls}
        try:
            resp = await get_client().post(
                TAVILY_EXTRACT_URL,
                json=body,
                headers=_auth_headers(self._api_key),
                timeout=http_settings.EXTRACT_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPStatusError as e:
            raise ProviderError(f"tavily extract returned HTTP {e.response.status_code}") from e
        except httpx.HTTPError as e:
            raise ProviderError("tavily extract request failed") from e

        by_url: dict[str, dict] = {}
        for item in data.get("results", []):
            u = item.get("url")
            if u:
                by_url[u] = item

        results = []
        for url in urls:
            item = by_url.get(url)
            if not item:
                results.append(
                    {
                        "url": url,
                        "status": "error",
                        "error": "url not returned by tavily extract",
                        "markdown": "",
                        "word_count": 0,
                    }
                )
                continue
            raw = item.get("raw_content") or item.get("content") or ""
            markdown = raw if isinstance(raw, str) else coerce_markdown(raw)
            results.append(
                {
                    "url": url,
                    "status": "ok" if markdown else "empty",
                    "markdown": markdown,
                    "word_count": len(markdown.split()) if markdown else 0,
                }
            )
        return {"results": results}
