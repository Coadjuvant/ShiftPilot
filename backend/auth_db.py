from __future__ import annotations

"""
Auth storage layer with two backends:
- Postgres (recommended for production): set AUTH_BACKEND=postgres and DATABASE_URL
- JSON file (fallback/dev): default if DATABASE_URL is missing
"""

import json
import os
import secrets
import hashlib
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any, List

# Config
AUTH_BACKEND = os.getenv("AUTH_BACKEND", "json").lower()
DATABASE_URL = os.getenv("DATABASE_URL")

# JSON defaults
DEFAULT_STORE = Path(__file__).resolve().parent.parent / "auth_store.json"
STORE_PATH = Path(os.getenv("AUTH_STORE_PATH", str(DEFAULT_STORE)))


def _now() -> str:
    return datetime.utcnow().isoformat()


def _hash_password(password: str) -> str:
    salt = secrets.token_hex(8)
    h = hashlib.sha256((salt + password).encode("utf-8")).hexdigest()
    return f"{salt}${h}"


def _check_password(password: str, stored: str) -> bool:
    try:
        salt, h = stored.split("$", 1)
    except ValueError:
        return False
    calc = hashlib.sha256((salt + password).encode("utf-8")).hexdigest()
    return secrets.compare_digest(calc, h)


# -----------------------
# JSON backend helpers
# -----------------------
def _load_json() -> Dict[str, Any]:
    if not STORE_PATH.exists():
        return {"users": [], "audit": []}
    try:
        return json.loads(STORE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"users": [], "audit": []}


def _save_json(data: Dict[str, Any]) -> None:
    STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = STORE_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    tmp.replace(STORE_PATH)


def _next_user_id(users: List[Dict[str, Any]]) -> int:
    return (max((u.get("id", 0) for u in users), default=0) or 0) + 1


# -----------------------
# Postgres backend helpers
# -----------------------
class PostgresAuth:
    def __init__(self, dsn: str):
        import psycopg2  # type: ignore

        self.dsn = dsn
        self.psycopg2 = psycopg2

    def _conn(self):
        return self.psycopg2.connect(self.dsn)

    def init_db(self):
        conn = self._conn()
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                license_key TEXT,
                invite_token TEXT,
                invite_expires_at TIMESTAMPTZ,
                invite_created_by INTEGER,
                last_invite_token TEXT,
                public_id TEXT UNIQUE,
                role TEXT NOT NULL DEFAULT 'user',
                created_at TIMESTAMPTZ,
                last_login TIMESTAMPTZ
            );
            """
        )
        # migrations for older tables
        cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS last_invite_token TEXT;")
        cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS invite_expires_at TIMESTAMPTZ;")
        cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS invite_created_by INTEGER;")
        cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS public_id TEXT UNIQUE;")
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_log (
                id SERIAL PRIMARY KEY,
                user_id INTEGER,
                event TEXT,
                detail TEXT,
                ip TEXT,
                user_agent TEXT,
                created_at TIMESTAMPTZ,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
            );
            """
        )
        conn.commit()
        conn.close()

    # --- admin helpers ---
    def list_users(self) -> List[Dict[str, Any]]:
        conn = self._conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT id, username, status, license_key, role, created_at, last_login, invite_expires_at, invite_created_by, last_invite_token, public_id FROM users ORDER BY id"
        )
        rows = cur.fetchall()
        conn.close()
        keys = [
            "id",
            "username",
            "status",
            "license_key",
            "role",
            "created_at",
            "last_login",
            "invite_expires_at",
            "invite_created_by",
            "last_invite_token",
            "public_id",
        ]
        return [dict(zip(keys, r)) for r in rows]

    def delete_user(self, user_id: int):
        # protect default admin
        admin_user = (os.getenv("ADMIN_USER", "admin") or "admin").strip()
        conn = self._conn()
        cur = conn.cursor()
        cur.execute("SELECT username FROM users WHERE id=%s", (user_id,))
        row = cur.fetchone()
        if row and row[0] == admin_user:
            conn.close()
            raise ValueError("Cannot delete default admin user")
        conn = self._conn()
        cur = conn.cursor()
        cur.execute("DELETE FROM users WHERE id=%s", (user_id,))
        conn.commit()
        conn.close()

    def revoke_invite(self, username: str):
        conn = self._conn()
        cur = conn.cursor()
        cur.execute(
            "UPDATE users SET invite_token=NULL, invite_expires_at=NULL, status='disabled' WHERE username=%s",
            (username.strip(),),
        )
        conn.commit()
        conn.close()

    def reset_invite(self, user_id: int, created_by: Optional[int] = None, ttl_hours: int = 24) -> str:
        token = secrets.token_hex(16)
        expires_at = datetime.utcnow() + timedelta(hours=ttl_hours)
        conn = self._conn()
        cur = conn.cursor()
        cur.execute("SELECT username FROM users WHERE id=%s", (user_id,))
        row = cur.fetchone()
        if not row:
            conn.close()
            raise ValueError("User not found")
        cur.execute(
            "UPDATE users SET invite_token=%s, invite_expires_at=%s, invite_created_by=%s WHERE id=%s",
            (token, expires_at, created_by, user_id),
        )
        conn.commit()
        conn.close()
        return token

    def update_role(self, user_id: int, role: str):
        conn = self._conn()
        cur = conn.cursor()
        # protect default admin
        admin_user = (os.getenv("ADMIN_USER", "admin") or "admin").strip()
        cur.execute("SELECT username FROM users WHERE id=%s", (user_id,))
        row = cur.fetchone()
        if row and row[0] == admin_user and role.lower() != "admin":
            conn.close()
            raise ValueError("Cannot demote default admin user")
        cur.execute("UPDATE users SET role=%s WHERE id=%s", (role, user_id))
        conn.commit()
        conn.close()

    def ensure_admin(self, username: str, password: str, license_key: str = "DEMO"):
        conn = self._conn()
        cur = conn.cursor()
        pwd_hash = _hash_password(password)
        now = datetime.utcnow()
        cur.execute(
            """
            INSERT INTO users (username, password_hash, status, license_key, role, created_at, public_id)
            VALUES (%s, %s, 'active', %s, 'admin', %s, %s)
            ON CONFLICT (username)
            DO UPDATE SET password_hash = EXCLUDED.password_hash,
                          status = 'active',
                          license_key = EXCLUDED.license_key,
                          role = 'admin',
                          invite_token = NULL,
                          public_id = COALESCE(users.public_id, EXCLUDED.public_id);
            """,
            (username.strip(), pwd_hash, license_key.strip(), now, str(uuid.uuid4())),
        )
        conn.commit()
        conn.close()

    def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        conn = self._conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT id, username, password_hash, status, license_key, invite_token, invite_expires_at, invite_created_by, last_invite_token, public_id, role, created_at, last_login FROM users WHERE username=%s",
            (username.strip(),),
        )
        row = cur.fetchone()
        conn.close()
        if not row:
            return None
        keys = [
            "id",
            "username",
            "password_hash",
            "status",
            "license_key",
            "invite_token",
            "invite_expires_at",
            "invite_created_by",
            "last_invite_token",
            "public_id",
            "role",
            "created_at",
            "last_login",
        ]
        return dict(zip(keys, row))

    def validate_login(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        user = self.get_user_by_username(username)
        if not user or user.get("status") != "active":
            return None
        if not user.get("license_key"):
            user["license_key"] = "DEMO"
            conn = self._conn()
            cur = conn.cursor()
            cur.execute("UPDATE users SET license_key=%s WHERE id=%s", ("DEMO", user["id"]))
            conn.commit()
            conn.close()
        if not user.get("password_hash") or not _check_password(password, user["password_hash"]):
            return None
        return user

    def create_invite(self, username: str, license_key: str, role: str = "user", created_by: Optional[int] = None, ttl_hours: int = 24) -> str:
        token = secrets.token_hex(16)
        expires_at = datetime.utcnow() + timedelta(hours=ttl_hours)
        conn = self._conn()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO users (username, status, license_key, invite_token, role, created_at, public_id)
            VALUES (%s, 'pending', %s, %s, %s, %s, %s)
            ON CONFLICT (username)
            DO UPDATE SET status='pending',
                          license_key=EXCLUDED.license_key,
                          invite_token=EXCLUDED.invite_token,
                          role=EXCLUDED.role,
                          public_id=COALESCE(users.public_id, EXCLUDED.public_id);
            """,
            (username.strip(), license_key.strip(), token, role, datetime.utcnow(), str(uuid.uuid4())),
        )
        # set expiry and creator
        cur.execute(
            "UPDATE users SET invite_expires_at=%s, invite_created_by=%s, public_id=COALESCE(public_id, %s) WHERE username=%s",
            (expires_at, created_by, str(uuid.uuid4()), username.strip()),
        )
        conn.commit()
        conn.close()
        return token

    def redeem_invite(self, invite_token: str, password: str) -> Optional[Dict[str, Any]]:
        conn = self._conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT id, username, status, license_key, role, invite_token, invite_expires_at, invite_created_by, public_id FROM users WHERE invite_token=%s",
            (invite_token,),
        )
        row = cur.fetchone()
        if not row:
            conn.close()
            return None
        user_id, username, status, license_key, role, inv, expires_at, inv_created_by, public_id = row
        if expires_at and datetime.utcnow() > expires_at:
            conn.close()
            return None
        pwd_hash = _hash_password(password)
        cur.execute(
            "UPDATE users SET password_hash=%s, status='active', last_invite_token=%s, invite_token=NULL WHERE id=%s",
            (pwd_hash, inv, user_id),
        )
        conn.commit()
        cur.execute(
            "SELECT id, username, password_hash, status, license_key, invite_token, invite_expires_at, invite_created_by, last_invite_token, public_id, role, created_at, last_login FROM users WHERE id=%s",
            (user_id,),
        )
        updated = cur.fetchone()
        conn.close()
        keys = [
            "id",
            "username",
            "password_hash",
            "status",
            "license_key",
            "invite_token",
            "invite_expires_at",
            "invite_created_by",
            "last_invite_token",
            "public_id",
            "role",
            "created_at",
            "last_login",
        ]
        return dict(zip(keys, updated)) if updated else None

    def update_last_login(self, user_id: int):
        conn = self._conn()
        cur = conn.cursor()
        cur.execute("UPDATE users SET last_login=%s WHERE id=%s", (datetime.utcnow(), user_id))
        conn.commit()
        conn.close()

    def log_event(self, user_id: Optional[int], event: str, detail: str, ip: str = "", user_agent: str = ""):
        conn = self._conn()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO audit_log (user_id, event, detail, ip, user_agent, created_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (user_id, event, detail, ip, user_agent, datetime.utcnow()),
        )
        conn.commit()
        conn.close()

    def list_audit(self, limit: int = 50) -> List[Dict[str, Any]]:
        conn = self._conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT id, user_id, event, detail, ip, user_agent, created_at FROM audit_log ORDER BY id DESC LIMIT %s",
            (limit,),
        )
        rows = cur.fetchall()
        conn.close()
        keys = ["id", "user_id", "event", "detail", "ip", "user_agent", "created_at"]
        return [dict(zip(keys, r)) for r in rows]


# -----------------------
# JSON backend (fallback)
# -----------------------
class JsonAuth:
    def init_db(self):
        if not STORE_PATH.exists():
            _save_json({"users": [], "audit": []})

    def ensure_admin(self, username: str, password: str, license_key: str = "DEMO"):
        data = _load_json()
        users = data.get("users", [])
        existing = next((u for u in users if u.get("username") == username), None)
        pwd_hash = _hash_password(password)
        now = _now()
        if existing:
            existing.update(
                {
                    "password_hash": pwd_hash,
                    "status": "active",
                    "role": "admin",
                    "license_key": license_key,
                    "invite_token": None,
                    "last_invite_token": existing.get("last_invite_token"),
                    "public_id": existing.get("public_id") or str(uuid.uuid4()),
                }
            )
        else:
            users.append(
                {
                    "id": _next_user_id(users),
                    "username": username,
                    "password_hash": pwd_hash,
                    "status": "active",
                    "license_key": license_key,
                    "role": "admin",
                    "invite_token": None,
                    "last_invite_token": None,
                    "public_id": str(uuid.uuid4()),
                    "created_at": now,
                    "last_login": None,
                }
            )
        data["users"] = users
        _save_json(data)

    def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        data = _load_json()
        return next((u for u in data.get("users", []) if u.get("username") == username.strip()), None)

    def validate_login(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        user = self.get_user_by_username(username)
        if not user or user.get("status") != "active":
            return None
        if not user.get("license_key"):
            user["license_key"] = "DEMO"
            self._update_user(user)
        if not user.get("password_hash") or not _check_password(password, user["password_hash"]):
            return None
        return user

    def _update_user(self, user: Dict[str, Any]) -> None:
        data = _load_json()
        users = data.get("users", [])
        for idx, u in enumerate(users):
            if u.get("id") == user.get("id"):
                users[idx] = user
                break
        else:
            users.append(user)
        data["users"] = users
        _save_json(data)

    def create_invite(self, username: str, license_key: str, role: str = "user", created_by: Optional[int] = None, ttl_hours: int = 24) -> str:
        token = secrets.token_hex(16)
        now = _now()
        expires_at = datetime.utcnow() + timedelta(hours=ttl_hours)
        data = _load_json()
        users = data.get("users", [])
        existing = next((u for u in users if u.get("username") == username.strip()), None)
        if existing:
            existing.update(
                {
                    "status": "pending",
                    "license_key": license_key.strip(),
                    "invite_token": token,
                    "invite_expires_at": expires_at.isoformat(),
                    "invite_created_by": created_by,
                    "last_invite_token": existing.get("last_invite_token"),
                    "public_id": existing.get("public_id") or str(uuid.uuid4()),
                    "role": role,
                }
            )
        else:
            users.append(
                {
                    "id": _next_user_id(users),
                    "username": username.strip(),
                    "status": "pending",
                    "license_key": license_key.strip(),
                    "invite_token": token,
                    "invite_expires_at": expires_at.isoformat(),
                    "invite_created_by": created_by,
                    "last_invite_token": None,
                    "public_id": str(uuid.uuid4()),
                    "role": role,
                    "password_hash": None,
                    "created_at": now,
                    "last_login": None,
                }
            )
        data["users"] = users
        _save_json(data)
        return token

    def redeem_invite(self, invite_token: str, password: str) -> Optional[Dict[str, Any]]:
        data = _load_json()
        users = data.get("users", [])
        target = next((u for u in users if u.get("invite_token") == invite_token), None)
        if not target:
            return None
        expires = target.get("invite_expires_at")
        if expires:
            try:
                if datetime.utcnow() > datetime.fromisoformat(expires):
                    return None
            except Exception:
                return None
        target["password_hash"] = _hash_password(password)
        target["status"] = "active"
        target["last_invite_token"] = target.get("invite_token")
        target["invite_token"] = None
        self._update_user(target)
        return target

    def update_last_login(self, user_id: int):
        data = _load_json()
        users = data.get("users", [])
        for u in users:
            if u.get("id") == user_id:
                u["last_login"] = _now()
                break
        data["users"] = users
        _save_json(data)

    def log_event(self, user_id: Optional[int], event: str, detail: str, ip: str = "", user_agent: str = ""):
        data = _load_json()
        audit = data.get("audit", [])
        audit.append(
            {
                "id": (max((r.get("id", 0) for r in audit), default=0) or 0) + 1,
                "user_id": user_id,
                "event": event,
                "detail": detail,
                "ip": ip,
                "user_agent": user_agent,
                "created_at": _now(),
            }
        )
        data["audit"] = audit
        _save_json(data)

    def list_audit(self, limit: int = 50) -> List[Dict[str, Any]]:
        data = _load_json()
        audit = data.get("audit", [])
        return list(reversed(audit))[:limit]

    # --- admin helpers ---
    def list_users(self) -> List[Dict[str, Any]]:
        data = _load_json()
        return data.get("users", [])

    def delete_user(self, user_id: int):
        data = _load_json()
        admin_user = (os.getenv("ADMIN_USER", "admin") or "admin").strip()
        keep = []
        for u in data.get("users", []):
            if u.get("id") == user_id and u.get("username") == admin_user:
                raise ValueError("Cannot delete default admin user")
            if u.get("id") != user_id:
                keep.append(u)
        data["users"] = keep
        _save_json(data)

    def revoke_invite(self, username: str):
        data = _load_json()
        users = data.get("users", [])
        for u in users:
            if u.get("username") == username.strip():
                u["invite_token"] = None
                u["invite_expires_at"] = None
                u["status"] = "disabled"
        data["users"] = users
        _save_json(data)

    def reset_invite(self, user_id: int, created_by: Optional[int] = None, ttl_hours: int = 24) -> str:
        token = secrets.token_hex(16)
        expires_at = datetime.utcnow() + timedelta(hours=ttl_hours)
        data = _load_json()
        users = data.get("users", [])
        found = False
        for u in users:
            if u.get("id") == user_id:
                u["invite_token"] = token
                u["invite_expires_at"] = expires_at.isoformat()
                u["invite_created_by"] = created_by
                found = True
                break
        if not found:
            raise ValueError("User not found")
        data["users"] = users
        _save_json(data)
        return token

    def update_role(self, user_id: int, role: str):
        data = _load_json()
        admin_user = (os.getenv("ADMIN_USER", "admin") or "admin").strip()
        for u in data.get("users", []):
            if u.get("id") == user_id:
                if u.get("username") == admin_user and role.lower() != "admin":
                    raise ValueError("Cannot demote default admin user")
                u["role"] = role
        _save_json(data)

# -----------------------
# Backend selector
# -----------------------
if AUTH_BACKEND == "postgres" and DATABASE_URL:
    try:
        _backend = PostgresAuth(DATABASE_URL)
    except Exception:
        _backend = JsonAuth()
else:
    _backend = JsonAuth()


def init_db():
    _backend.init_db()


def ensure_admin(username: str, password: str, license_key: str = "DEMO"):
    _backend.ensure_admin(username, password, license_key)


def get_user_by_username(username: str) -> Optional[Dict[str, Any]]:
    return _backend.get_user_by_username(username)


def validate_login(username: str, password: str) -> Optional[Dict[str, Any]]:
    return _backend.validate_login(username, password)


def create_invite(
    username: str,
    license_key: str,
    role: str = "user",
    created_by: Optional[int] = None,
    ttl_hours: int = 24,
) -> str:
    return _backend.create_invite(username, license_key, role, created_by=created_by, ttl_hours=ttl_hours)


def redeem_invite(invite_token: str, password: str) -> Optional[Dict[str, Any]]:
    return _backend.redeem_invite(invite_token, password)


def update_last_login(user_id: int):
    return _backend.update_last_login(user_id)


def log_event(user_id: Optional[int], event: str, detail: str, ip: str = "", user_agent: str = ""):
    return _backend.log_event(user_id, event, detail, ip, user_agent)


def list_users() -> List[Dict[str, Any]]:
    return _backend.list_users()


def delete_user(user_id: int):
    return _backend.delete_user(user_id)


def revoke_invite(username: str):
    return _backend.revoke_invite(username)


def list_audit(limit: int = 50) -> List[Dict[str, Any]]:
    return _backend.list_audit(limit=limit)


def update_role(user_id: int, role: str):
    return _backend.update_role(user_id, role)


def reset_invite(user_id: int, created_by: Optional[int] = None, ttl_hours: int = 24) -> str:
    return _backend.reset_invite(user_id, created_by=created_by, ttl_hours=ttl_hours)
