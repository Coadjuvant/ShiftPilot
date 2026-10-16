# ShiftPilot User Guide

ShiftPilot helps clinic managers build multi-week staff schedules, enforce clinic rules, and export rosters for downstream tools.

## Quick start

1) Open the site and select `Login`.
2) After login, go to `Planner`.
3) Load clinic settings, update inputs, and generate a draft. Review coverage before publishing.

## Local preview

1) Copy `.env.example` to `.env` and adjust local secrets if needed.
2) Start the Docker stack:
   ```
   docker compose up -d --build
   ```
3) Open `http://localhost:8080`.
4) Check backend health at `http://localhost:8000/api/health`.

For frontend hot reload, keep the Docker database/backend running and start Vite separately:

```
docker compose up -d db backend
cd frontend
npm install
npm run dev
```

Run local checks:

```
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements-dev.txt
python -m pytest -q
SHIFT_TEST_LIVE_API=1 python -m pytest tests/api/test_live_api.py -q
cd frontend
npm install
npm run lint
npm run build
```

The baseline Postgres schema is documented in `db/migrations/0001_initial.sql`; app startup still applies compatible `CREATE TABLE IF NOT EXISTS` checks for simple deployments.

## Planner workflow

### 1) Load or create a config
- Use the config dropdown to load an existing clinic config.
- Update clinic name, staffing, and rules as needed.
- Use `Save` to persist changes.

### 2) Staff
Define your roster (names + roles). This is the pool the scheduler can use.

### 3) Availability
Mark which days each staff member can work.

### 4) Prefs
Set preference weights (what each person prefers to open/close).

### 5) Demand
Define daily demand (how many Tech/RN/Admin slots are needed per day).

### 6) PTO
Add time off for each staff member (single day or ranges).

### 7) Bleach
Set bleach day frequency and the rotation order.
- The rotation advances when the assigned person bleaches.
- If someone is unavailable, they are skipped and placed first in line next time.

### 8) Run
Set the schedule window and constraints, then click `Run Schedule`.
- You can toggle constraints like max days/week, alternate Saturdays, and post-bleach rest.
- If a slot cannot be filled, it will be marked as needing coverage.

## Schedule results

- A schedule matrix appears in the planner after a successful run.
- Each run is saved as a separate draft. The home page shows the current published roster (only when logged in).
- Open earlier versions in Schedule history. Publishing a draft changes the current roster; generating one does not.
- Adjust staff assignments and locks in the review section. Saving edits creates a validated new draft. Regeneration keeps saved locks.
- Use the week arrows on the home page card to move through the schedule weeks.

## Exports

In the planner:
- `Download viewed schedule` exports the version currently open (Excel).
- `Export roles` controls which roles appear in exports.
- `Roles to schedule` independently controls generation. Export choices do not remove coverage from a roster.

## Login behavior

- The top-right button toggles between `Login` and `Logout`.
- Sessions expire; if the session ends, you will be prompted to log in again.
- Logout ends the server session. Disabled accounts lose access, and role changes apply to existing sessions.
- Use Accept invitation for account setup or administrator-issued password resets. New passwords require at least 12 characters.

## Admin (optional)

Admins can manage invites, user roles, and review recent activity.

## Development and deployment

Use [isolated local testing](docs/local-testing.md) to test authenticated workflows with fictional clinic data.
See [the Vultr/Cloudflare deployment runbook](docs/production-deployment.md) before pushing to the production branch.
The existing five-minute timer may deploy a production-branch push automatically.

## Support

If you need help, contact: `support@shiftpilot.me`
