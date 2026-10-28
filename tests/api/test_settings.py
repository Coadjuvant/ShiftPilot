from __future__ import annotations

import importlib
import pytest


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


def test_runtime_mode_does_not_require_bootstrap_password(monkeypatch):
    settings = importlib.import_module("backend.api.settings")
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.setenv("DB_INITIALIZE_ON_STARTUP", "false")
    monkeypatch.setenv("JWT_SECRET", "test-secret-with-more-than-thirty-two-characters")
    monkeypatch.setenv("CORS_ALLOW_ORIGINS", "https://shiftpilot.me")
    monkeypatch.delenv("ADMIN_PASS", raising=False)
    try:
        settings = importlib.reload(settings)
        settings.require_safe_prod_config()
    finally:
        monkeypatch.setenv("APP_ENV", "dev")
        monkeypatch.setenv("DB_INITIALIZE_ON_STARTUP", "true")
        importlib.reload(settings)


def test_invalid_database_startup_mode_fails(monkeypatch):
    settings = importlib.import_module("backend.api.settings")
    monkeypatch.setenv("DB_INITIALIZE_ON_STARTUP", "typo")
    try:
        with pytest.raises(RuntimeError, match="DB_INITIALIZE_ON_STARTUP"):
            importlib.reload(settings)
    finally:
        monkeypatch.setenv("DB_INITIALIZE_ON_STARTUP", "true")
        importlib.reload(settings)
