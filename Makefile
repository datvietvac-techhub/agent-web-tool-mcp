# mcp-web-tool — common operations.
#   make install   one-shot bootstrap on a fresh machine (calls ./install.sh)
#   make up/down/restart/ps/logs/build/pull/smoke/secret/clean
#
# `make install ARGS="--pull --no-smoke"` forwards flags to install.sh.

COMPOSE := docker compose
ARGS    ?=

.DEFAULT_GOAL := help

.PHONY: help install up down restart ps logs build pull smoke secret clean

help: ## Show this help
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) \
	  | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}'

install: ## Bootstrap the stack on this machine (prereqs, .env, secret, build, up, smoke)
	@./install.sh $(ARGS)

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

smoke: ## Hit all three HTTP endpoints to confirm they respond
	@set -e; \
	echo "SearXNG  :" ; curl -fsS -m 15 "http://localhost:8080/search?q=hello&format=json" >/dev/null && echo "  ok" ; \
	echo "Crawl4AI :" ; curl -fsS -m 30 -X POST "http://localhost:11235/md" -H 'Content-Type: application/json' -d '{"url":"https://example.com","f":"fit"}' >/dev/null && echo "  ok" ; \
	echo "MCP      :" ; printf "  HTTP %s (406/400/200 expected on bare GET)\n" "$$(curl -s -o /dev/null -w '%{http_code}' -m 10 http://localhost:8000/mcp)"

secret: ## Generate a SEARXNG_SECRET value and print it (does not write .env)
	@openssl rand -hex 32 2>/dev/null || python3 -c 'import secrets;print(secrets.token_hex(32))'

clean: ## Stop the stack AND remove the valkey cache volume
	$(COMPOSE) down -v
