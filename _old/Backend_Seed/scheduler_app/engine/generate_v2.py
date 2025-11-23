from __future__ import annotations

from typing import List, Tuple, Dict, Any, Set, Optional, Iterable
from datetime import date, timedelta
from io import BytesIO
from pathlib import Path
import csv
from collections import defaultdict

from .slot_builder import build_slots_v2
from .state import new_state, mark_assigned, worked_days_in_week
from .hard_constraints_v2 import can_assign
from ..io.export_weekgrid import export_excel

DOWS = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]

# -----------------------------
# PTO helpers (rows or CSV)
# -----------------------------
def _load_pto_rows(pto_rows: Iterable[Dict[str, str]] | None) -> Dict[str, Set[date]]:
    pto: Dict[str, Set[date]] = {}
    if not pto_rows:
        return pto
    for row in pto_rows:
        sid = str(row.get("id","")).strip()
        dstr = str(row.get("date","")).strip()
        if not sid or not dstr:
            continue
        try:
            d = date.fromisoformat(dstr)
        except Exception:
            continue
        pto.setdefault(sid, set()).add(d)
    return pto

def _load_pto_csv(pto_path: Optional[str]) -> Dict[str, Set[date]]:
    pto: Dict[str, Set[date]] = {}
    if not pto_path:
        return pto
    p = Path(pto_path)
    if not p.exists() or not p.is_file():
        return pto
    with p.open("r", newline="", encoding="utf-8") as f:
        rdr = csv.DictReader(f)
        for row in rdr:
            sid = str(row.get("id","")).strip()
            dstr = str(row.get("date","")).strip()
            if not sid or not dstr:
                continue
            try:
                d = date.fromisoformat(dstr)
            except Exception:
                continue
            pto.setdefault(sid, set()).add(d)
    return pto

# -----------------------------
# Basic helpers
# -----------------------------
def _duty_capable(person: Dict[str, Any], duty: Optional[str]) -> bool:
    if not duty:
        return True
    prefs = person.get("preferences", {}) or {}
    key = {"open":"can_open","close":"can_close","bleach":"can_bleach"}.get(duty)
    return bool(prefs.get(key, False)) if key else True

def _is_pto(pto: Dict[str, Set[date]], sid: str, d: date) -> bool:
    return d in pto.get(sid, set())

def _soft_weekday_penalty(cfg: Dict[str, Any], state, sid: str, slot) -> float:
    wd_cfg = cfg.get("constraints", {}).get("work_days_week", {})
    if str(wd_cfg.get("mode", "")).lower() != "soft":
        return 0.0
    by_role = wd_cfg.get("by_role", {})
    per_person = wd_cfg.get("per_person", {})
    target = int(per_person.get(sid, 0) or by_role.get(slot["role"], 0) or 0)
    if target <= 0:
        return 0.0
    weight = float(cfg.get("constraints", {}).get("soft_weights", {}).get("exceed_week_days", 1.0))
    # count days already worked in this ISO week; if this new slot adds a NEW day over target, penalize
    from .state import worked_days_in_week
    days_now = worked_days_in_week(state, sid, slot["day"])
    if (slot["day"] not in state["worked_day"][sid]) and (target and days_now >= target):
        return weight
    return 0.0

# -----------------------------
# Assignment primitives
# -----------------------------
def _eligible_staff_ids(staff: List[Dict[str, Any]], role: str) -> List[str]:
    return [str(p.get("id","")).strip() for p in staff if role in (p.get("roles") or []) and str(p.get("id","")).strip()]

def _staff_by_id(staff: List[Dict[str, Any]]) -> Dict[str, Dict[str,Any]]:
    return {str(p.get("id","")).strip(): p for p in staff if str(p.get("id","")).strip()}

# -----------------------------
# Generate (day-ordered with bleach strictness)
# -----------------------------
def generate(
    cfg: Dict[str, Any],
    start: date,
    weeks: int,
    *,
    pto: Optional[Dict[str, Set[date]]] = None
) -> List[Tuple[dict, Optional[str]]]:

    pto = pto or {}
    slots = build_slots_v2(cfg, start, weeks)
    state = new_state()

    staff: List[Dict[str, Any]] = [p for p in cfg.get("staff", []) if str(p.get("id","")).strip()]
    by_id = _staff_by_id(staff)

    bleach_days_set = set((cfg.get("constraints", {}) or {}).get("bleach_days", []))
    rot_cfg = (cfg.get("constraints", {}) or {}).get("bleach_rotation", {}) or {}
    rot_order = [x for x in rot_cfg.get("order", []) if x in _eligible_staff_ids(staff, "Tech")]
    if not rot_order:
        rot_order = _eligible_staff_ids(staff, "Tech")  # natural order fallback
    rot_cursor = int(rot_cfg.get("cursor", 0)) % (len(rot_order) if rot_order else 1)

    # Pre-group slots by day and then by role, and keep global index
    day_to_indices: Dict[date, List[int]] = defaultdict(list)
    for i, s in enumerate(slots):
        day_to_indices[s["day"]].append(i)

    # Track forced next-day bans for bleachers
    ban_on_day: Dict[date, Set[str]] = defaultdict(set)

    assignments: List[Tuple[dict, Optional[str]]] = [(slot, None) for slot in slots]

    # Helper to test if a given staff can take a slot considering PTO, availability, role, ban, and hard constraints
    def _can_take(sid: str, slot: dict, *, respect_constraints: bool = True) -> bool:
        person = by_id.get(sid)
        if not person:
            return False
        # PTO
        if _is_pto(pto, sid, slot["day"]):
            return False
        # Next-day bleach ban (strict)
        if sid in ban_on_day.get(slot["day"], set()):
            return False
        # Availability
        dow = DOWS[slot["day"].weekday()]
        if not person.get("availability", {}).get(dow, True):
            return False
        # Role
        if slot["role"] not in (person.get("roles") or []):
            return False
        # Duty capability if present
        duty = (slot.get("duty") or "").lower() or None
        if duty and not _duty_capable(person, duty):
            return False
        # Hard constraints
        if respect_constraints and not can_assign(state, cfg, sid, slot):
            return False
        return True

    # Assign Techs and RNs/Admins day by day
    for d in sorted(day_to_indices.keys()):
        idxs = day_to_indices[d]
        # partition slots by role then sort by time
        tech_idxs = [i for i in idxs if slots[i]["role"] == "Tech"]
        tech_idxs.sort(key=lambda i: (slots[i]["start_dt"], slots[i]["end_dt"]))
        rn_idxs   = [i for i in idxs if slots[i]["role"] == "RN"]
        rn_idxs.sort(key=lambda i: (slots[i]["start_dt"], slots[i]["end_dt"]))
        adm_idxs  = [i for i in idxs if slots[i]["role"] == "Admin"]
        adm_idxs.sort(key=lambda i: (slots[i]["start_dt"], slots[i]["end_dt"]))

        # ------------ BLEACH closer (strict) ------------
        is_bleach_day = DOWS[d.weekday()] in bleach_days_set
        bleacher_sid: Optional[str] = None
        if is_bleach_day and tech_idxs:
            closer_idx = max(tech_idxs, key=lambda i: slots[i]["end_dt"])
            closer_slot = slots[closer_idx]
            closer_slot["duty"] = "bleach"  # mark duty

            # Choose by rotation among bleach-capable Techs
            tried = 0
            n = len(rot_order)
            chosen: Optional[str] = None
            violation_reason: Optional[str] = None

            while tried < n:
                candidate = rot_order[(rot_cursor + tried) % n]
                person = by_id.get(candidate)
                if person and (person.get("preferences", {}) or {}).get("can_bleach", False):
                    if _can_take(candidate, closer_slot, respect_constraints=True):
                        chosen = candidate
                        rot_cursor = (rot_cursor + tried + 1) % n
                        break
                tried += 1

            if not chosen:
                # Force pick by rotation ignoring hard constraints, but DO NOT ignore PTO/availability/role/ban/capability
                tried = 0
                while tried < n:
                    candidate = rot_order[(rot_cursor + tried) % n]
                    person = by_id.get(candidate)
                    if person and (person.get("preferences", {}) or {}).get("can_bleach", False):
                        if _can_take(candidate, closer_slot, respect_constraints=False):
                            chosen = candidate
                            violation_reason = "bleach_strict_override"
                            rot_cursor = (rot_cursor + tried + 1) % n
                            break
                    tried += 1

            if not chosen:
                # Absolute fallback: pick any assigned tech that day who can bleach (already placed later?) else any tech that can take
                # but since bleach is STRICT, we will try any bleach-capable tech ignoring constraints
                for sid in _eligible_staff_ids(staff, "Tech"):
                    if (by_id.get(sid, {}).get("preferences", {}) or {}).get("can_bleach", False):
                        if _can_take(sid, closer_slot, respect_constraints=False):
                            chosen = sid
                            violation_reason = "bleach_strict_override_any"
                            break

            if chosen:
                assignments[closer_idx] = (closer_slot, chosen)
                mark_assigned(state, closer_slot, chosen)
                bleacher_sid = chosen
                if violation_reason:
                    closer_slot.setdefault("notes", []).append(f"VIOLATION:{violation_reason}")
            else:
                # If we truly cannot assign (e.g., everyone PTO/unavailable), we still mark violation on slot
                closer_slot.setdefault("notes", []).append("VIOLATION:bleach_unfilled_impossible")

        # ------------ OPENER (prefer can_open) ------------
        if tech_idxs:
            opener_idx = min(tech_idxs, key=lambda i: slots[i]["start_dt"])
            if assignments[opener_idx][1] is None:  # not same as closer already
                opener_slot = slots[opener_idx]
                opener_slot.setdefault("tags", []).append("opener")
                # Prefer can_open=True
                candidates = [sid for sid in _eligible_staff_ids(staff, "Tech")
                              if (by_id.get(sid, {}).get("preferences", {}) or {}).get("can_open", False)]
                # First try with constraints
                chosen = None
                for sid in candidates:
                    if _can_take(sid, opener_slot, respect_constraints=True):
                        chosen = sid; break
                # Then relax hard constraints
                if not chosen:
                    for sid in candidates:
                        if _can_take(sid, opener_slot, respect_constraints=False):
                            chosen = sid
                            opener_slot.setdefault("notes", []).append("VIOLATION:open_strict_override")
                            break
                # If still none, try anyone
                if not chosen:
                    for sid in _eligible_staff_ids(staff, "Tech"):
                        if _can_take(sid, opener_slot, respect_constraints=True):
                            chosen = sid; break
                if not chosen:
                    for sid in _eligible_staff_ids(staff, "Tech"):
                        if _can_take(sid, opener_slot, respect_constraints=False):
                            chosen = sid
                            opener_slot.setdefault("notes", []).append("VIOLATION:open_strict_override_any")
                            break
                if chosen:
                    assignments[opener_idx] = (opener_slot, chosen)
                    mark_assigned(state, opener_slot, chosen)

        # ------------ Remaining TECH slots ------------
        for i in tech_idxs:
            if assignments[i][1] is not None:  # already filled (closer/opener)
                continue
            slot = slots[i]
            # try best candidate with score (simple: minimize soft penalties)
            best_sid = None
            best_score = 1e9
            for sid in _eligible_staff_ids(staff, "Tech"):
                if not _can_take(sid, slot, respect_constraints=True):
                    continue
                score = _soft_weekday_penalty(cfg, state, sid, slot)
                if score < best_score:
                    best_score = score
                    best_sid = sid
            if best_sid is None:
                # relax hard constraints
                for sid in _eligible_staff_ids(staff, "Tech"):
                    if _can_take(sid, slot, respect_constraints=False):
                        best_sid = sid
                        slot.setdefault("notes", []).append("VIOLATION:tech_strict_override")
                        break
            if best_sid:
                assignments[i] = (slot, best_sid)
                mark_assigned(state, slot, best_sid)

        # ------------ RN/Admin (greedy) ------------
        def _fill_simple(idxs, role: str):
            for i in idxs:
                if assignments[i][1] is not None:
                    continue
                slot = slots[i]
                chosen = None
                for sid in _eligible_staff_ids(staff, role):
                    if _can_take(sid, slot, respect_constraints=True):
                        chosen = sid; break
                if not chosen:
                    for sid in _eligible_staff_ids(staff, role):
                        if _can_take(sid, slot, respect_constraints=False):
                            chosen = sid
                            slot.setdefault("notes", []).append(f"VIOLATION:{role.lower()}_strict_override")
                            break
                if chosen:
                    assignments[i] = (slot, chosen)
                    mark_assigned(state, slot, chosen)

        _fill_simple(rn_idxs, "RN")
        _fill_simple(adm_idxs, "Admin")

        # ------------ Post-day: ban bleacher on next day ------------
        if bleacher_sid:
            next_day = d + timedelta(days=1)
            ban_on_day[next_day].add(bleacher_sid)

    return assignments

# -----------------------------
# Tournament wrapper
# -----------------------------
def _score_assignments(assignments: List[Tuple[dict, Optional[str]]]) -> Tuple[int, int]:
    open_count = sum(1 for _slot, sid in assignments if not sid)
    filled = len(assignments) - open_count
    return (open_count, -filled)

def tournament(
    cfg: Dict[str, Any],
    start: date,
    weeks: int,
    pto_path: str | None = None,
    trials: int = 20,
    *,
    pto_rows: List[Dict[str, str]] | None = None
) -> bytes:
    pto = _load_pto_rows(pto_rows) if pto_rows else _load_pto_csv(pto_path)
    trials = max(1, int(trials))
    best_assignments: List[Tuple[dict, Optional[str]]] | None = None
    best_score = (10**9, -10**9)

    for _ in range(trials):
        a = generate(cfg, start, weeks, pto=pto)
        s = _score_assignments(a)
        if s < best_score:
            best_score = s
            best_assignments = a

    buf = BytesIO()
    export_excel(best_assignments or [], cfg, start, weeks, buf)
    return buf.getvalue()
