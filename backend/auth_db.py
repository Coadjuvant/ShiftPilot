from __future__ import annotations

"""
Auth storage layer with two backends:
- Postgres (recommended for production): set AUTH_BACKEND=postgres and DATABASE_URL
- JSON file (fallback/dev): default if DATABASE_URL is missing
"""

import json
import os
import secrets
import base64
import hashlib
import uuid
from datetime import datetime, timedelta, timezone
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
    salt = secrets.token_bytes(16)
    n = 2**14
    r = 8
    p = 1
    dk = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=n, r=r, p=p, dklen=32)
    salt_b64 = base64.urlsafe_b64encode(salt).decode("ascii").rstrip("=")
    dk_b64 = base64.urlsafe_b64encode(dk).decode("ascii").rstrip("=")
    return f"scrypt${n}${r}${p}${salt_b64}${dk_b64}"


def _is_legacy_hash(stored: str) -> bool:
    return not stored.startswith("scrypt$")


def _check_password(password: str, stored: str) -> bool:
    if stored.startswith("scrypt$"):
        try:
            _, n_str, r_str, p_str, salt_b64, dk_b64 = stored.split("$", 5)
            n = int(n_str)
            r = int(r_str)
            p = int(p_str)
            salt = base64.urlsafe_b64decode(salt_b64 + "==")
            expected = base64.urlsafe_b64decode(dk_b64 + "==")
        except Exception:
            return False
        calc = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=n, r=r, p=p, dklen=len(expected))
        return secrets.compare_digest(calc, expected)
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
                location TEXT,
                created_at TIMESTAMPTZ,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
            );
            """
        )
        cur.execute("ALTER TABLE audit_log ADD COLUMN IF NOT EXISTS location TEXT;")
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS configs (
                id SERIAL PRIMARY KEY,
                owner TEXT NOT NULL,
                filename TEXT NOT NULL,
                payload JSONB NOT NULL,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW(),
                UNIQUE(owner, filename)
            );
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS schedules (
                id SERIAL PRIMARY KEY,
                owner TEXT NOT NULL UNIQUE,
                clinic_name TEXT,
                start_date DATE,
                weeks INTEGER,
                payload JSONB NOT NULL,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
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
            "SELECT id, username, status, license_key, role, created_at, last_login, invite_expires_at, invite_created_by, last_invite_token, public_id, invite_token FROM users ORDER BY id"
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
            "invite_token",
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

    # --- schedules (latest per owner) ---
    def save_schedule(self, owner: str, payload: Dict[str, Any]) -> None:
        conn = self._conn()
        cur = conn.cursor()
        serial = json.dumps(payload, default=str)
        cur.execute(
            """
            INSERT INTO schedules (owner, clinic_name, start_date, weeks, payload, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, NOW(), NOW())
            ON CONFLICT (owner) DO UPDATE SET
                clinic_name = EXCLUDED.clinic_name,
                start_date = EXCLUDED.start_date,
                weeks = EXCLUDED.weeks,
                payload = EXCLUDED.payload,
                updated_at = NOW();
            """,
            (
                owner,
                payload.get("clinic_name"),
                payload.get("start_date"),
                payload.get("weeks"),
                serial,
            ),
        )
        conn.commit()
        conn.close()

    def get_latest_schedule(self, owner: str) -> Optional[Dict[str, Any]]:
        conn = self._conn()
        cur = conn.cursor()
        cur.execute("SELECT payload FROM schedules WHERE owner=%s", (owner,))
        row = cur.fetchone()
        conn.close()
        if not row:
            return None
        try:
            return row[0] if isinstance(row[0], dict) else json.loads(row[0])
        except Exception:
            return None

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
        if _is_legacy_hash(user["password_hash"]):
            user["password_hash"] = _hash_password(password)
            self._update_user(user)
        return user

    def create_invite(self, username: str, license_key: str, role: str = "user", created_by: Optional[int] = None, ttl_hours: int = 24) -> str:
        token = secrets.token_hex(16)
        expires_at = datetime.utcnow() + timedelta(hours=ttl_hours)
        conn = self._conn()
        cur = conn.cursor()
        desired_user = username.strip() or f"user-{token[:8]}"
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
            (desired_user, license_key.strip(), token, role, datetime.utcnow(), str(uuid.uuid4())),
        )
        # set expiry and creator
        cur.execute(
            "UPDATE users SET invite_expires_at=%s, invite_created_by=%s, public_id=COALESCE(public_id, %s) WHERE username=%s",
            (expires_at, created_by, str(uuid.uuid4()), desired_user),
        )
        conn.commit()
        conn.close()
        return token

    def redeem_invite(self, invite_token: str, password: str, desired_username: Optional[str] = None) -> Optional[Dict[str, Any]]:
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
        if expires_at:
            now = datetime.now(timezone.utc)
            exp = expires_at if expires_at.tzinfo else expires_at.replace(tzinfo=timezone.utc)
            exp = exp.astimezone(timezone.utc)
            if now > exp:
                conn.close()
                return None
        # allow username change on redeem if requested and unique
        if desired_username and desired_username.strip() and desired_username.strip() != username:
            desired = desired_username.strip()
            cur.execute("SELECT 1 FROM users WHERE username=%s", (desired,))
            if cur.fetchone():
                conn.close()
                raise ValueError("Username already exists")
            username = desired
            cur.execute("UPDATE users SET username=%s WHERE id=%s", (username, user_id))
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

    def log_event(
        self,
        user_id: Optional[int],
        event: str,
        detail: str,
        ip: str = "",
        user_agent: str = "",
        location: str = "",
    ):
        conn = self._conn()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO audit_log (user_id, event, detail, ip, user_agent, location, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (user_id, event, detail, ip, user_agent, location, datetime.utcnow()),
        )
        conn.commit()
        conn.close()

    def list_audit(
        self,
        limit: int = 50,
        event: Optional[str] = None,
        user_id: Optional[int] = None,
        search: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        conn = self._conn()
        cur = conn.cursor()
        query = "SELECT id, user_id, event, detail, ip, user_agent, location, created_at FROM audit_log"
        clauses = []
        params: list = []
        if event:
            clauses.append("event = %s")
            params.append(event)
        if user_id is not None:
            clauses.append("user_id = %s")
            params.append(user_id)
        if search:
            clauses.append(
                "(event ILIKE %s OR detail ILIKE %s OR ip ILIKE %s OR user_agent ILIKE %s OR location ILIKE %s)"
            )
            term = f"%{search}%"
            params.extend([term, term, term, term, term])
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY id DESC LIMIT %s"
        params.append(limit)
        cur.execute(query, tuple(params))
        rows = cur.fetchall()
        conn.close()
        keys = ["id", "user_id", "event", "detail", "ip", "user_agent", "location", "created_at"]
        return [dict(zip(keys, r)) for r in rows]

    # --- configs ---
    def list_configs(self, owner: str) -> List[str]:
        conn = self._conn()
        cur = conn.cursor()
        cur.execute("SELECT filename FROM configs WHERE owner=%s ORDER BY filename", (owner,))
        rows = cur.fetchall()
        conn.close()
        return [r[0] for r in rows]

    def load_config(self, owner: str, filename: str) -> Optional[dict]:
        conn = self._conn()
        cur = conn.cursor()
        cur.execute("SELECT payload FROM configs WHERE owner=%s AND filename=%s", (owner, filename))
        row = cur.fetchone()
        conn.close()
        if not row:
            return None
        return row[0]

    def save_config(self, owner: str, filename: str, payload: dict):
        conn = self._conn()
        cur = conn.cursor()
        # Ensure all values are JSON-serializable (e.g., date -> ISO string)
        payload_json = json.dumps(payload, default=str)
        cur.execute(
            """
            INSERT INTO configs (owner, filename, payload, created_at, updated_at)
            VALUES (%s, %s, %s::jsonb, NOW(), NOW())
            ON CONFLICT (owner, filename)
            DO UPDATE SET payload=EXCLUDED.payload, updated_at=NOW();
            """,
            (owner, filename, payload_json),
        )
        conn.commit()
        conn.close()

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
        if _is_legacy_hash(user["password_hash"]):
            pwd_hash = _hash_password(password)
            conn = self._conn()
            cur = conn.cursor()
            cur.execute("UPDATE users SET password_hash=%s WHERE id=%s", (pwd_hash, user["id"]))
            conn.commit()
            conn.close()
            user["password_hash"] = pwd_hash
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
        desired_user = username.strip() or f"user-{token[:8]}"
        existing = next((u for u in users if u.get("username") == desired_user), None)
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
                    "username": desired_user,
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

    def redeem_invite(self, invite_token: str, password: str, desired_username: Optional[str] = None) -> Optional[Dict[str, Any]]:
        data = _load_json()
        users = data.get("users", [])
        target = next((u for u in users if u.get("invite_token") == invite_token), None)
        if not target:
            return None
        expires = target.get("invite_expires_at")
        if expires:
            try:
                exp_dt = datetime.fromisoformat(expires)
                if exp_dt.tzinfo is None:
                    exp_dt = exp_dt.replace(tzinfo=timezone.utc)
                exp_dt = exp_dt.astimezone(timezone.utc)
                if datetime.now(timezone.utc) > exp_dt:
                    return None
            except Exception:
                return None
        # allow username change if requested and unique
        if desired_username and desired_username.strip() and desired_username.strip() != target.get("username"):
            desired = desired_username.strip()
            if any(u.get("username") == desired for u in users):
                raise ValueError("Username already exists")
            target["username"] = desired
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

    def log_event(
        self,
        user_id: Optional[int],
        event: str,
        detail: str,
        ip: str = "",
        user_agent: str = "",
        location: str = "",
    ):
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
                "location": location,
                "created_at": _now(),
            }
        )
        data["audit"] = audit
        _save_json(data)

    def list_audit(
        self,
        limit: int = 50,
        event: Optional[str] = None,
        user_id: Optional[int] = None,
        search: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        data = _load_json()
        audit = data.get("audit", [])
        entries = list(reversed(audit))
        if event:
            entries = [row for row in entries if row.get("event") == event]
        if user_id is not None:
            entries = [row for row in entries if row.get("user_id") == user_id]
        if search:
            term = search.lower()
            entries = [
                row
                for row in entries
                if term in (row.get("event") or "").lower()
                or term in (row.get("detail") or "").lower()
                or term in (row.get("ip") or "").lower()
                or term in (row.get("user_agent") or "").lower()
                or term in (row.get("location") or "").lower()
            ]
        return entries[:limit]

    # --- configs ---
    def list_configs(self, owner: str) -> List[str]:
        data = _load_json()
        cfgs = data.get("configs", [])
        return sorted([c.get("filename") for c in cfgs if c.get("owner") == owner])

    def load_config(self, owner: str, filename: str) -> Optional[dict]:
        data = _load_json()
        cfgs = data.get("configs", [])
        for c in cfgs:
            if c.get("owner") == owner and c.get("filename") == filename:
                return c.get("payload")
        return None

    def save_config(self, owner: str, filename: str, payload: dict):
        # Ensure serializable payload (e.g., date -> ISO string)
        payload = json.loads(json.dumps(payload, default=str))
        data = _load_json()
        cfgs = data.get("configs", [])
        updated = False
        for c in cfgs:
            if c.get("owner") == owner and c.get("filename") == filename:
                c["payload"] = payload
                updated = True
                break
        if not updated:
            cfgs.append({"owner": owner, "filename": filename, "payload": payload})
        data["configs"] = cfgs
        _save_json(data)

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

    # --- schedules (latest per owner) ---
    def save_schedule(self, owner: str, payload: Dict[str, Any]) -> None:
        data = _load_json()
        schedules = data.get("schedules", {})
        safe_payload = json.loads(json.dumps(payload, default=str))
        schedules[owner] = {"payload": safe_payload, "updated_at": _now()}
        data["schedules"] = schedules
        _save_json(data)

    def get_latest_schedule(self, owner: str) -> Optional[Dict[str, Any]]:
        data = _load_json()
        schedules = data.get("schedules", {})
        entry = schedules.get(owner)
        if not entry:
            return None
        payload = entry.get("payload")
        return payload if isinstance(payload, dict) else None

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
    return _backend.create_invite(username or "", license_key, role, created_by=created_by, ttl_hours=ttl_hours)


def redeem_invite(invite_token: str, password: str, desired_username: Optional[str] = None) -> Optional[Dict[str, Any]]:
    return _backend.redeem_invite(invite_token, password, desired_username=desired_username)


def update_last_login(user_id: int):
    return _backend.update_last_login(user_id)


def log_event(
    user_id: Optional[int],
    event: str,
    detail: str,
    ip: str = "",
    user_agent: str = "",
    location: str = "",
):
    return _backend.log_event(user_id, event, detail, ip, user_agent, location)


def list_users() -> List[Dict[str, Any]]:
    return _backend.list_users()


def delete_user(user_id: int):
    return _backend.delete_user(user_id)


def revoke_invite(username: str):
    return _backend.revoke_invite(username)


def list_audit(
    limit: int = 50,
    event: Optional[str] = None,
    user_id: Optional[int] = None,
    search: Optional[str] = None,
) -> List[Dict[str, Any]]:
    return _backend.list_audit(limit=limit, event=event, user_id=user_id, search=search)


def update_role(user_id: int, role: str):
    return _backend.update_role(user_id, role)


def reset_invite(user_id: int, created_by: Optional[int] = None, ttl_hours: int = 24) -> str:
    return _backend.reset_invite(user_id, created_by=created_by, ttl_hours=ttl_hours)


# Config helpers
def list_configs(owner: str) -> List[str]:
    return _backend.list_configs(owner)


def load_config(owner: str, filename: str) -> Optional[dict]:
    return _backend.load_config(owner, filename)


def save_config(owner: str, filename: str, payload: dict):
    return _backend.save_config(owner, filename, payload)


# Schedule helpers (latest per owner)
def save_schedule(owner: str, payload: dict):
    return _backend.save_schedule(owner, payload)


def get_latest_schedule(owner: str) -> Optional[dict]:
    return _backend.get_latest_schedule(owner)


# Config import/export helpers
def export_config(owner: str, filename: str) -> Optional[dict]:
    return _backend.load_config(owner, filename)


def import_config(owner: str, filename: str, payload: dict):
    return _backend.save_config(owner, filename, payload)
