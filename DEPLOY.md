# Deploying the Clinic Scheduler (free-friendly)

This app has a React/Vite frontend and a FastAPI backend. Below are simple steps using free tiers where possible.

## Frontend (Netlify or Vercel)
1. Set env vars in the dashboard:
   - `VITE_API_URL` = the full URL of your backend (e.g., `https://your-api.fly.dev`)
   - (Optional) `VITE_API_KEY` if you use the API key header.
2. Build command: `npm run build`
3. Publish directory: `dist/`
4. Deploy from GitHub or upload the `dist` folder.

## Backend (Fly.io or Render free tier)
### Using the provided Dockerfile
- `backend/Dockerfile` builds the FastAPI server. It expects to run from the repository root with `./backend` copied in.
- Required env vars:
  - `JWT_SECRET` (choose a strong random string)
  - `AUTH_BACKEND=postgres`
  - `DATABASE_URL=postgres://USER:PASSWORD@HOST:PORT/DBNAME`
  - Optional: `ADMIN_USER`, `ADMIN_PASS`, `LICENSE_KEY` (defaults: admin/admin/DEMO)
  - If you want to force JSON fallback: `AUTH_BACKEND=json` and `AUTH_STORE_PATH=/data/auth_store.json`

### Fly.io (example)
1. Install `flyctl`, run `fly launch` (choose a region, supply `backend/Dockerfile`).
2. Add env vars in Fly secrets: `fly secrets set JWT_SECRET=... DATABASE_URL=... AUTH_BACKEND=postgres`
3. If using Postgres on Fly, create a Fly Postgres app and set `DATABASE_URL` accordingly.
4. Deploy: `fly deploy`.

### Render (example)
1. Create a new Web Service, point to this repo, set build command `docker build -t app .` and start command `uvicorn api.main:app --host 0.0.0.0 --port 8000`.
2. Add env vars in the Render dashboard (same as above).
3. Optional free Postgres: create a Render Postgres instance and copy its `DATABASE_URL`.

## Database (free options)
- **Supabase**: free Postgres tier; use the provided `DATABASE_URL`.
- **Render Postgres**: limited free tier.
- **Fly Postgres**: hobby tier; configure `DATABASE_URL`.

## Local quick tunnel (for testing without deploying API)
- Run backend locally (`uvicorn api.main:app --reload --port 8000`).
- Expose with `ngrok http 8000` or `cloudflared tunnel --url http://localhost:8000`.
- Set `VITE_API_URL` to the tunnel URL in your frontend env (`frontend/.env.local`), then deploy frontend to Netlify/Vercel.

## Frontend env file (dev)
- `frontend/.env.local`:
  ```
  VITE_API_URL=http://localhost:8000
  # VITE_API_KEY=...
  ```

## Notes
- Keep `JWT_SECRET` and `DATABASE_URL` out of git; set them via platform secrets.
- Free tiers may sleep; for more reliable demos, consider a small paid plan (~$5/month).
