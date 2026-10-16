"""Run a local backend with generated credentials; never read the production .env."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import secrets
import sys
from urllib.parse import quote

root = Path(__file__).resolve().parents[1]
os.chdir(root)
sys.path.insert(0, str(root))
parser = argparse.ArgumentParser()
parser.add_argument("action", choices=["serve", "test", "seed"])
args = parser.parse_args()
settings_file = root / ".local" / "test-settings.json"
settings_file.parent.mkdir(exist_ok=True)
if not settings_file.exists():
    settings_file.write_text(json.dumps({"db_password": secrets.token_urlsafe(32), "admin_password": secrets.token_urlsafe(24), "jwt_secret": secrets.token_urlsafe(48)}))
settings = json.loads(settings_file.read_text())
dsn = f"postgresql://shiftpilot_test:{quote(settings['db_password'], safe='')}@127.0.0.1:55432/shiftpilot_test"
os.environ.update(DATABASE_URL=dsn, SHIFT_TEST_DATABASE_URL=dsn, AUTH_BACKEND="postgres", APP_ENV="dev",
                  ADMIN_USER="preview-admin", ADMIN_PASS=settings["admin_password"], JWT_SECRET=settings["jwt_secret"],
                  API_KEY="", CORS_ALLOW_ORIGINS="http://127.0.0.1:5173,http://localhost:5173")
if args.action == "test":
    import pytest
    raise SystemExit(pytest.main(["-q"]))
if args.action == "serve":
    import uvicorn
    uvicorn.run("backend.api.main:app", host="127.0.0.1", port=8000, proxy_headers=False)
else:
    from backend.api.main import app
    from fastapi.testclient import TestClient
    with TestClient(app) as client:
        result = client.post("/api/auth/login", json={"username": "preview-admin", "password": settings["admin_password"]})
        result.raise_for_status()
        staff = [{"id": f"tech-{i}", "name": f"Sample Tech {i}", "role": "Tech", "can_open": True,
                  "can_close": True, "can_bleach": True, "availability": {day: True for day in ["Mon","Tue","Wed","Thu","Fri","Sat"]}}
                 for i in range(1, 7)]
        staff += [{"id": f"rn-{i}", "name": f"Sample RN {i}", "role": "RN"} for i in range(1, 3)]
        staff += [{"id": f"admin-{i}", "name": f"Sample Admin {i}", "role": "Admin"} for i in range(1, 3)]
        config = {"clinic": {"name": "Sample Clinic", "timezone": "America/Chicago"},
                  "schedule": {"start": "2026-10-19", "weeks": 2},
                  "ratios": {"patients_per_tech": 4, "patients_per_rn": 12, "techs_per_rn": 4},
                  "constraints": {}, "bleach": {"day": "Thu", "rotation": ["tech-1", "tech-2"], "cursor": 0},
                  "tournament": {"trials": 10, "last_seed": 0}, "export_roles": ["Tech", "RN", "Admin"],
                  "scheduled_roles": ["Tech", "RN", "Admin"], "staff": staff,
                  "demand": [{"Day": day, "Patients": 8, "Tech_Open": 1, "Tech_Mid": 1, "Tech_Close": 1,
                              "RN_Count": 1, "Admin_Count": 1} for day in ["Mon","Tue","Wed","Thu","Fri","Sat"]], "pto": []}
        client.post("/api/configs/save", json={"filename": "sample-clinic.json", "payload": config}).raise_for_status()
    print("Sample clinic seeded; preview credentials remain in .local/test-settings.json")
