# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Search engine fallback** — YAML-configured provider chains in `config/providers.yaml` for `web_search` and `web_extract` (Tavily → Firecrawl → Exa → local). Hard-failure-only fallback; list order is priority (first = primary).
- `make config` to write provider chains and optionally prompt for Tavily, Firecrawl, and Exa API keys.
- Provider adapters under `mcp/providers/` with optional `FALLBACK_VERBOSE` diagnostics.

- Official REST API v1 on the same port as MCP: `POST /api/v1/search`, `POST /api/v1/extract`, `GET /healthz`, OpenAPI at `/docs`.
- Optional bearer auth for REST via `API_TOKEN` env var.
- `web-mcp` Docker healthcheck on `/healthz`.
- `make update` — one-command upgrade: sync git, bootstrap, pull upstream images, rebuild `web-mcp`, restart, and smoke.
- `update.sh` — curl-pipe wrapper for the same flow (attach to GitHub Releases alongside `install.sh`).
- [Upgrading](docs/install.md#upgrading) section in install docs and README pointer.
- Documentation site (MkDocs Material) published at <https://datvietvac-techhub.github.io/mcp-web-tools/>.
- `llms.txt` and `llms-full.txt` at repo root for LLM ingestion ([llmstxt.org](https://llmstxt.org)).
- `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `CHANGELOG.md` (this file), GitHub issue & PR templates.
- JSON-LD `SoftwareApplication` schema on the docs landing page, including `alternateName` entries for the previous project names.
- "Why self-host MCP Web Tools?" section in README leading with the cost/privacy/control angle vs paid SaaS search APIs.

### Removed

- Dev-only FastAPI playground (`make playground`, `mcp/playground.py`, `PLAYGROUND_PORT`). Use `/api/v1/*` and `/docs` on the main server instead.

### Changed

- Renamed repository to `mcp-web-tools` (from `agent-web-tool-mcp`). GitHub redirects old URLs, so existing clones, links, and badge sources keep working.
- Project display name updated from "Agent Web Tool MCP" to **MCP Web Tools**. JSON-LD `alternateName` retains both legacy names ("Agent Web Tool MCP", "agent-web-tool-mcp") for backlink continuity.
- README and docs rewritten to lead with the self-host purpose: developers serve `web_search` and `web_extractor` to their AI agents locally instead of paying per-query for Brave Search API, Tavily, Serper, or Bing.
- README and docs rewritten for SEO + LLM citation friendliness: keyword-rich H1, TL;DR block, Q-style H2s, and a comparison table vs Brave Search MCP / Tavily MCP. Deep reference content moved to the docs site.
- `SECURITY.md` replaced placeholder template with real policy (reporting via GitHub Security Advisories).
- `install.sh` `REPO_URL` and help text updated to the new repo slug; default install dir, container names, and compose project name remain unchanged for deployment compatibility.

### Notes

- Internal Docker service (`web-mcp`), container (`web-tool-{valkey,searxng,crawl4ai,mcp}`), network (`web-tool-net`), volume (`valkey-data`), FastMCP server name (`web-tool`), SearXNG `instance_name`, default install dir (`~/.local/share/mcp-web-tool`), and User-Agent string retain the project's previous slug to preserve deployment compatibility for existing installs. They will be unified to the `mcp-web-tools-*` prefix in a future major release.

## [1.0.0] - 2026-05

Initial public release.

### Added

- `web_search` MCP tool — queries a self-hosted [SearXNG](https://docs.searxng.org/) metasearch instance, returns ranked & de-duplicated results, supports `categories`, `language`, `time_range` filters, clamps to 1–50 results.
- `web_extractor` MCP tool — fetches one or more URLs via [Crawl4AI](https://docs.crawl4ai.com/) (headless Chromium) and returns clean Markdown. Supports `fit` / `raw` / `bm25` / `llm` modes, parallel fetching up to `MAX_CONCURRENCY`, max 20 URLs per call.
- [FastMCP](https://github.com/jlowin/fastmcp)-based server with Streamable HTTP and stdio transports (`MCP_TRANSPORT=http|stdio`).
- 4-service Docker Compose stack — `web-mcp` + `searxng` + `crawl4ai` + `valkey` on a single bridge network (`web-tool-net`).
- Valkey-backed cache + rate-limiter for SearXNG; in-process TTL cache in the MCP layer (`MCP_CACHE_TTL`, `EXTRACT_CACHE_TTL`).
- `install.sh` one-liner installer with curl-pipe + manual-clone modes, prerequisite checks, `.env` bootstrap, automatic `SEARXNG_SECRET` generation. Idempotent and safe to re-run.
- FastAPI dev playground (`make playground`) sharing the same tool implementations as the MCP server, with Swagger UI at `/docs`.
- Makefile convenience targets: `bootstrap`, `install`, `up`, `down`, `restart`, `ps`, `logs`, `build`, `pull`, `smoke`, `secret`, `playground`, `clean`.
- Pinnable upstream images via `VALKEY_IMAGE`, `SEARXNG_IMAGE`, `CRAWL4AI_IMAGE` for reproducible deploys.

[Unreleased]: https://github.com/datvietvac-techhub/mcp-web-tools/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/datvietvac-techhub/mcp-web-tools/releases/tag/v1.0.0
