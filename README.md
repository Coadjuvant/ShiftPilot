# Clinic Scheduler Platform

The repository now contains two UI paths:

- `UI/app.py` – legacy Streamlit prototype (still runnable for reference).
- `frontend/` + `backend/api/` – new FastAPI + React architecture for the licensable product.

## FastAPI backend

```bash
pip install -r backend/requirements.txt
uvicorn backend.api.main:app --reload
```

### Endpoints

- `GET /health` – simple status probe (used by the React app).
- `POST /schedule/run` – accepts staff/config/demand payloads (see `backend/api/schemas.py`) and returns tournament results.

## React frontend

```bash
cd frontend
npm install
npm run dev
```

The Vite dev server proxies `/api/*` calls to `http://localhost:8000`, so keep FastAPI running in another terminal. The initial `StaffPlanner` page verifies the API connection and demonstrates a local, non-resetting roster editor.

## Migration plan

1. Rebuild each Streamlit tab in React components while hitting the FastAPI endpoints.
2. Expand the API surface with config persistence, PTO management, Excel export, etc.
3. Package the React app via WebView2/Electron once feature-complete for distribution to clinics.
