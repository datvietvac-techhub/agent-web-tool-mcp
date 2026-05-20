import sys
from pathlib import Path

import pytest
from cachetools import TTLCache
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "mcp"))

import api  # noqa: E402
import server  # noqa: E402
import tools  # noqa: E402
from providers import chain as provider_chain  # noqa: E402
from providers import http as provider_http  # noqa: E402
from test_tools import FakeClient, FakeResponse, run  # noqa: E402


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(api, "API_TOKEN", "")
    return TestClient(api.create_app())


@pytest.fixture(autouse=True)
def reset_tool_state(monkeypatch):
    monkeypatch.setattr(tools, "_search_cache", TTLCache(maxsize=512, ttl=300))
    monkeypatch.setattr(tools, "_extract_cache", TTLCache(maxsize=1024, ttl=1800))
    monkeypatch.setattr(provider_http, "SEARXNG_URL", "http://searxng:8080")
    monkeypatch.setattr(provider_http, "CRAWL4AI_URL", "http://crawl4ai:11235")
    monkeypatch.setattr(provider_http, "_client", None)
    monkeypatch.setenv("PROVIDERS_CONFIG", "/nonexistent/providers.yaml")
    provider_chain.reload_config()


def test_healthz(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_search_happy_path(client, monkeypatch):
    fake = FakeClient(
        get_responses=[FakeResponse({"results": [{"title": "A", "url": "https://a.test"}]})]
    )
    monkeypatch.setattr(provider_http, "_client", fake)

    response = client.post("/api/v1/search", json={"query": "hello", "num_results": 3})

    assert response.status_code == 200
    assert response.json()["results"][0]["title"] == "A"


def test_extract_happy_path(client, monkeypatch):
    fake = FakeClient(
        post_responses=[FakeResponse({"url": "https://example.com", "markdown": "hello world"})]
    )
    monkeypatch.setattr(provider_http, "_client", fake)

    response = client.post("/api/v1/extract", json={"urls": "https://example.com"})

    assert response.status_code == 200
    assert response.json()["results"][0]["status"] == "ok"
    assert response.json()["results"][0]["word_count"] == 2


def test_search_validation_error(client):
    response = client.post("/api/v1/search", json={})
    assert response.status_code == 422


def test_search_upstream_error_is_value(client, monkeypatch):
    fake = FakeClient(get_responses=[FakeResponse({}, status_code=503)])
    monkeypatch.setattr(provider_http, "_client", fake)

    response = client.post("/api/v1/search", json={"query": "hello"})

    assert response.status_code == 200
    body = response.json()
    assert body["results"] == []
    assert body["error"] == "provider request failed"


def test_api_token_required(monkeypatch):
    monkeypatch.setattr(api, "API_TOKEN", "secret")
    client = TestClient(api.create_app())

    response = client.post("/api/v1/search", json={"query": "hello"})
    assert response.status_code == 401

    response = client.post(
        "/api/v1/search",
        json={"query": "hello"},
        headers={"Authorization": "Bearer wrong"},
    )
    assert response.status_code == 401

    fake = FakeClient(get_responses=[FakeResponse({"results": []})])
    monkeypatch.setattr(provider_http, "_client", fake)
    response = client.post(
        "/api/v1/search",
        json={"query": "hello"},
        headers={"Authorization": "Bearer secret"},
    )
    assert response.status_code == 200


def test_healthz_unauthenticated_when_api_token_set(monkeypatch):
    monkeypatch.setattr(api, "API_TOKEN", "secret")
    client = TestClient(api.create_app())

    response = client.get("/healthz")
    assert response.status_code == 200


def test_mcp_and_http_parity(monkeypatch):
    fake = FakeClient(
        get_responses=[
            FakeResponse(
                {
                    "results": [{"title": "A", "url": "https://a.test", "content": "snippet"}],
                    "suggestions": [],
                    "answers": [],
                    "number_of_results": 1,
                }
            )
        ]
    )
    monkeypatch.setattr(provider_http, "_client", fake)

    http_client = TestClient(api.create_app())
    http_out = http_client.post("/api/v1/search", json={"query": "parity"}).json()
    mcp_out = run(server.web_search("parity"))

    assert http_out == mcp_out
