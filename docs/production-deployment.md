# ShiftPilot on Vultr and Cloudflare

The intended path is Cloudflare â†’ host Nginx â†’ Docker frontend on 127.0.0.1:8080
â†’ backend â†’ Postgres. Host Nginx may also proxy the API to 127.0.0.1:8000.
Verify the actual host configuration before rollout. App ports now bind only to
loopback; host Nginx remains the public entry point.

## Restricted database runtime rollout

This release separates schema maintenance from HTTP access. For an existing
installation, follow [the attended database transition](database-runtime.md)
before recreating the backend. The previous administrator DATABASE_URL is rejected
by the new runtime preflight. Keep auto-deployment paused through that first switch.

## First rollout

Use an attended maintenance window. The existing timer may deploy within five
minutes of a push to its watched branch.

1. Inspect `systemctl cat shiftpilot-deploy.timer shiftpilot-deploy.service`.
   Confirm checkout path, branch, user, and script path. Verify `docker compose
   version` supports `up --wait`. The new script requires Compose v2, Bash, flock,
   and Git. Example service files may differ from the installed ones.
2. Pause the timer. Privately preserve the current `.env` and make a database
   backup using `bash deploy-scripts/backup-db.sh`. Before deploying that script,
   use an equivalent custom-format pg_dump from the existing database container.
   Never commit credentials or dumps.
3. Verify `.env`: `APP_ENV=prod`, strong JWT_SECRET, existing database credentials,
   and correct CORS_ALLOW_ORIGINS. Startup now leaves existing admin accounts and
   passwords unchanged. New accounts/password resets require 12 characters.
4. Check host Nginx destinations against the loopback port bindings. Verify DNS,
   Cloudflare origin TLS, and host/Vultr firewall settings against the real setup.
5. With the timer paused and enough disk space available, fast-forward the server
   checkout to the reviewed release. Run the newly fetched deployment script
   explicitly, so the first rollout also captures the old app images and enables
   health-based rollback. The marker forces a build even though the checkout was
   just updated to the target commit:

   ```bash
   git fetch origin main
   git merge --ff-only origin/main
   touch deploy-scripts/.local-deploy-failed
   REPO_DIR="$PWD" bash auto-deploy.sh
   ```

   Do not run the old script before fetching this release; it stops the stack
   before building. The new script builds before replacing containers, records
   the previous images as `shiftpilot-rollback-backend:previous` and
   `shiftpilot-rollback-frontend:previous`, and waits for health. An error must be
   investigated before the timer is resumed.
6. Startup adds sessions and schedule history; existing published schedules are
   retained and copied into history. No table is dropped. Existing JWTs need a
   fresh login. Legacy schedules remain viewable/exportable; editing requires a
   version with saved generation inputs.
7. Verify `/api/ready`, login, existing clinic settings, the published roster,
   generating a draft, exporting, and logout. Publish only a reviewed roster.
8. Resume the timer after verification. Its five-minute cadence is preserved.

The deployment script refuses tracked edits, fast-forwards the configured branch,
builds while the old stack runs, waits for health, and restores previous app
images on an unhealthy replacement. An ignored failure marker retries the same
commit. It does not reverse database migrations; this release is additive. Database password/role transitions also require their separate environment recovery procedure.

## Proxy trust

The backend ignores arbitrary Cloudflare/IP headers and walks X-Forwarded-For
from the nearest trusted proxy. Uvicorn header rewriting is disabled in Docker.
Set TRUSTED_PROXY_CIDRS to the actual proxies. Defaults include loopback and the
normal Docker bridge range. If Cloudflare is in the forwarded chain, include its
current official ranges after verifying Nginx appends the real peer IP. Otherwise
the safe fallback can identify the edge rather than the user. Official ranges:
https://www.cloudflare.com/ips/

## Backups and operations

`backup-db.sh` creates a private custom-format archive and checks its catalog
using pg_restore --list. It never deletes old backups. Keep encrypted off-server
copies and separately back up `.env`. Archive validation is not a restore drill:
restore a copy into an isolated PostgreSQL 15 database, verify schema/row counts
and a sample schedule export, and record the outcome. Never restore test data
over production. Never run `docker compose down -v` on production.

Operational checks: `docker compose ps`, container/Nginx logs, disk capacity,
and `/api/ready`. External alert delivery and off-server backup storage still
need the owner's chosen services and credentials.

## Optional webhook

The timer does not need the webhook listener. If used, configure WEBHOOK_SECRET
(32+ characters), DEPLOY_SCRIPT, DEPLOY_REPOSITORY, and DEPLOY_BRANCH. It defaults
to loopback, rejects the old default secret, bounds request size, and only
deploys push events for the configured repo/ref. The deployment lock prevents
timer/webhook overlap. Keep it behind the host proxy.
