# Separate database maintenance from the HTTP application

The HTTP container uses `DATABASE_URL` for a restricted runtime identity. Its
Compose environment excludes DB_USER, DB_PASSWORD, ADMIN_PASS and
RUNTIME_DB_PASSWORD. These remain operator/maintenance settings, not API secrets.

The `db-maintenance` service is short-lived and available only through the
`maintenance` profile. It uses the same built backend image, receives DB_*
connection fields separately (so special characters do not need URL encoding),
applies schema migrations, creates the initial application administrator only if
absent, and refreshes the reviewed runtime grants. Existing account passwords and
published schedules are preserved. Do not run it as a public HTTP service.

Runtime access covers the seven explicitly listed application tables and their
required sequences. Audit history allows SELECT/INSERT; legacy ownership aliases
allow SELECT only. The runtime identity has no superuser, role/database creation,
replication or row-security bypass privileges. It must not own schema objects,
create permanent schema objects or belong to other roles. PostgreSQL's ordinary
PUBLIC defaults, including temporary-table permissions where configured, still
apply; this is not per-tenant database isolation.

## Existing deployment: attended first switch

Keep automatic deployment paused. Take a fresh private custom-format database
backup, verify its catalog, retain the previous image identity and full previous
runtime environment, and preserve the root-owned settings file. Keep off-server
backups and perform restore drills separately: archive listing is not a restore.

1. Fetch the reviewed release and build the backend image while the current
   backend continues serving. Do not recreate the application yet.
2. Using administrative credentials in a one-off maintenance process, migrate
   the existing schema and create a NEW runtime login with an independent random
   password. The provisioning routine refuses an existing role or inherited
   schema CREATE permissions. It never demotes or deletes the recovery admin.
3. Privately replace DATABASE_URL with the new runtime connection, set
   DB_INITIALIZE_ON_STARTUP=false and RUNTIME_DB_USER to the provisioned role.
   Keep DB_USER/DB_PASSWORD as the administrative maintenance identity. Remove
   RUNTIME_DB_PASSWORD after provisioning; the runtime URL is its saved copy.
4. Run the runtime preflight using the new image and environment, then recreate
   only the backend with that image pinned. Verify readiness, login, clinic data,
   generation, publishing, history and export. A brief API interruption is expected.
5. If the first switch fails, restore BOTH the previous image and its previous
   environment, including the old DATABASE_URL and bootstrap variables required
   by legacy images. Disable the newly created runtime login. Do not drop user
   data or restore a test database over production. Image-only rollback is not
   sufficient across this initial transition.

An attended operator helper can automate these steps with a private recovery
checkpoint. Do not paste, commit or print the saved environment, connection URLs,
role passwords, verifier strings or backup archives.

## New installation

Fill the ignored .env with independently generated database, runtime, JWT and
initial administrator credentials. The example DATABASE_URL must be replaced;
its administrator URL is not suitable for starting the restricted HTTP service.
Generate a runtime password of at least 32 characters; hex avoids URL escaping
mistakes. Restrict .env to its owner.

```bash
docker compose build backend frontend
docker compose up -d --wait db
docker compose --profile maintenance run --rm --no-deps -T db-maintenance
docker compose --profile maintenance run --rm --no-deps -T db-maintenance python -m backend.manage_db provision-runtime
```

Privately update DATABASE_URL to that runtime identity and remove the temporary
RUNTIME_DB_PASSWORD provisioning value, then:

```bash
docker compose run --rm --no-deps -T backend python -m backend.check_runtime
docker compose up -d --no-deps --wait backend frontend
```

## Later releases

`auto-deploy.sh` builds before touching the serving containers, runs maintenance,
and validates the runtime connection before replacing the application. A failed
migration or unsafe runtime configuration stops deployment while the current
application containers remain serving. Normal application deployments replace
only backend/frontend; PostgreSQL upgrades remain an attended maintenance task.
Migrations must remain backward-compatible with the serving release.

Changes to runtime table permissions must be reviewed in
`backend/database_admin.py`. Maintenance regrants access to that explicit list;
it does not automatically expose every future table through default grants.
If administrators revoke access or change role memberships, maintenance refuses
unexpected administrative role privileges and the runtime preflight checks for
excessive privileges, object ownership and schema compatibility.

Direct Python development retains DB_INITIALIZE_ON_STARTUP=true as its default
for existing previews. Production Compose explicitly defaults to false. The
runtime preflight refuses initialization mode and does not apply migrations.

Tests run API workflows against both the schema-owner bootstrap profile and a
separate restricted role. They exercise real PostgreSQL, fail on permission
regressions and preserve disposable test-schema cleanup.
