from __future__ import annotations
from datetime import timedelta
def verify(assignments, min_rest_hours: float):
    issues = []; by_day_sid = {}; last_end = {}
    for slot, sid in assignments:
        if sid is None:
            issues.append(f"{slot['day']} {slot['shift']} {slot['label']}[{slot['idx']}]: unfilled"); continue
        key = (slot["day"], sid); by_day_sid.setdefault(key, []).append((slot["start_dt"], slot["end_dt"], slot))
        if sid in last_end:
            delta = slot["start_dt"] - last_end[sid]
            if delta < timedelta(hours=min_rest_hours):
                issues.append(f"{slot['day']} {sid}: rest violation ({delta} < {min_rest_hours}h) before {slot['shift']} {slot['label']}[{slot['idx']}]" )
        last_end[sid] = slot["end_dt"]
    for (day, sid), blocks in by_day_sid.items():
        blocks.sort()
        for i in range(1, len(blocks)):
            prev, cur = blocks[i-1], blocks[i]
            if not (prev[1] <= cur[0] or cur[1] <= prev[0]):
                issues.append(f"{day} {sid}: overlapping assignments between {prev[2]['shift']} and {cur[2]['shift']}")
    return issues
