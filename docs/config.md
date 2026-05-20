---
title: Configuration — MCP Web Tools
description: Full configuration reference for MCP Web Tools — every .env variable, complete parameter tables for the web_search and web_extractor tools, and the HTTP REST API.
---

# Configuration

Configuration is split between `.env` (service URLs, timeouts, secrets) and [`config/providers.yaml`](https://github.com/datvietvac-techhub/mcp-web-tools/blob/main/config/providers.yaml.example) (search/extract fallback chains).

## Provider fallback (`config/providers.yaml`)

Ordered lists define which backend runs first. **First entry = primary**, **last = final fallback**. The runner tries each provider top-to-bottom and stops on the first successful response. Reordering the YAML changes priority.

```bash
make config   # write providers.yaml; prompts for Brave and Tavily keys (Enter to skip)
```

Order is **fixed**: tavily → firecrawl → exa → local (`searxng` / `crawl4ai`). You only choose whether to supply API keys for the SaaS providers.

| chain key | providers (v1) |
|---|---|
| `web_search` | `tavily`, `firecrawl`, `exa`, `searxng` (local) |
| `web_extract` | `tavily`, `firecrawl`, `exa`, `crawl4ai` (local) |

Example:

```yaml
web_search:
  - provider: tavily
    credential: "${TAVILY_API_KEY}"
  - provider: firecrawl
    credential: "${FIRECRAWL_API_KEY}"
  - provider: exa
    credential: "${EXA_API_KEY}"
  - provider: searxng

web_extract:
  - provider: tavily
    credential: "${TAVILY_API_KEY}"
  - provider: firecrawl
    credential: "${FIRECRAWL_API_KEY}"
  - provider: exa
    credential: "${EXA_API_KEY}"
  - provider: crawl4ai
```

| field | notes |
|---|---|
| `provider` | `tavily`, `firecrawl`, `exa`, `searxng`, or `crawl4ai` |
| `credential` | API key literal or `${ENV_VAR}` expanded at load time. Optional for local providers. |

**Fallback rules:** only **hard failures** advance the chain (HTTP 4xx/5xx, timeout, transport error). Empty results, validation errors, and per-URL extract errors do **not** trigger fallback. SaaS providers without a credential are skipped. `bm25` / `llm` extract modes skip SaaS providers and use `crawl4ai` when it is in the chain.

| var | default | purpose |
|---|---|---|
| `PROVIDERS_CONFIG` | `config/providers.yaml` | path to the YAML file (`/app/config/providers.yaml` in Docker) |
| `FALLBACK_VERBOSE` | `false` | include `fallback_attempts` in tool responses when `true` |

`config/providers.yaml` is gitignored — commit only [`config/providers.yaml.example`](https://github.com/datvietvac-techhub/mcp-web-tools/blob/main/config/providers.yaml.example).

## Environment variables

| var | default | purpose |
|---|---|---|
| `SEARXNG_SECRET` | _(required)_ | HMAC signing key for SearXNG — **not** an API key |
| `CRAWL4AI_API_TOKEN` | _(empty)_ | optional bearer token if Crawl4AI is locked down |
| `API_TOKEN` | _(empty)_ | optional bearer token for REST API (`/api/v1/*`) |
| `MCP_TRANSPORT` | `http` | `http` (streamable-http) or `stdio` (subprocess) |
| `MCP_PORT` | `8000` | host port for MCP + REST API (also used for `make smoke`) |
| `MCP_CACHE_TTL` | `300` | `web_search` cache TTL in seconds (`0` disables) |
| `EXTRACT_CACHE_TTL` | `1800` | `web_extractor` cache TTL in seconds (`0` disables) |
| `REQUEST_TIMEOUT` | `30` | outbound search request timeout (s) |
| `EXTRACT_TIMEOUT` | `60` | outbound extract request timeout (s) |
| `MAX_CONCURRENCY` | `5` | parallel extract requests per `web_extractor` call (Crawl4AI) |
| `FALLBACK_VERBOSE` | `false` | include `fallback_attempts` in search/extract responses |
| `TAVILY_API_KEY` | _(empty)_ | optional; referenced from YAML via `${TAVILY_API_KEY}` |
| `FIRECRAWL_API_KEY` | _(empty)_ | optional; referenced from YAML via `${FIRECRAWL_API_KEY}` |
| `EXA_API_KEY` | _(empty)_ | optional; referenced from YAML via `${EXA_API_KEY}` |
| `VALKEY_IMAGE` | `valkey/valkey:8-alpine` | pin Valkey image |
| `SEARXNG_IMAGE` | `searxng/searxng:latest` | pin SearXNG image |
| `CRAWL4AI_IMAGE` | `unclecode/crawl4ai:latest` | pin Crawl4AI image (recommended for prod) |

After changing `MCP_PORT`, run `make restart` (not just `up`) so the new host-port mapping takes effect.

`SEARXNG_SECRET` is **not** an API key — nothing sends it. SearXNG uses it server-side to sign image-proxy URLs (HMAC) and internal tokens; it just needs to be random and stable. `install.sh` generates it; the SearXNG container won't start without one.

Search quality is tuned in [`searxng/settings.yml`](https://github.com/datvietvac-techhub/mcp-web-tools/blob/main/searxng/settings.yml) (engines enabled, weights, categories) — restart the `searxng` service after editing.

## Tool implementations

Core logic lives in [`mcp/tools.py`](https://github.com/datvietvac-techhub/mcp-web-tools/blob/main/mcp/tools.py) with provider adapters under [`mcp/providers/`](https://github.com/datvietvac-techhub/mcp-web-tools/blob/main/mcp/providers/). MCP (`server.py`) and HTTP (`api.py`) are thin exposers that delegate to the same functions.

### `web_search`

Runs the `web_search` chain from `config/providers.yaml` and returns ranked, de-duplicated results. Cached in-process for `MCP_CACHE_TTL` seconds. Successful responses include `"provider"` (which backend answered). On total chain failure the dict includes an `"error"` key and `"results": []`.

| param | type | default | notes |
|---|---|---|---|
| `query` | string | required | search query |
| `num_results` | int | `10` | clamped to `1..50` |
| `categories` | string | `"general"` | SearXNG category: `general`, `news`, `science`, `it`, `images`, … |
| `language` | string | `"auto"` | `"en"`, `"vi"`, …; `"auto"` lets SearXNG decide |
| `time_range` | string \| null | `null` | `"day"`, `"week"`, `"month"`, `"year"` |
| `provider` | string \| null | `null` | force one backend: `tavily`, `firecrawl`, `exa`, `searxng` (no fallback) |

Returns:

```json
{
  "query": "...",
  "results": [
    { "title": "...", "url": "https://...", "snippet": "...", "engine": "...", "score": 1.0 }
  ],
  "answers": [],
  "suggestions": ["..."],
  "number_of_results": 12345
}
```

Results are de-duplicated by normalized URL and truncated to `num_results`.

### `web_extractor`

Runs the `web_extract` chain from `config/providers.yaml`. Crawl4AI fetches in parallel up to `MAX_CONCURRENCY`; Tavily and Exa extract in batch; Firecrawl scrapes per URL. Max 20 URLs per call. Cached for `EXTRACT_CACHE_TTL` seconds per URL. Successful batch responses include `"provider"`.

| param | type | default | notes |
|---|---|---|---|
| `urls` | string \| list[string] | required | one URL or a list — max **20** per call |
| `mode` | string | `"fit"` | `fit` (pruned main content), `raw` (full page), `bm25` / `llm` (relevance-filtered — requires `query`) |
| `query` | string \| null | `null` | focus query for `bm25` / `llm` mode |
| `bypass_cache` | bool | `false` | skip the local cache and ask Crawl4AI to re-fetch |
| `provider` | string \| null | `null` | force one backend: `tavily`, `firecrawl`, `exa`, `crawl4ai` (no fallback) |

Returns:

```json
{
  "results": [
    {
      "url": "https://...",
      "status": "ok",
      "markdown": "# Heading\n...",
      "word_count": 1234,
      "error": "..."
    }
  ]
}
```

Order matches the input URL list. Per-URL failures surface as `{"status": "error", "error": "...", "markdown": ""}` without aborting the whole call. URLs must use `http` or `https`; `bm25` and `llm` mode return a per-URL error when `query` is missing.

The URL policy currently performs lightweight validation only. Crawl4AI's domain/link filters are useful for crawl behavior, but they are not treated as this project's SSRF protection boundary. If you expose the server beyond a trusted local network, put it behind access control and add any deployment-specific URL restrictions in `mcp/url_policy.py`.

## HTTP API

REST endpoints run on the same port as MCP (`${MCP_PORT}`). OpenAPI is auto-generated at `/docs` and `/redoc`.

| method | path | body | description |
|---|---|---|---|
| GET | `/healthz` | — | liveness probe → `{"ok": true}` |
| POST | `/api/v1/search` | `SearchReq` | same params/response as `web_search` |
| POST | `/api/v1/extract` | `ExtractReq` | same params/response as `web_extractor` |

When `API_TOKEN` is set, `/api/v1/*` requires `Authorization: Bearer <token>`. `/healthz` and `/docs` stay unauthenticated.

Tool-level failures return HTTP `200` with an `"error"` field in the JSON body (same as MCP). Auth failures return `401`; validation errors return `422`.

```bash
curl -sX POST http://localhost:8000/api/v1/search \
  -H 'content-type: application/json' \
  -H "Authorization: Bearer $API_TOKEN" \
  -d '{"query":"hello","num_results":3}'
```
