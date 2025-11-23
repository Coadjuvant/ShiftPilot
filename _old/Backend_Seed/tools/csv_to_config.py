
from __future__ import annotations
import csv, json, argparse
DOWS = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]

def read_staff(path):
    staff = []
    with open(path, newline='', encoding='utf-8') as f:
        r = csv.DictReader(f)
        for row in r:
            roles = [x.strip() for x in (row.get("roles") or "").split(";") if x.strip()]
            availability = {d: (row.get(d) in ("1","true","True","TRUE","yes","Y")) for d in DOWS if row.get(d) is not None}
            staff.append({"id": row["id"], "name": row["name"], "roles": roles, "availability": availability})
    return staff

def read_shifts(path):
    shifts = []
    with open(path, newline='', encoding='utf-8') as f:
        r = csv.DictReader(f)
        for row in r:
            shifts.append({"name": row["name"], "start": row["start"], "end": row["end"], "spans_midnight": row.get("spans_midnight","0") in ("1","true","True","TRUE","yes")})
    return shifts

def read_coverage(path):
    out = {}
    with open(path, newline='', encoding='utf-8') as f:
        r = csv.DictReader(f)
        for row in r:
            out.setdefault(row["shift"], []).append({"label": row["label"], "role": row["role"], "count": int(row.get("count","1"))})
    cov = [{"shift": k, "requirements": v} for k,v in out.items()]
    return cov

def read_week_pattern(path):
    wp = {d: [] for d in DOWS}
    with open(path, newline='', encoding='utf-8') as f:
        r = csv.DictReader(f)
        for row in r:
            d = row["dow"]; s = row["shift"]
            if d in wp: wp[d].append(s)
    return wp

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--staff", required=True)
    ap.add_argument("--patient_shifts", required=True)
    ap.add_argument("--coverage", required=True)
    ap.add_argument("--week_pattern", required=True)
    ap.add_argument("--clinic_name", default="Imported Clinic")
    ap.add_argument("--out", default="config_from_csv.json")
    args = ap.parse_args()

    staff = read_staff(args.staff)
    shifts = read_shifts(args.patient_shifts)
    coverage = read_coverage(args.coverage)
    wp = read_week_pattern(args.week_pattern)
    roles = sorted({r for s in staff for r in s["roles"]})

    cfg = {
        "config_version": "2",
        "clinic": {"name": args.clinic_name, "timezone": "America/Chicago"},
        "roles": roles,
        "staff": staff,
        "patient_shifts": shifts,
        "coverage": coverage,
        "week_pattern": wp,
        "constraints": {"min_rest_hours": 10, "max_hours_per_week": 48, "max_days_in_row": 6},
        "penalties": {"unfilled": 5.0, "double_assignment": 2.0, "weekly_balance": 1.0}
    }
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)
    print("Wrote", args.out)

if __name__ == "__main__":
    main()
