# MCP Web Tools — Self-Hosted Web Search & Extraction MCP Server for AI Agents

> Self-hosted Model Context Protocol (MCP) server giving AI agents free `web_search` and `web_extractor` tools — search via SearXNG, extract via Crawl4AI, no paid API keys.

[![License: Apache 2.0](https://img.shields.io/badge/license-Apache_2.0-blue.svg)](LICENSE)
[![Last commit](https://img.shields.io/github/last-commit/datvietvac-techhub/mcp-web-tools)](https://github.com/datvietvac-techhub/mcp-web-tools/commits/main)
[![Stars](https://img.shields.io/github/stars/datvietvac-techhub/mcp-web-tools?style=social)](https://github.com/datvietvac-techhub/mcp-web-tools/stargazers)
[![MCP Compatible](https://img.shields.io/badge/MCP-compatible-7c3aed)](https://modelcontextprotocol.io)
[![Python](https://img.shields.io/badge/python-3.12-3776AB?logo=python&logoColor=white)](mcp/Dockerfile)

> Previously known as **Agent Web Tool MCP** / [`agent-web-tool-mcp`](https://github.com/datvietvac-techhub/agent-web-tool-mcp). The repo was renamed to better match its purpose — GitHub redirects old URLs, so existing clones and links keep working.

## TL;DR

**MCP Web Tools is a self-hosted [Model Context Protocol](https://modelcontextprotocol.io) server that lets developers serve `web_search` and `web_extractor` to their AI agents locally — instead of paying per-query for [Brave Search API](https://brave.com/search/api/), [Tavily](https://tavily.com/), [Serper](https://serper.dev/), or Bing.** Search is backed by a self-hosted [SearXNG](https://docs.searxng.org/) metasearch instance aggregating ~70 engines; extraction is backed by [Crawl4AI](https://docs.crawl4ai.com/), which fetches pages with a headless Chromium and returns clean Markdown. The stack runs as a single `docker compose up` (FastMCP + SearXNG + Crawl4AI + Valkey), works with Claude Code / Cursor / any MCP client, and is Apache-2.0 licensed.

## Why self-host MCP Web Tools?

- **Free per-query**: replace Brave Search API, Tavily API, Serper, or Bing keys (each paid per query) with a SearXNG + Crawl4AI stack you control.
- **Private by default**: agent queries never leave your network — only the underlying SearXNG / Crawl4AI fetches do. No SaaS provider sees your prompts or URLs.
- **One `docker compose up`**: runs on a dev laptop, a shared internal box, or a VM. No SaaS account, no rotating API keys, no rate-limit dashboards.
- **Reproducible**: pin `VALKEY_IMAGE`, `SEARXNG_IMAGE`, `CRAWL4AI_IMAGE` in `.env` for byte-identical redeploys.
- **Standard MCP surface**: works unchanged with Claude Code, Cursor, Hermes, or any [MCP-compatible](https://modelcontextprotocol.io) client.

## What is MCP Web Tools?

**MCP Web Tools is a self-hosted MCP server that exposes two web tools — `web_search` (SearXNG-backed) and `web_extractor` (Crawl4AI-backed) — so developers can serve search and web-content extraction to AI agents locally instead of paying for Brave Search API, Tavily API, or Serper.**

The MCP server is a thin [FastMCP](https://github.com/jlowin/fastmcp) wrapper that calls SearXNG and Crawl4AI over the internal Docker network, normalizes their output, and adds a small TTL cache on top of each service's own caching. Agents only ever talk to the MCP server; the upstream services are internal.

**Use it when you need:**

- Agent web access without paying per-query for SaaS search APIs.
- Markdown extraction from arbitrary URLs (for RAG ingestion, summarization, agentic browsing, web scraping).
- A self-hostable, auditable web-tool layer that does not leak agent prompts to a third-party.
- A drop-in MCP server for Claude Code, Cursor, or any MCP-compatible client.

**Features:**

- Two MCP tools out of the box — `web_search` (SearXNG-backed, ~70 engines) and `web_extractor` (Crawl4AI-backed, returns Markdown), exposed at `http://<host>:${MCP_PORT}/mcp`.
- Self-hosted, no API keys — nothing leaves your network except the underlying SearXNG / Crawl4AI fetches.
- Transport flexible — Streamable HTTP (`MCP_TRANSPORT=http`) for remote/multi-agent, or stdio (`MCP_TRANSPORT=stdio`) for a single local client.
- Layered caching — Valkey backs SearXNG's limiter/cache; the MCP layer adds an in-process TTL cache on top.
- Parallel extraction — `web_extractor` fans out up to `MAX_CONCURRENCY` URLs per call, preserves input order, returns per-URL status.
- Official REST API — `POST /api/v1/search` and `POST /api/v1/extract` on the same port as MCP for agents that prefer plain HTTP; OpenAPI at `/docs`.
- Pinnable images — `VALKEY_IMAGE`, `SEARXNG_IMAGE`, `CRAWL4AI_IMAGE` in `.env` for reproducible deploys.
- **Hybrid provider fallback** — optional Tavily / Firecrawl / Exa API keys with self-hosted SearXNG / Crawl4AI as last resort (`config/providers.yaml`).

## Hybrid mode (SaaS + self-hosted fallback)

Use paid search/extract APIs as primary backends and keep local SearXNG / Crawl4AI as the final fallback when a provider hard-fails:

```bash
make config   # prompts for Tavily / Firecrawl / Exa keys (Enter to skip any)
make up
```

Fallback order is fixed: **tavily → firecrawl → exa → local** (SearXNG for search, Crawl4AI for extract). Skipped providers are omitted at runtime until you re-run `make config` or edit [`config/providers.yaml`](config/providers.yaml).

## How to install the MCP server for Claude Code

**Requirements:** Docker Engine + `docker compose` v2, `git`, and a free host port `8000` (MCP). SearXNG and Crawl4AI stay on the internal Docker network by default.

**1. One-liner install** (clones the repo, generates secrets, prints next steps):

```bash
curl -fsSL https://github.com/datvietvac-techhub/mcp-web-tools/releases/latest/download/install.sh | bash
```

The script clones to `~/.local/share/mcp-web-tool` (override with `--dir <path>`), creates `.env`, and generates a random `SEARXNG_SECRET`. It does **not** start containers — that's `make up`.

**2. Start the stack:**

```bash
cd ~/.local/share/mcp-web-tool
make up      # docker compose up -d
make smoke   # verify MCP plus internal SearXNG/Crawl4AI endpoints
```

First `make up` pulls the Crawl4AI image (~GB, includes Chromium) — budget a couple of minutes.

**3. Connect Claude Code** (or any MCP client) to `http://localhost:8000/mcp`:

```bash
claude mcp add --transport http web-tool http://localhost:8000/mcp
```

For other clients (Cursor, Hermes, etc.):

```json
{
  "mcpServers": {
    "web-tool": { "transport": "http", "url": "http://localhost:8000/mcp" }
  }
}
```

For a single local client launching the server as a subprocess, set `MCP_TRANSPORT=stdio` in `.env` and point the client at `python mcp/server.py`.

See [docs/install.md](docs/install.md) for manual install, `make` targets, smoke tests, and stdio configuration.

**Upgrading:** from your install directory, run `make update` (syncs code, rebuilds the stack, runs smoke tests). See [docs/install.md#upgrading](docs/install.md#upgrading).

## How does the web_search tool work (SearXNG)?

`web_search` is an MCP tool that queries a self-hosted SearXNG metasearch instance (aggregating ~70 search engines including Google, Bing, DuckDuckGo, Brave, Wikipedia) and returns ranked, de-duplicated results to the agent. Results are normalized to a stable JSON shape, cached in-process for `MCP_CACHE_TTL` seconds (default `300`), and clamped to `1..50` per call.

```python
# Tool signature (called by the MCP client / agent)
web_search(
    query: str,                  # search query
    num_results: int = 10,       # clamped to 1..50
    categories: str = "general", # "general" | "news" | "science" | "it" | "images" | ...
    language: str = "auto",      # "en" | "vi" | ...; "auto" lets SearXNG decide
    time_range: str | None = None,  # "day" | "week" | "month" | "year"
)
```

Response shape:

```json
{
  "query": "...",
  "results": [
    {"title": "...", "url": "https://...", "snippet": "...", "engine": "...", "score": 1.0}
  ],
  "answers": [],
  "suggestions": ["..."],
  "number_of_results": 12345
}
```

On failure the dict includes an `"error"` key and `"results": []` — tools return errors as values, never raise. Full parameter reference and tuning knobs: [docs/config.md#web_search](docs/config.md#web_search).

## How does the web_extractor tool work (Crawl4AI)?

`web_extractor` is an MCP tool that fetches one or more URLs via a self-hosted Crawl4AI service (headless Chromium) and returns clean Markdown — pruned to the main content by default. URLs are fetched in parallel up to `MAX_CONCURRENCY` (default `5`), max 20 URLs per call, with per-URL caching for `EXTRACT_CACHE_TTL` seconds (default `1800`).

```python
# Tool signature
web_extractor(
    urls: str | list[str],       # one URL or a list, max 20 per call
    mode: str = "fit",           # "fit" | "raw" | "bm25" | "llm"
    query: str | None = None,    # required for "bm25" / "llm" relevance filtering
    bypass_cache: bool = False,  # force a re-fetch
)
```

Response shape (order matches input URLs):

```json
{
  "results": [
    {
      "url": "https://...",
      "status": "ok",
      "markdown": "# Heading\n...",
      "word_count": 1234
    }
  ]
}
```

Per-URL failures surface as `{"status": "error", "error": "...", "markdown": ""}` without aborting the whole call. Full mode reference, tuning, and caching keys: [docs/config.md#web_extractor](docs/config.md#web_extractor).

## HTTP API (for agents without MCP)

The same `web_search` and `web_extractor` implementations are also exposed as a REST API on `${MCP_PORT}` (default `8000`), beside the MCP endpoint:

| Method | Path | Description |
|---|---|---|
| `GET` | `/healthz` | Liveness probe |
| `POST` | `/api/v1/search` | Same params/response as `web_search` |
| `POST` | `/api/v1/extract` | Same params/response as `web_extractor` |
| `GET` | `/docs` | Swagger UI (OpenAPI) |

```bash
# Search
curl -sX POST http://localhost:8000/api/v1/search \
  -H 'content-type: application/json' \
  -d '{"query":"fastmcp","num_results":5}'

# Extract
curl -sX POST http://localhost:8000/api/v1/extract \
  -H 'content-type: application/json' \
  -d '{"urls":["https://example.com"],"mode":"fit"}'
```

Set `API_TOKEN` in `.env` to require `Authorization: Bearer <token>` on `/api/v1/*`. Full reference: [docs/config.md#http-api](docs/config.md#http-api).

## MCP Web Tools vs Brave Search MCP vs Tavily MCP

A side-by-side of self-hosted MCP Web Tools against the two most common hosted alternatives most teams reach for first:

| | **MCP Web Tools (this project)** | Brave Search MCP | Tavily MCP |
|---|---|---|---|
| Hosting | **Self-hosted** (Docker Compose) | Hosted SaaS API | Hosted SaaS API |
| API key required | **None** | Brave Search API key | Tavily API key |
| Web search | Yes (SearXNG, ~70 engines) | Yes (Brave index) | Yes (Tavily index) |
| Page extraction → Markdown | Yes (Crawl4AI, headless Chromium) | No | Yes (Tavily Extract) |
| Output format | JSON + Markdown | JSON | JSON + Markdown |
| Cost | **$0** per query (your compute only) | Free tier + paid tiers | Free tier + paid tiers |
| Data leaves your network | Only target sites; queries stay local | Yes — sent to Brave | Yes — sent to Tavily |
| License | Apache-2.0 (open source) | Proprietary service | Proprietary service |

Pick MCP Web Tools if you want zero per-query cost, no vendor lock-in, full control over the search/crawl layer, and prompts that never hit a third-party SaaS. Pick Brave or Tavily if you don't want to run any infrastructure.

## Documentation

Full docs are published on GitHub Pages: **https://datvietvac-techhub.github.io/mcp-web-tools/**

- [Install guide](docs/install.md) — one-liner, manual clone, `make` targets, smoke tests, agent connect snippets.
- [Configuration reference](docs/config.md) — every `.env` variable + full `web_search` / `web_extractor` parameter tables + HTTP API.
- [Architecture](docs/architecture.md) — service topology, request flow, Mermaid diagrams, gotchas.
- [Changelog](CHANGELOG.md) — release notes (Keep a Changelog format).

For LLM ingestion / RAG indexing of this project, see [llms.txt](llms.txt) and [llms-full.txt](llms-full.txt).

## Contributing

Bug reports, feature requests, and PRs are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for the dev loop, coding conventions, and PR checklist. Security issues: see [SECURITY.md](SECURITY.md).

## License & Attributions

Licensed under the [Apache License, Version 2.0](LICENSE).

The `web_extractor` tool is powered by [Crawl4AI](https://github.com/unclecode/crawl4ai), a headless-browser crawler developed by [UncleCode](https://x.com/unclecode). As required by the Crawl4AI license:

> "This product includes software developed by UncleCode (https://x.com/unclecode) as part of the Crawl4AI project (https://github.com/unclecode/crawl4ai)."

Full third-party notices: [NOTICE](NOTICE).

---

_Project: **MCP Web Tools** (repo: `mcp-web-tools`, formerly `agent-web-tool-mcp`) · Version: 1.0.0 · Updated: 2026-05_
