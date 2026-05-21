"""MCP exposer for web_search and web_extractor.

Thin FastMCP layer: registers tools and delegates to `tools.py`. HTTP mode
mounts this ASGI app alongside the REST routes in `api.py`.
"""

import os

import uvicorn
from fastmcp import FastMCP

from api import create_app
from tools import web_extractor_impl, web_search_impl

MCP_TRANSPORT = os.environ.get("MCP_TRANSPORT", "http").lower()
MCP_HOST = os.environ.get("MCP_HOST", "0.0.0.0")
MCP_PORT = int(os.environ.get("MCP_PORT", "8000"))

MCP_INSTRUCTIONS = """\
MCP Web Tools exposes web_search (discovery) and web_extractor (full-page Markdown).

Workflow:
- Need to find sources? Call web_search first; use result URLs/snippets to decide what to read.
- Already have URLs? Call web_extractor directly (max 20 http/https URLs per call).

Backends come from config/providers.yaml (ordered fallback: first configured provider wins).
Do not assume a specific vendor. Successful responses include "provider" (which backend answered).
Set provider= on a tool only to force one backend with no fallback.

Errors are returned inside the JSON payload (never raised as tool exceptions):
- web_search: {"error": "...", "results": []} on total failure.
- web_extractor: per-URL {"status": "error", "error": "..."}; batch-level "error" only if every URL failed.

Caching: web_search uses an in-process cache (MCP_CACHE_TTL, default 300s).
web_extractor caches per URL (EXTRACT_CACHE_TTL, default 1800s); set bypass_cache=true to skip server cache.

Extract URLs must use http or https. localhost, .local/.internal hosts, and private/reserved IPs are rejected.
"""

mcp = FastMCP("web-tool", instructions=MCP_INSTRUCTIONS)


@mcp.tool
async def web_search(
    query: str,
    num_results: int = 10,
    categories: str = "general",
    language: str = "auto",
    time_range: str | None = None,
    provider: str | None = None,
) -> dict:
    """Search the web via the configured fallback chain; returns ranked results or an error dict (never raises).

    Args:
        query: The search query.
        num_results: Maximum number of results to return (clamped to 1-50).
        categories: Topic filter (e.g. general, news, science, it, images). Mapped per active backend;
            some providers ignore values that do not apply to them.
        language: Language hint such as "en" or "vi", or "auto" for backend default.
        time_range: Optional recency filter: "day", "week", "month", or "year".
        provider: Force one search backend with no fallback: "tavily", "firecrawl", "exa", or "searxng".
            Omit to walk the YAML chain in config/providers.yaml.

    Returns:
        On success: query, provider, results (list of {title, url, snippet, engine, score}),
        answers, suggestions, number_of_results. On failure: error and results=[].
    """
    return await web_search_impl(
        query, num_results, categories, language, time_range, provider=provider
    )


@mcp.tool
async def web_extractor(
    urls: str | list[str],
    mode: str = "fit",
    query: str | None = None,
    bypass_cache: bool = False,
    provider: str | None = None,
) -> dict:
    """Fetch http(s) URLs via the configured fallback chain; returns Markdown per URL or error dict (never raises).

    Args:
        urls: A single URL string, or a list of URL strings (max 20 per call). http/https only.
        mode: Content filter: "fit" (pruned main content), "raw" (full page),
            or "bm25"/"llm" (relevance-filtered; requires query).
        query: Focus query; required when mode is "bm25" or "llm".
        bypass_cache: If true, skip this server's in-process cache and re-fetch from the active backend.
        provider: Force one extract backend with no fallback: "tavily", "firecrawl", "exa", or "crawl4ai".
            Omit to walk the YAML chain in config/providers.yaml.

    Returns:
        On success: provider (optional), results — list of {url, status, markdown, word_count, error?}
        in the same order as input URLs. Per-URL failures use status="error" without aborting other URLs.
    """
    return await web_extractor_impl(urls, mode, query, bypass_cache, provider=provider)


if __name__ == "__main__":
    if MCP_TRANSPORT == "stdio":
        mcp.run()
    else:
        mcp_app = mcp.http_app(path="/")
        app = create_app(mcp_app)
        uvicorn.run(app, host=MCP_HOST, port=MCP_PORT)
