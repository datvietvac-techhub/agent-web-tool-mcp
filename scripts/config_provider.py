#!/usr/bin/env python3
"""Write config/providers.yaml with fixed order: tavily → firecrawl → exa → local."""

from __future__ import annotations

import argparse
import getpass
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("PyYAML is required: pip install pyyaml", file=sys.stderr)
    sys.exit(1)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "config" / "providers.yaml"

SEARCH_CHAIN = ("tavily", "firecrawl", "exa", "searxng")
EXTRACT_CHAIN = ("tavily", "firecrawl", "exa", "crawl4ai")
SAAS_PROVIDERS = ("tavily", "firecrawl", "exa")

_PROMPTS = {
    "tavily": "Tavily API key",
    "firecrawl": "Firecrawl API key",
    "exa": "Exa API key",
}


def _prompt_credential(label: str) -> str:
    return getpass.getpass(f"{label} [Enter to skip]: ").strip()


def _entry(provider: str, credential: str) -> dict:
    item: dict = {"provider": provider}
    if credential:
        item["credential"] = credential
    return item


def build_providers_data(credentials: dict[str, str]) -> dict:
    def chain(providers: tuple[str, ...]) -> list[dict]:
        return [_entry(p, credentials.get(p, "")) for p in providers]

    return {"web_search": chain(SEARCH_CHAIN), "web_extract": chain(EXTRACT_CHAIN)}


def write_config(path: Path, credentials: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = build_providers_data(credentials)
    path.write_text(yaml.safe_dump(data, default_flow_style=False, sort_keys=False), encoding="utf-8")


def _print_summary(path: Path, credentials: dict[str, str]) -> None:
    print(f"\nWrote {path}")

    if not any(credentials.get(p) for p in SAAS_PROVIDERS):
        print()
        print("No API keys entered — using local providers by default:")
        print("  web_search  → searxng (self-hosted)")
        print("  web_extract → crawl4ai (self-hosted)")
        return

    for name in SAAS_PROVIDERS:
        if credentials.get(name):
            print(f"  {name}: configured")
        else:
            print(f"  {name}: skipped (no credential)")
    print("  local: searxng / crawl4ai (final fallback)")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Configure provider fallback (tavily → firecrawl → exa → local)"
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    for name in SAAS_PROVIDERS:
        parser.add_argument(f"--{name}-key", default="", help=f"{name} API key (non-interactive)")
    parser.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="non-interactive: write chains with no SaaS credentials",
    )
    args = parser.parse_args()

    print("Provider fallback order (fixed): tavily → firecrawl → exa → local")
    print("  web_search:  tavily → firecrawl → exa → searxng")
    print("  web_extract: tavily → firecrawl → exa → crawl4ai")
    print("  (Press Enter for all keys to use local providers only.)")
    print()

    credentials: dict[str, str] = {}
    if args.yes:
        pass
    elif any(getattr(args, f"{name}_key") for name in SAAS_PROVIDERS):
        for name in SAAS_PROVIDERS:
            credentials[name] = getattr(args, f"{name}_key")
    else:
        for name in SAAS_PROVIDERS:
            credentials[name] = _prompt_credential(_PROMPTS[name])

    write_config(args.config, credentials)
    _print_summary(args.config, credentials)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
