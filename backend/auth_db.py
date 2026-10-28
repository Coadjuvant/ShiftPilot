from __future__ import annotations

"""
Auth storage layer.

Production and local preview use Postgres auth/config/schedule storage.
"""

import json
import os
import secrets
import base64
import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List

# Config
AUTH_BACKEND = os.getenv("AUTH_BACKEND", "postgres").lower()
DATABASE_URL = os.getenv("DATABASE_URL")


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
# Postgres backend helpers
# -----------------------
class PostgresAuth:
    def __init__(self, dsn: str):
        import psycopg2  # type: ignore

        self.dsn = dsn
        self.psycopg2 = psycopg2

    def _conn(self):
        return self.psycopg2.connect(self.dsn)

    def check_runtime_database(self):
        """Check an already migrated schema without DDL or bootstrap writes."""
        conn = self._conn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls "
                            "FROM pg_roles WHERE rolname=current_user")
                if any(cur.fetchone()):
                    raise RuntimeError("Runtime database role has administrative privileges.")
                cur.execute("SELECT has_schema_privilege(current_user,current_schema(),'CREATE')")
                if cur.fetchone()[0]:
                    raise RuntimeError("Runtime database role must not create schema objects.")
                cur.execute("SELECT EXISTS (SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
                            "WHERE n.nspname=current_schema() AND c.relowner=(SELECT oid FROM pg_roles WHERE rolname=current_user)) "
                            "OR EXISTS (SELECT 1 FROM pg_auth_members WHERE member=(SELECT oid FROM pg_roles WHERE rolname=current_user))")
                if cur.fetchone()[0]:
                    raise RuntimeError("Runtime database role must not own schema objects or inherit other roles.")
                for query in (
                    "SELECT id,username,password_hash,status,license_key,role,public_id,invite_token,invite_expires_at,invite_created_by,last_invite_token,created_at,last_login FROM users LIMIT 0",
                    "SELECT id,user_id,expires_at FROM auth_sessions LIMIT 0",
                    "SELECT id,user_id,event,detail,ip,ip_v4,user_agent,location,created_at FROM audit_log LIMIT 0",
                    "SELECT owner,filename,payload,created_at,updated_at FROM configs LIMIT 0",
                    "SELECT owner,payload,created_at,updated_at FROM schedules LIMIT 0",
                    "SELECT id,owner,payload,state,created_at,published_at FROM schedule_versions LIMIT 0",
                    "SELECT owner,user_id FROM legacy_schedule_owners LIMIT 0",
                ):
                    cur.execute(query)
        finally:
            conn.close()

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
            CREATE TABLE IF NOT EXISTS auth_sessions (
                id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                expires_at TIMESTAMPTZ NOT NULL
            );
            CREATE INDEX IF NOT EXISTS auth_sessions_user_idx ON auth_sessions(user_id);
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_log (
                id SERIAL PRIMARY KEY,
                user_id INTEGER,
                event TEXT,
                detail TEXT,
                ip TEXT,
                ip_v4 TEXT,
                user_agent TEXT,
                location TEXT,
                created_at TIMESTAMPTZ,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
            );
            """
        )
        cur.execute("ALTER TABLE audit_log ADD COLUMN IF NOT EXISTS location TEXT;")
        cur.execute("ALTER TABLE audit_log ADD COLUMN IF NOT EXISTS ip_v4 TEXT;")
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
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS schedule_versions (
                id TEXT PRIMARY KEY,
                owner TEXT NOT NULL,
                payload JSONB NOT NULL,
                state TEXT NOT NULL DEFAULT 'draft' CHECK (state IN ('draft', 'published')),
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                published_at TIMESTAMPTZ
            );
            CREATE INDEX IF NOT EXISTS schedule_versions_owner_idx ON schedule_versions(owner, created_at DESC);
            INSERT INTO schedule_versions (id, owner, payload, state, created_at, published_at)
            SELECT 'legacy-' || id, owner, payload, 'published', COALESCE(created_at, NOW()), COALESCE(updated_at, NOW())
            FROM schedules WHERE NOT (payload ? 'version_id') ON CONFLICT (id) DO NOTHING;
            CREATE TABLE IF NOT EXISTS legacy_schedule_owners (
                owner TEXT PRIMARY KEY,
                user_id INTEGER REFERENCES users(id) ON DELETE SET NULL
            );
            INSERT INTO legacy_schedule_owners (owner, user_id)
            SELECT DISTINCT u.username, u.id FROM users u JOIN schedules s ON s.owner=u.username
            WHERE u.username !~ '^[0-9]+$' ON CONFLICT(owner) DO NOTHING;
            """
        )
        conn.commit()
        conn.close()

    # --- admin helpers ---
    def list_users(self) -> List[Dict[str, Any]]:
        conn = self._conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT id, username, status, license_key, role, created_at, last_login, invite_expires_at, invite_created_by, public_id FROM users ORDER BY id"
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
            "public_id",
        ]
        admin_user = (os.getenv("ADMIN_USER", "admin") or "admin").strip()
        return [{**dict(zip(keys, r)), "is_bootstrap_admin": r[1] == admin_user} for r in rows]

    def create_session(self, session_id: str, user_id: int, expires_at: datetime):
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM auth_sessions WHERE expires_at <= NOW()")
                cur.execute(
                    "INSERT INTO auth_sessions (id, user_id, expires_at) VALUES (%s, %s, %s)",
                    (session_id, user_id, expires_at),
                )
        conn.close()

    def get_session_user(self, session_id: str, user_id: str) -> Optional[dict]:
        # JWT claims alone must not preserve disabled accounts or old roles.
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT u.id, u.username, u.role FROM auth_sessions s
                    JOIN users u ON u.id=s.user_id
                    WHERE s.id=%s AND u.id::text=%s AND s.expires_at > NOW() AND u.status='active'""",
                    (session_id, user_id),
                )
                row = cur.fetchone()
        conn.close()
        return dict(zip(("id", "username", "role"), row)) if row else None

    def revoke_session(self, session_id: str):
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM auth_sessions WHERE id=%s", (session_id,))
        conn.close()

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
        cur.execute("DELETE FROM users WHERE id=%s", (user_id,))
        conn.commit()
        conn.close()

    def revoke_invite(self, username: str):
        admin_user = (os.getenv("ADMIN_USER", "admin") or "admin").strip()
        if username.strip() == admin_user:
            raise ValueError("Cannot disable the bootstrap admin")
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
        expires_at = datetime.now(timezone.utc) + timedelta(hours=ttl_hours)
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

    def get_invite_context(self, invite_token: str) -> Optional[Dict[str, Any]]:
        conn = self._conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT username, status, password_hash, invite_expires_at FROM users WHERE invite_token=%s",
            (invite_token.strip(),),
        )
        row = cur.fetchone()
        conn.close()
        if not row:
            return None
        username, status, password_hash, expires_at = row
        if expires_at:
            now = datetime.now(timezone.utc)
            exp = expires_at if expires_at.tzinfo else expires_at.replace(tzinfo=timezone.utc)
            if now > exp.astimezone(timezone.utc):
                return None
        token_type = "reset" if password_hash or status == "active" else "invite"
        return {"username": username, "type": token_type}

    # --- schedules (latest per owner) ---
    def legacy_schedule_owners(self, user_id: str) -> List[str]:
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT owner FROM legacy_schedule_owners WHERE user_id::text=%s", (user_id,))
                owners = [row[0] for row in cur.fetchall()]
        conn.close()
        return owners

    def save_schedule_draft(self, owner: str, payload: Dict[str, Any]) -> str:
        version_id = uuid.uuid4().hex
        payload = {**payload, "version_id": version_id, "schedule_status": "draft"}
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO schedule_versions (id, owner, payload) VALUES (%s,%s,%s::jsonb)",
                            (version_id, owner, json.dumps(payload, default=str)))
        conn.close()
        return version_id

    def list_schedule_versions(self, owners: List[str]) -> list[dict]:
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT id, state, created_at, published_at, payload->>'clinic_name', payload->>'start_date',
                    payload->>'weeks' FROM schedule_versions WHERE owner=ANY(%s) ORDER BY created_at DESC, id DESC LIMIT 50""",
                    (owners,),
                )
                rows = cur.fetchall()
        conn.close()
        return [dict(zip(("id", "state", "created_at", "published_at", "clinic_name", "start_date", "weeks"), row)) for row in rows]

    def get_schedule_version(self, owners: List[str], version_id: str) -> Optional[dict]:
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT payload, state FROM schedule_versions WHERE owner=ANY(%s) AND id=%s", (owners, version_id))
                row = cur.fetchone()
        conn.close()
        return {**row[0], "version_id": version_id, "schedule_status": row[1]} if row else None

    def delete_schedule_draft(self, owners: List[str], version_id: str) -> str:
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT state FROM schedule_versions WHERE owner=ANY(%s) AND id=%s FOR UPDATE", (owners, version_id))
                row = cur.fetchone()
                if not row:
                    result = "missing"
                elif row[0] != "draft":
                    result = "published"
                else:
                    cur.execute("DELETE FROM schedule_versions WHERE id=%s", (version_id,))
                    result = "deleted"
        conn.close()
        return result

    def publish_schedule_version(self, owner: str, owners: List[str], version_id: str) -> Optional[dict]:
        with self._conn() as conn:
            with conn.cursor() as cur:
                # Serialize publishing per owner, including concurrent requests for different drafts.
                cur.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (owner,))
                cur.execute("SELECT payload FROM schedule_versions WHERE owner=ANY(%s) AND id=%s FOR UPDATE", (owners, version_id))
                row = cur.fetchone()
                if row:
                    payload = {**row[0], "version_id": version_id, "schedule_status": "published"}
                    serial = json.dumps(payload, default=str)
                    cur.execute("UPDATE schedule_versions SET state='published', published_at=NOW(), payload=%s::jsonb WHERE id=%s", (serial, version_id))
                    cur.execute(
                        """INSERT INTO schedules (owner,clinic_name,start_date,weeks,payload) VALUES (%s,%s,%s,%s,%s::jsonb)
                        ON CONFLICT(owner) DO UPDATE SET clinic_name=EXCLUDED.clinic_name, start_date=EXCLUDED.start_date,
                        weeks=EXCLUDED.weeks, payload=EXCLUDED.payload, updated_at=NOW()""",
                        (owner, payload.get("clinic_name"), payload.get("start_date"), payload.get("weeks"), serial),
                    )
        conn.close()
        return payload if row else None

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
        if role not in {"user", "admin"}:
            raise ValueError("Role must be user or admin")
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
        now = datetime.now(timezone.utc)
        cur.execute(
            """
            INSERT INTO users (username, password_hash, status, license_key, role, created_at, public_id)
            VALUES (%s, %s, 'active', %s, 'admin', %s, %s)
            ON CONFLICT (username)
            DO NOTHING;
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
        expires_at = datetime.now(timezone.utc) + timedelta(hours=ttl_hours)
        conn = self._conn()
        cur = conn.cursor()
        desired_user = username.strip() or f"user-{token[:8]}"
        cur.execute("SELECT status FROM users WHERE username=%s", (desired_user,))
        existing = cur.fetchone()
        if existing and existing[0] == "active":
            conn.close()
            raise ValueError("This account already exists. Use password reset instead.")
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
            (desired_user, license_key.strip(), token, role, datetime.now(timezone.utc), str(uuid.uuid4())),
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
        try:
            with conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT id, username, status, password_hash FROM users "
                        "WHERE invite_token=%s AND (invite_expires_at IS NULL OR invite_expires_at > clock_timestamp())",
                        (invite_token,),
                    )
                    row = cur.fetchone()
                    if not row:
                        return None
                    user_id, username, status, existing_hash = row
                    is_reset = bool(existing_hash) or status == "active"
                    if not is_reset and desired_username and desired_username.strip():
                        username = desired_username.strip()
                    pwd_hash = _hash_password(password)
                    # Recheck while acquiring the update lock: only one concurrent caller
                    # can consume this token, including if it expires/revokes during hashing.
                    cur.execute(
                        "UPDATE users SET username=%s, password_hash=%s, status='active', "
                        "last_invite_token=NULL, invite_token=NULL, invite_expires_at=NULL "
                        "WHERE id=%s AND invite_token=%s "
                        "AND (invite_expires_at IS NULL OR invite_expires_at > clock_timestamp()) "
                        "RETURNING id, username, password_hash, status, license_key, invite_token, "
                        "invite_expires_at, invite_created_by, last_invite_token, public_id, role, created_at, last_login",
                        (username, pwd_hash, user_id, invite_token),
                    )
                    updated = cur.fetchone()
                    if not updated:
                        return None
                    cur.execute("DELETE FROM auth_sessions WHERE user_id=%s", (user_id,))
        except self.psycopg2.errors.UniqueViolation as exc:
            raise ValueError("Username already exists") from exc
        finally:
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
        cur.execute("UPDATE users SET last_login=%s WHERE id=%s", (datetime.now(timezone.utc), user_id))
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
        ip_v4: str = "",
    ):
        conn = self._conn()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO audit_log (user_id, event, detail, ip, ip_v4, user_agent, location, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (user_id, event, detail, ip, ip_v4, user_agent, location, datetime.now(timezone.utc)),
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
        query = "SELECT id, user_id, event, detail, ip, ip_v4, user_agent, location, created_at FROM audit_log"
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
                "(event ILIKE %s OR detail ILIKE %s OR ip ILIKE %s OR ip_v4 ILIKE %s OR user_agent ILIKE %s OR location ILIKE %s)"
            )
            term = f"%{search}%"
            params.extend([term, term, term, term, term, term])
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY id DESC LIMIT %s"
        params.append(limit)
        cur.execute(query, tuple(params))
        rows = cur.fetchall()
        conn.close()
        keys = ["id", "user_id", "event", "detail", "ip", "ip_v4", "user_agent", "location", "created_at"]
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

    def delete_config(self, owner: str, filename: str):
        conn = self._conn()
        cur = conn.cursor()
        cur.execute("DELETE FROM configs WHERE owner=%s AND filename=%s", (owner, filename))
        conn.commit()
        conn.close()

# -----------------------
# Backend selector
# -----------------------
if AUTH_BACKEND != "postgres":
    raise RuntimeError("AUTH_BACKEND must be 'postgres'. JSON auth backend is disabled.")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is required when AUTH_BACKEND=postgres.")

try:
    _backend = PostgresAuth(DATABASE_URL)
except Exception as exc:
    raise RuntimeError("Failed to initialize Postgres auth backend.") from exc


def init_db():
    _backend.init_db()


def create_session(session_id: str, user_id: int, expires_at: datetime):
    return _backend.create_session(session_id, user_id, expires_at)


def get_session_user(session_id: str, user_id: str) -> Optional[dict]:
    return _backend.get_session_user(session_id, user_id)


def revoke_session(session_id: str):
    return _backend.revoke_session(session_id)


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
    ip_v4: str = "",
):
    return _backend.log_event(user_id, event, detail, ip, user_agent, location, ip_v4)


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


def get_invite_context(invite_token: str) -> Optional[Dict[str, Any]]:
    return _backend.get_invite_context(invite_token)


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


def save_schedule_draft(owner: str, payload: dict) -> str:
    return _backend.save_schedule_draft(owner, payload)


def legacy_schedule_owners(user_id: str) -> List[str]:
    return _backend.legacy_schedule_owners(user_id)


def list_schedule_versions(owners: List[str]) -> list[dict]:
    return _backend.list_schedule_versions(owners)


def get_schedule_version(owners: List[str], version_id: str) -> Optional[dict]:
    return _backend.get_schedule_version(owners, version_id)


def publish_schedule_version(owner: str, owners: List[str], version_id: str) -> Optional[dict]:
    return _backend.publish_schedule_version(owner, owners, version_id)


def delete_schedule_draft(owners: List[str], version_id: str) -> str:
    return _backend.delete_schedule_draft(owners, version_id)


# Config import/export helpers
def export_config(owner: str, filename: str) -> Optional[dict]:
    return _backend.load_config(owner, filename)


def import_config(owner: str, filename: str, payload: dict):
    return _backend.save_config(owner, filename, payload)


def delete_config(owner: str, filename: str):
    return _backend.delete_config(owner, filename)
