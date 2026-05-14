from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request

from backend.auth_db import (
    delete_config as delete_user_config,
    export_config as export_user_config,
    import_config as import_user_config,
    list_configs as list_user_configs,
    load_config as load_user_config,
    log_event,
    save_config as save_user_config,
)

from ..dependencies import require_auth
from ..request_context import request_meta
from ..schemas import ConfigPayload, SaveConfigRequest
from ..serialization import config_owner, slugify
from ..settings import IS_PROD

router = APIRouter(prefix="/api")


def _safe_error(message: str, exc: Exception) -> str:
    return message if IS_PROD else f"{message}: {exc}"


@router.get("/configs")
def list_configs(payload: dict = Depends(require_auth)) -> List[str]:
    owner = config_owner(payload)
    return list_user_configs(owner)


@router.get("/configs/{filename}", response_model=ConfigPayload)
def load_config(filename: str, payload: dict = Depends(require_auth)) -> ConfigPayload:
    owner = config_owner(payload)
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
    owner = config_owner(payload)
    filename = body.filename.strip() if body.filename else ""
    if not filename:
        filename = f"{slugify(body.payload.clinic.name)}.json"
    if not filename.endswith(".json"):
        filename += ".json"
    try:
        payload_dict = body.payload.dict()
        safe_name = Path(filename).name
        save_user_config(owner, safe_name, payload_dict)
        size_kb = round(len(json.dumps(payload_dict, default=str)) / 1024, 1)
        ip, ip_v4, user_agent, location = request_meta(request)
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


@router.get("/configs/export/{filename}")
def export_config(request: Request, filename: str, payload: dict = Depends(require_auth)) -> dict:
    owner = config_owner(payload)
    safe_name = Path(filename).name
    data = export_user_config(owner, safe_name)
    if data is None:
        raise HTTPException(status_code=404, detail="Config not found")
    encoded = base64.b64encode(json.dumps(data, default=str).encode("utf-8")).decode("utf-8")
    ip, ip_v4, user_agent, location = request_meta(request)
    log_event(payload.get("sub"), "config_export", f"config={safe_name}", ip, user_agent, location, ip_v4)
    return {"filename": safe_name, "payload": data, "encoded": encoded}


@router.post("/configs/import")
def import_config(request: Request, body: SaveConfigRequest, payload: dict = Depends(require_auth)) -> dict:
    owner = config_owner(payload)
    filename = body.filename.strip() if body.filename else ""
    if not filename:
        filename = f"{slugify(body.payload.clinic.name)}.config"
    try:
        safe_name = Path(filename).name
        payload_dict = body.payload.dict()
        import_user_config(owner, safe_name, payload_dict)
        size_kb = round(len(json.dumps(payload_dict, default=str)) / 1024, 1)
        ip, ip_v4, user_agent, location = request_meta(request)
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


@router.delete("/configs/{filename}")
def delete_config(request: Request, filename: str, payload: dict = Depends(require_auth)) -> dict:
    owner = config_owner(payload)
    safe_name = Path(filename).name
    try:
        delete_user_config(owner, safe_name)
        ip, ip_v4, user_agent, location = request_meta(request)
        log_event(payload.get("sub"), "config_delete", f"config={safe_name}", ip, user_agent, location, ip_v4)
        return {"status": "deleted", "filename": safe_name}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=_safe_error("Failed to delete config", exc)) from exc
