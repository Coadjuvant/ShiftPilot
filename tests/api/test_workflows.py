"""Real PostgreSQL workflow tests; use only a dedicated *_test database."""
from __future__ import annotations

import copy
import importlib
import os
import uuid

import psycopg2
import pytest
from fastapi.testclient import TestClient
from psycopg2.extensions import make_dsn, parse_dsn


def schedule_request():
    days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
    return {
        "staff": [
            {"id": "tech", "name": "Sample Tech", "role": "Tech"},
            {"id": "rn", "name": "Sample RN", "role": "RN"},
        ],
        "requirements": [{"day_name": d, "tech_mids": 1, "rn_count": 1} for d in days],
        "config": {"clinic_name": "Test Clinic", "timezone": "America/Chicago", "start_date": "2026-10-19",
                   "weeks": 1, "patients_per_tech": 0, "patients_per_rn": 0, "techs_per_rn": 0},
        "tournament_trials": 2, "base_seed": 42, "export_roles": ["Tech"],
        "scheduled_roles": ["Tech", "RN"],
    }


@pytest.fixture(scope="module")
def application():
    dsn = os.getenv("SHIFT_TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("Set SHIFT_TEST_DATABASE_URL to a dedicated *_test database")
    params = parse_dsn(dsn)
    if not params.get("dbname", "").endswith("_test"):
        pytest.fail("Workflow tests require a dedicated database name ending in _test")
    schema = "test_" + uuid.uuid4().hex
    conn = psycopg2.connect(dsn)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute(f'CREATE SCHEMA "{schema}"')
    previous = dict(os.environ)
    os.environ.update(DATABASE_URL=make_dsn(dsn, options=f"-c search_path={schema}"), AUTH_BACKEND="postgres",
                      APP_ENV="dev", ADMIN_USER="test-admin", ADMIN_PASS="sample-admin-password",
                      JWT_SECRET="test-secret-with-at-least-thirty-two-bytes", API_KEY="")
    try:
        # Existing unit tests may have loaded settings/storage with fake connections.
        for name in ("backend.auth_db", "backend.api.settings", "backend.api.dependencies",
                     "backend.api.request_context", "backend.api.routes.auth", "backend.api.routes.schedules",
                     "backend.api.routes.configs", "backend.api.main"):
            module = importlib.import_module(name)
            importlib.reload(module)
        yield importlib.import_module("backend.api.main").app
    finally:
        os.environ.clear()
        os.environ.update(previous)
        with conn.cursor() as cur:
            cur.execute(f'DROP SCHEMA "{schema}" CASCADE')
        conn.close()


@pytest.fixture
def client(application):
    from backend.api import request_context
    request_context._rate_buckets.clear()
    with TestClient(application) as client:
        result = client.post("/api/auth/login", json={"username": "test-admin", "password": "sample-admin-password"})
        assert result.status_code == 200, result.text
        yield client


def invite(client):
    username = "user-" + uuid.uuid4().hex[:10]
    result = client.post("/api/auth/invite", json={"username": username, "license_key": "DEMO"})
    assert result.status_code == 200, result.text
    token = result.json()["token"]
    from backend.api.main import app
    other = TestClient(app)
    response = other.post("/api/auth/setup", json={"invite_token": token, "username": username, "password": "sample-user-password"})
    assert response.status_code == 200, response.text
    return other, username, token


def test_logout_revokes_cookie_and_bearer_token(client):
    token = client.cookies.get("auth_token")
    assert client.get("/api/auth/me").status_code == 200
    assert client.post("/api/auth/logout").status_code == 200
    assert not client.cookies.get("auth_token")
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401
    assert client.get("/api/auth/me", headers={"Cookie": f"auth_token={token}"}).status_code == 401


def test_account_permissions_reset_and_invite_secrecy(client):
    other, username, token = invite(client)
    users = client.get("/api/auth/users").json()
    user = next(user for user in users if user["username"] == username)
    assert "invite_token" not in user and "last_invite_token" not in user
    assert token not in str(client.get("/api/auth/audit").json())
    assert other.get("/api/auth/users").status_code == 403
    assert client.post(f'/api/auth/users/{user["id"]}/role', json={"role": "admin"}).status_code == 200
    assert other.get("/api/auth/users").status_code == 200
    assert client.post(f'/api/auth/users/{user["id"]}/role', json={"role": "user"}).status_code == 200
    assert other.get("/api/auth/users").status_code == 403
    reset = client.post(f'/api/auth/users/{user["id"]}/reset').json()["token"]
    old_token = other.cookies.get("auth_token")
    response = other.post("/api/auth/setup", json={"invite_token": reset, "username": username, "password": "replacement-password"})
    assert response.status_code == 200, response.text
    assert other.get("/api/auth/me", headers={"Authorization": f"Bearer {old_token}"}).status_code == 401
    assert other.post("/api/auth/setup", json={"invite_token": reset, "username": username, "password": "replacement-password"}).status_code == 400
    assert client.post("/api/auth/invite/revoke", json={"username": username, "license_key": "DEMO"}).status_code == 200
    assert other.get("/api/auth/me").status_code == 401
    assert client.post("/api/auth/invite/revoke", json={"username": "test-admin", "license_key": "DEMO"}).status_code == 400


def test_bootstrap_does_not_reset_existing_password(client):
    from backend.auth_db import ensure_admin
    ensure_admin("test-admin", "a-different-password")
    result = client.post("/api/auth/login", json={"username": "test-admin", "password": "sample-admin-password"})
    assert result.status_code == 200


def test_generate_history_publish_export_and_isolation(client):
    first = client.post("/api/schedule/run", json=schedule_request())
    assert first.status_code == 200, first.text
    version_id = first.json()["version_id"]
    assert {a["role"] for a in first.json()["assignments"]} == {"Tech", "RN"}  # Export selection does not remove RN.
    assert client.get("/api/schedule/latest").json() == {"status": "none"}
    assert client.post(f"/api/schedule/versions/{version_id}/publish").status_code == 200
    published = client.get("/api/schedule/latest").json()
    assert published["version_id"] == version_id
    second = client.post("/api/schedule/run", json=schedule_request()).json()["version_id"]
    assert client.get("/api/schedule/latest").json()["version_id"] == version_id
    assert client.get(f"/api/schedule/versions/{version_id}").json()["assignments"] == first.json()["assignments"]
    history = client.get("/api/schedule/versions").json()
    assert {v["id"] for v in history} >= {version_id, second}
    exported = client.get("/api/schedule/export/excel", params={"version_id": second, "roles": "RN"})
    assert exported.status_code == 200 and exported.content.startswith(b"PK")
    other, _, _ = invite(client)
    assert other.get(f"/api/schedule/versions/{version_id}").status_code == 404
    assert other.post(f"/api/schedule/versions/{version_id}/publish").status_code == 404
    assert other.get("/api/schedule/export/excel", params={"version_id": version_id}).status_code == 404
    assert other.get("/api/schedule/versions").json() == []


@pytest.mark.parametrize("change", ["duplicates", "days", "pto", "budget", "timezone", "weeks"])
def test_invalid_schedule_inputs_rejected(client, change):
    request = copy.deepcopy(schedule_request())
    if change == "duplicates": request["staff"].append(request["staff"][0])
    if change == "days": request["requirements"][-1]["day_name"] = "Mon"
    if change == "pto": request["pto"] = [{"staff_id": "missing", "date": "2026-10-19"}]
    if change == "budget": request["requirements"][0]["tech_mids"] = 100000
    if change == "timezone": request["config"]["timezone"] = "invalid/timezone"
    if change == "weeks": request["config"]["weeks"] = 100
    result = client.post("/api/schedule/run", json=request)
    assert result.status_code == 422, result.text


def test_database_readiness(client):
    assert client.get("/api/ready").json() == {"status": "ready"}


def test_delete_draft_enforces_ownership_and_protects_published_versions(client):
    version_id = client.post("/api/schedule/run", json=schedule_request()).json()["version_id"]
    other, _, _ = invite(client)
    assert other.delete(f"/api/schedule/versions/{version_id}").status_code == 404
    assert client.get(f"/api/schedule/versions/{version_id}").status_code == 200
    assert client.delete(f"/api/schedule/versions/{version_id}").json() == {"status": "deleted"}
    assert client.get(f"/api/schedule/versions/{version_id}").status_code == 404
    assert version_id not in {v["id"] for v in client.get("/api/schedule/versions").json()}
    assert client.delete(f"/api/schedule/versions/{version_id}").status_code == 404
    published = client.post("/api/schedule/run", json=schedule_request()).json()["version_id"]
    assert client.post(f"/api/schedule/versions/{published}/publish").status_code == 200
    newer = client.post("/api/schedule/run", json=schedule_request()).json()["version_id"]
    assert client.post(f"/api/schedule/versions/{newer}/publish").status_code == 200
    for protected in (published, newer):
        assert client.delete(f"/api/schedule/versions/{protected}").status_code == 409
        assert client.get(f"/api/schedule/versions/{protected}").status_code == 200
    assert client.get("/api/schedule/latest").json()["version_id"] == newer


def test_manual_adjustments_create_versions_and_locks_survive_regeneration(client):
    request = schedule_request()
    request["staff"].append({"id": "tech2", "name": "Alternate Tech", "role": "Tech"})
    request["config"]["toggles"] = {"enforce_three_day_cap": 0, "limit_tech_four_days": 0,
                                    "limit_rn_four_days": 0, "enforce_alt_saturdays": 0, "enforce_post_bleach_rest": 0}
    response = client.post("/api/schedule/run", json=request)
    assert response.status_code == 200, response.text
    original_id = response.json()["version_id"]
    original = client.get(f"/api/schedule/versions/{original_id}").json()
    assignments = copy.deepcopy(original["assignments"])
    target = next(a for a in assignments if a["role"] == "Tech")
    previous_staff = target["staff_id"]
    target["staff_id"] = "tech2" if previous_staff == "tech" else "tech"
    target["is_locked"] = True
    changes = [{key: a[key] for key in ("date", "role", "duty", "slot_index", "staff_id", "is_locked")} for a in assignments]
    adjusted = client.post(f"/api/schedule/versions/{original_id}/adjust", json={"assignments": changes})
    assert adjusted.status_code == 200, adjusted.text
    adjusted_id = adjusted.json()["version_id"]
    assert adjusted_id != original_id
    still_original = client.get(f"/api/schedule/versions/{original_id}").json()
    assert still_original["assignments"] == original["assignments"]
    regenerated = client.post(f"/api/schedule/versions/{adjusted_id}/regenerate")
    assert regenerated.status_code == 200, regenerated.text
    kept = next(a for a in regenerated.json()["assignments"] if a["date"] == target["date"] and a["role"] == "Tech")
    assert kept["is_locked"] and kept["staff_id"] == target["staff_id"]
    bad_changes = copy.deepcopy(changes)
    next(a for a in bad_changes if a["role"] == "Tech")["staff_id"] = "rn"
    assert client.post(f"/api/schedule/versions/{original_id}/adjust", json={"assignments": bad_changes}).status_code == 422
    assert client.post(f"/api/schedule/versions/{original_id}/adjust", json={"assignments": changes[:-1]}).status_code == 422


def test_reused_username_cannot_inherit_legacy_schedules(client):
    other, username, _ = invite(client)
    from backend.auth_db import init_db, save_schedule
    save_schedule(username, {"clinic_name": "Legacy Clinic", "assignments": [], "weeks": 1, "start_date": "2026-10-19"})
    init_db()
    assert other.get("/api/schedule/latest").json()["clinic_name"] == "Legacy Clinic"
    user_id = other.get("/api/auth/me").json()["sub"]
    assert client.delete(f"/api/auth/users/{user_id}").status_code == 200
    response = client.post("/api/auth/invite", json={"username": username, "license_key": "DEMO"})
    token = response.json()["token"]
    from backend.api.main import app
    replacement = TestClient(app)
    assert replacement.post("/api/auth/setup", json={"username": username, "password": "sample-replacement-password", "invite_token": token}).status_code == 200
    init_db()  # A subsequent restart must not reassign the old alias.
    assert replacement.get("/api/schedule/latest").json() == {"status": "none"}
    assert replacement.get("/api/schedule/versions").json() == []


def test_upgrade_keeps_existing_published_roster_and_backfills_history_once(client):
    other, username, _ = invite(client)
    from backend.auth_db import init_db, save_schedule
    draft = client.post("/api/schedule/run", json=schedule_request()).json()
    legacy = {**draft, "clinic_name": "Existing production-style roster",
              "start_date": "2026-10-19", "weeks": 1,
              "staff": schedule_request()["staff"]}
    legacy.pop("version_id")
    save_schedule(username, legacy)
    init_db()
    init_db()  # A restart must not duplicate history or rewrite the saved roster.
    assert other.get("/api/schedule/latest").json()["assignments"] == legacy["assignments"]
    history = other.get("/api/schedule/versions").json()
    assert len(history) == 1 and history[0]["state"] == "published"
    loaded = other.get(f"/api/schedule/versions/{history[0]['id']}").json()
    assert loaded["assignments"] == legacy["assignments"]
    assert other.delete(f"/api/schedule/versions/{history[0]['id']}").status_code == 409
    exported = other.get("/api/schedule/export/excel", params={"version_id": history[0]["id"]})
    assert exported.status_code == 200 and exported.content.startswith(b"PK")
