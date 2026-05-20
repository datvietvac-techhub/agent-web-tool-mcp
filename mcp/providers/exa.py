"""Exa search and contents providers."""

from __future__ import annotations

import httpx

from providers import http as http_settings
from providers.base import ProviderError, dedupe_search_results
from providers.http import get_client

EXA_SEARCH_URL = "https://api.exa.ai/search"
EXA_CONTENTS_URL = "https://api.exa.ai/contents"


def _auth_headers(api_key: str) -> dict[str, str]:
    return {"x-api-key": api_key, "Content-Type": "application/json"}


class ExaSearchProvider:
    name = "exa"

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
        del categories, language, time_range
        body: dict = {"query": query, "numResults": num_results, "type": "auto"}

        try:
            resp = await get_client().post(
                EXA_SEARCH_URL,
                json=body,
                headers=_auth_headers(self._api_key),
                timeout=http_settings.REQUEST_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPStatusError as e:
            raise ProviderError(f"exa search returned HTTP {e.response.status_code}") from e
        except httpx.HTTPError as e:
            raise ProviderError("exa search request failed") from e

        raw_results = []
        for item in data.get("results", []):
            url = item.get("url")
            if not url:
                continue
            highlights = item.get("highlights") or []
            snippet = item.get("text") or (highlights[0] if highlights else "")
            raw_results.append(
                {
                    "title": item.get("title", ""),
                    "url": url,
                    "snippet": snippet,
                    "engine": "exa",
                    "score": item.get("score"),
                }
            )

        return {
            "query": query,
            "results": dedupe_search_results(raw_results, num_results),
            "answers": [],
            "suggestions": [],
            "number_of_results": len(raw_results),
        }


class ExaExtractProvider:
    name = "exa"

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
        del query, bypass_cache, mode
        body = {"urls": urls, "text": True}
        try:
            resp = await get_client().post(
                EXA_CONTENTS_URL,
                json=body,
                headers=_auth_headers(self._api_key),
                timeout=http_settings.EXTRACT_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPStatusError as e:
            raise ProviderError(f"exa contents returned HTTP {e.response.status_code}") from e
        except httpx.HTTPError as e:
            raise ProviderError("exa contents request failed") from e

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
                        "error": "url not returned by exa contents",
                        "markdown": "",
                        "word_count": 0,
                    }
                )
                continue
            markdown = item.get("text") or ""
            results.append(
                {
                    "url": url,
                    "status": "ok" if markdown else "empty",
                    "markdown": markdown,
                    "word_count": len(markdown.split()) if markdown else 0,
                }
            )
        return {"results": results}
