# Security Policy

## Supported Versions

Security fixes are provided for the latest tagged release and the `main` branch.

| Version | Supported |
|---|---|
| `main` | Yes |
| `1.x` | Yes |
| `< 1.0.0` | No |

## Reporting a Vulnerability

Do **not** open a public GitHub issue for security vulnerabilities.

Report vulnerabilities through [GitHub Security Advisories](https://github.com/datvietvac-techhub/mcp-web-tools/security/advisories/new). Include:

- affected version or commit SHA,
- deployment mode (`http` or `stdio` transport),
- relevant Docker Compose configuration with secrets redacted,
- steps to reproduce,
- observed impact,
- any known mitigation or workaround.

We will acknowledge valid reports as soon as possible, investigate privately, and publish a fix or advisory when appropriate.

## Deployment Notes

By default, only `web-mcp` is published to the host (MCP at `/mcp`, REST at `/api/v1/*`); SearXNG, Crawl4AI, and Valkey stay on the Docker network. If you expose the server outside a trusted local environment, set `API_TOKEN` for REST endpoints and/or put the service behind a VPN, firewall rule, or authenticated reverse proxy.

`web_extractor` performs lightweight URL validation before calling extract providers. Crawl4AI domain/link filters are useful for crawl behavior, but they are not treated as this project's SSRF protection boundary.

Do **not** commit `config/providers.yaml` — it may contain API keys. Prefer `${ENV_VAR}` references and keep `.env` out of version control. `config/providers.yaml.example` is safe to commit.

## Scope

In scope:

- vulnerabilities in the `web-mcp` server (MCP and REST exposers),
- unsafe request handling in `web_search` or `web_extractor`,
- secret leakage in install, compose, logging, or docs,
- container configuration issues that expose internal services unexpectedly.

Out of scope:

- vulnerabilities in upstream SearXNG, Crawl4AI, Valkey, Docker, or Python dependencies unless this repo's configuration makes them exploitable in a new way,
- denial-of-service against a publicly exposed SearXNG or Crawl4AI instance that was intentionally exposed outside the compose network,
- reports that require access to a user's private deployment without authorization.
