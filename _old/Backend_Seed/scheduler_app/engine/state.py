from __future__ import annotations
from collections import defaultdict
from datetime import date
from typing import Dict, Set

def new_state():
    return {
        "per_day_role_count": defaultdict(lambda: defaultdict(lambda: defaultdict(int))),
        "last_end_same_day": defaultdict(lambda: defaultdict(lambda: None)),
        "worked_day": defaultdict(set),
    }

def week_key(d: date):
    y, w, _ = d.isocalendar()
    return (y, w)

def worked_days_in_week(state, sid: str, d: date) -> int:
    y, w = week_key(d)
    return sum(1 for day in state["worked_day"][sid] if week_key(day) == (y, w))

def current_streak_len(state, sid: str, d: date) -> int:
    from datetime import timedelta
    n, day = 0, d - timedelta(days=1)
    while day in state["worked_day"][sid]:
        n += 1
        day -= timedelta(days=1)
    return n

def mark_assigned(state, slot, sid: str):
    role = slot["role"]; day = slot["day"]
    state["per_day_role_count"][sid][day][role] += 1
    prev = state["last_end_same_day"][sid][day]
    state["last_end_same_day"][sid][day] = max(prev or slot["end_dt"], slot["end_dt"])
    state["worked_day"][sid].add(day)
