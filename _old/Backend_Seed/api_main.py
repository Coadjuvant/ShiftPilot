# Backend_Seed/api_main.py
from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel
from typing import Dict, List, Optional
from datetime import date as _date

from scheduler_app.engine.generate_v2 import tournament

app = FastAPI()

class GenerateRequest(BaseModel):
    config: Dict
    start: str
    weeks: int
    trials: int = 20
    pto_path: Optional[str] = None           # legacy optional
    pto_rows: Optional[List[Dict[str, str]]] = None  # NEW

@app.get("/health")
def health():
    return {"ok": True}

@app.post("/validate")
def validate(payload: Dict):
    cfg = (payload or {}).get("config") or {}
    # accept major version 2 (e.g., "2" or "2.1") — default to "2" if missing
    ver = str(cfg.get("config_version", "2")).strip()
    major = ver.split(".")[0] if ver else "2"
    if major != "2":
        raise HTTPException(status_code=400, detail="config_version must be '2'")
    for key in ["roles","staff","patient_shifts","coverage","week_pattern","constraints"]:
        if key not in cfg:
            raise HTTPException(status_code=400, detail=f"Missing key: {key}")
    return JSONResponse({"ok": True})

@app.post("/generate")
def generate(req: GenerateRequest):
    try:
        start = _date.fromisoformat(req.start)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid start date (YYYY-MM-DD)")
    # optional lightweight validation
    _ = validate({"config": req.config})
    excel_bytes = tournament(
        req.config, start, req.weeks, req.pto_path, trials=req.trials, pto_rows=req.pto_rows
    )
    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
