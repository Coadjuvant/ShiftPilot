from __future__ import annotations
from pathlib import Path
import json
def load_pto(path):
    if not path or not Path(path).exists(): return {}
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    return {k: set(v) for k, v in (raw or {}).items()}
def is_pto(pto_map, staff_id, d):
    return d.isoformat() in pto_map.get(staff_id, set())
