"""Instantiate providers from YAML chain entries."""

from __future__ import annotations

from providers.config import ProviderEntry
from providers.crawl4ai import Crawl4aiExtractProvider
from providers.exa import ExaExtractProvider, ExaSearchProvider
from providers.firecrawl import FirecrawlExtractProvider, FirecrawlSearchProvider
from providers.searxng import SearxngSearchProvider
from providers.tavily import TavilyExtractProvider, TavilySearchProvider

_SAAS_PROVIDERS = frozenset({"tavily", "firecrawl", "exa"})


def build_search_provider(entry: ProviderEntry):
    if entry.provider == "tavily":
        return TavilySearchProvider(entry.credential)
    if entry.provider == "firecrawl":
        return FirecrawlSearchProvider(entry.credential)
    if entry.provider == "exa":
        return ExaSearchProvider(entry.credential)
    if entry.provider == "searxng":
        return SearxngSearchProvider(entry.credential)
    raise ValueError(f"unknown search provider: {entry.provider}")


def build_extract_provider(entry: ProviderEntry):
    if entry.provider == "tavily":
        return TavilyExtractProvider(entry.credential)
    if entry.provider == "firecrawl":
        return FirecrawlExtractProvider(entry.credential)
    if entry.provider == "exa":
        return ExaExtractProvider(entry.credential)
    if entry.provider == "crawl4ai":
        return Crawl4aiExtractProvider(entry.credential)
    raise ValueError(f"unknown extract provider: {entry.provider}")


def entry_is_skipped(entry: ProviderEntry, chain_kind: str) -> bool:
    del chain_kind
    if entry.provider in _SAAS_PROVIDERS:
        return not (entry.credential or "").strip()
    return False
