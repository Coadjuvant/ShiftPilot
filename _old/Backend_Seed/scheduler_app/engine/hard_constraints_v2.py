from __future__ import annotations
from datetime import timedelta
from typing import Dict, Any

from .state import worked_days_in_week, current_streak_len

def _role_day_cap_ok(state, cfg, sid: str, slot) -> bool:
    cap = cfg.get("constraints", {}).get("max_shifts_per_day_by_role", {})
    limit = int(cap.get(slot["role"], 999))
    return state["per_day_role_count"][sid][slot["day"]][slot["role"]] < limit

def _same_day_gap_ok(state, cfg, sid: str, slot) -> bool:
    gap = float(cfg.get("constraints", {}).get("min_gap_same_day_hours", 0.0))
    if gap <= 0: 
        return True
    last_end = state["last_end_same_day"][sid][slot["day"]]
    return (not last_end) or ((slot["start_dt"] - last_end) >= timedelta(hours=gap))

def _streak_ok(state, cfg, sid: str, slot) -> bool:
    max_consec = int(cfg.get("constraints", {}).get("max_consecutive_days", 0))
    if max_consec <= 0: 
        return True
    return current_streak_len(state, sid, slot["day"]) < max_consec

def _weekdays_ok(state, cfg, sid: str, slot) -> bool:
    cst = cfg.get("constraints", {})
    wd = cst.get("work_days_week", None)
    if not wd:
        max_wk = int(cst.get("max_work_days_per_week", 0))
        if max_wk <= 0:
            return True
        return worked_days_in_week(state, sid, slot["day"]) < max_wk or slot["day"] in state["worked_day"][sid]
    mode = str(wd.get("mode", "hard")).lower()
    if mode == "off":
        return True
    by_role = wd.get("by_role", {})
    per_person = wd.get("per_person", {})
    target = int(per_person.get(sid, 0) or by_role.get(slot["role"], 0) or 999999)
    if target <= 0:
        return True
    days_now = worked_days_in_week(state, sid, slot["day"])
    if mode == "hard":
        return (days_now < target) or (slot["day"] in state["worked_day"][sid])
    else:
        return True

def can_assign(state, cfg: Dict[str, Any], sid: str, slot) -> bool:
    return (
        _role_day_cap_ok(state, cfg, sid, slot)
        and _same_day_gap_ok(state, cfg, sid, slot)
        and _streak_ok(state, cfg, sid, slot)
        and _weekdays_ok(state, cfg, sid, slot)
    )
