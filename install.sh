#!/usr/bin/env bash
# install.sh — bootstrap the mcp-web-tool stack.
#
# Two ways to run:
#
#   1) One-liner (clones the repo, then bootstraps):
#        curl -fsSL https://github.com/datvietvac-techhub/mcp-web-tools/releases/latest/download/install.sh | bash
#        curl -fsSL https://github.com/datvietvac-techhub/mcp-web-tools/releases/latest/download/install.sh | bash -s -- --dir /opt/mcp-web-tool --pull
#
#   2) From an existing checkout:
#        git clone https://github.com/datvietvac-techhub/mcp-web-tools.git && cd mcp-web-tools
#        ./install.sh
#
# Bootstrap only — does NOT start containers. After this runs, use:
#   make up        # start the stack
#   make smoke     # verify endpoints
#   make install   # one-shot: bootstrap + up + smoke
#
# Idempotent: safe to re-run. It will
#   1. (curl-pipe mode only) clone or update the repo, then re-exec from it
#   2. check prerequisites (docker, docker compose v2, daemon reachable, free ports)
#   3. create .env from .env.example if missing
#   4. generate SEARXNG_SECRET if it's empty
#   5. optionally pull upstream images (--pull)
#
# Flags:
#   --dir <path>   target dir for the curl-pipe clone (default: ~/.local/share/mcp-web-tool)
#   --pull         `docker compose pull` upstream images now
#   --skip-checks  skip the prerequisite checks (ports etc.)
#   -h, --help     show this help

set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/datvietvac-techhub/mcp-web-tools.git}"
REPO_BRANCH="${REPO_BRANCH:-main}"

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

print_help() {
  cat <<EOF
install.sh — bootstrap the mcp-web-tool stack.

Usage:
  # one-liner (clones the repo, then bootstraps):
  curl -fsSL ${REPO_URL%.git}/releases/latest/download/install.sh | bash
  curl -fsSL ${REPO_URL%.git}/releases/latest/download/install.sh | bash -s -- --dir /opt/mcp-web-tool --pull

  # from an existing checkout:
  ./install.sh [--pull] [--skip-checks]

Flags:
  --dir <path>   target dir for the curl-pipe clone (default: ~/.local/share/mcp-web-tool)
  --pull         \`docker compose pull\` upstream images after bootstrap
  --skip-checks  skip the prerequisite checks (ports etc.)
  -h, --help     show this help
EOF
}

# ── 0. detect curl-pipe mode and self-clone if needed ─────────────────────────
# When run via `curl ... | bash`, BASH_SOURCE[0] is empty or points outside the
# repo, so docker-compose.yml won't be next to it. In that case we git-clone
# the repo and re-exec install.sh from the checkout so the rest of the script
# runs exactly as it would after a manual `git clone && ./install.sh`.
SCRIPT_PATH="${BASH_SOURCE[0]:-}"
if [ -n "$SCRIPT_PATH" ] && [ -f "$SCRIPT_PATH" ]; then
  SCRIPT_DIR="$(cd -- "$(dirname -- "$SCRIPT_PATH")" >/dev/null 2>&1 && pwd)"
else
  SCRIPT_DIR=""
fi

if [ -z "$SCRIPT_DIR" ] || [ ! -f "$SCRIPT_DIR/docker-compose.yml" ]; then
  CLONE_DIR=""
  PASS_ARGS=()
  while [ $# -gt 0 ]; do
    case "$1" in
      --dir)     [ $# -ge 2 ] || die "--dir requires a path"; CLONE_DIR="$2"; shift 2 ;;
      --dir=*)   CLONE_DIR="${1#--dir=}"; shift ;;
      -h|--help) print_help; exit 0 ;;
      *)         PASS_ARGS+=("$1"); shift ;;
    esac
  done

  if [ -z "$CLONE_DIR" ]; then
    if [ -n "${HOME:-}" ]; then
      CLONE_DIR="$HOME/.local/share/mcp-web-tool"
    else
      CLONE_DIR="$PWD/mcp-web-tool"
    fi
  fi

  command -v git >/dev/null 2>&1 || die "git not found — install git first, then re-run."

  step "Fetching mcp-web-tool"
  if [ -d "$CLONE_DIR/.git" ]; then
    info "repo present at $CLONE_DIR — updating to origin/$REPO_BRANCH"
    git -C "$CLONE_DIR" fetch --depth 1 origin "$REPO_BRANCH"
    git -C "$CLONE_DIR" reset --hard "origin/$REPO_BRANCH"
  else
    mkdir -p "$(dirname -- "$CLONE_DIR")"
    info "cloning $REPO_URL → $CLONE_DIR"
    git clone --depth 1 --branch "$REPO_BRANCH" "$REPO_URL" "$CLONE_DIR"
  fi
  ok "repo ready at $CLONE_DIR"

  exec bash "$CLONE_DIR/install.sh" ${PASS_ARGS[@]+"${PASS_ARGS[@]}"}
fi

cd "$SCRIPT_DIR"

# ── args ──────────────────────────────────────────────────────────────────────
DO_PULL=0 DO_CHECKS=1
for arg in "$@"; do
  case "$arg" in
    --pull)        DO_PULL=1 ;;
    --skip-checks) DO_CHECKS=0 ;;
    --dir|--dir=*) ;;  # only meaningful in curl-pipe mode; ignore when in-repo
    -h|--help)     print_help; exit 0 ;;
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

if [ "$DO_CHECKS" -eq 1 ]; then
  port_busy() {
    # returns 0 if something is listening on $1
    if command -v ss >/dev/null 2>&1;       then ss -ltn "( sport = :$1 )" 2>/dev/null | grep -q ":$1 "
    elif command -v lsof >/dev/null 2>&1;   then lsof -iTCP:"$1" -sTCP:LISTEN >/dev/null 2>&1
    else return 1; fi
  }
  for p in 8000; do
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

# ── 2b. providers.yaml ────────────────────────────────────────────────────────
step "Configuring provider fallback chains"
if [ ! -f config/providers.yaml ]; then
  mkdir -p config
  python3 scripts/config_provider.py --yes
  ok "created config/providers.yaml (local-only; run make config to add API keys)"
else
  info "config/providers.yaml already exists — leaving it as is"
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

# ── 4. optional image pull ────────────────────────────────────────────────────
if [ "$DO_PULL" -eq 1 ]; then
  step "Pulling upstream images"
  compose pull valkey searxng crawl4ai
fi

# ── done ──────────────────────────────────────────────────────────────────────
mcp_port="$(grep -E '^MCP_PORT=' .env | cut -d= -f2- || echo 8000)"
printf '\n%s\n' "${BOLD}${GRN}✔ bootstrap complete${RST}"
cat <<EOF

  ${BOLD}Repo${RST}
    $SCRIPT_DIR

  ${BOLD}Next${RST}
    cd "$SCRIPT_DIR"
    make up           # start the stack
    make smoke        # verify endpoints

  ${BOLD}Endpoints (once up)${RST}
    SearXNG    internal: http://searxng:8080
    Crawl4AI   internal: http://crawl4ai:11235
    MCP        http://localhost:${mcp_port:-8000}/mcp
    REST API   http://localhost:${mcp_port:-8000}/api/v1/search
    OpenAPI    http://localhost:${mcp_port:-8000}/docs

EOF
exit 0
