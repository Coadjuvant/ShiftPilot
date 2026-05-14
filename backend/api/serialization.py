from __future__ import annotations

import re
from datetime import date, datetime
from typing import Callable

from backend.scheduler.model import Assignment, PTOEntry, ScheduleResult, ScheduleSlot, StaffMember


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (value or "schedule").strip().lower()).strip("-")
    return slug or "schedule"


def owner_candidates(payload: dict) -> list[str]:
    candidates: list[str] = []
    for key in ("sub", "username"):
        value = payload.get(key)
        if value is not None:
            text = str(value).strip()
            if text and text not in candidates:
                candidates.append(text)
    return candidates or ["public"]


def config_owner(payload: dict) -> str:
    return owner_candidates(payload)[0]


def schedule_owners(payload: dict) -> list[str]:
    return owner_candidates(payload)


def parse_generated_at(value: object) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return datetime.min
    return datetime.min


def latest_schedule_for(payload: dict, loader: Callable[[str], dict | None]) -> dict | None:
    schedules = [data for owner in schedule_owners(payload) if (data := loader(owner))]
    if not schedules:
        return None
    return max(schedules, key=lambda item: parse_generated_at(item.get("generated_at")))


def _parse_schedule_date(value: object) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def hydrate_schedule_result(data: dict) -> tuple[ScheduleResult, dict[str, StaffMember]]:
    staff = {
        str(item.get("id")): StaffMember(
            id=str(item.get("id")),
            name=str(item.get("name") or item.get("id")),
            role=str(item.get("role") or "Tech"),
        )
        for item in data.get("staff", [])
        if item.get("id") is not None
    }
    assignments: list[Assignment] = []
    for item in data.get("assignments", []):
        slot = ScheduleSlot(
            day_index=0,
            date=_parse_schedule_date(item.get("date")),
            day_name=str(item.get("day_name") or ""),
            role=str(item.get("role") or "Tech"),
            duty=str(item.get("duty") or ""),
            slot_index=int(item.get("slot_index") or 0),
            is_bleach=bool(item.get("is_bleach")),
        )
        assignments.append(
            Assignment(
                slot=slot,
                staff_id=item.get("staff_id"),
                notes=list(item.get("notes") or []),
            )
        )
    result = ScheduleResult(
        assignments=assignments,
        bleach_cursor=int(data.get("bleach_cursor") or 0),
        total_penalty=float(data.get("total_penalty") or 0),
        stats=dict(data.get("stats") or {}),
        seed=data.get("winning_seed"),
    )
    return result, staff


def hydrate_pto_entries(data: dict) -> list[PTOEntry]:
    entries: list[PTOEntry] = []
    for item in data.get("pto", []):
        staff_id = item.get("staff_id")
        pto_date = item.get("date")
        if not staff_id or not pto_date:
            continue
        entries.append(PTOEntry(staff_id=str(staff_id), date=_parse_schedule_date(pto_date)))
    return entries


def schedule_date_range(data: dict) -> str:
    dates = [_parse_schedule_date(item.get("date")) for item in data.get("assignments", []) if item.get("date")]
    if not dates:
        start = data.get("start_date")
        weeks = int(data.get("weeks") or 0)
        if not start or not weeks:
            return ""
        start_date = _parse_schedule_date(start)
        end_date = date.fromordinal(start_date.toordinal() + weeks * 7 - 2)
    else:
        start_date = min(dates)
        end_date = max(dates)
    if start_date == end_date:
        return start_date.isoformat()
    return f"{start_date.isoformat()}-to-{end_date.isoformat()}"
