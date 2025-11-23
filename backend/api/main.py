from __future__ import annotations

from typing import List
from pathlib import Path
import json
import re
import base64

from fastapi import APIRouter, FastAPI, HTTPException
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
from .schemas import (
    AssignmentOut,
    ConfigPayload,
    SaveConfigRequest,
    ScheduleRequest,
    ScheduleResponse,
    StaffMemberIn,
)


app = FastAPI(title="Clinic Scheduler API", version="0.1.0")
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


@router.post("/schedule/run", response_model=ScheduleResponse)
def run_schedule(request: ScheduleRequest) -> ScheduleResponse:
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
        excel_bytes = export_schedule_to_excel(result, {s.id: s for s in staff_members})
        excel_b64 = base64.b64encode(excel_bytes).decode("utf-8")
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


CONFIG_ROOT = Path("configs")


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", name).strip("-").lower()
    return slug or "clinic"


@router.get("/configs")
def list_configs() -> List[str]:
    CONFIG_ROOT.mkdir(parents=True, exist_ok=True)
    return sorted([p.name for p in CONFIG_ROOT.glob("*.json")])


@router.get("/configs/{filename}", response_model=ConfigPayload)
def load_config(filename: str) -> ConfigPayload:
    path = CONFIG_ROOT / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="Config not found")
    try:
        data = json.loads(path.read_text())
        return ConfigPayload(**data)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to load config: {exc}") from exc


@router.post("/configs/save")
def save_config(request: SaveConfigRequest) -> dict:
    CONFIG_ROOT.mkdir(parents=True, exist_ok=True)
    filename = request.filename.strip() if request.filename else ""
    if not filename:
        filename = f"{_slugify(request.payload.clinic.name)}.json"
    if not filename.endswith(".json"):
        filename += ".json"
    path = CONFIG_ROOT / filename
    try:
        path.write_text(json.dumps(request.payload.dict(), indent=2, default=str))
        return {"status": "saved", "filename": filename}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to save config: {exc}") from exc


app.include_router(router)
