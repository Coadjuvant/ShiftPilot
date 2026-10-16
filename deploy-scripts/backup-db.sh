#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
cd "${REPO_DIR:-/opt/shiftpilot}"
backup_dir="${BACKUP_DIR:-/var/backups/shiftpilot}"
mkdir -p "$backup_dir"
temporary=$(mktemp "$backup_dir/.dump-XXXXXX")
trap 'rm -f "$temporary"' EXIT
docker compose exec -T db sh -c 'exec pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom' > "$temporary"
test -s "$temporary"
docker compose exec -T db pg_restore --list < "$temporary" >/dev/null
destination="$backup_dir/shiftpilot-db-$(date -u +%Y%m%dT%H%M%SZ)-$$.dump"
mv "$temporary" "$destination"
echo "Database backup created and archive checked: $destination"
