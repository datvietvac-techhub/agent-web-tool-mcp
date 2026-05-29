import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "mcp"))

from providers.base import interpolate_credential  # noqa: E402
from providers.config import ProviderEntry, load_providers_config  # noqa: E402
from providers.registry import entry_is_skipped  # noqa: E402


def test_interpolate_credential_expands_env(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "secret-key")
    assert interpolate_credential("${TAVILY_API_KEY}", os.environ) == "secret-key"


def test_load_providers_config_defaults_when_missing(tmp_path, monkeypatch):
    missing = tmp_path / "nope.yaml"
    monkeypatch.setenv("PROVIDERS_CONFIG", str(missing))
    cfg = load_providers_config()
    assert [e.provider for e in cfg.web_search] == ["searxng"]
    assert [e.provider for e in cfg.web_extract] == ["crawl4ai"]


def test_load_providers_config_preserves_order(tmp_path, monkeypatch):
    path = tmp_path / "providers.yaml"
    path.write_text(
        "web_search:\n"
        "  - provider: tavily\n"
        "    credential: key-t\n"
        "  - provider: firecrawl\n"
        "    credential: key-f\n"
        "  - provider: exa\n"
        "    credential: key-e\n"
        "  - provider: searxng\n"
        "web_extract:\n"
        "  - provider: crawl4ai\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("PROVIDERS_CONFIG", str(path))
    cfg = load_providers_config()
    assert [e.provider for e in cfg.web_search] == [
        "tavily",
        "firecrawl",
        "exa",
        "searxng",
    ]
    assert cfg.web_search[0].credential == "key-t"


def test_entry_is_skipped_for_empty_saas_credential():
    assert entry_is_skipped(
        ProviderEntry(provider="firecrawl", credential=""), "search"
    )
    assert not entry_is_skipped(
        ProviderEntry(provider="searxng", credential=""), "search"
    )


def test_make_config_writes_fixed_chains(tmp_path):
    script = Path(__file__).resolve().parents[1] / "scripts" / "config_provider.py"
    config = tmp_path / "providers.yaml"

    import subprocess

    subprocess.run(
        [
            sys.executable,
            str(script),
            "--config",
            str(config),
            "--tavily-key",
            "tavily-secret",
            "--firecrawl-key",
            "firecrawl-secret",
            "--exa-key",
            "exa-secret",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    cfg = load_providers_config(config)
    assert [e.provider for e in cfg.web_search] == [
        "tavily",
        "firecrawl",
        "exa",
        "searxng",
    ]
    assert [e.provider for e in cfg.web_extract] == [
        "tavily",
        "firecrawl",
        "exa",
        "crawl4ai",
    ]
    assert cfg.web_search[1].credential == "firecrawl-secret"


def test_make_config_yes_skips_saas_credentials(tmp_path):
    script = Path(__file__).resolve().parents[1] / "scripts" / "config_provider.py"
    config = tmp_path / "providers.yaml"

    import subprocess

    subprocess.run(
        [sys.executable, str(script), "--config", str(config), "--yes"],
        check=True,
        capture_output=True,
        text=True,
    )

    cfg = load_providers_config(config)
    assert [e.provider for e in cfg.web_search] == [
        "tavily",
        "firecrawl",
        "exa",
        "searxng",
    ]
    assert cfg.web_search[0].credential == ""
    assert cfg.web_search[2].credential == ""
