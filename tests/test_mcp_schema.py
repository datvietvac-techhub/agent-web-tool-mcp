"""Regression tests for MCP tool descriptions exposed to agents."""

import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "mcp"))

import server  # noqa: E402

_PROVIDER_NOISE = ("searxng category", "crawl4ai", "let searxng")


def _prop(schema: dict, name: str) -> dict:
    return schema["properties"][name]


@pytest.fixture
def mcp_tools():
    return asyncio.run(server.mcp.list_tools())


def test_mcp_server_has_instructions():
    assert server.MCP_INSTRUCTIONS
    assert "web_search" in server.MCP_INSTRUCTIONS
    assert "web_extractor" in server.MCP_INSTRUCTIONS
    assert "config/providers.yaml" in server.MCP_INSTRUCTIONS


def test_mcp_tool_names(mcp_tools):
    names = {t.name for t in mcp_tools}
    assert names == {"web_search", "web_extractor"}


def test_mcp_tool_summaries_mention_contract(mcp_tools):
    by_name = {t.name: t for t in mcp_tools}
    search_desc = by_name["web_search"].description.lower()
    extract_desc = by_name["web_extractor"].description.lower()

    assert "fallback" in search_desc or "provider" in search_desc
    assert "error" in search_desc or "never raises" in search_desc
    assert "markdown" in extract_desc
    assert "http" in extract_desc


def test_mcp_param_descriptions_are_provider_agnostic(mcp_tools):
    by_name = {t.name: t for t in mcp_tools}
    search_schema = by_name["web_search"].parameters
    extract_schema = by_name["web_extractor"].parameters

    for field in ("categories", "language", "bypass_cache"):
        if field == "bypass_cache":
            desc = _prop(extract_schema, field)["description"].lower()
        else:
            desc = _prop(search_schema, field)["description"].lower()
        for phrase in _PROVIDER_NOISE:
            assert phrase not in desc, (
                f"{field} still names a vendor: {phrase!r} in {desc!r}"
            )

    provider_search = _prop(search_schema, "provider")["description"].lower()
    provider_extract = _prop(extract_schema, "provider")["description"].lower()
    assert "yaml" in provider_search
    assert "yaml" in provider_extract
