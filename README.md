# ShiftPilot (Clinic Scheduler)

ShiftPilot is a scheduling assistant for dialysis clinics. It helps clinic managers
build multi-week rosters, enforce rules (coverage, bleach rotation, max days, etc),
and export schedules for downstream tools.

## Stack

- Frontend: React + Vite
- Backend: FastAPI + Python scheduler engine
- Database: Postgres (auth, configs, schedules, audit log)
- Local/dev: Docker Compose

## Repo layout

- `frontend/` - React app (landing, planner, login).
- `backend/api/` - FastAPI app + API routes.
- `backend/scheduler/` - scheduling logic.
- `configs/` - sample config files.
- `docs/` - notes and docs.
- `DEPLOY.md` - deployment notes.

## Quick start (Docker)

1) Create a `.env` file at the repo root:

```
ADMIN_USER=admin
ADMIN_PASS=admin
ADMIN_LICENSE=DEMO
JWT_SECRET=change-me
AUTH_BACKEND=postgres
DATABASE_URL=postgresql://admin:changeme@db:5432/shiftpilot_db
VITE_API_URL=http://localhost:8000/api
GEOIP_API_URL=https://www.iplocate.io/api/lookup/{ip}
GEOIP_API_TIMEOUT=2
GEOIP_CACHE_TTL=3600
```

2) Build and run:

```
docker compose up -d --build
```

- Frontend: `http://localhost:8080`
- API: `http://localhost:8000`

## Local dev (no Docker)

Backend:
```
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt
uvicorn backend.api.main:app --reload
```

Frontend:
```
cd frontend
npm install
npm run dev
```

Set `VITE_API_URL` for dev in `frontend/.env.local`, for example:
```
VITE_API_URL=http://localhost:8000/api
```

## Build tag (optional)

The footer can show a build label when you set these at build time:
- `VITE_APP_BUILD` (usually a short git hash)
- `VITE_APP_VERSION` (optional version string)

## Deployment

See `DEPLOY.md` for environment variables and hosting notes.

## Notes

- Do not commit secrets; keep `.env` local or set platform secrets.
- If you change backend env vars, rebuild/restart the backend container.
