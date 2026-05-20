"""Shared HTTP client and environment-backed settings."""

from __future__ import annotations

import os

import httpx

SEARXNG_URL = os.environ.get("SEARXNG_URL", "http://localhost:8080").rstrip("/")
CRAWL4AI_URL = os.environ.get("CRAWL4AI_URL", "http://localhost:11235").rstrip("/")
CRAWL4AI_API_TOKEN = os.environ.get("CRAWL4AI_API_TOKEN", "").strip()

REQUEST_TIMEOUT = float(os.environ.get("REQUEST_TIMEOUT", "30"))
EXTRACT_TIMEOUT = float(os.environ.get("EXTRACT_TIMEOUT", "60"))
MAX_CONCURRENCY = int(os.environ.get("MAX_CONCURRENCY", "5"))
MAX_URLS_PER_CALL = 20

FALLBACK_VERBOSE = os.environ.get("FALLBACK_VERBOSE", "").lower() in ("1", "true", "yes")

_client: httpx.AsyncClient | None = None


def get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(
            follow_redirects=True,
            headers={"User-Agent": "mcp-web-tool/1.0"},
        )
    return _client


def reset_client() -> None:
    global _client
    _client = None
