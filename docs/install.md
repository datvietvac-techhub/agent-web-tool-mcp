---
title: Install — MCP Web Tools
description: How to install and run the MCP Web Tools server — one-liner installer, manual clone, Make targets, smoke tests, and how to connect Claude Code or any MCP client.
---

# Install

Three install paths are supported, in order of convenience: the one-liner curl installer, a manual clone + `./install.sh`, and a fully manual `docker compose` setup. All three end with a running 4-service stack whose MCP endpoint is reachable at `http://localhost:8000/mcp`.

## Requirements

- Docker Engine + `docker compose` v2 plugin.
- `git` (used by the curl-pipe installer to clone the repo).
- Free host port: `8000` (MCP). SearXNG and Crawl4AI are internal Docker services by default.

If `docker` needs `sudo` on your host, prefix commands with `sudo` or add yourself to the `docker` group:

```bash
sudo usermod -aG docker "$USER" && newgrp docker
```

## One-liner install (recommended)

```bash
curl -fsSL https://github.com/datvietvac-techhub/mcp-web-tools/releases/latest/download/install.sh | bash
```

The script clones the repo to `~/.local/share/mcp-web-tool` (override with `--dir <path>`), runs prerequisite checks, creates `.env` from `.env.example`, and generates a random `SEARXNG_SECRET`. It does **not** start containers — that's `make up`. Idempotent and safe to re-run.

Forward flags after `--`:

```bash
curl -fsSL https://github.com/datvietvac-techhub/mcp-web-tools/releases/latest/download/install.sh \
  | bash -s -- --dir /opt/mcp-web-tool --pull
```

Pin to a specific release by swapping `latest` for a tag (e.g. `v1.0.0`):

```bash
curl -fsSL https://github.com/datvietvac-techhub/mcp-web-tools/releases/download/v1.0.0/install.sh | bash
```

### Installer flags

| flag | purpose |
|---|---|
| `--dir <path>` | target dir for the clone (default `~/.local/share/mcp-web-tool`) |
| `--pull` | `docker compose pull` upstream images right after bootstrap |
| `--skip-checks` | skip port / daemon prerequisite checks |
| `-h, --help` | show help |

## Manual clone install

```bash
git clone https://github.com/datvietvac-techhub/mcp-web-tools.git
cd mcp-web-tools
./install.sh        # bootstrap only — prereqs, .env, SEARXNG_SECRET
make up             # start the stack
make smoke          # verify endpoints
```

`make install` is the all-in-one equivalent: bootstrap + `compose up -d --build` + smoke. First `make up` pulls the Crawl4AI image (~GB, includes Chromium) — budget a couple of minutes.

## Fully manual (no install script)

```bash
cp .env.example .env
echo "SEARXNG_SECRET=$(openssl rand -hex 32)" >> .env
docker compose up -d --build
docker compose ps        # wait until searxng + crawl4ai are "healthy"
```

## Day-to-day Make targets

```
make bootstrap   # ./install.sh only (prereqs, .env, secret) — no compose up
make install     # one-shot: bootstrap + up + smoke (forward flags with ARGS="--pull")
make up          # start              make down     # stop (keeps cache volume)
make restart     # restart            make ps       # status
make logs        # tail logs          make smoke    # re-run endpoint smoke tests
make build       # rebuild web-mcp    make pull     # refresh upstream images
make secret      # print a fresh SEARXNG_SECRET value
make clean       # stop + remove the valkey cache volume
```

## Smoke tests

```bash
# SearXNG, Crawl4AI, REST API, and MCP
make smoke

# REST API OpenAPI UI
open http://localhost:${MCP_PORT:-8000}/docs

# MCP server: inspect tools
npx @modelcontextprotocol/inspector
# then connect to http://localhost:${MCP_PORT:-8000}/mcp
```

## Connect an agent

The MCP server listens on `http://<host>:${MCP_PORT}/mcp` (Streamable HTTP). `MCP_PORT` defaults to `8000`.

SearXNG and Crawl4AI are not published to the host by default. For debugging, run commands inside the compose network, for example `docker compose exec searxng wget -q -O - "http://localhost:8080/search?q=test&format=json"`.

### Claude Code

```bash
claude mcp add --transport http web-tool http://localhost:8000/mcp
```

### Any MCP client (Cursor, Hermes, etc.)

```json
{
  "mcpServers": {
    "web-tool": { "transport": "http", "url": "http://localhost:8000/mcp" }
  }
}
```

### stdio transport (single local client, subprocess)

Set `MCP_TRANSPORT=stdio` in `.env`, restart the stack, and point the client at:

```
python mcp/server.py
```

or `docker compose run --rm web-mcp python server.py`.

## Stopping

```bash
docker compose down            # keep the Valkey cache volume
docker compose down -v         # also remove cached data
make clean                     # equivalent to `down -v`
```
