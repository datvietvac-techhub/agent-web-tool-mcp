# mcp-web-tool — common operations.
#   make bootstrap  one-time setup on a fresh machine (prereqs, .env, secret)
#   make up         start the stack
#   make install    convenience one-shot: bootstrap + up + smoke
#
# `make bootstrap ARGS="--pull"` forwards flags to install.sh.

COMPOSE := docker compose
ARGS    ?=

.DEFAULT_GOAL := help

.PHONY: help bootstrap install up down restart ps logs build pull smoke secret clean config

help: ## Show this help
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) \
	  | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}'

bootstrap: ## Bootstrap only — prereqs, .env, secret (no compose up)
	@./install.sh $(ARGS)

install: ## One-shot: bootstrap + up + smoke (convenience wrapper)
	@./install.sh $(ARGS) && $(COMPOSE) up -d --build && $(MAKE) smoke

up: ## Start the stack in the background
	$(COMPOSE) up -d

down: ## Stop the stack (keeps the valkey cache volume)
	$(COMPOSE) down

restart: ## Restart the stack
	$(COMPOSE) down && $(COMPOSE) up -d

ps: ## Show container status
	$(COMPOSE) ps

logs: ## Tail logs from all services (Ctrl-C to stop)
	$(COMPOSE) logs -f --tail=100

build: ## (Re)build the web-mcp image
	$(COMPOSE) build

pull: ## Pull fresh upstream images (valkey, searxng, crawl4ai)
	$(COMPOSE) pull valkey searxng crawl4ai

smoke: ## Hit all endpoints to confirm they respond
	@set -a; [ -f .env ] && . ./.env; set +a; \
	MCP_PORT=$${MCP_PORT:-8000}; \
	set -e; \
	echo "SearXNG  :" ; $(COMPOSE) exec -T searxng wget -q -O /dev/null "http://localhost:8080/search?q=hello&format=json" ; echo "  ok" ; \
	echo "Crawl4AI :" ; $(COMPOSE) exec -T crawl4ai python -c "import urllib.request; req=urllib.request.Request('http://localhost:11235/md', data=b'{\"url\":\"https://example.com\",\"f\":\"fit\"}', headers={'Content-Type': 'application/json'}, method='POST'); urllib.request.urlopen(req, timeout=30).read()" >/dev/null ; echo "  ok" ; \
	echo "Health   :" ; curl -sf "http://localhost:$$MCP_PORT/healthz" >/dev/null ; echo "  ok" ; \
	echo "REST     :" ; \
	if [ -n "$${API_TOKEN:-}" ]; then \
	  curl -sfX POST "http://localhost:$$MCP_PORT/api/v1/search" \
	    -H 'content-type: application/json' \
	    -H "Authorization: Bearer $$API_TOKEN" \
	    -d '{"query":"hello","num_results":1}' >/dev/null ; \
	else \
	  curl -sfX POST "http://localhost:$$MCP_PORT/api/v1/search" \
	    -H 'content-type: application/json' \
	    -d '{"query":"hello","num_results":1}' >/dev/null ; \
	fi ; echo "  ok" ; \
	echo "MCP      :" ; code="$$(curl -sL -o /dev/null -w '%{http_code}' -m 10 http://localhost:$$MCP_PORT/mcp)" ; \
	case "$$code" in 200|400|406) printf "  HTTP %s (ok)\n" "$$code" ;; *) printf "  HTTP %s (expected 200/400/406)\n" "$$code" >&2; exit 1 ;; esac

secret: ## Generate a SEARXNG_SECRET value and print it (does not write .env)
	@openssl rand -hex 32 2>/dev/null || python3 -c 'import secrets;print(secrets.token_hex(32))'

config: ## Configure provider fallback (tavily → firecrawl → exa → local)
	@python3 scripts/config_provider.py

clean: ## Stop the stack AND remove the valkey cache volume
	$(COMPOSE) down -v
