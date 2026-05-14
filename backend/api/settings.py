from __future__ import annotations

import os


def env_float(name: str, default: float) -> float:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def env_int(name: str, default: int) -> int:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def split_env_csv(name: str, default: str = "") -> list[str]:
    raw = os.getenv(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


APP_ENV = os.getenv("APP_ENV", "dev").lower()
IS_PROD = APP_ENV == "prod"
API_VERSION = os.getenv("API_VERSION", "1")
API_KEY = os.getenv("API_KEY")

ADMIN_USER = (os.getenv("ADMIN_USER", "admin") or "admin").strip()
ADMIN_PASS = (os.getenv("ADMIN_PASS", "admin") or "admin").strip()
ADMIN_LICENSE = (os.getenv("ADMIN_LICENSE", "DEMO") or "DEMO").strip()

JWT_SECRET = os.getenv("JWT_SECRET", os.getenv("API_KEY", "dev-secret"))
JWT_EXPIRE_HOURS = env_int("JWT_EXPIRE_HOURS", 8)

GEOIP_API_URL = (os.getenv("GEOIP_API_URL") or "").strip()
GEOIP_API_TIMEOUT = env_float("GEOIP_API_TIMEOUT", 2.0)
GEOIP_CACHE_TTL = env_int("GEOIP_CACHE_TTL", 3600)

DEFAULT_CORS_ALLOW_ORIGINS = (
    "http://localhost:8080,"
    "http://localhost:5173,"
    "http://127.0.0.1:8080,"
    "http://127.0.0.1:5173,"
    "https://shiftpilot.me,"
    "https://www.shiftpilot.me"
)
CORS_ALLOW_ORIGINS = split_env_csv("CORS_ALLOW_ORIGINS", DEFAULT_CORS_ALLOW_ORIGINS)


def require_safe_prod_config() -> None:
    if not IS_PROD:
        return
    jwt_secret = (os.getenv("JWT_SECRET") or "").strip()
    if not jwt_secret or jwt_secret in {"dev-secret", "change-me", "local-dev-secret-change-later"}:
        raise RuntimeError("JWT_SECRET must be set to a strong non-default value when APP_ENV=prod.")
    if ADMIN_USER == "admin" and ADMIN_PASS == "admin":
        raise RuntimeError("Default admin/admin credentials are not allowed when APP_ENV=prod.")
    if not CORS_ALLOW_ORIGINS:
        raise RuntimeError("CORS_ALLOW_ORIGINS must be set when APP_ENV=prod.")
