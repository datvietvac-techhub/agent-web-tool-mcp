import asyncio
import sys
from pathlib import Path

import httpx
import pytest
from cachetools import TTLCache

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "mcp"))

import tools  # noqa: E402
from providers import chain as provider_chain  # noqa: E402
from providers import http as provider_http  # noqa: E402
from url_policy import validate_fetch_url  # noqa: E402


def run(coro):
    return asyncio.run(coro)


class FakeResponse:
    def __init__(self, data, status_code=200):
        self._data = data
        self.status_code = status_code
        self.request = httpx.Request("GET", "http://example.test")

    def json(self):
        return self._data

    def raise_for_status(self):
        if self.status_code >= 400:
            response = httpx.Response(self.status_code, request=self.request)
            raise httpx.HTTPStatusError("boom", request=self.request, response=response)


class FakeClient:
    def __init__(
        self, get_responses=None, post_responses=None, get_exc=None, post_exc=None
    ):
        self.get_responses = list(get_responses or [])
        self.post_responses = list(post_responses or [])
        self.get_exc = get_exc
        self.post_exc = post_exc
        self.get_calls = []
        self.post_calls = []

    async def get(self, url, **kwargs):
        self.get_calls.append((url, kwargs))
        if self.get_exc:
            raise self.get_exc
        return self.get_responses.pop(0)

    async def post(self, url, **kwargs):
        self.post_calls.append((url, kwargs))
        if self.post_exc:
            raise self.post_exc
        return self.post_responses.pop(0)


@pytest.fixture(autouse=True)
def reset_tool_state(monkeypatch):
    monkeypatch.setattr(tools, "_search_cache", TTLCache(maxsize=512, ttl=300))
    monkeypatch.setattr(tools, "_extract_cache", TTLCache(maxsize=1024, ttl=1800))
    monkeypatch.setattr(provider_http, "SEARXNG_URL", "http://searxng:8080")
    monkeypatch.setattr(provider_http, "CRAWL4AI_URL", "http://crawl4ai:11235")
    monkeypatch.setattr(provider_http, "_client", None)
    monkeypatch.setenv("PROVIDERS_CONFIG", "/nonexistent/providers.yaml")
    provider_chain.reload_config()


def test_normalize_url_lowercases_and_preserves_query():
    assert (
        tools._normalize_url("HTTPS://Example.COM/Path/?a=1")
        == "https://example.com/Path?a=1"
    )


def test_coerce_markdown_handles_supported_shapes():
    assert tools._coerce_markdown("hello") == "hello"
    assert (
        tools._coerce_markdown({"fit_markdown": "fit", "raw_markdown": "raw"}) == "fit"
    )
    assert tools._coerce_markdown({"raw_markdown": "raw"}) == "raw"
    assert tools._coerce_markdown({"markdown": "plain"}) == "plain"
    assert tools._coerce_markdown(["nope"]) == ""


def test_validate_fetch_url_accepts_only_http_urls():
    assert validate_fetch_url("https://example.com/a") is None
    assert validate_fetch_url("http://example.com/a") is None
    assert validate_fetch_url(" ") == "url is required"
    assert (
        validate_fetch_url("ftp://example.com/a") == "url scheme must be http or https"
    )
    assert validate_fetch_url("https:///missing-host") == "url must include a host"


def test_web_search_empty_query_skips_network(monkeypatch):
    client = FakeClient()
    monkeypatch.setattr(provider_http, "_client", client)

    out = run(tools.web_search_impl("   "))

    assert out == {"query": "", "results": [], "error": "empty query"}
    assert client.get_calls == []


def test_web_search_clamps_and_deduplicates(monkeypatch):
    client = FakeClient(
        get_responses=[
            FakeResponse(
                {
                    "results": [
                        {
                            "title": "A",
                            "url": "HTTPS://Example.com/a/",
                            "content": "one",
                        },
                        {
                            "title": "B",
                            "url": "https://example.com/a",
                            "content": "dup",
                        },
                        {"title": "C", "url": "https://other.test/", "content": "two"},
                    ],
                    "suggestions": ["x", "y", "z", "a", "b", "c"],
                    "answers": ["answer"],
                    "number_of_results": 3,
                }
            )
        ]
    )
    monkeypatch.setattr(provider_http, "_client", client)

    out = run(tools.web_search_impl("hello", num_results=999))

    assert client.get_calls[0][1]["params"]["q"] == "hello"
    assert len(out["results"]) == 2
    assert [item["title"] for item in out["results"]] == ["A", "C"]
    assert out["suggestions"] == ["x", "y", "z", "a", "b"]


def test_web_search_errors_are_values(monkeypatch):
    client = FakeClient(get_responses=[FakeResponse({}, status_code=403)])
    monkeypatch.setattr(provider_http, "_client", client)

    out = run(tools.web_search_impl("hello"))

    assert out["results"] == []
    assert out["error"] == "provider request failed"


def test_web_search_explicit_provider_no_fallback(monkeypatch):
    client = FakeClient(
        get_responses=[
            FakeResponse({"results": [{"title": "Local", "url": "https://local.test"}]}),
            FakeResponse({"results": [{"title": "Should not run", "url": "https://x.test"}]}),
        ]
    )
    monkeypatch.setattr(provider_http, "_client", client)

    out = run(tools.web_search_impl("hello", provider="searxng"))

    assert out["provider"] == "searxng"
    assert len(client.get_calls) == 1


def test_web_search_unknown_provider_returns_error(monkeypatch):
    client = FakeClient()
    monkeypatch.setattr(provider_http, "_client", client)

    out = run(tools.web_search_impl("hello", provider="invalid"))

    assert "unknown search provider" in out["error"]
    assert client.get_calls == []


def test_web_extractor_explicit_provider(monkeypatch):
    client = FakeClient(
        post_responses=[FakeResponse({"url": "https://example.com", "markdown": "ok"})]
    )
    monkeypatch.setattr(provider_http, "_client", client)

    out = run(tools.web_extractor_impl("https://example.com", provider="crawl4ai"))

    assert out["provider"] == "crawl4ai"
    assert out["results"][0]["markdown"] == "ok"


def test_web_search_cache_hit_skips_second_network(monkeypatch):
    client = FakeClient(
        get_responses=[
            FakeResponse({"results": [{"title": "A", "url": "https://a.test"}]})
        ]
    )
    monkeypatch.setattr(provider_http, "_client", client)

    first = run(tools.web_search_impl("hello"))
    second = run(tools.web_search_impl("hello"))

    assert first == second
    assert len(client.get_calls) == 1


def test_web_extractor_preserves_order_and_payload(monkeypatch):
    client = FakeClient(
        post_responses=[
            FakeResponse(
                {"url": "https://a.test", "markdown": {"fit_markdown": "alpha beta"}}
            ),
            FakeResponse({"url": "https://b.test", "markdown": "gamma"}),
        ]
    )
    monkeypatch.setattr(provider_http, "_client", client)

    out = run(
        tools.web_extractor_impl(["https://a.test", "https://b.test"], mode="raw")
    )

    assert [item["url"] for item in out["results"]] == [
        "https://a.test",
        "https://b.test",
    ]
    assert out["results"][0]["word_count"] == 2
    assert client.post_calls[0][1]["json"] == {"url": "https://a.test", "f": "raw"}


def test_web_extractor_truncates_to_max_urls(monkeypatch):
    responses = [
        FakeResponse({"url": f"https://{i}.test", "markdown": "ok"}) for i in range(20)
    ]
    client = FakeClient(post_responses=responses)
    monkeypatch.setattr(provider_http, "_client", client)

    out = run(tools.web_extractor_impl([f"https://{i}.test" for i in range(25)]))

    assert len(out["results"]) == 20
    assert len(client.post_calls) == 20


def test_web_extractor_invalid_url_skips_crawl4ai(monkeypatch):
    client = FakeClient()
    monkeypatch.setattr(provider_http, "_client", client)

    out = run(tools.web_extractor_impl("file:///etc/passwd"))

    assert out["results"][0]["status"] == "error"
    assert "scheme" in out["results"][0]["error"]
    assert client.post_calls == []


def test_web_extractor_empty_url_preserves_result(monkeypatch):
    client = FakeClient()
    monkeypatch.setattr(provider_http, "_client", client)

    out = run(tools.web_extractor_impl(["", "https://example.com"]))

    assert out["results"][0]["status"] == "error"
    assert out["results"][0]["error"] == "url is required"
    assert out["results"][1]["status"] == "error"
    assert "crawl4ai request failed" in out["results"][1]["error"]


def test_web_extractor_bm25_requires_query(monkeypatch):
    client = FakeClient()
    monkeypatch.setattr(provider_http, "_client", client)

    out = run(tools.web_extractor_impl("https://example.com", mode="bm25"))

    assert out["results"][0]["status"] == "error"
    assert "query is required" in out["results"][0]["error"]
    assert client.post_calls == []


def test_web_extractor_bypass_cache_refetches(monkeypatch):
    client = FakeClient(
        post_responses=[
            FakeResponse({"url": "https://example.com", "markdown": "first"}),
            FakeResponse({"url": "https://example.com", "markdown": "second"}),
        ]
    )
    monkeypatch.setattr(provider_http, "_client", client)

    first = run(tools.web_extractor_impl("https://example.com", bypass_cache=True))
    second = run(tools.web_extractor_impl("https://example.com", bypass_cache=True))

    assert first["results"][0]["markdown"] == "first"
    assert second["results"][0]["markdown"] == "second"
    assert len(client.post_calls) == 2


def test_validate_fetch_url_ssrf_protection():
    # External URLs are allowed
    assert validate_fetch_url("http://example.com") is None

    # Block internal hostnames
    assert (
        validate_fetch_url("http://localhost:8000")
        == "url uses a disallowed internal hostname"
    )
    assert (
        validate_fetch_url("http://localhost.")
        == "url uses a disallowed internal hostname"
    )
    assert (
        validate_fetch_url("http://my-service.local")
        == "url uses a disallowed internal hostname"
    )
    assert (
        validate_fetch_url("http://db.internal")
        == "url uses a disallowed internal hostname"
    )

    # Block private, loopback, and link-local IP addresses (IPv4)
    assert (
        validate_fetch_url("http://127.0.0.1")
        == "url resolves to a disallowed internal IP address"
    )
    assert (
        validate_fetch_url("http://127.0.0.1.")
        == "url resolves to a disallowed internal IP address"
    )
    assert (
        validate_fetch_url("http://10.0.0.1")
        == "url resolves to a disallowed internal IP address"
    )
    assert (
        validate_fetch_url("http://192.168.1.100")
        == "url resolves to a disallowed internal IP address"
    )
    assert (
        validate_fetch_url("http://169.254.169.254")
        == "url resolves to a disallowed internal IP address"
    )

    # Block private/loopback IP addresses (IPv6)
    assert (
        validate_fetch_url("http://[::1]/")
        == "url resolves to a disallowed internal IP address"
    )

    # Block unspecified, reserved, and multicast IP addresses
    assert (
        validate_fetch_url("http://0.0.0.0")
        == "url resolves to a disallowed internal IP address"
    )
    assert (
        validate_fetch_url("http://224.0.0.1")
        == "url resolves to a disallowed internal IP address"
    )
    assert (
        validate_fetch_url("http://240.0.0.1")
        == "url resolves to a disallowed internal IP address"
    )
    assert (
        validate_fetch_url("http://[::]")
        == "url resolves to a disallowed internal IP address"
    )

    # Invalid resolution is allowed through here, relying on HTTP client to fail
    assert validate_fetch_url("http://this-domain-does-not-exist.com") is None
