from __future__ import annotations

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    pass

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.auth_db import ensure_admin, init_db

from .middleware import security_headers_middleware
from .routes.auth import router as auth_router
from .routes.configs import router as configs_router
from .routes.schedules import router as schedules_router
from .settings import (
    ADMIN_LICENSE,
    ADMIN_PASS,
    ADMIN_USER,
    CORS_ALLOW_ORIGINS,
    IS_PROD,
    require_safe_prod_config,
)

require_safe_prod_config()

app = FastAPI(
    title="Clinic Scheduler API",
    version="0.1.0",
    docs_url=None if IS_PROD else "/docs",
    redoc_url=None if IS_PROD else "/redoc",
    openapi_url=None if IS_PROD else "/openapi.json",
)
init_db()
app.middleware("http")(security_headers_middleware)

ensure_admin(
    ADMIN_USER,
    ADMIN_PASS,
    ADMIN_LICENSE,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOW_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

health_router = APIRouter(prefix="/api")


@health_router.get("/health")
def healthcheck() -> dict:
    return {"status": "ok"}


app.include_router(health_router)
app.include_router(auth_router)
app.include_router(configs_router)
app.include_router(schedules_router)
