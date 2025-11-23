from __future__ import annotations
import json
from pathlib import Path
from jsonschema import Draft202012Validator

def load_config(path):
    with open(path, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    if cfg.get("config_version") != "2":
        raise ValueError("Expected config_version '2'")
    schema_path = Path(__file__).with_name("config_schema.v2.json")
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    errs = []
    validator = Draft202012Validator(schema)
    for e in sorted(validator.iter_errors(cfg), key=str):
        errs.append(f"{'/'.join(map(str, e.path)) or '<root>'}: {e.message}")
    shifts = {s["name"] for s in cfg.get("patient_shifts", [])}
    for k, v in (cfg.get("week_pattern") or {}).items():
        for s in v:
            if s not in shifts:
                errs.append(f"week_pattern[{k}] references unknown shift '{s}'")
    roles = set(cfg.get("roles") or [])
    for s in cfg.get("staff") or []:
        extra = set(s.get("roles") or []) - roles
        if extra:
            errs.append(f"staff {s.get('name')} has unknown roles {sorted(extra)}")
    for cov in cfg.get("coverage", []):
        if cov["shift"] not in shifts:
            errs.append(f"coverage.shift '{cov['shift']}' not in patient_shifts")
        for req in cov["requirements"]:
            if req["role"] not in roles:
                errs.append(f"coverage {cov['shift']} requires role '{req['role']}' not in roles")
    if errs:
        raise ValueError("Config validation errors:\n" + "\n".join(errs))
    return cfg
