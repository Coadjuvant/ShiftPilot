#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "[shiftpilot] pulling latest..."
git pull --rebase --autostash

echo "[shiftpilot] building images..."
docker compose build --pull

echo "[shiftpilot] deploying..."
docker compose up -d --remove-orphans

echo "[shiftpilot] pruning old images..."
docker image prune -f

echo "[shiftpilot] done."
