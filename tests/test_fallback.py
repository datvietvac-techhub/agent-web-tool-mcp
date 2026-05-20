import asyncio
import sys
from pathlib import Path
from urllib.parse import urlparse

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "mcp"))

import tools  # noqa: E402
from providers import chain as provider_chain  # noqa: E402
from providers import http as provider_http  # noqa: E402
from test_tools import FakeResponse  # noqa: E402


def run(coro):
    return asyncio.run(coro)


@pytest.fixture(autouse=True)
def reset_state(monkeypatch, tmp_path):
    config = tmp_path / "providers.yaml"
    config.write_text(
        "web_search:\n"
        "  - provider: tavily\n"
        "    credential: tavily-key\n"
        "  - provider: searxng\n"
        "web_extract:\n"
        "  - provider: crawl4ai\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("PROVIDERS_CONFIG", str(config))
    provider_chain.reload_config()
    monkeypatch.setattr(provider_http, "_client", None)
    monkeypatch.setattr(provider_http, "SEARXNG_URL", "http://searxng:8080")
    monkeypatch.setattr(provider_http, "CRAWL4AI_URL", "http://crawl4ai:11235")
    monkeypatch.setattr(tools, "_search_cache", None)
    monkeypatch.setattr(tools, "_extract_cache", None)


def test_search_fallback_on_primary_hard_failure(monkeypatch):
    calls = []

    class RoutingClient:
        async def get(self, url, **kwargs):
            calls.append(url)
            return FakeResponse(
                {
                    "results": [{"title": "Local", "url": "https://local.test", "content": "x"}],
                    "suggestions": [],
                    "answers": [],
                }
            )

        async def post(self, url, **kwargs):
            calls.append(url)
            if urlparse(url).hostname == "api.tavily.com":
                response = httpx.Response(503, request=httpx.Request("POST", url))
                raise httpx.HTTPStatusError("fail", request=kwargs.get("request") or httpx.Request("POST", url), response=response)
            raise AssertionError(f"unexpected post to {url}")

    monkeypatch.setattr(provider_http, "_client", RoutingClient())

    out = run(tools.web_search_impl("hello"))

    assert out["provider"] == "searxng"
    assert len(out["results"]) == 1
    assert any(urlparse(u).hostname == "api.tavily.com" for u in calls)
    assert any("searxng" in u for u in calls)


def test_search_no_fallback_on_empty_results(monkeypatch):
    class RoutingClient:
        async def get(self, url, **kwargs):
            return FakeResponse({"results": []})

        async def post(self, url, **kwargs):
            if urlparse(url).hostname == "api.tavily.com":
                return FakeResponse({"results": []})
            raise AssertionError(f"unexpected post to {url}")

    monkeypatch.setattr(provider_http, "_client", RoutingClient())

    out = run(tools.web_search_impl("hello"))

    assert out["provider"] == "tavily"
    assert out["results"] == []
