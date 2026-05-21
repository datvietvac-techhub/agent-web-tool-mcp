#!/usr/bin/env bash
# update.sh — upgrade an existing mcp-web-tool install.
#
# Two ways to run:
#
#   1) One-liner (clones or updates the repo, then upgrades the stack):
#        curl -fsSL https://github.com/datvietvac-techhub/mcp-web-tools/releases/latest/download/update.sh | bash
#        curl -fsSL https://github.com/datvietvac-techhub/mcp-web-tools/releases/latest/download/update.sh | bash -s -- --dir /opt/mcp-web-tool
#
#   2) From an existing checkout:
#        cd ~/.local/share/mcp-web-tool && ./update.sh
#
# Runs: make update (sync git, bootstrap, pull images, rebuild web-mcp, smoke).
# See docs/install.md#upgrading for details.
#
# Flags:
#   --dir <path>   target dir for the curl-pipe clone (default: ~/.local/share/mcp-web-tool)
#   -h, --help     show this help

set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/datvietvac-techhub/mcp-web-tools.git}"
REPO_BRANCH="${REPO_BRANCH:-main}"

print_help() {
  cat <<EOF
update.sh — upgrade an existing mcp-web-tool install.

Usage:
  # one-liner (clones or updates the repo, then upgrades the stack):
  curl -fsSL ${REPO_URL%.git}/releases/latest/download/update.sh | bash
  curl -fsSL ${REPO_URL%.git}/releases/latest/download/update.sh | bash -s -- --dir /opt/mcp-web-tool

  # from an existing checkout:
  ./update.sh

Runs \`make update\` in the install directory (sync git, bootstrap, pull images,
rebuild web-mcp, restart, smoke). See docs/install.md#upgrading.

Flags:
  --dir <path>   target dir for the curl-pipe clone (default: ~/.local/share/mcp-web-tool)
  -h, --help     show this help
EOF
}

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
      --dir)     [ $# -ge 2 ] || { echo "error: --dir requires a path" >&2; exit 1; }; CLONE_DIR="$2"; shift 2 ;;
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

  command -v git >/dev/null 2>&1 || { echo "error: git not found" >&2; exit 1; }

  if [ -d "$CLONE_DIR/.git" ]; then
    git -C "$CLONE_DIR" fetch --depth 1 origin "$REPO_BRANCH"
    git -C "$CLONE_DIR" reset --hard "origin/$REPO_BRANCH"
  else
    mkdir -p "$(dirname -- "$CLONE_DIR")"
    git clone --depth 1 --branch "$REPO_BRANCH" "$REPO_URL" "$CLONE_DIR"
  fi

  exec bash "$CLONE_DIR/update.sh" ${PASS_ARGS[@]+"${PASS_ARGS[@]}"}
fi

cd "$SCRIPT_DIR"

for arg in "$@"; do
  case "$arg" in
    --dir|--dir=*) ;;  # only meaningful in curl-pipe mode
    -h|--help)     print_help; exit 0 ;;
    *) echo "error: unknown flag: $arg (try --help)" >&2; exit 1 ;;
  esac
done

command -v make >/dev/null 2>&1 || { echo "error: make not found" >&2; exit 1; }
exec make update
