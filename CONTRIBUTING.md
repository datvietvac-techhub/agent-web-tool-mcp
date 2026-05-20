# Contributing to MCP Web Tools

Thanks for considering a contribution. Bug reports, feature requests, and PRs are welcome.

For the project overview and architecture, see [README.md](README.md) and the [docs site](https://datvietvac-techhub.github.io/mcp-web-tools/).

## Project layout

```
.
├── docker-compose.yml      # 4-service stack
├── install.sh              # bootstrap (curl-pipe + in-repo modes)
├── Makefile                # make up/down/logs/smoke/...
├── .env.example            # all tunables, copied to .env by install.sh
├── mcp/                    # the only service we build
│   ├── Dockerfile
│   ├── server.py           # MCP exposer (FastMCP tool registration)
│   ├── api.py              # HTTP exposer (REST routes)
│   ├── tools.py            # web_search_impl + web_extractor_impl (core)
│   ├── url_policy.py       # URL validation boundary for extraction
│   └── requirements.txt
├── searxng/
│   └── settings.yml        # engines, categories, formats, limiter
└── docs/                   # MkDocs source for https://datvietvac-techhub.github.io/mcp-web-tools/
```

## Local dev loop

```bash
git clone https://github.com/datvietvac-techhub/mcp-web-tools.git
cd mcp-web-tools
./install.sh                         # one-time bootstrap
make up                              # start the stack
curl http://localhost:8000/docs      # OpenAPI UI for REST endpoints

# after editing mcp/*.py:
make build && make restart           # rebuild the web-mcp image and restart
make logs                            # tail all services
python -m compileall mcp
pytest
```

Unit tests in `tests/test_tools.py` target the core layer directly. `tests/test_api.py` covers the HTTP exposer.

## Coding conventions

- **Python**: target the version pinned in [`mcp/Dockerfile`](mcp/Dockerfile). Keep tool impls (`mcp/tools.py`) free of MCP- or FastAPI-specific imports so `server.py` and `api.py` can share them.
- **Tool contracts are stable** — return shapes for `web_search` / `web_extractor` are part of the public surface; bump [`docs/config.md`](docs/config.md) when you change them.
- **Failures are values, not exceptions** — both tools return a dict with an `error` field on failure (and `results: []` / `status: "error"` per URL). Don't raise from tool entrypoints.
- **Caching keys** must include every input that affects the response (query, categories, language, time_range, mode, query for bm25/llm, etc.).
- **URL policy** starts in `mcp/url_policy.py`. Keep the default extractor zero-config unless a future hardening change explicitly introduces optional allow/deny controls.
- **Shell scripts** are bash-only, `set -euo pipefail`, and must stay idempotent. Test both in-repo and curl-pipe paths when touching `install.sh`.
- **Compose**: don't add new host-port bindings without an env-var default and a note in `.env.example` + the config table at [`docs/config.md`](docs/config.md).

## Submitting changes

1. Fork and create a feature branch off `main`.
2. Run `python -m compileall mcp`, `pytest`, and `make build && make restart && make smoke` before pushing — all endpoints must return `ok` / `2xx`.
3. If your change touches a tool's request/response shape, update [`docs/config.md`](docs/config.md) and any clients you know of.
4. Open a PR with:
   - what changed and why (one paragraph is fine),
   - `make smoke` output, or a manual `curl` against the relevant endpoint,
   - any new env vars added to `.env.example`,
   - a `CHANGELOG.md` entry under `## [Unreleased]` (Keep a Changelog format).
5. Avoid drive-by reformatting; keep diffs focused.

## Reporting issues

When filing a bug, include:

- output of `docker compose ps` and `docker compose version`,
- relevant logs: `make logs` (or `docker compose logs <service>`),
- `.env` with `SEARXNG_SECRET` and `CRAWL4AI_API_TOKEN` redacted,
- exact tool call (params) and the response you got.

Use the [bug report issue template](https://github.com/datvietvac-techhub/mcp-web-tools/issues/new?template=bug_report.yml) for a pre-filled checklist.

## Code of Conduct

Participation in this project is governed by the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md).

## Security

Do **not** open public issues for security vulnerabilities. See [SECURITY.md](SECURITY.md) for the reporting process.
