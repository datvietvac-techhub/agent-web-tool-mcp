"""SearXNG search provider (local)."""

from __future__ import annotations

import httpx

from providers.base import ProviderError, dedupe_search_results
from providers import http as http_settings
from providers.http import get_client


class SearxngSearchProvider:
    name = "searxng"

    def __init__(self, credential: str = "") -> None:
        self._credential = credential

    def is_configured(self) -> bool:
        return bool(http_settings.SEARXNG_URL)

    async def search(
        self,
        query: str,
        num_results: int,
        categories: str,
        language: str,
        time_range: str | None,
    ) -> dict:
        params = {"q": query, "format": "json", "categories": categories, "pageno": 1}
        if language and language != "auto":
            params["language"] = language
        if time_range:
            params["time_range"] = time_range

        try:
            resp = await get_client().get(
                f"{http_settings.SEARXNG_URL}/search",
                params=params,
                timeout=http_settings.REQUEST_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPStatusError as e:
            raise ProviderError(
                f"searxng returned HTTP {e.response.status_code} "
                f"(is the 'json' format enabled in searxng/settings.yml?)"
            ) from e
        except httpx.HTTPError as e:
            raise ProviderError("searxng request failed") from e

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
                    "engine": item.get("engine", ""),
                    "score": item.get("score"),
                }
            )

        return {
            "query": query,
            "results": dedupe_search_results(raw_results, num_results),
            "answers": data.get("answers", []),
            "suggestions": (data.get("suggestions") or [])[:5],
            "number_of_results": data.get("number_of_results"),
        }
