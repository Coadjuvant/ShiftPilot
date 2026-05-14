from __future__ import annotations

import importlib


def test_prod_requires_non_default_jwt_secret(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.setenv("JWT_SECRET", "dev-secret")
    monkeypatch.setenv("ADMIN_USER", "shiftpilot-admin")
    monkeypatch.setenv("ADMIN_PASS", "not-default")
    monkeypatch.setenv("CORS_ALLOW_ORIGINS", "https://shiftpilot.me")

    settings = importlib.import_module("backend.api.settings")
    settings = importlib.reload(settings)

    try:
        try:
            settings.require_safe_prod_config()
        except RuntimeError as exc:
            assert "JWT_SECRET" in str(exc)
        else:
            raise AssertionError("Expected unsafe JWT_SECRET to fail prod config validation")
    finally:
        monkeypatch.setenv("APP_ENV", "dev")
        importlib.reload(settings)


def test_prod_requires_non_default_admin_credentials(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.setenv("JWT_SECRET", "a-long-enough-production-secret")
    monkeypatch.setenv("ADMIN_USER", "admin")
    monkeypatch.setenv("ADMIN_PASS", "admin")
    monkeypatch.setenv("CORS_ALLOW_ORIGINS", "https://shiftpilot.me")

    settings = importlib.import_module("backend.api.settings")
    settings = importlib.reload(settings)

    try:
        try:
            settings.require_safe_prod_config()
        except RuntimeError as exc:
            assert "admin/admin" in str(exc)
        else:
            raise AssertionError("Expected default admin credentials to fail prod config validation")
    finally:
        monkeypatch.setenv("APP_ENV", "dev")
        importlib.reload(settings)
