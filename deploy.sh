#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ "${SKIP_GIT_PULL:-}" != "1" ]; then
  echo "[shiftpilot] pulling latest..."
  git pull --ff-only origin "${DEPLOY_BRANCH:-main}"
else
  echo "[shiftpilot] skipping git pull (SKIP_GIT_PULL=1)"
fi

export VITE_APP_BUILD="$(git rev-parse --short HEAD 2>/dev/null || echo unknown)"
export VITE_APP_VERSION="${VITE_APP_VERSION:-$VITE_APP_BUILD}"

echo "[shiftpilot] selecting compose..."
if docker compose version >/dev/null 2>&1; then
  COMPOSE_CMD="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE_CMD="docker-compose"
else
  echo "Docker Compose is not installed. Install docker-compose-plugin (Ubuntu: apt-get install -y docker-compose-plugin) or docker-compose." >&2
  exit 1
fi

echo "[shiftpilot] building images..."
# Try with --pull; fall back if unsupported by older compose versions
if ! ${COMPOSE_CMD} build --pull; then
  ${COMPOSE_CMD} build
fi

echo "[shiftpilot] deploying..."
${COMPOSE_CMD} up -d --remove-orphans

echo "[shiftpilot] pruning old images..."
docker image prune -f

echo "[shiftpilot] done."
