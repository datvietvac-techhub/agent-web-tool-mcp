---
title: MCP Web Tools — Self-Hosted Web Search & Extraction MCP
description: Self-hosted Model Context Protocol (MCP) server giving AI agents free web_search and web_extractor tools — search via SearXNG, extract via Crawl4AI, no paid API keys.
---

# MCP Web Tools

> Self-hosted Model Context Protocol (MCP) server giving AI agents free `web_search` and `web_extractor` tools — search via SearXNG, extract via Crawl4AI, no paid API keys.

> Previously known as **Agent Web Tool MCP** / [`agent-web-tool-mcp`](https://github.com/datvietvac-techhub/agent-web-tool-mcp). GitHub redirects old URLs — existing clones and links keep working.

**MCP Web Tools is a self-hosted [Model Context Protocol](https://modelcontextprotocol.io) server that lets developers serve `web_search` and `web_extractor` to their AI agents locally — instead of paying per-query for [Brave Search API](https://brave.com/search/api/), [Tavily](https://tavily.com/), or [Serper](https://serper.dev/).** Search is backed by a self-hosted [SearXNG](https://docs.searxng.org/) metasearch instance aggregating ~70 engines; extraction is backed by [Crawl4AI](https://docs.crawl4ai.com/), which fetches pages with a headless Chromium and returns clean Markdown.

The whole stack is a 4-service Docker Compose deployment: [FastMCP](https://github.com/jlowin/fastmcp) server + SearXNG + Crawl4AI + [Valkey](https://valkey.io/) cache. Apache-2.0 licensed.

## Why self-host MCP Web Tools?

- **Free per-query**: replace Brave Search API / Tavily API / Serper / Bing keys (each paid per query) with a stack you control.
- **Private by default**: agent queries never leave your network — only the underlying SearXNG / Crawl4AI fetches do.
- **One `docker compose up`**: runs on a dev laptop, a shared internal box, or a VM. No SaaS account, no rotating API keys.
- **Reproducible**: pin every upstream image for byte-identical redeploys.
- **Standard MCP surface**: works unchanged with Claude Code, Cursor, Hermes, or any MCP-compatible client.

## Use cases

- Agent web access without paying per-query for SaaS search APIs.
- Markdown extraction from arbitrary URLs (for RAG ingestion, summarization, agentic browsing, web scraping).
- A self-hostable, auditable web-tool layer that does not leak agent prompts to a third-party SaaS.
- A single `docker compose up` to add web capability to Claude Code, Cursor, or any MCP-compatible client.

## Quick links

- **[Install guide](install.md)** — one-liner installer, manual clone, `make` targets, smoke tests, agent connect snippets.
- **[Configuration reference](config.md)** — every `.env` variable + full `web_search` / `web_extractor` parameter tables + dev playground.
- **[Architecture](architecture.md)** — service topology, request flow, Mermaid diagrams, gotchas.
- **[Changelog](changelog.md)** — release notes.
- **[Source on GitHub](https://github.com/datvietvac-techhub/mcp-web-tools)** — Apache-2.0.

## At a glance

| | |
|---|---|
| Hosting | Self-hosted (Docker Compose) |
| API key required | None |
| Tools | `web_search`, `web_extractor` |
| Search backend | SearXNG (~70 engines) |
| Extraction backend | Crawl4AI (headless Chromium) |
| Transport | Streamable HTTP (default) or stdio |
| Cache | Valkey + in-process TTL cache |
| License | Apache-2.0 |

## One-liner install

```bash
curl -fsSL https://github.com/datvietvac-techhub/mcp-web-tools/releases/latest/download/install.sh | bash
cd ~/.local/share/mcp-web-tool
make up && make smoke
claude mcp add --transport http web-tool http://localhost:8000/mcp
```

See the [install guide](install.md) for details.
