
Backend patch — allow up to 2 shifts per person/day (by role)
=============================================================

New config fields (already included by the UI above):
- constraints.max_shifts_per_day_by_role: {"Tech": 2, "RN": 2, "Admin": 1}
- constraints.min_gap_same_day_hours: 0.0   # hours; between two same-day shifts

Greedy/heuristic solver snippet
-------------------------------
Add to your assignment loop:

from collections import defaultdict
from datetime import timedelta

def can_assign(slot, sid, state, cfg):
    max_by_role = cfg.get("constraints", {}).get("max_shifts_per_day_by_role", {})
    same_day_gap = float(cfg.get("constraints", {}).get("min_gap_same_day_hours", 0.0))
    role = slot["role"]; day = slot["day"]

    # per-day per-role cap
    if state["per_day_role_count"][sid][day][role] >= int(max_by_role.get(role, 999)):
        return False

    # same-day gap
    last_end = state["last_end_same_day"][sid][day]
    if last_end is not None and same_day_gap > 0:
        if (slot["start_dt"] - last_end) < timedelta(hours=same_day_gap):
            return False
    return True

# In your loop, maintain:
state = {
  "per_day_role_count": defaultdict(lambda: defaultdict(lambda: defaultdict(int))),
  "last_end_same_day": defaultdict(lambda: defaultdict(lambda: None)),
}
# When assigning:
state["per_day_role_count"][sid][day][role] += 1
state["last_end_same_day"][sid][day] = max(state["last_end_same_day"][sid][day] or slot["end_dt"], slot["end_dt"])

ILP/CP-SAT model
----------------
For each staff s, day d, role r:
    sum_{slots on day d with role r} x[s, slot] <= max_shifts_per_day_by_role[r]

For the same-day gap: for any two slots i, j on the same day for the same staff where
(j.start - i.end) < min_gap_same_day_hours, add:
    x[s,i] + x[s,j] <= 1
(You likely already enforce time-overlap; this extends it to small gaps if desired.)
