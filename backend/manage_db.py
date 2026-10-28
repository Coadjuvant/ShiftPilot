"""Run with maintenance credentials, separate from the HTTP server."""
from __future__ import annotations

import argparse
import os

from psycopg2.extensions import make_dsn


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["migrate", "provision-runtime"])
    args = parser.parse_args()
    # Maintenance containers receive only DB_* credentials. Runtime DATABASE_URL
    # is deliberately not accepted as a fallback for a privileged operation.
    required = ("DB_USER", "DB_PASSWORD", "DB_NAME")
    if any(not os.getenv(name) for name in required):
        raise RuntimeError("Database maintenance credentials are missing.")
    dsn = make_dsn(host=os.getenv("DB_HOST", "db"), port=os.getenv("DB_PORT", "5432"),
                   user=os.environ["DB_USER"], password=os.environ["DB_PASSWORD"], dbname=os.environ["DB_NAME"])
    # The storage module constructs its default backend at import time.
    os.environ["DATABASE_URL"] = dsn
    from backend.auth_db import PostgresAuth
    store = PostgresAuth(dsn)
    if args.command == "migrate":
        store.init_db()
        admin = (os.getenv("ADMIN_USER") or "admin").strip()
        if not store.get_user_by_username(admin):
            password = os.getenv("ADMIN_PASS", "")
            if len(password) < 12 or password.lower() in {"admin", "password", "changeme"}:
                raise RuntimeError("Initial administrator setup requires a non-default password of at least 12 characters.")
            store.ensure_admin(admin, password, os.getenv("ADMIN_LICENSE", "DEMO"))
        from backend.database_admin import refresh_runtime_permissions
        refresh_runtime_permissions(dsn, os.getenv("RUNTIME_DB_USER", "shiftpilot_runtime"))
        print("Database maintenance completed; existing accounts and passwords retained.")
    else:
        from backend.database_admin import provision_runtime_role
        provision_runtime_role(dsn, os.getenv("RUNTIME_DB_USER", "shiftpilot_runtime"), os.getenv("RUNTIME_DB_PASSWORD", ""))
        print("Restricted runtime database role created.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        # Connection exceptions may include credential-bearing DSNs.
        raise SystemExit(f"Database maintenance failed ({type(exc).__name__}). Credentials suppressed; inspect the configuration and migration state.") from None
