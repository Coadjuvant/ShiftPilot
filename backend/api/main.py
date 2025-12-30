from __future__ import annotations

from typing import List
from pathlib import Path
import json
import re
import base64
import os
import csv
import jwt
from datetime import datetime, timedelta
from fastapi import Request

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    # dotenv is optional; ignore if not installed
    pass
from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware

from backend.scheduler import (
    ConstraintToggles,
    DailyRequirement,
    PTOEntry,
    ScheduleConfig,
    StaffMember,
    StaffPreferences,
    export_schedule_to_excel,
    run_tournament,
)
from backend.scheduler.model import DAYS
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
JWT_EXPIRE_HOURS = int(os.getenv("JWT_EXPIRE_HOURS", "24"))
ADMIN_USER = (os.getenv("ADMIN_USER", "admin") or "admin").strip()
ADMIN_PASS = (os.getenv("ADMIN_PASS", "admin") or "admin").strip()

app = FastAPI(title="Clinic Scheduler API", version="0.1.0")
init_db()
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
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
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


@router.post("/auth/login", response_model=LoginResponse)
def login(request: Request, creds: LoginRequest) -> LoginResponse:
    user = validate_login(creds.username, creds.password)
    if not user:
        log_event(None, "login_fail", "invalid_credentials", request.client.host if request.client else "", request.headers.get("user-agent", ""))
        raise HTTPException(status_code=401, detail="Invalid credentials or license")
    update_last_login(user["id"])
    payload = {
        "sub": str(user["id"]),
        "username": user["username"],
        "role": user.get("role", "user"),
        "iat": datetime.utcnow(),
        "exp": datetime.utcnow() + timedelta(hours=JWT_EXPIRE_HOURS),
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm="HS256")
    log_event(user["id"], "login_success", "", request.client.host if request.client else "", request.headers.get("user-agent", ""))
    return LoginResponse(token=token)


@router.post("/auth/invite", response_model=LoginResponse, dependencies=[Depends(require_admin)])
def invite_user(req: InviteRequest, payload: dict = Depends(require_admin)) -> dict:
    creator = payload.get("sub")
    try:
        creator_id = int(creator) if creator is not None else None
    except Exception:
        creator_id = None
    token = create_invite(req.username, req.license_key, role=req.role or "user", created_by=creator_id)
    log_event(
        creator_id,
        "invite_created",
        f"username={req.username or ''};token={token}",
        "",
        "",
    )
    return {"token": token}


@router.post("/auth/setup", response_model=LoginResponse)
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
    log_event(user["id"], "login_success", "invite_setup", request.client.host if request.client else "", request.headers.get("user-agent", ""))
    return LoginResponse(token=token)


@router.get("/auth/me", response_model=UserInfo, dependencies=[Depends(require_auth)])
def me(payload: dict = Depends(require_auth)) -> UserInfo:
    return UserInfo(sub=str(payload.get("sub", "")), username=payload.get("username", ""), role=payload.get("role", ""))


@router.get("/auth/users", dependencies=[Depends(require_admin)])
def list_users_admin():
    return list_users()


@router.delete("/auth/users/{user_id}", dependencies=[Depends(require_admin)])
def delete_user_admin(user_id: int):
    try:
        delete_user(user_id)
        # log after deletion without FK reference
        log_event(None, "user_deleted", f"user_id={user_id}", "", "")
        return {"status": "deleted", "id": user_id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/auth/invite/revoke", dependencies=[Depends(require_admin)])
def revoke_invite_admin(req: InviteRequest):
    revoke_invite(req.username)
    log_event(None, "invite_revoked", f"username={req.username}", "", "")
    return {"status": "revoked", "username": req.username}


@router.get("/auth/audit", dependencies=[Depends(require_admin)])
def audit_feed(limit: int = 50):
    return list_audit(limit=limit)


@router.post("/auth/users/{user_id}/role", dependencies=[Depends(require_admin)])
def update_user_role(user_id: int, body: dict | None = None, payload: dict = Depends(require_auth)):
    role = body.get("role") if body else None
    if not role:
        raise HTTPException(status_code=400, detail="Role required")
    try:
        update_role(user_id, role)
        log_event(payload.get("sub"), "role_updated", f"user_id={user_id}, role={role}", "", "")
        return {"status": "ok", "id": user_id, "role": role}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/auth/users/{user_id}/reset", dependencies=[Depends(require_admin)])
def reset_user_invite(user_id: int, payload: dict = Depends(require_auth)):
    creator = payload.get("sub")
    try:
        creator_id = int(creator) if creator is not None else None
    except Exception:
        creator_id = None
    try:
        token = reset_invite(user_id, created_by=creator_id)
        log_event(creator_id, "reset_invite", f"user_id={user_id}", "", "")
        return {"token": token}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/schedule/run", response_model=ScheduleResponse, dependencies=[Depends(require_auth)])
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
            "generated_at": datetime.utcnow().isoformat(),
        }
        # ensure fully serializable before persisting
        import json as _json

        safe_payload = _json.loads(_json.dumps(schedule_payload, default=str))
        for owner in owners:
            persist_schedule(owner, safe_payload)
        return ScheduleResponse(
            bleach_cursor=result.bleach_cursor,
            winning_seed=winning_seed,
            assignments=assignments,
            total_penalty=result.total_penalty,
            stats=result.stats,
            excel=excel_b64,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


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


def _latest_schedule_for(payload: dict) -> dict | None:
    candidates: List[dict] = []
    for owner in _schedule_owners(payload):
        data = get_latest_schedule(owner)
        if isinstance(data, dict):
            candidates.append(data)
    if not candidates:
        return None
    return max(candidates, key=lambda d: _parse_generated_at(d.get("generated_at")))


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
        raise HTTPException(status_code=400, detail=f"Failed to load config: {exc}") from exc


@router.post("/configs/save")
def save_config(request: SaveConfigRequest, payload: dict = Depends(require_auth)) -> dict:
    owner = _config_owner(payload)
    filename = request.filename.strip() if request.filename else ""
    if not filename:
        filename = f"{_slugify(request.payload.clinic.name)}.json"
    if not filename.endswith(".json"):
        filename += ".json"
    try:
        save_user_config(owner, Path(filename).name, request.payload.dict())
        return {"status": "saved", "filename": filename}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to save config: {exc}") from exc


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
def export_schedule_csv(payload: dict = Depends(require_auth)):
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

    return PlainTextResponse(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="schedule.csv"'},
    )


@router.post("/schedule/import/csv")
async def import_schedule_csv(request: Request, payload: dict = Depends(require_auth)) -> dict:
    owner = _schedule_owner(payload)
    form = await request.form()
    file = form.get("file")
    if not file:
        raise HTTPException(status_code=400, detail="CSV file required")
    content = (await file.read()).decode("utf-8", errors="ignore")
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
    return {"status": "imported", "assignments": len(assignments)}


@router.get("/configs/export/{filename}")
def export_config(filename: str, payload: dict = Depends(require_auth)) -> dict:
    owner = _config_owner(payload)
    safe_name = Path(filename).name
    data = export_user_config(owner, safe_name)
    if data is None:
        raise HTTPException(status_code=404, detail="Config not found")
    encoded = base64.b64encode(json.dumps(data, default=str).encode("utf-8")).decode("utf-8")
    return {"filename": safe_name, "payload": data, "encoded": encoded}


@router.post("/configs/import")
def import_config(request: SaveConfigRequest, payload: dict = Depends(require_auth)) -> dict:
    owner = _config_owner(payload)
    filename = request.filename.strip() if request.filename else ""
    if not filename:
        filename = f"{_slugify(request.payload.clinic.name)}.config"
    try:
        import_user_config(owner, Path(filename).name, request.payload.dict())
        return {"status": "imported", "filename": filename}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to import config: {exc}") from exc


app.include_router(router)
