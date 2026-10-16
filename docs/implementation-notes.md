# Local implementation checkpoint — October 15, 2026

Checkout: `D:\Coding\ShiftPilot\ShiftPilot`.
Branch: `improve/reliability-and-planner`, based on main at f50fb36.
Changes are local and unpushed. No production configuration, database, or running
service was changed by this implementation work.

## Implemented

- Weekly workload fairness alongside full-period fairness. Eligible staff with
  fewer shifts in the current week receive a stronger preference; this remains
  soft and does not bypass PTO, availability, capabilities, locks, or required
  rules. Trials prioritize fewer uncovered slots before the preference score.
  The reported six-week sample now has three shifts per Tech each week and all
  108 slots covered using the original winning seed as the replay seed. This is
  not a guarantee of equal weeks for arbitrary inputs. Saved versions are unchanged;
  generating a new draft uses the updated scoring.
- Revocable server sessions, complete logout, live role/status checks, password
  reset revocation, create-only admin bootstrap, and secret-free new invite logs.
- Protected bootstrap-admin actions, clear admin errors, account disable feedback,
  and read responses that omit invite tokens.
- Draft deletion with inline confirmation, account ownership checks, and server-side
  protection for current and previously published versions.
- Additive schedule versions, draft/publish separation, restoring older versions,
  and ownership checks, including permanent binding of legacy username-owned data.
  A reused username cannot inherit a deleted account's legacy schedules.
- Independent scheduled/exported role choices. Existing saved settings migrate
  their previous role scope once when read.
- Manual assignment adjustment and locking. Changes produce new drafts and are
  checked against availability, PTO, capabilities, daily duties, and required rules.
  Regeneration retains locks and reports unsuccessful searches without claiming
  the schedule is mathematically impossible.
- Saved/unsaved settings status, tab-session recovery, safe config-load sequencing,
  preserving the existing config filename on Save, and explicit Save copy.
- Clear Off / Prefer / Required rules; readable API validation errors; honest
  generation activity; shortened login and improved invitation/reset flow.
- Calmer planner surfaces, persistent theme choice, theme control in navigation,
  phone-width navigation fixes, focus styling, and reduced-motion support.
- Request bounds, conservative forwarded-IP handling, loopback app ports,
  restart/health settings, production-ready build metadata, and build exclusions
  for local credentials/test data.
- Deployment builds before replacing containers, preserves tracked edits, uses
  atomic locking, checks health, retries failures, and restores previous images
  with compatible health checks. The five-minute timer cadence is unchanged.
- Backup helper, hardened optional webhook defaults, CI checks, updated dependency
  locks/runtime pins, and local/production runbooks.

## Verification

- 33 Python tests passed; 1 opt-in live-API test intentionally skipped.
- 9 frontend workflow tests passed.
- Frontend lint, TypeScript checking, and production build passed.
- npm audit: no reported vulnerabilities. pip-audit of backend requirements:
  no known vulnerabilities found at review time. These audits do not cover OS or
  container-image vulnerabilities or prove absence of application flaws.
- Compose files parsed successfully; release/backup scripts passed Bash syntax checks.
- Release behavior tested with isolated repositories and mocked Docker commands:
  failed builds do not stop the running stack; unhealthy replacements roll back;
  dirty checkouts are preserved; unchanged commits skip rebuilds; failed commits retry.
- A synthetic local PostgreSQL backup restored into a separate test database,
  with matching users/configs/schedules/history row counts.
- Upgrade regression verifies that existing published assignments survive
  repeated startup migrations, history is backfilled only once, and legacy
  published versions remain exportable and protected from deletion.
- Browser checks: authenticated clinic loading; a two-week draft with 58
  assignments and no coverage gaps; history reopening; inline publish confirmation;
  published roster on home; protected admin controls; unsaved-settings recovery;
  saving into the existing clinic file; logout; and phone-width layout.

## Preview

Local frontend: http://127.0.0.1:5173
Local backend: http://127.0.0.1:8000/api/ready
Database: 127.0.0.1:55432, dedicated `shiftpilot_test` database.

Username is `preview-admin`; the generated password is stored privately in
`.local/test-settings.json`. Sample staff are fictional. `.venv`, `.local`,
database files, recovered settings, and screenshots are ignored by Git.

## Before production rollout

Docker Desktop was reopened and the production Compose stack was built and
started successfully in the separate `shiftpilot-integration` project. Only
local test credentials and fictional data were used. All three services passed
their health checks. Packaged Nginx/API checks covered login, production Secure
cookies, clinic saving, draft generation, publishing, Excel export, and logout
revocation. Published schedules and sessions survived app container restarts.
Readiness returned 503 with PostgreSQL stopped and recovered after it restarted.
An actual container PostgreSQL backup restored into a separate scratch database
with matching users/configs/schedules/history counts; the scratch database was
then removed. Restart policies and loopback-only app port bindings were verified.

The Docker preview is available at http://127.0.0.1:18080 with backend port
18000. Its generated credentials remain in ignored `.local/docker-test.env`.
The separate database volume is retained. This local check does not verify the
installed production timer, host Nginx, Cloudflare, or production data migration.

Inspect the installed deployment service, Compose v2 support, host Nginx
destinations, trusted proxy CIDRs, production environment settings, and a real
backup/restore path before pushing to the watched branch. Existing sessions will
need a new login after this release. The database changes are additive.

External uptime alert delivery, encrypted off-server backup storage, restore
drills using a production backup, and any future shared-clinic membership model
remain separate infrastructure/product work. No production database clone was
needed for this implementation; representative real configurations should still
be exercised against an isolated copy before release if available.

See [production deployment](production-deployment.md) and
[local testing](local-testing.md).
