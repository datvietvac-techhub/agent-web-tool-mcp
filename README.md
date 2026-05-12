# mcp-web-tool

A single `docker compose` stack that gives AI agents two web tools over MCP:

- **`web_search`** — web search via a self-hosted [SearXNG](https://docs.searxng.org/) metasearch instance (no third-party API keys).
- **`web_extractor`** — fetch one or more URLs and return clean Markdown via [Crawl4AI](https://docs.crawl4ai.com/) (headless-browser crawler).

The MCP server is a thin [FastMCP](https://github.com/jlowin/fastmcp) wrapper that calls SearXNG and Crawl4AI over the internal Docker network, normalizes their output, and adds a small TTL cache on top of each service's own caching.

## Architecture

```
docker-compose.yml  (network: web-tool-net)
  valkey     valkey/valkey:8-alpine                  cache / limiter backend for SearXNG
  searxng    searxng/searxng        :8080            metasearch, JSON API enabled
  crawl4ai   unclecode/crawl4ai     :11235           REST crawler (/md, /crawl), shm_size 1g
  web-mcp    build ./mcp            :8000            MCP server — tools: web_search, web_extractor
```

## Install

**Requirements on the target machine:** Docker Engine + the `docker compose` v2 plugin. That's it — everything else runs in containers.

```bash
git clone <this-repo> mcp-web-tool
cd mcp-web-tool
./install.sh
```

`install.sh` is idempotent (safe to re-run). It checks prerequisites, creates `.env` from `.env.example`, generates `SEARXNG_SECRET` for you, builds the `web-mcp` image, brings the stack up, waits for `searxng` + `crawl4ai` to report healthy, and runs smoke tests against all three endpoints. First run pulls the Crawl4AI image (~GB, includes Chromium) — budget a couple of minutes.

Flags: `--no-build` (skip rebuilding the MCP image), `--pull` (refresh upstream images first), `--no-smoke`, `--skip-checks`, `--help`.

If `docker` needs `sudo` on your box, run `sudo ./install.sh` (or add yourself to the `docker` group: `sudo usermod -aG docker "$USER" && newgrp docker`).

### Day-to-day (`make`)

```
make install   # = ./install.sh   (forward flags with ARGS="--pull")
make up        # start            make down      # stop (keeps cache volume)
make restart   # restart          make ps        # status
make logs      # tail logs        make smoke     # re-run the endpoint smoke tests
make build     # rebuild web-mcp  make pull      # refresh upstream images
make secret    # print a fresh SEARXNG_SECRET value
make clean     # stop + remove the valkey cache volume
```

### Manual install (no script)

```bash
cp .env.example .env
echo "SEARXNG_SECRET=$(openssl rand -hex 32)" >> .env   # or edit .env by hand
docker compose up -d --build
docker compose ps        # wait until searxng + crawl4ai are "healthy"
```

## Smoke tests

```bash
# SearXNG JSON API
curl -s "http://localhost:8080/search?q=anthropic+claude&format=json" | jq '.results[0]'

# Crawl4AI markdown endpoint
curl -s -X POST http://localhost:11235/md \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://example.com","f":"fit"}' | jq '.markdown'

# MCP server: inspect tools
npx @modelcontextprotocol/inspector       # then connect to http://localhost:8000/mcp
```

## Connecting an agent

The MCP server listens on **`http://<host>:8000/mcp`** (Streamable HTTP) by default.

Claude Code:

```bash
claude mcp add --transport http web-tool http://localhost:8000/mcp
```

Any MCP client config (Hermes, etc.):

```json
{
  "mcpServers": {
    "web-tool": { "transport": "http", "url": "http://localhost:8000/mcp" }
  }
}
```

To run the MCP server over stdio instead (single local client launches it as a subprocess), set `MCP_TRANSPORT=stdio` in `.env`. In that mode you typically don't expose port 8000; point the client at `python mcp/server.py` (or `docker compose run`).

## Tools

### `web_search(query, num_results=10, categories="general", language="auto", time_range=None)`

Returns `{ query, results: [{title, url, snippet, engine, score}], answers, suggestions, number_of_results }`. Results are de-duplicated by normalized URL and truncated to `num_results`. `time_range` accepts `day` / `week` / `month` / `year`.

### `web_extractor(urls, mode="fit", query=None, bypass_cache=False)`

`urls` is a single URL string or a list (max 20). Returns `{ results: [{url, status, markdown, word_count, error?}] }` in input order. `mode`:

- `fit` — pruned main-content markdown (default)
- `raw` — full-page markdown
- `bm25` / `llm` — relevance-filtered; requires `query`

Multiple URLs are fetched in parallel (`MAX_CONCURRENCY`, default 5).

## Configuration

Everything is set via `.env` (see `.env.example`): `SEARXNG_SECRET`, `CRAWL4AI_API_TOKEN`, `MCP_TRANSPORT`, `MCP_CACHE_TTL`, `EXTRACT_CACHE_TTL`, `REQUEST_TIMEOUT`, `EXTRACT_TIMEOUT`, `MAX_CONCURRENCY`. Set a cache TTL to `0` to disable that layer.

`SEARXNG_SECRET` is **not** an API key — nothing sends it. SearXNG uses it server-side to sign image-proxy URLs (HMAC) and internal tokens; it just needs to be random and stable. `install.sh` generates it; the SearXNG container won't start without one.

Image versions are pinnable for reproducible installs: set `VALKEY_IMAGE`, `SEARXNG_IMAGE`, `CRAWL4AI_IMAGE` in `.env` (they default to `:latest`). Pinning at least `CRAWL4AI_IMAGE` is recommended in production.

Search quality is tuned in `searxng/settings.yml` (which engines are enabled, weights, categories) — restart the `searxng` service after editing.

## Notes / gotchas

- **SearXNG JSON API must be enabled** — `searxng/settings.yml` already lists `json` under `search.formats`. Without it the API returns `403`.
- **`SEARXNG_SECRET` is required** — the SearXNG container fails to start without it. The compose file errors out early if it's unset; `install.sh` generates it.
- **Limiter is disabled** (`limiter: false`) because the instance is only reachable inside the compose network. Enable and configure it if you ever expose port 8080 publicly.
- **Pin the Crawl4AI image** in production — set `CRAWL4AI_IMAGE=unclecode/crawl4ai:<version>` in `.env`; its API has changed between releases. If `web_extractor` ever returns empty markdown, check `http://localhost:11235/playground` to see the current `/md` request shape.
- **`shm_size: 1g`** on the `crawl4ai` service avoids Chromium crashes on large pages.

## Stopping

```bash
docker compose down            # keep the Valkey volume
docker compose down -v         # also remove cached data
```
