# Isolated local testing

Use a dedicated database named `shiftpilot_test`, role `shiftpilot_test`, and
port 55432 bound to 127.0.0.1. Never use the production .env for this preview.
`.local/` and local environment files are ignored by Git.

## Prepared environment

Checkout: `D:\Coding\ShiftPilot\ShiftPilot`. Docker Desktop failed at startup,
so official EDB PostgreSQL 15 Windows binaries were used. The isolated cluster
is `.local/pgdata`. Generated credentials are in `.local/test-settings.json`.
Python dependencies are installed in this checkout's `.venv`, so the preview is
self-contained.

Start the initialized standalone cluster:

```powershell
& .local/postgres/pgsql/bin/pg_ctl.exe -D .local/pgdata -l .local/postgres.log -o '-p 55432 -h 127.0.0.1' start
```

Stop it using the same pg_ctl.exe with `-D .local/pgdata stop`.

For Docker instead, set SHIFT_TEST_DB_PASSWORD to the db_password in the local
settings file (the launcher generates this file if absent). Then use
`docker compose -f docker-compose.test.yml up -d --wait`. This has a separate
project/volume and initializes the test role/database automatically. Set the
environment variable in the shell; do not use the production .env.

## Preview

```text
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements-dev.txt
.venv\Scripts\python scripts/local-preview.py seed
.venv\Scripts\python scripts/local-preview.py serve
npm ci --prefix frontend
npm run dev --prefix frontend -- --host 127.0.0.1
```

Open http://127.0.0.1:5173. Username: `preview-admin`. Privately use admin_password
from `.local/test-settings.json`. Sample clinic staff are fictional. Startup
does not reset an existing account. If a preview password is changed, update the
local settings file so subsequent seed commands can sign in.

The launcher explicitly sets local database/auth/admin/JWT/API-key/CORS settings
before importing the app. A standalone cluster must already contain the test
role/database; the Docker alternative creates these automatically.

## Checks

```text
python scripts/local-preview.py test
npm run lint --prefix frontend
npx --prefix frontend tsc --noEmit -p frontend/tsconfig.json
npm run build --prefix frontend
npm audit --prefix frontend --audit-level=high
```

Database tests create a temporary schema and remove only that schema. They
require the database name to end in `_test`. For another dedicated test database,
set SHIFT_TEST_DATABASE_URL and run pytest. The old opt-in live-API test remains
disabled unless explicitly enabled.

Tests cover revocation, role changes, password resets, admin bootstrap, history,
publishing, account isolation, Excel export, manual edits, locks, malformed input,
proxy headers, and release failure/rollback behavior. The full production Compose
stack also passed an isolated Docker run: image builds, all service health
checks, authenticated API requests through packaged Nginx, schedule publication
and export, app restarts, database outage/recovery, and a backup restore with
matching row counts. Actual host Nginx/Cloudflare/systemd configuration still
needs server verification.

The retained Docker preview uses http://127.0.0.1:18080, backend port 18000,
project `shiftpilot-integration`, and a private database volume with fictional
data. Generated credentials and the port/env-file override are under ignored
`.local/docker-test.env` and `.local/docker-test.override.yml`. To restart it:

```text
docker compose --env-file .local/docker-test.env -p shiftpilot-integration -f docker-compose.yml -f .local/docker-test.override.yml up -d --wait
```

This uses the production Compose definition with local-only settings and port
overrides; it does not need a production `.env` or expose PostgreSQL to the host.
