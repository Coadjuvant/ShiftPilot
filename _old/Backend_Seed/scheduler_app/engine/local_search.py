
from __future__ import annotations
import random
from copy import deepcopy
from typing import List, Tuple
from datetime import timedelta
from .slots_v2 import DOW
from ..engine.generate_v2 import score

def _hours(slot): return (slot["end_dt"] - slot["start_dt"]).total_seconds()/3600.0

def _feasible_for_staff(staff_id: str, slots: list[dict], cfg: dict) -> bool:
    st = next((x for x in cfg["staff"] if x["id"] == staff_id), None)
    if not st: return False
    blocks = sorted([(s["start_dt"], s["end_dt"]) for s in slots], key=lambda x: x[0])
    weekly_hours = 0.0
    last_end = None
    for s0, s1 in blocks:
        key = DOW[s0.weekday()]
        if not (st.get("availability") or {}).get(key, True):
            return False
        if last_end is not None:
            delta = s0 - last_end
            if delta < timedelta(hours=cfg["constraints"]["min_rest_hours"]):
                return False
        last_end = s1
        weekly_hours += (s1 - s0).total_seconds()/3600.0
    if weekly_hours > cfg["constraints"]["max_hours_per_week"]:
        return False
    # Overlaps
    for i in range(1, len(blocks)):
        a0,a1 = blocks[i-1]; b0,b1 = blocks[i]
        if not (a1 <= b0 or b1 <= a0):
            return False
    return True

def improve_by_swaps(assignments: list[tuple[dict, str|None]], cfg: dict, iterations: int = 1000, rnd_seed: int = 42):
    rnd = random.Random(rnd_seed)
    current = deepcopy(assignments)
    best = score(current, cfg)
    accepted = 0

    role_indices = {}
    for i, (slot, sid) in enumerate(current):
        role_indices.setdefault(slot["role"], []).append(i)

    for _ in range(iterations):
        role = rnd.choice(list(role_indices.keys()))
        idxs = role_indices[role]
        if len(idxs) < 2: 
            continue
        i, j = rnd.sample(idxs, 2)
        (slot_i, si), (slot_j, sj) = current[i], current[j]
        if si is None or sj is None or si == sj:
            continue

        current[i] = (slot_i, sj)
        current[j] = (slot_j, si)

        si_slots = [slot for slot, s in current if s == si]
        sj_slots = [slot for slot, s in current if s == sj]
        if _feasible_for_staff(si, si_slots, cfg) and _feasible_for_staff(sj, sj_slots, cfg):
            new_score = score(current, cfg)
            if new_score <= best:
                best = new_score
                accepted += 1
            else:
                current[i] = (slot_i, si)
                current[j] = (slot_j, sj)
        else:
            current[i] = (slot_i, si)
            current[j] = (slot_j, sj)

    return current, best, accepted
