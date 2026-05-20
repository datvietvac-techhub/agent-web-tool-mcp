"""Fallback chain orchestration (YAML order: top = primary, bottom = last)."""

from __future__ import annotations

import logging

from providers.base import ProviderError
from providers.config import (
    EXTRACT_PROVIDER_IDS,
    SEARCH_PROVIDER_IDS,
    ProviderEntry,
    get_extract_chain,
    get_search_chain,
    load_providers_config,
    resolve_provider_entry,
)
from providers.http import FALLBACK_VERBOSE
from providers.registry import (
    build_extract_provider,
    build_search_provider,
    entry_is_skipped,
)

logger = logging.getLogger(__name__)

_config = None


def _get_config():
    global _config
    if _config is None:
        _config = load_providers_config()
    return _config


def reload_config() -> None:
    global _config
    _config = None


def _invalid_provider_error(provider_id: str, chain_kind: str) -> dict:
    allowed = sorted(SEARCH_PROVIDER_IDS if chain_kind == "search" else EXTRACT_PROVIDER_IDS)
    label = "search" if chain_kind == "search" else "extract"
    return {
        "error": f"unknown {label} provider {provider_id!r}; valid: {', '.join(allowed)}",
    }


async def _run_search_entry(entry: ProviderEntry, query: str, num_results: int, categories: str, language: str, time_range: str | None) -> dict:
    if entry_is_skipped(entry, "search"):
        return {
            "query": query,
            "results": [],
            "error": f"provider {entry.provider!r} is not configured (missing API key in providers.yaml)",
        }
    provider = build_search_provider(entry)
    try:
        result = await provider.search(query, num_results, categories, language, time_range)
        if "error" in result:
            result["provider"] = entry.provider
            return result
        result["provider"] = entry.provider
        return result
    except ProviderError:
        logger.exception("search provider %s raised ProviderError", entry.provider)
        return {
            "query": query,
            "results": [],
            "error": "provider request failed",
            "provider": entry.provider,
        }


async def _run_extract_entry(
    entry: ProviderEntry, urls: list[str], mode: str, query: str | None, bypass_cache: bool
) -> dict:
    if entry_is_skipped(entry, "extract"):
        return {
            "results": [],
            "error": f"provider {entry.provider!r} is not configured (missing API key in providers.yaml)",
        }
    provider = build_extract_provider(entry)
    if not provider.supports_mode(mode):
        return {
            "results": [],
            "error": f"provider {entry.provider!r} does not support extract mode {mode!r}",
        }
    try:
        result = await provider.extract(urls, mode, query, bypass_cache)
        if "error" in result and not result.get("results"):
            result["provider"] = entry.provider
            return result
        result["provider"] = entry.provider
        return result
    except ProviderError:
        logger.exception("extract provider %s raised ProviderError", entry.provider)
        return {"results": [], "error": "provider request failed", "provider": entry.provider}


async def run_search_provider(
    provider_id: str,
    query: str,
    num_results: int,
    categories: str,
    language: str,
    time_range: str | None,
) -> dict:
    entry = resolve_provider_entry(provider_id, "search", _get_config())
    if entry is None:
        err = _invalid_provider_error(provider_id, "search")
        return {"query": query, "results": [], **err}
    return await _run_search_entry(entry, query, num_results, categories, language, time_range)


async def run_extract_provider(
    provider_id: str,
    urls: list[str],
    mode: str,
    query: str | None,
    bypass_cache: bool,
) -> dict:
    entry = resolve_provider_entry(provider_id, "extract", _get_config())
    if entry is None:
        err = _invalid_provider_error(provider_id, "extract")
        return {"results": [], **err}
    return await _run_extract_entry(entry, urls, mode, query, bypass_cache)


async def run_search_chain(
    query: str,
    num_results: int,
    categories: str,
    language: str,
    time_range: str | None,
) -> dict:
    chain = get_search_chain(_get_config())
    attempts: list[dict] = []
    last_error = "all search providers failed"

    for entry in chain:
        if entry_is_skipped(entry, "search"):
            attempts.append({"provider": entry.provider, "skipped": "not configured"})
            continue
        result = await _run_search_entry(entry, query, num_results, categories, language, time_range)
        if "error" in result and not result.get("results"):
            last_error = result["error"]
            attempts.append({"provider": entry.provider, "error": last_error})
            logger.warning("search provider %s failed: %s", entry.provider, last_error)
            continue
        if FALLBACK_VERBOSE:
            result["fallback_attempts"] = attempts + [
                {"provider": entry.provider, "status": "ok"}
            ]
        return result

    out = {"query": query, "results": [], "error": last_error}
    if FALLBACK_VERBOSE:
        out["fallback_attempts"] = attempts
    return out


async def run_extract_chain(
    urls: list[str],
    mode: str,
    query: str | None,
    bypass_cache: bool,
) -> dict:
    chain = get_extract_chain(_get_config())
    attempts: list[dict] = []
    last_error = "all extract providers failed"

    for entry in chain:
        if entry_is_skipped(entry, "extract"):
            attempts.append({"provider": entry.provider, "skipped": "not configured"})
            continue
        provider = build_extract_provider(entry)
        if not provider.supports_mode(mode):
            attempts.append({"provider": entry.provider, "skipped": f"unsupported mode {mode}"})
            continue
        result = await _run_extract_entry(entry, urls, mode, query, bypass_cache)
        if "error" in result and not result.get("results"):
            last_error = result["error"]
            attempts.append({"provider": entry.provider, "error": last_error})
            logger.warning("extract provider %s failed: %s", entry.provider, last_error)
            continue
        if FALLBACK_VERBOSE:
            result["fallback_attempts"] = attempts + [
                {"provider": entry.provider, "status": "ok"}
            ]
        return result

    out = {"results": [], "error": last_error}
    if FALLBACK_VERBOSE:
        out["fallback_attempts"] = attempts
    return out
