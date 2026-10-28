"""Validate the runtime configuration without starting HTTP or applying migrations."""
from __future__ import annotations


def main() -> None:
    from backend.api.settings import DB_INITIALIZE_ON_STARTUP, require_safe_prod_config
    require_safe_prod_config()
    if DB_INITIALIZE_ON_STARTUP:
        raise RuntimeError("Container runtime must not initialize the database.")
    from backend.auth_db import _backend
    _backend.check_runtime_database()
    print("Restricted runtime database configuration verified.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        raise SystemExit(f"Runtime database preflight failed ({type(exc).__name__}); serving containers retained.") from None
