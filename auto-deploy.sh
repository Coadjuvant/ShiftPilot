#!/usr/bin/env bash
# Run by the existing five-minute systemd timer. Requires Docker Compose v2.
set -Eeuo pipefail
REPO_DIR="${REPO_DIR:-/opt/shiftpilot}"
BRANCH="${DEPLOY_BRANCH:-main}"
LOG_FILE="${LOG_FILE:-/var/log/shiftpilot-deploy.log}"
LOCK_FILE="${LOCK_FILE:-/tmp/shiftpilot-deploy.lock}"

mkdir -p "$(dirname "$LOG_FILE")"
exec > >(tee -a "$LOG_FILE") 2>&1
command -v flock >/dev/null || { echo "flock is required"; exit 1; }
exec 9>"$LOCK_FILE"
if flock -n 9; then :; else
  lock_status=$?
  if [[ "$lock_status" == 1 ]]; then echo "Deployment already running"; exit 0; fi
  echo "Could not acquire deployment lock"; exit "$lock_status"
fi
cd "$REPO_DIR"
command -v docker >/dev/null
docker compose version >/dev/null
if [[ "$(git branch --show-current)" != "$BRANCH" ]]; then
  echo "Refusing deployment: checkout must be on $BRANCH"; exit 1
fi
if ! git diff --quiet || ! git diff --cached --quiet; then
  echo "Refusing deployment: tracked local changes must be reviewed first"; exit 1
fi
git fetch origin "$BRANCH"
previous=$(git rev-parse HEAD)
target=$(git rev-parse "origin/$BRANCH")
failed_marker="$REPO_DIR/deploy-scripts/.local-deploy-failed"
if [[ "$previous" == "$target" && ! -f "$failed_marker" ]]; then
  echo "Already up to date: ${target:0:12}"; exit 0
fi
# Reject rewritten/diverging history instead of merging on the production server.
touch "$failed_marker"
git merge --ff-only "origin/$BRANCH"
export VITE_GIT_COMMIT="$target"
export VITE_APP_VERSION="${target:0:12}"
export VITE_APP_BUILD="$(git log -1 --format=%cd --date=format:%Y%m%d).${target:0:12}"

rollback_file=$(mktemp)
trap 'rm -f "$rollback_file"' EXIT
printf 'services:\n' > "$rollback_file"
rollback_ready=1
for service in backend frontend; do
  container=$(docker compose ps -aq "$service")
  if [[ -z "$container" ]]; then rollback_ready=0; continue; fi
  image=$(docker inspect --format '{{.Image}}' "$container")
  rollback_tag="shiftpilot-rollback-$service:previous"
  docker image tag "$image" "$rollback_tag"
  printf '  %s:\n    image: %s\n' "$service" "$rollback_tag" >> "$rollback_file"
  # Previous releases may not expose the new /api/ready endpoint.
  if [[ "$service" == backend ]]; then
    cat >> "$rollback_file" <<'YAML'
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4)"]
YAML
  else
    cat >> "$rollback_file" <<'YAML'
    healthcheck:
      test: ["CMD", "wget", "-q", "--spider", "http://127.0.0.1/api/health"]
YAML
  fi
done

# The existing stack continues serving throughout the image build.
if ! docker compose build backend frontend; then
  touch "$failed_marker"
  echo "Build failed. Existing containers are still serving."; exit 1
fi
# Schema maintenance uses a separate, short-lived service. Its administrative
# credentials are never supplied to the HTTP application's environment.
if ! docker compose --profile maintenance run --rm --no-deps -T db-maintenance; then
  echo "Database maintenance failed. Existing application containers are still serving."
  exit 1
fi
if ! docker compose run --rm --no-deps -T backend python -m backend.check_runtime; then
  echo "Runtime database preflight failed. Existing application containers are still serving."
  exit 1
fi
if docker compose up -d --no-deps --no-build --wait --wait-timeout 180 backend frontend; then
  rm -f "$failed_marker"
  echo "Deployment healthy: $target"
else
  touch "$failed_marker"
  echo "Readiness failed for $target"
  docker compose ps
  if [[ "$rollback_ready" == 1 ]]; then
    echo "Restoring previous application images; additive database changes are retained."
    docker compose -f docker-compose.yml -f "$rollback_file" up -d --no-deps --no-build --wait --wait-timeout 180 backend frontend
  else
    echo "No complete previous application images are available for automatic rollback."
  fi
  exit 1
fi
