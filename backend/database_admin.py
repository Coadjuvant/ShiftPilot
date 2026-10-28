"""Database maintenance operations; never imported by the HTTP application."""
from __future__ import annotations

from psycopg2 import sql
from psycopg2.extensions import encrypt_password
import psycopg2


RUNTIME_TABLE_PRIVILEGES = {
    "users": "SELECT, INSERT, UPDATE, DELETE",
    "auth_sessions": "SELECT, INSERT, UPDATE, DELETE",
    "audit_log": "SELECT, INSERT",
    "configs": "SELECT, INSERT, UPDATE, DELETE",
    "schedules": "SELECT, INSERT, UPDATE, DELETE",
    "schedule_versions": "SELECT, INSERT, UPDATE, DELETE",
    "legacy_schedule_owners": "SELECT",
}


def _grant_access(cur, username: str, schema: str) -> None:
    cur.execute("SELECT current_database()")
    database = cur.fetchone()[0]
    cur.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(sql.Identifier(database), sql.Identifier(username)))
    cur.execute(sql.SQL("GRANT USAGE ON SCHEMA {} TO {}").format(sql.Identifier(schema), sql.Identifier(username)))
    for table, privileges in RUNTIME_TABLE_PRIVILEGES.items():
        cur.execute(sql.SQL("GRANT {} ON {}.{} TO {}").format(
            sql.SQL(privileges), sql.Identifier(schema), sql.Identifier(table), sql.Identifier(username),
        ))
    for table in ("users", "audit_log", "configs", "schedules"):
        cur.execute("SELECT pg_get_serial_sequence(%s, 'id')", (sql.Identifier(schema, table).as_string(cur.connection),))
        sequence = cur.fetchone()[0]
        if sequence:
            cur.execute(sql.SQL("GRANT USAGE, SELECT ON SEQUENCE {} TO {}").format(sql.SQL(sequence), sql.Identifier(username)))
    cur.execute("SELECT has_schema_privilege(%s,%s,'CREATE')", (username, schema))
    if cur.fetchone()[0]:
        raise ValueError("Schema CREATE is inherited through existing grants; review those grants first.")


def refresh_runtime_permissions(dsn: str, username: str, schema: str = "public") -> None:
    """Regrant only reviewed tables after maintenance; never upgrade an unknown identity."""
    conn = psycopg2.connect(dsn)
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("SELECT oid,rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls FROM pg_roles WHERE rolname=%s", (username,))
                role = cur.fetchone()
                if not role:
                    return  # Initial migration precedes role provisioning.
                if any(role[1:]):
                    raise ValueError("Runtime role has administrative privileges.")
                cur.execute("SELECT EXISTS (SELECT 1 FROM pg_auth_members WHERE member=%s) "
                            "OR EXISTS (SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
                            "WHERE c.relowner=%s AND n.nspname=%s)", (role[0], role[0], schema))
                if cur.fetchone()[0]:
                    raise ValueError("Runtime role has unexpected membership or object ownership.")
                _grant_access(cur, username, schema)
    finally:
        conn.close()


def provision_runtime_role(dsn: str, username: str, password: str, schema: str = "public") -> None:
    """Create a fresh runtime identity atomically; refuse to reuse an unknown role."""
    if not username.strip() or len(password) < 32:
        raise ValueError("A runtime username and a password of at least 32 characters are required.")
    conn = psycopg2.connect(dsn)
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", (username,))
                if cur.fetchone():
                    raise ValueError("The requested runtime role already exists; inspect it before continuing.")
                # An explicit list prevents granting access to future administrative tables.
                for table in RUNTIME_TABLE_PRIVILEGES:
                    cur.execute(sql.SQL("SELECT 1 FROM {}.{} LIMIT 0").format(sql.Identifier(schema), sql.Identifier(table)))
                verifier = encrypt_password(password, username, scope=conn, algorithm="scram-sha-256")
                cur.execute(
                    sql.SQL("CREATE ROLE {} LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD %s")
                    .format(sql.Identifier(username)), (verifier,),
                )
                _grant_access(cur, username, schema)
    finally:
        conn.close()
