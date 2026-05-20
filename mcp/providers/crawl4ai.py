"""Crawl4AI extract provider (local)."""

from __future__ import annotations

import asyncio

import httpx

from providers import http as http_settings
from providers.base import coerce_markdown
from providers.http import get_client


class Crawl4aiExtractProvider:
    name = "crawl4ai"

    def __init__(self, credential: str = "") -> None:
        self._credential = (credential or "").strip()

    def is_configured(self) -> bool:
        return bool(http_settings.CRAWL4AI_URL)

    def _token(self) -> str:
        return self._credential or http_settings.CRAWL4AI_API_TOKEN

    def supports_mode(self, mode: str) -> bool:
        return mode in {"fit", "raw", "bm25", "llm"}

    async def extract(
        self,
        urls: list[str],
        mode: str,
        query: str | None,
        bypass_cache: bool,
    ) -> dict:
        sem = asyncio.Semaphore(http_settings.MAX_CONCURRENCY)
        results = await asyncio.gather(
            *[self._extract_one(sem, u, mode, query, bypass_cache) for u in urls]
        )
        return {"results": list(results)}

    async def _extract_one(
        self,
        sem: asyncio.Semaphore,
        url: str,
        mode: str,
        focus_query: str | None,
        bypass_cache: bool,
    ) -> dict:
        payload: dict = {"url": url, "f": mode}
        if focus_query:
            payload["q"] = focus_query
        if bypass_cache:
            payload["c"] = "0"

        headers: dict[str, str] = {}
        token = self._token()
        if token:
            headers["Authorization"] = f"Bearer {token}"

        async with sem:
            try:
                resp = await get_client().post(
                    f"{http_settings.CRAWL4AI_URL}/md",
                    json=payload,
                    headers=headers,
                    timeout=http_settings.EXTRACT_TIMEOUT,
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
            except httpx.HTTPError as e:
                return {
                    "url": url,
                    "status": "error",
                    "error": f"crawl4ai request failed: {e}",
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

        markdown = coerce_markdown(data.get("markdown"))
        return {
            "url": data.get("url", url),
            "status": "ok" if markdown else "empty",
            "markdown": markdown,
            "word_count": len(markdown.split()) if markdown else 0,
        }
