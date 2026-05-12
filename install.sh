#!/usr/bin/env bash
# install.sh — bootstrap the mcp-web-tool stack on a fresh machine.
#
#   git clone <repo> && cd mcp-web-tool && ./install.sh
#
# Idempotent: safe to re-run. It will
#   1. check prerequisites (docker, docker compose v2, daemon reachable, free ports)
#   2. create .env from .env.example if missing
#   3. generate SEARXNG_SECRET if it's empty
#   4. build + start the stack (docker compose up -d --build)
#   5. wait for searxng + crawl4ai to report healthy
#   6. run smoke tests against all three HTTP endpoints
#
# Flags:
#   --no-build     don't pass --build to `docker compose up` (use existing image)
#   --pull         `docker compose pull` before starting (refresh upstream images)
#   --no-smoke     skip the post-start smoke tests
#   --skip-checks  skip the prerequisite checks (ports etc.)
#   -h, --help     show this help

set -euo pipefail

# ── locate repo root (this script's directory) ────────────────────────────────
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
cd "$SCRIPT_DIR"

# ── pretty output ─────────────────────────────────────────────────────────────
if [ -t 1 ]; then
  BOLD=$'\033[1m'; DIM=$'\033[2m'; RED=$'\033[31m'; GRN=$'\033[32m'; YLW=$'\033[33m'; CYN=$'\033[36m'; RST=$'\033[0m'
else
  BOLD=; DIM=; RED=; GRN=; YLW=; CYN=; RST=
fi
info()  { printf '%s\n' "${DIM}  $*${RST}"; }
step()  { printf '\n%s\n' "${BOLD}${CYN}▸ $*${RST}"; }
ok()    { printf '%s\n' "${GRN}  ✓ $*${RST}"; }
warn()  { printf '%s\n' "${YLW}  ⚠ $*${RST}"; }
die()   { printf '%s\n' "${RED}  ✗ $*${RST}" >&2; exit 1; }

# ── args ──────────────────────────────────────────────────────────────────────
DO_BUILD=1 DO_PULL=0 DO_SMOKE=1 DO_CHECKS=1
for arg in "$@"; do
  case "$arg" in
    --no-build)    DO_BUILD=0 ;;
    --pull)        DO_PULL=1 ;;
    --no-smoke)    DO_SMOKE=0 ;;
    --skip-checks) DO_CHECKS=0 ;;
    -h|--help)
      # print the leading comment block (skip the shebang, stop at first code line)
      awk 'NR==1{next} /^#/{sub(/^# ?/,""); print; next} {exit}' "$0"
      exit 0 ;;
    *) die "unknown flag: $arg (try --help)" ;;
  esac
done

# ── compose wrapper (v2 plugin only) ──────────────────────────────────────────
export COMPOSE_BAKE=false   # silence the "configured to build using Bake" notice
compose() { docker compose "$@"; }

# ── 1. prerequisites ──────────────────────────────────────────────────────────
step "Checking prerequisites"

command -v docker >/dev/null 2>&1 || die "docker not found. Install Docker Engine: https://docs.docker.com/engine/install/"
ok "docker: $(docker --version | sed 's/^Docker version //')"

if ! docker compose version >/dev/null 2>&1; then
  die "'docker compose' (v2 plugin) not found. Install the Compose plugin: https://docs.docker.com/compose/install/"
fi
ok "compose: $(docker compose version --short 2>/dev/null || docker compose version | head -1)"

docker_err="$(docker info 2>&1 1>/dev/null || true)"
if ! docker info >/dev/null 2>&1; then
  case "$docker_err" in
    *[Pp]ermission\ denied*)
      die "Cannot talk to the Docker daemon (permission denied).
       Either re-run as root:               sudo ./install.sh
       or add yourself to the docker group: sudo usermod -aG docker \"\$USER\" && newgrp docker" ;;
    *)
      die "Cannot talk to the Docker daemon — is it running?  (try: sudo systemctl start docker)" ;;
  esac
fi
ok "docker daemon reachable"

command -v openssl >/dev/null 2>&1 || warn "openssl not found — will fall back to python3/urandom for secret generation"
command -v curl    >/dev/null 2>&1 || warn "curl not found — post-start smoke tests will be skipped"

if [ "$DO_CHECKS" -eq 1 ]; then
  port_busy() {
    # returns 0 if something is listening on $1
    if command -v ss >/dev/null 2>&1;       then ss -ltn "( sport = :$1 )" 2>/dev/null | grep -q ":$1 "
    elif command -v lsof >/dev/null 2>&1;   then lsof -iTCP:"$1" -sTCP:LISTEN >/dev/null 2>&1
    else return 1; fi
  }
  for p in 8080 11235 8000; do
    if port_busy "$p"; then
      # ours is fine — only complain about foreign listeners
      if docker ps --format '{{.Ports}}' 2>/dev/null | grep -q ":$p->"; then
        info "port $p in use by this stack already (ok)"
      else
        warn "port $p is already in use by another process — the stack may fail to bind it"
      fi
    fi
  done
fi

# ── 2. .env ───────────────────────────────────────────────────────────────────
step "Configuring .env"
if [ ! -f .env ]; then
  cp .env.example .env
  ok "created .env from .env.example"
else
  info ".env already exists — leaving it as is"
fi

# ── 3. SEARXNG_SECRET ─────────────────────────────────────────────────────────
gen_secret() {
  if command -v openssl >/dev/null 2>&1; then openssl rand -hex 32
  elif command -v python3 >/dev/null 2>&1; then python3 -c 'import secrets;print(secrets.token_hex(32))'
  else head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n'; fi
}
current_secret="$(grep -E '^SEARXNG_SECRET=' .env | head -1 | cut -d= -f2- || true)"
if [ -z "$current_secret" ]; then
  secret="$(gen_secret)"
  # portable in-place edit
  tmp="$(mktemp)"; awk -v s="$secret" '/^SEARXNG_SECRET=/{print "SEARXNG_SECRET=" s; next} {print}' .env > "$tmp" && mv "$tmp" .env
  grep -qE '^SEARXNG_SECRET=' .env || printf 'SEARXNG_SECRET=%s\n' "$secret" >> .env
  ok "generated SEARXNG_SECRET (32 random bytes, hex)"
else
  ok "SEARXNG_SECRET already set"
fi

# ── 4. build + up ─────────────────────────────────────────────────────────────
if [ "$DO_PULL" -eq 1 ]; then
  step "Pulling upstream images"
  compose pull valkey searxng crawl4ai
fi

step "Starting the stack"
if [ "$DO_BUILD" -eq 1 ]; then
  compose up -d --build
else
  compose up -d
fi
ok "containers started"

# ── 5. wait for health ────────────────────────────────────────────────────────
step "Waiting for services to become healthy"
wait_healthy() {
  local cname="$1" label="$2" timeout="${3:-180}" waited=0 status
  while :; do
    status="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$cname" 2>/dev/null || echo missing)"
    case "$status" in
      healthy|running) ok "$label: $status"; return 0 ;;
      missing)         die "$label: container '$cname' not found" ;;
      *)
        if [ "$waited" -ge "$timeout" ]; then
          warn "$label: still '$status' after ${timeout}s — check 'docker compose logs $cname'"
          return 1
        fi
        printf '\r%s' "${DIM}  $label: $status  (${waited}s/${timeout}s)…${RST}"
        sleep 3; waited=$((waited + 3)) ;;
    esac
  done
}
rc=0
wait_healthy web-tool-searxng  "searxng"  180 || rc=1
wait_healthy web-tool-crawl4ai "crawl4ai" 240 || rc=1   # first run pulls Chromium image
wait_healthy web-tool-mcp      "web-mcp"  60  || rc=1
printf '\n'

# ── 6. smoke tests ────────────────────────────────────────────────────────────
if [ "$DO_SMOKE" -eq 1 ] && command -v curl >/dev/null 2>&1; then
  step "Smoke tests"
  if curl -fsS -m 15 "http://localhost:8080/search?q=hello&format=json" >/dev/null 2>&1; then
    ok "SearXNG JSON API responds (http://localhost:8080)"
  else
    warn "SearXNG JSON API not responding yet — retry: curl 'http://localhost:8080/search?q=hello&format=json'"
    rc=1
  fi
  if curl -fsS -m 30 -X POST "http://localhost:11235/md" -H 'Content-Type: application/json' -d '{"url":"https://example.com","f":"fit"}' >/dev/null 2>&1; then
    ok "Crawl4AI /md responds (http://localhost:11235)"
  else
    warn "Crawl4AI /md not responding yet — it can take a minute on first start"
    rc=1
  fi
  code="$(curl -s -o /dev/null -w '%{http_code}' -m 10 "http://localhost:8000/mcp" || echo 000)"
  if [ "$code" = "406" ] || [ "$code" = "400" ] || [ "$code" = "200" ]; then
    ok "MCP endpoint up (http://localhost:8000/mcp — HTTP $code on bare GET is expected)"
  else
    warn "MCP endpoint returned HTTP $code — check 'docker compose logs web-mcp'"
    rc=1
  fi
fi

# ── done ──────────────────────────────────────────────────────────────────────
transport="$(grep -E '^MCP_TRANSPORT=' .env | cut -d= -f2- || echo http)"
printf '\n'
if [ "$rc" -eq 0 ]; then
  printf '%s\n' "${BOLD}${GRN}✔ mcp-web-tool is up.${RST}"
else
  printf '%s\n' "${BOLD}${YLW}△ mcp-web-tool started, but some checks didn't pass — see warnings above.${RST}"
fi
cat <<EOF

  ${BOLD}Endpoints${RST}
    SearXNG    http://localhost:8080
    Crawl4AI   http://localhost:11235   (playground: /playground)
    MCP        http://localhost:8000/mcp   (transport: ${transport})

  ${BOLD}Connect an agent${RST}
    Claude Code:   claude mcp add --transport http web-tool http://localhost:8000/mcp
    Hermes:        hermes mcp add web-tool --url http://localhost:8000/mcp

  ${BOLD}Manage${RST}
    make ps        # status            make logs      # tail logs
    make down      # stop              make restart   # restart
    make clean     # stop + wipe cache volume

EOF
exit "$rc"
