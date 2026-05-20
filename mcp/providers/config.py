"""Load and validate config/providers.yaml."""

from __future__ import annotations

import logging
import os
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, field_validator

from providers.base import interpolate_credential

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_PATH = Path("config/providers.yaml")


def config_path() -> Path:
    return Path(os.environ.get("PROVIDERS_CONFIG", str(DEFAULT_CONFIG_PATH)))

SEARCH_PROVIDER_IDS = frozenset({"tavily", "firecrawl", "exa", "searxng"})
EXTRACT_PROVIDER_IDS = frozenset({"tavily", "firecrawl", "exa", "crawl4ai"})


class ProviderEntry(BaseModel):
    provider: str
    credential: str = ""

    @field_validator("provider")
    @classmethod
    def normalize_provider(cls, value: str) -> str:
        return value.strip().lower()


class ProvidersConfig(BaseModel):
    web_search: list[ProviderEntry] = Field(default_factory=list)
    web_extract: list[ProviderEntry] = Field(default_factory=list)


def _dedupe_entries(entries: list[ProviderEntry]) -> list[ProviderEntry]:
    seen: set[str] = set()
    out: list[ProviderEntry] = []
    for entry in entries:
        if entry.provider in seen:
            continue
        seen.add(entry.provider)
        out.append(entry)
    return out


def _resolve_entries(
    entries: list[ProviderEntry], allowed: frozenset[str]
) -> list[ProviderEntry]:
    environ = os.environ
    resolved: list[ProviderEntry] = []
    for entry in entries:
        if entry.provider not in allowed:
            logger.warning("unknown provider %r — skipping", entry.provider)
            continue
        cred = interpolate_credential(entry.credential or None, environ)
        resolved.append(ProviderEntry(provider=entry.provider, credential=cred))
    return _dedupe_entries(resolved)


def _default_config() -> ProvidersConfig:
    return ProvidersConfig(
        web_search=[ProviderEntry(provider="searxng")],
        web_extract=[ProviderEntry(provider="crawl4ai")],
    )


def load_providers_config(path: str | Path | None = None) -> ProvidersConfig:
    cfg_path = Path(path) if path is not None else config_path()
    if not cfg_path.is_file():
        logger.info("providers config not found at %s — using defaults", cfg_path)
        return _default_config()

    raw = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise ValueError(f"invalid providers config at {cfg_path}: expected mapping")

    model = ProvidersConfig.model_validate(raw)
    search = _resolve_entries(model.web_search, SEARCH_PROVIDER_IDS)
    extract = _resolve_entries(model.web_extract, EXTRACT_PROVIDER_IDS)

    if not search:
        logger.warning("web_search chain empty — defaulting to searxng")
        search = [ProviderEntry(provider="searxng")]
    if not extract:
        logger.warning("web_extract chain empty — defaulting to crawl4ai")
        extract = [ProviderEntry(provider="crawl4ai")]

    return ProvidersConfig(web_search=search, web_extract=extract)


def get_search_chain(config: ProvidersConfig | None = None) -> list[ProviderEntry]:
    cfg = config or load_providers_config()
    return list(cfg.web_search)


def get_extract_chain(config: ProvidersConfig | None = None) -> list[ProviderEntry]:
    cfg = config or load_providers_config()
    return list(cfg.web_extract)


def resolve_provider_entry(
    provider_id: str,
    chain_kind: str,
    config: ProvidersConfig | None = None,
) -> ProviderEntry | None:
    """Resolve a provider id to a chain entry (credential from YAML when present)."""
    allowed = SEARCH_PROVIDER_IDS if chain_kind == "search" else EXTRACT_PROVIDER_IDS
    pid = (provider_id or "").strip().lower()
    if pid not in allowed:
        return None
    cfg = config or load_providers_config()
    chain = cfg.web_search if chain_kind == "search" else cfg.web_extract
    for entry in chain:
        if entry.provider == pid:
            return entry
    return ProviderEntry(provider=pid)
