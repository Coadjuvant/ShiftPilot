# ShiftPilot deployment

Use the [production rollout guide](../docs/production-deployment.md) for an
existing server. The first release must be attended: pause the timer, preserve
`.env`, back up PostgreSQL, verify host Nginx, and validate the upgraded stack
before resuming automatic deployment.

## Existing timer

The installed service should run Bash against the checkout's `auto-deploy.sh`
with its working directory set to that checkout. The release defaults to
`/opt/shiftpilot` and `main`; custom installations should provide `REPO_DIR` and
`DEPLOY_BRANCH` in the service environment. Inspect the installed unit rather
than assuming the repository templates match the running server.

```bash
systemctl show shiftpilot-deploy.service -p WorkingDirectory -p ExecStart
systemctl list-timers --all --no-pager
```

The script requires Bash, Git, `flock`, and Docker Compose with `up --wait`
support. It locks concurrent runs, refuses tracked checkout edits, fast-forwards
the watched branch, builds while the old stack serves, and checks replacement
health. Failed builds leave the old stack running; unhealthy replacements
attempt to restore the previous app images. Database migrations are retained.
Failed commits are retried on the next run.

The timer can continue checking every five minutes. Do not rerun the legacy
interactive installer for this existing installation: it edits tracked scripts
and templates, which conflicts with the new clean-checkout deployment check.

## Backups and recovery

`backup-db.sh` creates a private custom-format PostgreSQL archive and checks its
catalog. Preserve `.env` separately, keep copies off the server, and rehearse
restoring into an isolated database. A catalog check alone is not a restore test.
See the rollout guide for verification and operational requirements. Do not
stop or remove the database volume during an app release.

## Optional webhook

The timer does not require the webhook listener. If used, configure a strong
`WEBHOOK_SECRET`, the expected repository and branch, and the deployment script
path. Bind it behind the host proxy. Never commit credentials or database dumps.
