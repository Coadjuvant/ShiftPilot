from __future__ import annotations

from typing import List
from pathlib import Path
import json
import re
import base64
import os
import csv
import jwt
from datetime import datetime, timedelta, timezone
import ipaddress
import urllib.request
import urllib.error
import time
from collections import defaultdict, deque
from fastapi import Request

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    # dotenv is optional; ignore if not installed
    pass
from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, Response
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from backend.scheduler import (
    ConstraintToggles,
    DailyRequirement,
    ScheduleConfig,
    StaffMember,
    StaffPreferences,
    export_schedule_to_excel,
    run_tournament,
)
from backend.scheduler.model import DAYS, Assignment, ScheduleResult, ScheduleSlot, PTOEntry
from backend.auth_db import (
    init_db,
    create_invite,
    redeem_invite,
    validate_login,
    update_last_login,
    log_event,
    ensure_admin,
    list_users,
    delete_user,
    revoke_invite,
    list_audit,
    update_role,
    reset_invite,
    list_configs as list_user_configs,
    load_config as load_user_config,
    save_config as save_user_config,
    save_schedule as persist_schedule,
    get_latest_schedule,
    export_config as export_user_config,
    import_config as import_user_config,
)
from .schemas import (
    AssignmentOut,
    ConfigPayload,
    SaveConfigRequest,
    ScheduleRequest,
    ScheduleResponse,
    LoginRequest,
    LoginResponse,
    InviteRequest,
    SetupRequest,
    UserInfo,
    StaffMemberIn,
)

JWT_SECRET = os.getenv("JWT_SECRET", os.getenv("API_KEY", "dev-secret"))
JWT_EXPIRE_HOURS = int(os.getenv("JWT_EXPIRE_HOURS", "8"))
APP_ENV = os.getenv("APP_ENV", "dev").lower()
IS_PROD = APP_ENV == "prod"
API_VERSION = os.getenv("API_VERSION", "1")
ADMIN_USER = (os.getenv("ADMIN_USER", "admin") or "admin").strip()
ADMIN_PASS = (os.getenv("ADMIN_PASS", "admin") or "admin").strip()
GEOIP_API_URL = (os.getenv("GEOIP_API_URL") or "").strip()
GEOIP_API_TIMEOUT = float(os.getenv("GEOIP_API_TIMEOUT", "2.0"))
GEOIP_CACHE_TTL = int(os.getenv("GEOIP_CACHE_TTL", "3600"))
_geoip_cache: dict[str, tuple[float, tuple[str | None, str | None, str | None]]] = {}

app = FastAPI(
    title="Clinic Scheduler API",
    version="0.1.0",
    docs_url=None if IS_PROD else "/docs",
    redoc_url=None if IS_PROD else "/redoc",
    openapi_url=None if IS_PROD else "/openapi.json",
)
init_db()
# Basic in-memory rate limiter (per IP, per endpoint).
_rate_buckets: dict[str, deque] = defaultdict(deque)
_login_failures: dict[str, deque] = defaultdict(deque)
_login_lockouts: dict[str, float] = {}


def _client_ip(request: Request) -> str:
    header = request.headers.get("cf-connecting-ip") or request.headers.get("x-forwarded-for")
    if header:
        return header.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _client_ipv4(request: Request) -> str:
    candidates = [
        request.headers.get("cf-pseudo-ipv4"),
        request.headers.get("true-client-ip"),
        request.headers.get("x-real-ip"),
        request.headers.get("cf-connecting-ip"),
        request.headers.get("x-forwarded-for"),
    ]
    for candidate in candidates:
        if not candidate:
            continue
        for part in candidate.split(","):
            ip = part.strip()
            try:
                addr = ipaddress.ip_address(ip)
            except ValueError:
                continue
            if addr.version == 4:
                return ip
    return ""


def _geoip_cache_get(ip: str) -> tuple[str | None, str | None, str | None] | None:
    entry = _geoip_cache.get(ip)
    if not entry:
        return None
    ts, value = entry
    if (time.time() - ts) > GEOIP_CACHE_TTL:
        _geoip_cache.pop(ip, None)
        return None
    return value


def _geoip_cache_set(ip: str, value: tuple[str | None, str | None, str | None]) -> None:
    _geoip_cache[ip] = (time.time(), value)


def _geoip_api_lookup(ip: str) -> tuple[str | None, str | None, str | None]:
    if not GEOIP_API_URL:
        return None, None, None
    cached = _geoip_cache_get(ip)
    if cached is not None:
        return cached
    if "{ip}" in GEOIP_API_URL:
        url = GEOIP_API_URL.replace("{ip}", ip)
    elif GEOIP_API_URL.endswith("/"):
        url = f"{GEOIP_API_URL}{ip}"
    else:
        url = f"{GEOIP_API_URL}/{ip}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "ShiftPilot/GeoIP"})
        with urllib.request.urlopen(req, timeout=GEOIP_API_TIMEOUT) as resp:
            payload = resp.read().decode("utf-8", errors="ignore")
        data = json.loads(payload) if payload else {}
    except Exception:
        return None, None, None
    city = data.get("city") or data.get("city_name")
    region = (
        data.get("region")
        or data.get("region_name")
        or data.get("state")
        or data.get("subdivision")
        or data.get("subdivision_name")
    )
    country = (
        data.get("country_code")
        or data.get("country")
        or data.get("country_name")
        or data.get("countryCode")
    )
    result = (city or None, region or None, country or None)
    _geoip_cache_set(ip, result)
    return result


def _geoip_location(ip: str) -> tuple[str | None, str | None, str | None]:
    if not ip:
        return None, None, None
    try:
        addr = ipaddress.ip_address(ip)
        if addr.is_private or addr.is_loopback or addr.is_reserved or addr.is_multicast:
            return None, None, None
    except ValueError:
        return None, None, None
    return _geoip_api_lookup(ip)


def _client_location(request: Request) -> str:
    headers = request.headers
    city = headers.get("cf-ipcity") or headers.get("cf-city") or headers.get("x-geo-city")
    region = headers.get("cf-region") or headers.get("cf-region-code") or headers.get("x-geo-region")
    country = headers.get("cf-ipcountry") or headers.get("x-geo-country")
    if not city or not region:
        ip = _client_ip(request)
        geo_city, geo_region, geo_country = _geoip_location(ip)
        if geo_city:
            city = geo_city
        if geo_region:
            region = geo_region
        if not country and geo_country:
            country = geo_country
    if city and region:
        return f"{city}, {region}"
    if city and country:
        return f"{city}, {country}"
    if region and country:
        return f"{region}, {country}"
    if country:
        return country
    return ""


def _request_meta(request: Request) -> tuple[str, str, str, str]:
    return (
        _client_ip(request),
        _client_ipv4(request),
        request.headers.get("user-agent", ""),
        _client_location(request),
    )


def rate_limit(key: str, *, limit: int, window_seconds: int):
    async def _guard(request: Request):
        now = time.time()
        bucket_key = f"{key}:{_client_ip(request)}"
        bucket = _rate_buckets[bucket_key]
        while bucket and bucket[0] <= now - window_seconds:
            bucket.popleft()
        if len(bucket) >= limit:
            raise HTTPException(status_code=429, detail="Too many requests")
        bucket.append(now)
    return _guard


def _login_key(request: Request, username: str) -> str:
    return f"{username.lower()}:{_client_ip(request)}"


def _is_locked_out(key: str) -> bool:
    until = _login_lockouts.get(key)
    if not until:
        return False
    if until <= time.time():
        _login_lockouts.pop(key, None)
        return False
    return True


def _record_login_failure(key: str, *, limit: int = 5, window_seconds: int = 900, lockout_seconds: int = 900):
    now = time.time()
    bucket = _login_failures[key]
    while bucket and bucket[0] <= now - window_seconds:
        bucket.popleft()
    bucket.append(now)
    if len(bucket) >= limit:
        _login_lockouts[key] = now + lockout_seconds


def _clear_login_failures(key: str):
    _login_failures.pop(key, None)
    _login_lockouts.pop(key, None)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
    response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains; preload")
    response.headers.setdefault("X-API-Version", API_VERSION)
    response.headers.setdefault("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'; base-uri 'none'")
    return response
# seed default admin user if provided
ensure_admin(
    os.getenv("ADMIN_USER", "admin"),
    os.getenv("ADMIN_PASS", "admin"),
    os.getenv("ADMIN_LICENSE", "DEMO"),
)


@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains; preload"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    csp = (
        "default-src 'self'; "
        "script-src 'self' https://static.cloudflareinsights.com; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: https:; "
        "font-src 'self' data:; "
        "connect-src 'self' https://api.shiftpilot.me https:; "
        "frame-ancestors 'self';"
    )
    response.headers["Content-Security-Policy"] = csp
    return response


def _decode_jwt(token: str) -> dict:
    return jwt.decode(token, JWT_SECRET, algorithms=["HS256"])


def require_auth(
    request: Request,
    authorization: str = Header(default=None),
    x_api_key: str = Header(default=None, alias="x-api-key"),
) -> dict:
    """
    Auth stub: allow either a valid Bearer JWT or matching x-api-key.
    If neither is configured in the environment, allow all.
    """
    expected_key = os.getenv("API_KEY")
    allow_public = not expected_key and not ADMIN_USER
    token = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
    if not token:
        token = request.cookies.get("auth_token")
    if token:
        try:
            payload = _decode_jwt(token)
            return payload
        except Exception:
            raise HTTPException(status_code=401, detail="Invalid token")
    if expected_key:
        if x_api_key == expected_key:
            return {"sub": "api-key"}
        raise HTTPException(status_code=401, detail="Unauthorized")
    if allow_public:
        return {"sub": "public"}
    raise HTTPException(status_code=401, detail="Unauthorized")


router = APIRouter(prefix="/api")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _to_staff_member(payload: StaffMemberIn) -> StaffMember:
    preferences = StaffPreferences(**payload.preferences.dict())
    availability = {day: bool(payload.availability.get(day, False)) for day in DAYS}
    return StaffMember(
        id=payload.id,
        name=payload.name,
        role=payload.role or "Tech",
        can_open=payload.can_open,
        can_close=payload.can_close,
        can_bleach=payload.can_bleach if payload.role == "Tech" else False,
        availability=availability,
        preferences=preferences,
    )


@router.get("/health")
def healthcheck() -> dict:
    return {"status": "ok"}


def require_admin(payload: dict = Depends(require_auth)) -> dict:
    if payload.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    return payload


def _token_response(token: str) -> JSONResponse:
    response = JSONResponse(content={"token": token})
    response.set_cookie(
        "auth_token",
        token,
        httponly=True,
        secure=IS_PROD,
        samesite="strict",
        max_age=JWT_EXPIRE_HOURS * 3600,
    )
    return response


@router.post(
    "/auth/login",
    response_model=LoginResponse,
    dependencies=[Depends(rate_limit("login", limit=10, window_seconds=60))],
)
def login(request: Request, creds: LoginRequest) -> LoginResponse:
    lock_key = _login_key(request, creds.username)
    if _is_locked_out(lock_key):
        raise HTTPException(status_code=429, detail="Too many failed login attempts")
    user = validate_login(creds.username, creds.password)
    if not user:
        ip, ip_v4, user_agent, location = _request_meta(request)
        detail = f"username={creds.username};result=fail;reason=invalid_credentials"
        log_event(None, "login_fail", detail, ip, user_agent, location, ip_v4)
        _record_login_failure(lock_key)
        raise HTTPException(status_code=401, detail="Invalid credentials or license")
    _clear_login_failures(lock_key)
    update_last_login(user["id"])
    payload = {
        "sub": str(user["id"]),
        "username": user["username"],
        "role": user.get("role", "user"),
        "iat": datetime.utcnow(),
        "exp": datetime.utcnow() + timedelta(hours=JWT_EXPIRE_HOURS),
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm="HS256")
    ip, ip_v4, user_agent, location = _request_meta(request)
    detail = f"username={user['username']};method=password"
    log_event(user["id"], "login_success", detail, ip, user_agent, location, ip_v4)
    return _token_response(token)


@router.post("/auth/invite", response_model=LoginResponse, dependencies=[Depends(require_admin)])
def invite_user(request: Request, req: InviteRequest, payload: dict = Depends(require_admin)) -> dict:
    creator = payload.get("sub")
    try:
        creator_id = int(creator) if creator is not None else None
    except Exception:
        creator_id = None
    token = create_invite(req.username, req.license_key, role=req.role or "user", created_by=creator_id)
    ip, ip_v4, user_agent, location = _request_meta(request)
    log_event(
        creator_id,
        "invite_created",
        f"username={req.username or ''};token={token}",
        ip,
        user_agent,
        location,
        ip_v4,
    )
    return {"token": token}


@router.post(
    "/auth/setup",
    response_model=LoginResponse,
    dependencies=[Depends(rate_limit("setup", limit=5, window_seconds=60))],
)
def setup_user(request: Request, body: SetupRequest) -> LoginResponse:
    try:
        user = redeem_invite(body.invite_token, body.password, desired_username=body.username)
    except ValueError as e:
        # propagate specific username conflict
        raise HTTPException(status_code=409, detail=str(e))
    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired invite token")
    payload = {
        "sub": str(user["id"]),
        "username": user["username"],
        "role": user.get("role", "user"),
        "iat": datetime.utcnow(),
        "exp": datetime.utcnow() + timedelta(hours=JWT_EXPIRE_HOURS),
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm="HS256")
    ip, ip_v4, user_agent, location = _request_meta(request)
    log_event(user["id"], "login_success", "invite_setup", ip, user_agent, location, ip_v4)
    return _token_response(token)


@router.get("/auth/me", response_model=UserInfo, dependencies=[Depends(require_auth)])
def me(payload: dict = Depends(require_auth)) -> UserInfo:
    return UserInfo(sub=str(payload.get("sub", "")), username=payload.get("username", ""), role=payload.get("role", ""))


@router.get("/auth/users", dependencies=[Depends(require_admin)])
def list_users_admin():
    return list_users()


@router.delete("/auth/users/{user_id}", dependencies=[Depends(require_admin)])
def delete_user_admin(request: Request, user_id: int):
    try:
        delete_user(user_id)
        # log after deletion without FK reference
        ip, ip_v4, user_agent, location = _request_meta(request)
        log_event(None, "user_deleted", f"user_id={user_id}", ip, user_agent, location, ip_v4)
        return {"status": "deleted", "id": user_id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/auth/invite/revoke", dependencies=[Depends(require_admin)])
def revoke_invite_admin(request: Request, req: InviteRequest):
    revoke_invite(req.username)
    ip, ip_v4, user_agent, location = _request_meta(request)
    log_event(None, "invite_revoked", f"username={req.username}", ip, user_agent, location, ip_v4)
    return {"status": "revoked", "username": req.username}


@router.get("/auth/audit", dependencies=[Depends(require_admin)])
def audit_feed(
    limit: int = 50,
    event: str | None = None,
    user_id: int | None = None,
    search: str | None = None,
):
    return list_audit(limit=limit, event=event, user_id=user_id, search=search)


@router.post("/auth/users/{user_id}/role", dependencies=[Depends(require_admin)])
def update_user_role(
    request: Request,
    user_id: int,
    body: dict | None = None,
    payload: dict = Depends(require_auth),
):
    role = body.get("role") if body else None
    if not role:
        raise HTTPException(status_code=400, detail="Role required")
    try:
        update_role(user_id, role)
        ip, ip_v4, user_agent, location = _request_meta(request)
        log_event(payload.get("sub"), "role_updated", f"user_id={user_id}, role={role}", ip, user_agent, location, ip_v4)
        return {"status": "ok", "id": user_id, "role": role}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/auth/users/{user_id}/reset", dependencies=[Depends(require_admin)])
def reset_user_invite(request: Request, user_id: int, payload: dict = Depends(require_auth)):
    creator = payload.get("sub")
    try:
        creator_id = int(creator) if creator is not None else None
    except Exception:
        creator_id = None
    try:
        token = reset_invite(user_id, created_by=creator_id)
        ip, ip_v4, user_agent, location = _request_meta(request)
        log_event(creator_id, "reset_invite", f"user_id={user_id}", ip, user_agent, location, ip_v4)
        return {"token": token}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/schedule/run",
    response_model=ScheduleResponse,
    dependencies=[Depends(require_auth), Depends(rate_limit("schedule_run", limit=8, window_seconds=60))],
)
def run_schedule(request: ScheduleRequest, payload: dict = Depends(require_auth)) -> ScheduleResponse:
    try:
        staff_members = [_to_staff_member(s) for s in request.staff]
        if not staff_members:
            raise ValueError("At least one staff member is required.")
        requirements: List[DailyRequirement] = [
            DailyRequirement(
                day_name=req.day_name,
                patient_count=req.patient_count,
                tech_openers=req.tech_openers,
                tech_mids=req.tech_mids,
                tech_closers=req.tech_closers,
                rn_count=req.rn_count,
                admin_count=req.admin_count,
            )
            for req in request.requirements
        ]
        if len(requirements) != len(DAYS):
            raise ValueError("Requirements must include all clinic days (Mon-Sat).")
        toggles = ConstraintToggles(**request.config.toggles.dict())
        config = ScheduleConfig(
            clinic_name=request.config.clinic_name,
            timezone=request.config.timezone,
            start_date=request.config.start_date,
            weeks=request.config.weeks,
            bleach_day=request.config.bleach_day,
            bleach_rotation=request.config.bleach_rotation,
            bleach_cursor=request.config.bleach_cursor,
            bleach_frequency=request.config.bleach_frequency,
            patients_per_tech=request.config.patients_per_tech,
            patients_per_rn=request.config.patients_per_rn,
            techs_per_rn=request.config.techs_per_rn,
            toggles=toggles,
        )
        pto_entries = [
            PTOEntry(staff_id=item.staff_id, date=item.date) for item in request.pto
        ]
        result, winning_seed = run_tournament(
            staff_members,
            requirements,
            config,
            pto_entries=pto_entries,
            trials=request.tournament_trials,
            base_seed=request.base_seed,
        )
        assignments = [
            AssignmentOut(
                date=assignment.slot.date,
                day_name=assignment.slot.day_name,
                role=assignment.slot.role,
                duty="bleach" if assignment.slot.is_bleach else assignment.slot.duty,
                staff_id=assignment.staff_id,
                notes=assignment.notes,
                slot_index=assignment.slot.slot_index,
                is_bleach=assignment.slot.is_bleach,
            )
            for assignment in result.assignments
        ]
        roles_filter = request.export_roles or None
        excel_bytes = export_schedule_to_excel(
            result,
            {s.id: s for s in staff_members},
            export_roles=roles_filter,
            pto_entries=pto_entries,
        )
        excel_b64 = base64.b64encode(excel_bytes).decode("utf-8")
        # Persist latest schedule snapshot for this owner (save under both id + username if present)
        owners = _schedule_owners(payload)
        def _serialize_assignments():
            out = []
            for a in assignments:
                out.append(
                    {
                        "date": a.date.isoformat() if hasattr(a, "date") else getattr(a, "date", None),
                        "day_name": getattr(a, "day_name", None),
                        "role": getattr(a, "role", None),
                        "duty": getattr(a, "duty", None),
                        "staff_id": getattr(a, "staff_id", None),
                        "notes": getattr(a, "notes", []),
                        "slot_index": getattr(a, "slot_index", None),
                        "is_bleach": getattr(a, "is_bleach", False),
                    }
                )
            return out

        schedule_payload = {
            "clinic_name": request.config.clinic_name,
            "timezone": request.config.timezone,
            "start_date": request.config.start_date.isoformat() if hasattr(request.config.start_date, "isoformat") else request.config.start_date,
            "weeks": request.config.weeks,
            "bleach_frequency": request.config.bleach_frequency,
            "requirements": [
                {
                    "day_name": req.day_name,
                    "patient_count": req.patient_count,
                    "tech_openers": req.tech_openers,
                    "tech_mids": req.tech_mids,
                    "tech_closers": req.tech_closers,
                    "rn_count": req.rn_count,
                    "admin_count": req.admin_count,
                }
                for req in request.requirements
            ],
            "assignments": _serialize_assignments(),
            "staff": [{"id": s.id, "name": s.name, "role": s.role} for s in staff_members],
            "stats": result.stats,
            "total_penalty": result.total_penalty,
            "winning_seed": winning_seed,
            "bleach_cursor": result.bleach_cursor,
            "export_roles": request.export_roles,
            "tournament_trials": request.tournament_trials,
            "pto": [
                {
                    "staff_id": item.staff_id,
                    "date": item.date.isoformat() if hasattr(item.date, "isoformat") else item.date,
                }
                for item in request.pto
            ],
            "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }
        # ensure fully serializable before persisting
        import json as _json

        safe_payload = _json.loads(_json.dumps(schedule_payload, default=str))
        for owner in owners:
            persist_schedule(owner, safe_payload)
        open_slots = sum(
            1
            for assignment in assignments
            if assignment.staff_id is None or str(assignment.staff_id).upper() == "OPEN"
        )
        start_label = (
            request.config.start_date.isoformat()
            if hasattr(request.config.start_date, "isoformat")
            else str(request.config.start_date)
        )
        detail = (
            f"clinic={request.config.clinic_name};start={start_label};weeks={request.config.weeks};"
            f"bleach={request.config.bleach_frequency or 'weekly'};seed={winning_seed};open_slots={open_slots}"
        )
        ip, ip_v4, user_agent, location = _request_meta(request)
        log_event(payload.get("sub"), "schedule_run", detail, ip, user_agent, location, ip_v4)
        return ScheduleResponse(
            bleach_cursor=result.bleach_cursor,
            winning_seed=winning_seed,
            assignments=assignments,
            total_penalty=result.total_penalty,
            stats=result.stats,
            excel=excel_b64,
        )
    except Exception as exc:
        detail = str(exc) if not IS_PROD else "Invalid schedule request"
        raise HTTPException(status_code=400, detail=detail) from exc


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", name).strip("-").lower()
    return slug or "clinic"


def _owner_candidates(payload: dict) -> List[str]:
    owners: List[str] = []
    username = (payload.get("username") or "").strip()
    sub = str(payload.get("sub") or "").strip()
    if username:
        owners.append(username)
    if sub and sub not in owners:
        owners.append(sub)
    if not owners:
        owners.append("public")
    return owners


def _config_owner(payload: dict) -> str:
    username = (payload.get("username") or "").strip()
    sub = str(payload.get("sub") or "").strip()
    return username or sub or "public"


def _schedule_owners(payload: dict) -> List[str]:
    return _owner_candidates(payload)


def _parse_generated_at(value: object) -> datetime:
    if isinstance(value, str) and value:
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except Exception:
            return datetime.min
    return datetime.min


def _safe_error(message: str, exc: Exception) -> str:
    return message if IS_PROD else f"{message}: {exc}"


def _latest_schedule_for(payload: dict) -> dict | None:
    candidates: List[dict] = []
    for owner in _schedule_owners(payload):
        data = get_latest_schedule(owner)
        if isinstance(data, dict):
            candidates.append(data)
    if not candidates:
        return None
    return max(candidates, key=lambda d: _parse_generated_at(d.get("generated_at")))


def _parse_schedule_date(value: object) -> datetime.date:
    if isinstance(value, datetime):
        return value.date()
    if hasattr(value, "year") and hasattr(value, "month") and hasattr(value, "day"):
        return value  # date-like
    if isinstance(value, str) and value:
        try:
            return datetime.fromisoformat(value).date()
        except Exception:
            pass
    return datetime.now(timezone.utc).date()


def _hydrate_schedule_result(data: dict) -> tuple[ScheduleResult, dict[str, StaffMember]]:
    staff_map: dict[str, StaffMember] = {}
    for entry in data.get("staff", []) or []:
        staff_id = entry.get("id") or entry.get("staff_id")
        if not staff_id:
            continue
        staff_map[staff_id] = StaffMember(
            id=staff_id,
            name=entry.get("name") or staff_id,
            role=entry.get("role") or "",
        )

    start_date = _parse_schedule_date(data.get("start_date")) if data.get("start_date") else None
    assignments: list[Assignment] = []
    for item in data.get("assignments", []) or []:
        slot_date = _parse_schedule_date(item.get("date"))
        day_index = 0
        if start_date:
            try:
                day_index = max((slot_date - start_date).days, 0)
            except Exception:
                day_index = 0
        slot = ScheduleSlot(
            day_index=day_index,
            date=slot_date,
            day_name=item.get("day_name") or "",
            role=item.get("role") or "",
            duty=item.get("duty") or "",
            slot_index=int(item.get("slot_index") or 0),
            is_bleach=bool(item.get("is_bleach")),
        )
        assignments.append(
            Assignment(
                slot=slot,
                staff_id=item.get("staff_id"),
                notes=item.get("notes") or [],
            )
        )

    result = ScheduleResult(
        assignments=assignments,
        bleach_cursor=int(data.get("bleach_cursor") or 0),
        total_penalty=float(data.get("total_penalty") or 0.0),
        stats=data.get("stats") or {},
        seed=data.get("winning_seed"),
    )
    return result, staff_map


def _hydrate_pto_entries(data: dict) -> List[PTOEntry]:
    entries: List[PTOEntry] = []
    for entry in data.get("pto", []) or []:
        if isinstance(entry, dict):
            staff_id = entry.get("staff_id")
            date_val = entry.get("date")
        else:
            staff_id = getattr(entry, "staff_id", None)
            date_val = getattr(entry, "date", None)
        if not staff_id or not date_val:
            continue
        entries.append(PTOEntry(staff_id=staff_id, date=_parse_schedule_date(date_val)))
    return entries


def _schedule_date_range(data: dict) -> str:
    start_raw = data.get("start_date")
    weeks = data.get("weeks")
    if not start_raw or not isinstance(weeks, int):
        return ""
    start = _parse_schedule_date(start_raw)
    end = start + timedelta(days=weeks * 7 - 2)
    return f"{start.isoformat()}_to_{end.isoformat()}"


@router.get("/configs")
def list_configs(payload: dict = Depends(require_auth)) -> List[str]:
    owner = _config_owner(payload)
    return list_user_configs(owner)


@router.get("/configs/{filename}", response_model=ConfigPayload)
def load_config(filename: str, payload: dict = Depends(require_auth)) -> ConfigPayload:
    owner = _config_owner(payload)
    safe_name = Path(filename).name
    data = load_user_config(owner, safe_name)
    if data is None:
        raise HTTPException(status_code=404, detail="Config not found")
    try:
        return ConfigPayload(**data)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=_safe_error("Failed to load config", exc)) from exc


@router.post("/configs/save")
def save_config(request: Request, body: SaveConfigRequest, payload: dict = Depends(require_auth)) -> dict:
    owner = _config_owner(payload)
    filename = body.filename.strip() if body.filename else ""
    if not filename:
        filename = f"{_slugify(body.payload.clinic.name)}.json"
    if not filename.endswith(".json"):
        filename += ".json"
    try:
        payload_dict = body.payload.dict()
        safe_name = Path(filename).name
        save_user_config(owner, safe_name, payload_dict)
        size_kb = round(len(json.dumps(payload_dict, default=str)) / 1024, 1)
        ip, ip_v4, user_agent, location = _request_meta(request)
        log_event(
            payload.get("sub"),
            "config_save",
            f"config={safe_name};size_kb={size_kb}",
            ip,
            user_agent,
            location,
            ip_v4,
        )
        return {"status": "saved", "filename": filename}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=_safe_error("Failed to save config", exc)) from exc


@router.get("/schedule/latest")
def latest_schedule(response: Response, payload: dict = Depends(require_auth)) -> dict:
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    data = _latest_schedule_for(payload)
    if not data:
        return {"status": "none"}
    return data


@router.get("/schedule/export/csv")
def export_schedule_csv(request: Request, payload: dict = Depends(require_auth)):
    data = _latest_schedule_for(payload)
    if not data or not data.get("assignments"):
        raise HTTPException(status_code=404, detail="No saved schedule")
    staff_map = {s.get("id"): s for s in data.get("staff", [])}
    output_rows = []
    for a in data.get("assignments", []):
        staff = staff_map.get(a.get("staff_id"))
        output_rows.append(
            {
                "date": a.get("date"),
                "day_name": a.get("day_name"),
                "role": a.get("role"),
                "duty": a.get("duty"),
                "staff_name": staff.get("name") if staff else "",
                "staff_key": staff.get("id") if staff else "",
                "is_bleach": a.get("is_bleach"),
                "slot_index": a.get("slot_index"),
                "notes": "|".join(a.get("notes", [])) if a.get("notes") else "",
            }
        )
    # Return as CSV text for download
    fieldnames = ["date", "day_name", "role", "duty", "staff_name", "staff_key", "is_bleach", "slot_index", "notes"]
    import io

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(output_rows)
    buf.seek(0)
    from fastapi.responses import PlainTextResponse

    clinic_name = data.get("clinic_name") or "schedule"
    range_label = _schedule_date_range(data)
    filename = f"{_slugify(clinic_name)}-{range_label}.csv" if range_label else f"{_slugify(clinic_name)}.csv"
    ip, ip_v4, user_agent, location = _request_meta(request)
    log_event(
        payload.get("sub"),
        "schedule_export",
        f"format=csv;clinic={clinic_name};range={range_label or 'unknown'}",
        ip,
        user_agent,
        location,
        ip_v4,
    )
    return PlainTextResponse(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/schedule/export/excel")
def export_schedule_excel(request: Request, payload: dict = Depends(require_auth)):
    data = _latest_schedule_for(payload)
    if not data or not data.get("assignments"):
        raise HTTPException(status_code=404, detail="No saved schedule")
    result, staff = _hydrate_schedule_result(data)
    pto_entries = _hydrate_pto_entries(data)
    excel_bytes = export_schedule_to_excel(
        result,
        staff,
        export_roles=data.get("export_roles"),
        pto_entries=pto_entries,
    )
    clinic_name = data.get("clinic_name") or "schedule"
    range_label = _schedule_date_range(data)
    filename = (
        f"{_slugify(clinic_name)}-{range_label}.xlsx" if range_label else f"{_slugify(clinic_name)}.xlsx"
    )
    ip, ip_v4, user_agent, location = _request_meta(request)
    log_event(
        payload.get("sub"),
        "schedule_export",
        f"format=excel;clinic={clinic_name};range={range_label or 'unknown'}",
        ip,
        user_agent,
        location,
        ip_v4,
    )
    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/schedule/import/csv")
async def import_schedule_csv(request: Request, payload: dict = Depends(require_auth)) -> dict:
    owner = _schedule_owner(payload)
    form = await request.form()
    file = form.get("file")
    if not file:
        raise HTTPException(status_code=400, detail="CSV file required")
    filename = getattr(file, "filename", "") or ""
    if filename and not filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only .csv files are allowed")
    content_type = getattr(file, "content_type", "") or ""
    if content_type and content_type not in ("text/csv", "application/vnd.ms-excel"):
        raise HTTPException(status_code=400, detail="Invalid CSV content type")
    raw = await file.read()
    max_bytes = int(os.getenv("MAX_CSV_BYTES", "2097152"))
    if len(raw) > max_bytes:
        raise HTTPException(status_code=413, detail="CSV file too large")
    content = raw.decode("utf-8", errors="ignore")
    reader = csv.DictReader(content.splitlines())
    assignments = []
    staff_entries = {}
    for row in reader:
        staff_key = row.get("staff_key", "") or row.get("staff_id", "")
        staff_name = row.get("staff_name", "") or ""
        if staff_key and staff_name and staff_key not in staff_entries:
            staff_entries[staff_key] = {"id": staff_key, "name": staff_name, "role": row.get("role", "Tech")}
        assignments.append(
            {
                "date": row.get("date"),
                "day_name": row.get("day_name"),
                "role": row.get("role"),
                "duty": row.get("duty"),
                "staff_id": staff_key or None,
                "notes": [n for n in (row.get("notes", "") or "").split("|") if n],
                "slot_index": int(row.get("slot_index") or 0),
                "is_bleach": str(row.get("is_bleach") or "").lower() in ["true", "1", "yes"],
            }
        )
    if not assignments:
        raise HTTPException(status_code=400, detail="No assignments found in CSV")
    snapshot = {
        "clinic_name": "Imported schedule",
        "timezone": "UTC",
        "start_date": assignments[0].get("date") or datetime.utcnow().date().isoformat(),
        "weeks": 1,
        "requirements": [],
        "assignments": assignments,
        "staff": list(staff_entries.values()),
        "stats": {},
        "total_penalty": 0,
        "winning_seed": None,
        "bleach_cursor": 0,
        "generated_at": datetime.utcnow().isoformat(),
    }
    persist_schedule(owner, snapshot)
    ip, ip_v4, user_agent, location = _request_meta(request)
    log_event(
        payload.get("sub"),
        "schedule_import",
        f"format=csv;rows={len(assignments)}",
        ip,
        user_agent,
        location,
        ip_v4,
    )
    return {"status": "imported", "assignments": len(assignments)}


@router.get("/configs/export/{filename}")
def export_config(request: Request, filename: str, payload: dict = Depends(require_auth)) -> dict:
    owner = _config_owner(payload)
    safe_name = Path(filename).name
    data = export_user_config(owner, safe_name)
    if data is None:
        raise HTTPException(status_code=404, detail="Config not found")
    encoded = base64.b64encode(json.dumps(data, default=str).encode("utf-8")).decode("utf-8")
    ip, ip_v4, user_agent, location = _request_meta(request)
    log_event(payload.get("sub"), "config_export", f"config={safe_name}", ip, user_agent, location, ip_v4)
    return {"filename": safe_name, "payload": data, "encoded": encoded}


@router.post("/configs/import")
def import_config(request: Request, body: SaveConfigRequest, payload: dict = Depends(require_auth)) -> dict:
    owner = _config_owner(payload)
    filename = body.filename.strip() if body.filename else ""
    if not filename:
        filename = f"{_slugify(body.payload.clinic.name)}.config"
    try:
        safe_name = Path(filename).name
        payload_dict = body.payload.dict()
        import_user_config(owner, safe_name, payload_dict)
        size_kb = round(len(json.dumps(payload_dict, default=str)) / 1024, 1)
        ip, ip_v4, user_agent, location = _request_meta(request)
        log_event(
            payload.get("sub"),
            "config_import",
            f"config={safe_name};size_kb={size_kb}",
            ip,
            user_agent,
            location,
            ip_v4,
        )
        return {"status": "imported", "filename": filename}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=_safe_error("Failed to import config", exc)) from exc


app.include_router(router)
