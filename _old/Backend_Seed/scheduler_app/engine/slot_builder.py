# Backend_Seed/scheduler_app/engine/slot_builder.py
from __future__ import annotations
from datetime import datetime, timedelta, date
from typing import List, Dict, Any
try:
    from zoneinfo import ZoneInfo
except Exception:
    from backports.zoneinfo import ZoneInfo  # type: ignore

DOWS = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]

def iter_dates(start: date, weeks: int) -> List[date]:
    days = max(1, int(weeks)) * 7
    return [start + timedelta(days=i) for i in range(days)]

def _make_local_dt(d: date, hhmm: str, tz: ZoneInfo) -> datetime:
    hh, mm = map(int, hhmm.split(":"))
    return datetime(d.year, d.month, d.day, hh, mm, tzinfo=tz)

def build_slots_v2(cfg: Dict[str, Any], start: date, weeks: int) -> List[Dict[str, Any]]:
    tz = ZoneInfo(cfg.get("clinic", {}).get("timezone", "America/Chicago"))
    shift_defs = {s["name"]: s for s in cfg.get("patient_shifts", [])}
    coverage = {c["shift"]: list(c.get("requirements", [])) for c in cfg.get("coverage", [])}
    week_pattern: Dict[str, list] = {k: list(v) for k, v in cfg.get("week_pattern", {}).items()}
    slots: List[Dict[str, Any]] = []
    for d in iter_dates(start, weeks):
        dow = DOWS[d.weekday()]
        for shift_name in week_pattern.get(dow, []):
            sd = shift_defs.get(shift_name)
            if not sd:
                continue
            start_dt = _make_local_dt(d, sd["start"], tz)
            end_dt = _make_local_dt(d, sd["end"], tz)
            if sd.get("spans_midnight"):
                end_dt += timedelta(days=1)
            for req in coverage.get(shift_name, []):
                role = req["role"]
                label = req.get("label", role)
                duty = (req.get("duty") or None)  # "open"|"close"|"bleach"|None
                count = int(req.get("count", 0))
                for idx in range(1, count+1):
                    slots.append({
                        "day": d, "date_str": d.strftime("%Y-%m-%d"),
                        "shift": shift_name, "role": role, "label": label, "idx": idx,
                        "start_dt": start_dt, "end_dt": end_dt,
                        "duty": duty,
                    })
    return slots
