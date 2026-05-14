from __future__ import annotations

import base64
import json
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from backend.auth_db import get_latest_schedule, log_event, save_schedule as persist_schedule
from backend.scheduler import (
    ConstraintToggles,
    DailyRequirement,
    ScheduleConfig,
    StaffMember,
    StaffPreferences,
    export_schedule_to_excel,
    run_tournament,
)
from backend.scheduler.engine import OPEN_LABEL
from backend.scheduler.model import DAYS, PTOEntry

from ..dependencies import require_auth
from ..request_context import rate_limit, request_meta
from ..schemas import AssignmentOut, ScheduleRequest, ScheduleResponse, StaffMemberIn
from ..serialization import (
    hydrate_pto_entries,
    hydrate_schedule_result,
    latest_schedule_for,
    schedule_date_range,
    schedule_owners,
    slugify,
)
from ..settings import IS_PROD

router = APIRouter(prefix="/api")


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


def _serialize_assignments(assignments: list[AssignmentOut]) -> list[dict]:
    return [
        {
            "date": item.date.isoformat() if hasattr(item, "date") else getattr(item, "date", None),
            "day_name": getattr(item, "day_name", None),
            "role": getattr(item, "role", None),
            "duty": getattr(item, "duty", None),
            "staff_id": getattr(item, "staff_id", None),
            "notes": getattr(item, "notes", []),
            "slot_index": getattr(item, "slot_index", None),
            "is_bleach": getattr(item, "is_bleach", False),
        }
        for item in assignments
    ]


@router.post(
    "/schedule/run",
    response_model=ScheduleResponse,
    dependencies=[Depends(require_auth), Depends(rate_limit("schedule_run", limit=8, window_seconds=60))],
)
def run_schedule(
    http_request: Request,
    body: ScheduleRequest,
    payload: dict = Depends(require_auth),
) -> ScheduleResponse:
    try:
        staff_members = [_to_staff_member(staff) for staff in body.staff]
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
            for req in body.requirements
        ]
        if len(requirements) != len(DAYS):
            raise ValueError("Requirements must include all clinic days (Mon-Sat).")
        if body.config.start_date.weekday() != 0:
            selected = body.config.start_date.isoformat()
            weekday = body.config.start_date.strftime("%A")
            raise HTTPException(
                status_code=422,
                detail=(
                    "Schedule failed: start date must be a Monday for Mon-Sat demand templates. "
                    f"You selected {selected} ({weekday}). "
                    "Suggested fix: choose the Monday for that schedule week, then run again."
                ),
            )
        toggles = ConstraintToggles(**body.config.toggles.dict())
        config = ScheduleConfig(
            clinic_name=body.config.clinic_name,
            timezone=body.config.timezone,
            start_date=body.config.start_date,
            weeks=body.config.weeks,
            bleach_day=body.config.bleach_day,
            bleach_rotation=body.config.bleach_rotation,
            bleach_cursor=body.config.bleach_cursor,
            bleach_frequency=body.config.bleach_frequency,
            patients_per_tech=body.config.patients_per_tech,
            patients_per_rn=body.config.patients_per_rn,
            techs_per_rn=body.config.techs_per_rn,
            toggles=toggles,
        )
        pto_entries = [PTOEntry(staff_id=item.staff_id, date=item.date) for item in body.pto]
        if not body.export_roles:
            raise HTTPException(status_code=400, detail="Select at least one export role.")
        active_roles = body.export_roles
        result, winning_seed = run_tournament(
            staff_members,
            requirements,
            config,
            pto_entries=pto_entries,
            trials=body.tournament_trials,
            base_seed=body.base_seed,
            scheduled_roles=active_roles,
            score_roles=active_roles,
        )
        essential_float_slots: List[str] = []
        for assignment in result.assignments:
            slot = assignment.slot
            if slot.role != "Tech":
                continue
            duty = (slot.duty or "").strip().lower()
            if duty not in {"open", "close"}:
                continue
            staff_raw = "" if assignment.staff_id is None else str(assignment.staff_id).strip()
            staff_norm = staff_raw.upper()
            if not staff_raw or staff_norm in {"OPEN", str(OPEN_LABEL).upper()}:
                duty_label = "Close (Bleach)" if slot.is_bleach else duty.capitalize()
                essential_float_slots.append(f"{slot.date.isoformat()} {slot.day_name} {duty_label}")
        if essential_float_slots:
            preview = ", ".join(essential_float_slots[:6])
            if len(essential_float_slots) > 6:
                preview += f", +{len(essential_float_slots) - 6} more"
            raise HTTPException(
                status_code=422,
                detail=(
                    "Schedule failed: essential opener/closer coverage became FLOAT. "
                    f"Affected slots: {preview}. "
                    "Suggested fix: add Tech staff who can open/close (and bleach-capable closer on bleach day), "
                    "reduce open/close demand for the affected days, or lower conflicting hard constraints set to 10."
                ),
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
        excel_bytes = export_schedule_to_excel(
            result,
            {staff.id: staff for staff in staff_members},
            export_roles=body.export_roles,
            pto_entries=pto_entries,
        )
        excel_b64 = base64.b64encode(excel_bytes).decode("utf-8")
        schedule_payload = {
            "clinic_name": body.config.clinic_name,
            "timezone": body.config.timezone,
            "start_date": body.config.start_date.isoformat()
            if hasattr(body.config.start_date, "isoformat")
            else body.config.start_date,
            "weeks": body.config.weeks,
            "bleach_frequency": body.config.bleach_frequency,
            "toggles": body.config.toggles.dict(),
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
                for req in body.requirements
            ],
            "assignments": _serialize_assignments(assignments),
            "staff": [{"id": staff.id, "name": staff.name, "role": staff.role} for staff in staff_members],
            "stats": result.stats,
            "total_penalty": result.total_penalty,
            "winning_seed": winning_seed,
            "bleach_cursor": result.bleach_cursor,
            "export_roles": body.export_roles,
            "tournament_trials": body.tournament_trials,
            "pto": [
                {
                    "staff_id": item.staff_id,
                    "date": item.date.isoformat() if hasattr(item.date, "isoformat") else item.date,
                }
                for item in body.pto
            ],
            "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }
        safe_payload = json.loads(json.dumps(schedule_payload, default=str))
        for owner in schedule_owners(payload):
            persist_schedule(owner, safe_payload)
        open_slots = sum(
            1
            for assignment in assignments
            if (
                assignment.staff_id is None
                or str(assignment.staff_id).strip().upper() in {"OPEN", str(OPEN_LABEL).upper()}
            )
        )
        start_label = (
            body.config.start_date.isoformat()
            if hasattr(body.config.start_date, "isoformat")
            else str(body.config.start_date)
        )
        detail = (
            f"clinic={body.config.clinic_name};start={start_label};weeks={body.config.weeks};"
            f"bleach={body.config.bleach_frequency or 'weekly'};seed={winning_seed};open_slots={open_slots}"
        )
        ip, ip_v4, user_agent, location = request_meta(http_request)
        log_event(payload.get("sub"), "schedule_run", detail, ip, user_agent, location, ip_v4)
        return ScheduleResponse(
            bleach_cursor=result.bleach_cursor,
            winning_seed=winning_seed,
            assignments=assignments,
            total_penalty=result.total_penalty,
            stats=result.stats,
            excel=excel_b64,
        )
    except HTTPException as exc:
        raise exc
    except Exception as exc:
        detail = str(exc) if not IS_PROD else "Invalid schedule request"
        raise HTTPException(status_code=400, detail=detail) from exc


@router.get("/schedule/latest")
def latest_schedule(response: Response, payload: dict = Depends(require_auth)) -> dict:
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    data = latest_schedule_for(payload, get_latest_schedule)
    if not data:
        return {"status": "none"}
    return data


@router.get("/schedule/export/csv")
def export_schedule_csv(request: Request, payload: dict = Depends(require_auth)):
    raise HTTPException(status_code=501, detail="CSV export is disabled for now")


@router.get("/schedule/export/excel")
def export_schedule_excel(request: Request, payload: dict = Depends(require_auth)):
    data = latest_schedule_for(payload, get_latest_schedule)
    if not data or not data.get("assignments"):
        raise HTTPException(status_code=404, detail="No saved schedule")
    result, staff = hydrate_schedule_result(data)
    pto_entries = hydrate_pto_entries(data)
    excel_bytes = export_schedule_to_excel(
        result,
        staff,
        export_roles=data.get("export_roles"),
        pto_entries=pto_entries,
    )
    clinic_name = data.get("clinic_name") or "schedule"
    range_label = schedule_date_range(data)
    filename = (
        f"{slugify(clinic_name)}-{range_label}.xlsx" if range_label else f"{slugify(clinic_name)}.xlsx"
    )
    ip, ip_v4, user_agent, location = request_meta(request)
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
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Content-Type-Options": "nosniff",
            "X-Download-Options": "noopen",
            "Cache-Control": "no-store, must-revalidate",
        },
    )


@router.post("/schedule/import/csv")
async def import_schedule_csv(request: Request, payload: dict = Depends(require_auth)) -> dict:
    raise HTTPException(status_code=501, detail="CSV import is disabled for now")
