"""Shared types and helpers for provider adapters."""

from __future__ import annotations

import re
from typing import Protocol
from urllib.parse import urlsplit, urlunsplit

_ENV_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


class ProviderError(Exception):
    """Hard failure from an upstream provider (triggers fallback)."""


def interpolate_credential(value: str | None, environ: dict[str, str]) -> str:
    if not value:
        return ""

    def repl(match: re.Match[str]) -> str:
        key = match.group(1)
        return environ.get(key, "")

    return _ENV_PATTERN.sub(repl, value.strip())


def normalize_url(url: str) -> str:
    try:
        parts = urlsplit(url.strip())
        path = parts.path.rstrip("/") or "/"
        return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, parts.query, ""))
    except Exception:
        return url.strip()


def coerce_markdown(value) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return value.get("fit_markdown") or value.get("raw_markdown") or value.get("markdown") or ""
    return ""


def dedupe_search_results(items: list[dict], num_results: int) -> list[dict]:
    seen: set[str] = set()
    results: list[dict] = []
    for item in items:
        url = item.get("url")
        if not url:
            continue
        key = normalize_url(url)
        if key in seen:
            continue
        seen.add(key)
        results.append(item)
        if len(results) >= num_results:
            break
    return results


class SearchProvider(Protocol):
    name: str

    def is_configured(self) -> bool: ...

    async def search(
        self,
        query: str,
        num_results: int,
        categories: str,
        language: str,
        time_range: str | None,
    ) -> dict: ...


class ExtractProvider(Protocol):
    name: str

    def is_configured(self) -> bool: ...

    def supports_mode(self, mode: str) -> bool: ...

    async def extract(
        self,
        urls: list[str],
        mode: str,
        query: str | None,
        bypass_cache: bool,
    ) -> dict: ...
