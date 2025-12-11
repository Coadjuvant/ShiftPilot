from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Dict, Iterable, List, Optional, Sequence, Tuple
import random

from .model import (
    Assignment,
    DailyRequirement,
    DAYS,
    PTOEntry,
    ScheduleConfig,
    ScheduleResult,
    ScheduleSlot,
    StaffMember,
)

# Scheduler tuning knobs
FAIRNESS_WEIGHT = 0.5
BLEACH_PENALTY = 5.0  # discourage assigning bleach-capable techs outside rotation if avoidable
JITTER_SCALE = 1e-3
OPEN_LABEL = "OPEN"


@dataclass
class _StaffState:
    assignments: List[Assignment]
    worked_day_indices: List[int]
    last_bleach_day: Optional[int] = None
    last_saturday_week: Optional[int] = None
    week_assignments: Dict[int, set] = field(default_factory=lambda: defaultdict(set))

    def total_assignments(self) -> int:
        return len(self.assignments)


def _ensure_requirements(requirements: Sequence[DailyRequirement]) -> Dict[str, DailyRequirement]:
    req_map: Dict[str, DailyRequirement] = {}
    for req in requirements:
        req_map[req.day_name] = req
    missing = [d for d in DAYS if d not in req_map]
    if missing:
        raise ValueError(f"Missing requirements for day(s): {', '.join(missing)}")
    return req_map


def _week_and_day_index(idx: int) -> Tuple[int, int]:
    return divmod(idx, len(DAYS))


def _build_slots(requirements: Dict[str, DailyRequirement], cfg: ScheduleConfig) -> List[ScheduleSlot]:
    slots: List[ScheduleSlot] = []
    day_index = 0
    for week in range(cfg.weeks):
        for day_pos, day_name in enumerate(DAYS):
            req = requirements[day_name]
            # No admin coverage on Saturdays
            if day_name == "Sat" and req.admin_count:
                req = DailyRequirement(
                    day_name=req.day_name,
                    patient_count=req.patient_count,
                    tech_openers=req.tech_openers,
                    tech_mids=req.tech_mids,
                    tech_closers=req.tech_closers,
                    rn_count=req.rn_count,
                    admin_count=0,
                )
                requirements[day_name] = req
            # ensure tech counts meet patient ratios
            tech_total = req.tech_openers + req.tech_mids + req.tech_closers
            need_tech = math.ceil(req.patient_count / cfg.patients_per_tech) if cfg.patients_per_tech else 0
            if need_tech > tech_total:
                additional = need_tech - tech_total
                req = DailyRequirement(
                    day_name=req.day_name,
                    patient_count=req.patient_count,
                    tech_openers=req.tech_openers,
                    tech_mids=req.tech_mids + additional,
                    tech_closers=req.tech_closers,
                    rn_count=req.rn_count,
                    admin_count=req.admin_count,
                )
                requirements[day_name] = req
                tech_total += additional

            rn_min_from_tech = math.ceil(tech_total / cfg.techs_per_rn) if cfg.techs_per_rn else 0
            rn_min_from_patients = math.ceil(req.patient_count / cfg.patients_per_rn) if cfg.patients_per_rn else 0
            rn_needed = max(req.rn_count, rn_min_from_patients, rn_min_from_tech)
            if rn_needed != req.rn_count:
                req = DailyRequirement(
                    day_name=req.day_name,
                    patient_count=req.patient_count,
                    tech_openers=req.tech_openers,
                    tech_mids=req.tech_mids,
                    tech_closers=req.tech_closers,
                    rn_count=rn_needed,
                    admin_count=req.admin_count,
                )
                requirements[day_name] = req

            schedule_date = cfg.start_date + timedelta(days=week * 7 + day_pos)

            def add_slot(role: str, duty: str, count: int, *, bleach: bool = False):
                for idx in range(count):
                    slots.append(
                        ScheduleSlot(
                            day_index=day_index,
                            date=schedule_date,
                            day_name=day_name,
                            role=role,
                            duty=duty,
                            slot_index=idx + 1,
                            is_bleach=bleach and idx == 0,
                        )
                    )

            add_slot("Tech", "open", req.tech_openers)
            add_slot("Tech", "mid", req.tech_mids)
            bleach = False
            if req.tech_closers > 0:
                freq = (cfg.bleach_frequency or "weekly").lower()
                if freq == "weekly":
                    bleach = day_name == cfg.bleach_day
                elif freq == "quarterly":
                    # second week (index 1) of Feb/May/Aug/Nov using the schedule date month
                    if week == 1 and schedule_date.month in (2, 5, 8, 11) and day_name == cfg.bleach_day:
                        bleach = True
                else:
                    bleach = day_name == cfg.bleach_day
            add_slot("Tech", "close", req.tech_closers, bleach=bleach)
            add_slot("RN", "coverage", req.rn_count)
            add_slot("Admin", "coverage", req.admin_count)

            day_index += 1
    return slots


def _pto_lookup(pto_entries: Iterable[PTOEntry]) -> Dict[str, set]:
    out: Dict[str, set] = defaultdict(set)
    for entry in pto_entries:
        out[entry.staff_id].add(entry.date)
    return out


def _is_available(
    member: StaffMember,
    slot: ScheduleSlot,
    pto_dates: Dict[str, set],
) -> bool:
    if slot.day_name not in member.availability or not member.availability.get(slot.day_name, True):
        return False
    if slot.date in pto_dates.get(member.id, ()):
        return False
    if member.role != slot.role:
        return False
    if slot.role == "Tech":
        if slot.duty == "open" and not member.can_open:
            return False
        if slot.duty == "close" and not member.can_close:
            return False
        if slot.is_bleach and not member.can_bleach:
            return False
    return True


def _violates_toggles(
    member_state: _StaffState,
    slot: ScheduleSlot,
    cfg: ScheduleConfig,
    *,
    ignore_post_bleach: bool = False,
    ignore_week_cap: bool = False,
    ignore_three_day: bool = False,
    ignore_alt_sat: bool = False,
) -> bool:
    toggles = cfg.toggles
    week_idx, _ = _week_and_day_index(slot.day_index)
    # No three consecutive days
    if toggles.enforce_three_day_cap and not ignore_three_day:
        recent = sorted(member_state.worked_day_indices)
        if len(recent) >= 2:
            if slot.day_index - 1 in recent and slot.day_index - 2 in recent:
                return True
    # Rest after bleach (no day after)
    if toggles.enforce_post_bleach_rest and not ignore_post_bleach and member_state.last_bleach_day is not None:
        if slot.day_index == member_state.last_bleach_day + 1:
            return True
    # No consecutive Saturdays
    if toggles.enforce_alt_saturdays and not ignore_alt_sat and slot.day_name == "Sat":
        if member_state.last_saturday_week == week_idx - 1:
            return True
    if toggles.limit_tech_four_days and not ignore_week_cap and slot.role == "Tech":
        worked = member_state.week_assignments.get(week_idx, set())
        if slot.day_index not in worked and len(worked) >= 4:
            return True
    if toggles.limit_rn_four_days and not ignore_week_cap and slot.role == "RN":
        worked = member_state.week_assignments.get(week_idx, set())
        if slot.day_index not in worked and len(worked) >= 4:
            return True
    return False


def _preference_penalty(member: StaffMember, slot: ScheduleSlot) -> float:
    if slot.role != "Tech":
        return 1.0  # neutral for RN/Admin
    return member.preferences.weight_for(slot.duty, slot.day_name)


def _score_candidate(
    member_state: _StaffState,
    *,
    base_penalty: float,
    fairness_weight: float,
) -> float:
    workload_penalty = fairness_weight * member_state.total_assignments()
    return base_penalty + workload_penalty


def _select_bleach_candidate(
    rotation: List[str],
    cursor: int,
    candidates: List[Tuple[StaffMember, _StaffState]],
) -> Tuple[Optional[StaffMember], Optional[int]]:
    if not rotation or not candidates:
        return None, None
    cand_ids = {member.id: (member, state) for member, state in candidates}
    for offset in range(len(rotation)):
        idx = (cursor + offset) % len(rotation)
        staff_id = rotation[idx]
        if staff_id in cand_ids:
            member, _ = cand_ids[staff_id]
            return member, idx
    return None, None


def generate_schedule(
    staff: Sequence[StaffMember],
    requirements: Sequence[DailyRequirement],
    cfg: ScheduleConfig,
    pto_entries: Iterable[PTOEntry] = (),
    *,
    rng_seed: Optional[int] = None,
    rng: Optional[random.Random] = None,
) -> ScheduleResult:
    """
    Generate a schedule and return assignments + updated bleach cursor.
    """
    requirements_map = _ensure_requirements(requirements)
    slots = _build_slots(requirements_map, cfg)
    pto_lookup = _pto_lookup(pto_entries)

    if rng is None:
        rng = random.Random(rng_seed)

    staff_by_role: Dict[str, List[StaffMember]] = defaultdict(list)
    for member in staff:
        staff_by_role[member.role].append(member)

    states: Dict[str, _StaffState] = {
        member.id: _StaffState(assignments=[], worked_day_indices=[]) for member in staff
    }
    staff_map: Dict[str, StaffMember] = {member.id: member for member in staff}

    assignments: List[Assignment] = []
    bleach_cursor = cfg.bleach_cursor % len(cfg.bleach_rotation) if cfg.bleach_rotation else 0

    total_penalty = 0.0

    for slot in slots:
        role_candidates = staff_by_role.get(slot.role, [])
        if role_candidates:
            role_candidates = role_candidates.copy()
            rng.shuffle(role_candidates)

        def gather_candidates(
            *,
            ignore_post_bleach: bool = False,
            ignore_week_cap: bool = False,
            ignore_three_day: bool = False,
            ignore_alt_sat: bool = False,
        ) -> List[Tuple[StaffMember, _StaffState]]:
            found: List[Tuple[StaffMember, _StaffState]] = []
            for member in role_candidates:
                state = states[member.id]
                if slot.day_index in state.worked_day_indices:
                    continue
                if not _is_available(member, slot, pto_lookup):
                    continue
                if _violates_toggles(
                    state,
                    slot,
                    cfg,
                    ignore_post_bleach=ignore_post_bleach,
                    ignore_week_cap=ignore_week_cap,
                    ignore_three_day=ignore_three_day,
                    ignore_alt_sat=ignore_alt_sat,
                ):
                    continue
                found.append((member, state))
            return found

        # priority: fill slots -> honor bleach rotation -> post-bleach rest -> week caps -> 3-day cap -> alt Saturdays
        # For non-bleach slots we relax in reverse priority if needed.
        candidates: List[Tuple[StaffMember, _StaffState]] = gather_candidates()
        relaxed_note = None
        if not candidates:
            # Allow violating alt Saturdays first, then 3-day cap, then week cap, then post-bleach rest
            for ignore_alt, ignore_three, ignore_week, ignore_post, note in [
                (True, False, False, False, "Relax: alt Saturdays"),
                (True, True, False, False, "Relax: 3-day cap"),
                (True, True, True, False, "Relax: 4-day/week cap"),
                (True, True, True, True, "Relax: post-bleach rest"),
            ]:
                candidates = gather_candidates(
                    ignore_post_bleach=ignore_post,
                    ignore_week_cap=ignore_week,
                    ignore_three_day=ignore_three,
                    ignore_alt_sat=ignore_alt,
                )
                if candidates:
                    relaxed_note = note
                    break

        chosen: Optional[StaffMember] = None
        chosen_state: Optional[_StaffState] = None
        note: Optional[str] = None
        rotation_index_used: Optional[int] = None

        base_penalty = None

        if slot.is_bleach and cfg.bleach_rotation:
            week_idx, _ = _week_and_day_index(slot.day_index)
            # Do not relax post-bleach rest: it is treated as hard for bleach slots.
            relax_options = [
                (False, False, False, False, None),
                (False, False, False, True, "Relax: alt Saturdays"),
                (False, False, True, True, "Relax: 3-day cap"),
                (False, True, True, True, "Relax: 4-day/week cap"),
            ]
            for ignore_post, ignore_week, ignore_three, ignore_alt, relax_note in relax_options:
                for offset in range(len(cfg.bleach_rotation)):
                    idx = (bleach_cursor + offset) % len(cfg.bleach_rotation)
                    rid = cfg.bleach_rotation[idx]
                    member = staff_map.get(rid)
                    if member is None:
                        continue
                    state = states.get(rid)
                    if state is None:
                        continue
                    if slot.day_index in state.worked_day_indices:
                        continue
                    if not _is_available(member, slot, pto_lookup):
                        continue
                    if _violates_toggles(
                        state,
                        slot,
                        cfg,
                        ignore_post_bleach=ignore_post,
                        ignore_week_cap=ignore_week,
                        ignore_three_day=ignore_three,
                        ignore_alt_sat=ignore_alt,
                    ):
                        continue
                    chosen = member
                    chosen_state = state
                    rotation_index_used = idx
                    base_penalty = _preference_penalty(member, slot)
                    if relax_note:
                        note = relax_note
                    break
                if chosen:
                    break
            if chosen is None:
                note = "Bleach rotation unavailable"
                if cfg.bleach_rotation:
                    bleach_cursor = (bleach_cursor + 1) % len(cfg.bleach_rotation)

        if chosen is None and candidates and not slot.is_bleach:
            scored: List[Tuple[float, float, StaffMember, _StaffState]] = []
            for member, state in candidates:
                base = _preference_penalty(member, slot)
                if slot.is_bleach and cfg.bleach_rotation:
                    # apply extra penalty if we are off rotation
                    try:
                        pos = cfg.bleach_rotation.index(member.id)
                    except ValueError:
                        pos = None
                    if pos is None:
                        base += BLEACH_PENALTY
                score = _score_candidate(state, base_penalty=base, fairness_weight=FAIRNESS_WEIGHT)
                jitter = rng.random() * JITTER_SCALE
                scored.append((score + jitter, score, member, state))
            scored.sort(key=lambda tup: (tup[0], tup[2].id))
            _, score_value, chosen, chosen_state = scored[0]
            base_penalty = score_value - FAIRNESS_WEIGHT * chosen_state.total_assignments()

        if chosen is None:
            notes = [note] if note else []
            if relaxed_note:
                notes.append(relaxed_note)
            notes.append("Needs coverage")
            assignments.append(Assignment(slot=slot, staff_id=OPEN_LABEL, notes=notes))
            continue

        # Update state
        assigned = Assignment(slot=slot, staff_id=chosen.id, notes=[note] if note else [])
        assignments.append(assigned)
        chosen_state.assignments.append(assigned)
        chosen_state.worked_day_indices.append(slot.day_index)
        week_idx, _ = _week_and_day_index(slot.day_index)
        chosen_state.week_assignments.setdefault(week_idx, set()).add(slot.day_index)
        if slot.is_bleach and slot.role == "Tech":
            chosen_state.last_bleach_day = slot.day_index
            if rotation_index_used is not None:
                bleach_cursor = (rotation_index_used + 1) % len(cfg.bleach_rotation)
        if slot.day_name == "Sat":
            chosen_state.last_saturday_week = week_idx
        if base_penalty is None:
            base_penalty = _preference_penalty(chosen, slot)
        total_penalty += _score_candidate(chosen_state, base_penalty=base_penalty, fairness_weight=FAIRNESS_WEIGHT)

    # compute summary stats
    totals = {staff_id: state.total_assignments() for staff_id, state in states.items()}
    stats = {member_id: float(count) for member_id, count in totals.items()}

    return ScheduleResult(
        assignments=assignments,
        bleach_cursor=bleach_cursor,
        total_penalty=total_penalty,
        stats=stats,
        seed=rng_seed,
    )
