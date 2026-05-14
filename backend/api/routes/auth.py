from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from backend.auth_db import (
    create_invite,
    delete_user,
    list_audit,
    list_users,
    log_event,
    redeem_invite,
    reset_invite,
    revoke_invite,
    update_last_login,
    update_role,
    validate_login,
)

from ..dependencies import encode_token, make_token_payload, require_admin, require_auth, token_response
from ..request_context import (
    clear_login_failures,
    is_locked_out,
    login_key,
    rate_limit,
    record_login_failure,
    request_meta,
)
from ..schemas import InviteRequest, LoginRequest, LoginResponse, SetupRequest, UserInfo

router = APIRouter(prefix="/api")


@router.post(
    "/auth/login",
    response_model=LoginResponse,
    dependencies=[Depends(rate_limit("login", limit=10, window_seconds=60))],
)
def login(request: Request, creds: LoginRequest) -> LoginResponse:
    lock_key = login_key(request, creds.username)
    if is_locked_out(lock_key):
        raise HTTPException(status_code=429, detail="Too many failed login attempts")
    user = validate_login(creds.username, creds.password)
    if not user:
        ip, ip_v4, user_agent, location = request_meta(request)
        detail = f"username={creds.username};result=fail;reason=invalid_credentials"
        log_event(None, "login_fail", detail, ip, user_agent, location, ip_v4)
        record_login_failure(lock_key)
        raise HTTPException(status_code=401, detail="Invalid credentials or license")
    clear_login_failures(lock_key)
    update_last_login(user["id"])
    token = encode_token(make_token_payload(user))
    ip, ip_v4, user_agent, location = request_meta(request)
    detail = f"username={user['username']};method=password"
    log_event(user["id"], "login_success", detail, ip, user_agent, location, ip_v4)
    return token_response(token)


@router.post("/auth/invite", response_model=LoginResponse, dependencies=[Depends(require_admin)])
def invite_user(request: Request, req: InviteRequest, payload: dict = Depends(require_admin)) -> dict:
    creator = payload.get("sub")
    try:
        creator_id = int(creator) if creator is not None else None
    except Exception:
        creator_id = None
    token = create_invite(req.username, req.license_key, role=req.role or "user", created_by=creator_id)
    ip, ip_v4, user_agent, location = request_meta(request)
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
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired invite token")
    token = encode_token(make_token_payload(user))
    ip, ip_v4, user_agent, location = request_meta(request)
    log_event(user["id"], "login_success", "invite_setup", ip, user_agent, location, ip_v4)
    return token_response(token)


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
        ip, ip_v4, user_agent, location = request_meta(request)
        log_event(None, "user_deleted", f"user_id={user_id}", ip, user_agent, location, ip_v4)
        return {"status": "deleted", "id": user_id}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/auth/invite/revoke", dependencies=[Depends(require_admin)])
def revoke_invite_admin(request: Request, req: InviteRequest):
    revoke_invite(req.username)
    ip, ip_v4, user_agent, location = request_meta(request)
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
        ip, ip_v4, user_agent, location = request_meta(request)
        log_event(payload.get("sub"), "role_updated", f"user_id={user_id}, role={role}", ip, user_agent, location, ip_v4)
        return {"status": "ok", "id": user_id, "role": role}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/auth/users/{user_id}/reset", dependencies=[Depends(require_admin)])
def reset_user_invite(request: Request, user_id: int, payload: dict = Depends(require_auth)):
    creator = payload.get("sub")
    try:
        creator_id = int(creator) if creator is not None else None
    except Exception:
        creator_id = None
    try:
        token = reset_invite(user_id, created_by=creator_id)
        ip, ip_v4, user_agent, location = request_meta(request)
        log_event(creator_id, "reset_invite", f"user_id={user_id}", ip, user_agent, location, ip_v4)
        return {"token": token}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
