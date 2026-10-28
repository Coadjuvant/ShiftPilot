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


@pytest.fixture(scope="module", params=["bootstrap", "restricted"])
def application(request):
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
                      JWT_SECRET="test-secret-with-at-least-thirty-two-bytes", API_KEY="",
                      DB_INITIALIZE_ON_STARTUP="true")
    runtime_user = None
    try:
        if request.param == "restricted":
            from backend.database_admin import provision_runtime_role
            storage = importlib.reload(importlib.import_module("backend.auth_db"))
            admin_store = storage.PostgresAuth(os.environ["DATABASE_URL"])
            admin_store.init_db()
            admin_store.ensure_admin("test-admin", "sample-admin-password")
            candidate = "runtime_" + uuid.uuid4().hex
            password = uuid.uuid4().hex + uuid.uuid4().hex
            provision_runtime_role(admin_store.dsn, candidate, password, schema=schema)
            runtime_user = candidate
            os.environ["DATABASE_URL"] = make_dsn(dsn, user=runtime_user, password=password, options=f"-c search_path={schema}")
            os.environ["DB_INITIALIZE_ON_STARTUP"] = "false"
            # The runtime application must not need the bootstrap admin password.
            os.environ.pop("ADMIN_PASS", None)
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
            if runtime_user:
                from psycopg2 import sql
                cur.execute(sql.SQL("DROP OWNED BY {}").format(sql.Identifier(runtime_user)))
                cur.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(runtime_user)))
        conn.close()


@pytest.fixture
def migration_store(application):
    from backend.auth_db import PostgresAuth, _backend
    return PostgresAuth(make_dsn(os.environ["SHIFT_TEST_DATABASE_URL"], options=parse_dsn(_backend.dsn)["options"]))


def test_restricted_database_cannot_change_schema_or_roles(application):
    from backend.auth_db import _backend
    if os.environ["DB_INITIALIZE_ON_STARTUP"] != "false":
        pytest.skip("Privilege denials apply to the restricted runtime profile")
    from psycopg2 import sql
    conn = _backend._conn()
    try:
        for statement in (
            "CREATE TABLE privilege_probe (id integer)",
            "ALTER TABLE users ADD COLUMN privilege_probe integer",
            "DROP TABLE configs",
            sql.SQL("CREATE ROLE {}").format(sql.Identifier("probe_" + uuid.uuid4().hex)),
            "INSERT INTO legacy_schedule_owners(owner,user_id) VALUES ('not-allowed',NULL)",
            "DELETE FROM audit_log",
        ):
            try:
                with conn.cursor() as cur:
                    with pytest.raises(psycopg2.errors.InsufficientPrivilege):
                        cur.execute(statement)
            finally:
                conn.rollback()
        _backend.check_runtime_database()
    finally:
        conn.close()


def test_maintenance_can_refresh_permissions_without_promoting_runtime(application, migration_store):
    if os.environ["DB_INITIALIZE_ON_STARTUP"] != "false":
        pytest.skip("Permission refresh applies to the restricted runtime profile")
    from backend.auth_db import _backend
    from backend.database_admin import refresh_runtime_permissions
    from psycopg2 import sql
    runtime = parse_dsn(_backend.dsn)["user"]
    conn = migration_store._conn()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("SELECT current_schema()")
                schema = cur.fetchone()[0]
                cur.execute(sql.SQL("REVOKE SELECT ON configs FROM {}").format(sql.Identifier(runtime)))
        refresh_runtime_permissions(migration_store.dsn, runtime, schema)
        _backend.check_runtime_database()
    finally:
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


@pytest.mark.parametrize("reset", [False, True])
def test_invite_and_reset_tokens_are_consumed_once_under_concurrency(client, monkeypatch, reset):
    import threading
    from concurrent.futures import ThreadPoolExecutor
    import backend.auth_db as auth

    store = auth._backend
    username = "race-" + uuid.uuid4().hex
    token = store.create_invite(username, "DEMO")
    if reset:
        user = store.redeem_invite(token, "initial-fictional-password")
        token = store.reset_invite(user["id"])
    barrier = threading.Barrier(2)
    original_hash = auth._hash_password

    def synchronized_hash(password):
        barrier.wait(timeout=10)
        return original_hash(password)

    monkeypatch.setattr(auth, "_hash_password", synchronized_hash)
    passwords = ["fictional-password-one", "fictional-password-two"]
    with ThreadPoolExecutor(max_workers=2) as pool:
        users = list(pool.map(lambda password: store.redeem_invite(token, password), passwords))
    assert sum(user is not None for user in users) == 1
    winner = next(index for index, user in enumerate(users) if user is not None)
    stored = store.get_user_by_username(username)
    assert auth._check_password(passwords[winner], stored["password_hash"])
    assert not auth._check_password(passwords[1 - winner], stored["password_hash"])
    assert store.get_invite_context(token) is None


@pytest.mark.parametrize("interruption", ["revoke", "expire", "replace", "hash_failure"])
def test_redemption_does_not_accept_a_token_changed_during_hashing(client, monkeypatch, interruption):
    import backend.auth_db as auth

    store = auth._backend
    username = "interrupted-" + uuid.uuid4().hex
    token = store.create_invite(username, "DEMO")
    original_hash = auth._hash_password

    def interrupted_hash(password):
        if interruption == "hash_failure":
            raise RuntimeError("Simulated password hashing failure")
        if interruption == "revoke":
            store.revoke_invite(username)
        else:
            conn = store._conn()
            try:
                with conn:
                    with conn.cursor() as cur:
                        if interruption == "expire":
                            cur.execute("UPDATE users SET invite_expires_at=clock_timestamp() - interval '1 second' WHERE username=%s", (username,))
                        else:
                            cur.execute("UPDATE users SET invite_token=%s WHERE username=%s", ("replacement-token", username))
            finally:
                conn.close()
        return original_hash(password)

    monkeypatch.setattr(auth, "_hash_password", interrupted_hash)
    if interruption == "hash_failure":
        with pytest.raises(RuntimeError):
            store.redeem_invite(token, "fictional-new-password", desired_username="must-not-be-saved")
        assert store.get_invite_context(token) is not None
    else:
        assert store.redeem_invite(token, "fictional-new-password", desired_username="must-not-be-saved") is None
    assert store.get_user_by_username("must-not-be-saved") is None
    stored = store.get_user_by_username(username)
    assert stored is not None and not stored["password_hash"]


def test_username_conflict_does_not_consume_invitation(client):
    import backend.auth_db as auth

    store = auth._backend
    existing_name = "existing-" + uuid.uuid4().hex
    existing = store.create_invite(existing_name, "DEMO")
    store.redeem_invite(existing, "fictional-existing-password")
    username = "pending-" + uuid.uuid4().hex
    token = store.create_invite(username, "DEMO")
    with pytest.raises(ValueError, match="Username already exists"):
        store.redeem_invite(token, "fictional-new-password", desired_username=existing_name)
    assert store.get_invite_context(token) is not None
    assert store.redeem_invite(token, "fictional-new-password", desired_username=username)


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


@pytest.mark.parametrize("change", ["duplicates", "days", "pto", "budget", "timezone", "weeks", "trials"])
def test_invalid_schedule_inputs_rejected(client, change):
    request = copy.deepcopy(schedule_request())
    if change == "duplicates": request["staff"].append(request["staff"][0])
    if change == "days": request["requirements"][-1]["day_name"] = "Mon"
    if change == "pto": request["pto"] = [{"staff_id": "missing", "date": "2026-10-19"}]
    if change == "budget": request["requirements"][0]["tech_mids"] = 100000
    if change == "timezone": request["config"]["timezone"] = "invalid/timezone"
    if change == "weeks": request["config"]["weeks"] = 100
    if change == "trials": request["tournament_trials"] = 501
    result = client.post("/api/schedule/run", json=request)
    assert result.status_code == 422, result.text


def test_database_readiness(client):
    assert client.get("/api/ready").json() == {"status": "ready"}


def test_generation_accepts_five_hundred_trials(client):
    request = schedule_request()
    request["tournament_trials"] = 500
    response = client.post("/api/schedule/run", json=request)
    assert response.status_code == 200, response.text
    assert response.json()["assignments"]


def test_legacy_config_with_large_trial_count_loads_without_losing_staff(client):
    from backend.auth_db import save_config
    owner = client.get("/api/auth/me").json()["sub"]
    legacy = {
        "clinic": {"name": "Legacy Clinic", "timezone": "America/Chicago"},
        "schedule": {"start": "2026-10-19", "weeks": 1},
        "ratios": {"patients_per_tech": 4, "patients_per_rn": 12, "techs_per_rn": 4},
        "constraints": {}, "bleach": {"day": "Thu", "rotation": [], "cursor": 0},
        "tournament": {"trials": 1000, "last_seed": 0}, "export_roles": ["Tech"],
        "staff": [{"id": "legacy-tech", "name": "Existing Tech", "role": "Tech",
                   "availability": {"Mon": False, "Tue": True}, "pref_open_mwf": 2}],
        "demand": [], "pto": [],
    }
    save_config(owner, "legacy-trials.json", legacy)
    loaded = client.get("/api/configs/legacy-trials.json")
    assert loaded.status_code == 200, loaded.text
    assert loaded.json()["tournament"]["trials"] == 1000
    assert loaded.json()["staff"] == legacy["staff"]
    # Round-tripping a saved setup must not silently rewrite preferences/trials.
    assert client.post("/api/configs/save", json={"filename": "legacy-trials.json", "payload": loaded.json()}).status_code == 200
    assert client.get("/api/configs/legacy-trials.json").json()["staff"] == legacy["staff"]


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


def test_reused_username_cannot_inherit_legacy_schedules(client, migration_store):
    other, username, _ = invite(client)
    from backend.auth_db import save_schedule
    init_db = migration_store.init_db
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


def test_upgrade_keeps_existing_published_roster_and_backfills_history_once(client, migration_store):
    other, username, _ = invite(client)
    from backend.auth_db import save_schedule
    init_db = migration_store.init_db
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
