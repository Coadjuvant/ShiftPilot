from __future__ import annotations

from datetime import datetime, timedelta

import jwt
from fastapi import Depends, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from .settings import API_KEY, ADMIN_USER, IS_PROD, JWT_EXPIRE_HOURS, JWT_SECRET


def decode_jwt(token: str) -> dict:
    return jwt.decode(token, JWT_SECRET, algorithms=["HS256"])


def require_auth(
    request: Request,
    authorization: str = Header(default=None),
    x_api_key: str = Header(default=None, alias="x-api-key"),
) -> dict:
    expected_key = API_KEY
    allow_public = not expected_key and not ADMIN_USER
    token = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
    if not token:
        token = request.cookies.get("auth_token")
    if token:
        try:
            return decode_jwt(token)
        except Exception:
            raise HTTPException(status_code=401, detail="Invalid token")
    if expected_key:
        if x_api_key == expected_key:
            return {"sub": "api-key"}
        raise HTTPException(status_code=401, detail="Unauthorized")
    if allow_public:
        return {"sub": "public"}
    raise HTTPException(status_code=401, detail="Unauthorized")


def require_admin(payload: dict = Depends(require_auth)) -> dict:
    if payload.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    return payload


def make_token_payload(user: dict) -> dict:
    return {
        "sub": str(user["id"]),
        "username": user["username"],
        "role": user.get("role", "user"),
        "iat": datetime.utcnow(),
        "exp": datetime.utcnow() + timedelta(hours=JWT_EXPIRE_HOURS),
    }


def encode_token(payload: dict) -> str:
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def token_response(token: str) -> JSONResponse:
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
