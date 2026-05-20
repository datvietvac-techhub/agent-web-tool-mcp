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

mcp = FastMCP("web-tool")


@mcp.tool
async def web_search(
    query: str,
    num_results: int = 10,
    categories: str = "general",
    language: str = "auto",
    time_range: str | None = None,
    provider: str | None = None,
) -> dict:
    """Search the web using the configured provider fallback chain and return ranked results.

    Args:
        query: The search query.
        num_results: Maximum number of results to return (clamped to 1-50).
        categories: SearXNG category, e.g. "general", "news", "science", "it", "images".
        language: Language code such as "en" or "vi", or "auto" to let SearXNG decide.
        time_range: Optional recency filter: "day", "week", "month", or "year".
        provider: Force a single search backend: "tavily", "firecrawl", "exa", or "searxng".
            Omit to use the YAML fallback chain.

    Returns:
        A dict with keys: query, provider, results (list of {title, url, snippet, engine, score}),
        answers, suggestions, number_of_results. On failure, includes an "error" key.
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
    """Fetch one or more URLs via the configured extract fallback chain and return markdown.

    Args:
        urls: A single URL string, or a list of URL strings (max 20 per call).
        mode: Markdown filter: "fit" (pruned main content), "raw" (full page),
              or "bm25"/"llm" (relevance-filtered; requires `query`).
        query: Focus query, used when mode is "bm25" or "llm".
        bypass_cache: If true, skip this server's cache and ask Crawl4AI to re-fetch.
        provider: Force a single extract backend: "tavily", "firecrawl", "exa", or "crawl4ai".
            Omit to use the YAML fallback chain.

    Returns:
        A dict with keys: provider (on success), results — a list of
        {url, status, markdown, word_count, error?} in the same order as the input URLs.
    """
    return await web_extractor_impl(urls, mode, query, bypass_cache, provider=provider)


if __name__ == "__main__":
    if MCP_TRANSPORT == "stdio":
        mcp.run()
    else:
        mcp_app = mcp.http_app(path="/")
        app = create_app(mcp_app)
        uvicorn.run(app, host=MCP_HOST, port=MCP_PORT)
