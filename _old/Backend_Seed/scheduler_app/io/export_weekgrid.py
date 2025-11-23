# Backend_Seed/scheduler_app/io/export_weekgrid.py
from __future__ import annotations

from collections import defaultdict, OrderedDict
from datetime import date as _date, datetime as _dt, timedelta
from typing import Dict, List, Tuple, Any
import pandas as pd

DOWS = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]

def _as_date(x):
    if isinstance(x, _dt):
        return x.date()
    return x  # assume date

def _week_index(start_date: _date, d: _date) -> int:
    return max(0, (d - start_date).days // 7)

def week_grid_sheets(assignments: List[Tuple[dict, Any]], cfg: Dict[str,Any], start: _date, weeks: int):
    """
    Build per-week simple grid DataFrames.

    Output format (dict):
        {
          "Week 1": pd.DataFrame([...]),
          "Week 2": pd.DataFrame([...]),
          ...
        }

    The DataFrame has columns:
        Date, DOW, Shift, Role, Label, SlotIdx, StaffID, StaffName, Duty, Notes
    """
    # Collect rows per week
    buckets: Dict[int, List[dict]] = defaultdict(list)

    for slot, sid in assignments:
        d = _as_date(slot["day"])
        w = _week_index(start, d)

        duty = (slot.get("duty") or "")
        notes = "; ".join(slot.get("notes", [])) if isinstance(slot.get("notes", []), list) else (slot.get("notes") or "")

        # Try to include staff name if present in cfg
        staff_name = ""
        if sid:
            for p in cfg.get("staff", []):
                if str(p.get("id","")).strip() == str(sid):
                    staff_name = str(p.get("name",""))
                    break

        buckets[w].append({
            "Date": d.strftime("%Y-%m-%d"),
            "DOW": DOWS[d.weekday()],
            "Shift": slot.get("shift",""),
            "Role": slot.get("role",""),
            "Label": slot.get("label",""),
            "SlotIdx": slot.get("idx",""),
            "StaffID": sid or "",
            "StaffName": staff_name,
            "Duty": duty,
            "Notes": notes,
        })

    # Ensure all weeks 0..weeks-1 exist (even if empty)
    out = OrderedDict()
    for i in range(weeks):
        rows = buckets.get(i, [])
        df = pd.DataFrame(rows, columns=["Date","DOW","Shift","Role","Label","SlotIdx","StaffID","StaffName","Duty","Notes"])
        # Sort by date, role, shift, idx for readability
        if not df.empty:
            df["Date2"] = pd.to_datetime(df["Date"])
            df.sort_values(["Date2","Role","Shift","SlotIdx"], inplace=True)
            df.drop(columns=["Date2"], inplace=True)
        out[f"Week {i+1}"] = df
    return out

def export_excel(assignments: List[Tuple[dict, Any]], cfg: Dict[str,Any], start: _date, weeks: int, buf):
    """
    Writes:
      - Coverage (summary counts by day/shift/role)
      - Roster  (long form assignments)
      - Week 1..N (simple readable tables)
    """
    # Coverage
    from collections import defaultdict
    cov = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
    for slot, sid in assignments:
        d = _as_date(slot["day"]).strftime("%Y-%m-%d")
        s = slot.get("shift","")
        r = slot.get("role","")
        cov[d][s][r] += 1 if sid else 0

    cov_rows = []
    for d in sorted(cov.keys()):
        for s in sorted(cov[d].keys()):
            row = {"Date": d, "Shift": s}
            row.update({role: cov[d][s][role] for role in sorted(cov[d][s].keys())})
            cov_rows.append(row)
    df_cov = pd.DataFrame(cov_rows).fillna(0)

    # Roster (long form)
    ros_rows = []
    for slot, sid in assignments:
        d = _as_date(slot["day"]).strftime("%Y-%m-%d")
        name = ""
        if sid:
            for p in cfg.get("staff", []):
                if str(p.get("id","")).strip() == str(sid):
                    name = str(p.get("name","")); break
        ros_rows.append({
            "Date": d,
            "DOW": DOWS[_as_date(slot["day"]).weekday()],
            "Shift": slot.get("shift",""),
            "Role": slot.get("role",""),
            "Label": slot.get("label",""),
            "SlotIdx": slot.get("idx",""),
            "StaffID": sid or "",
            "StaffName": name,
            "Duty": (slot.get("duty") or ""),
            "Notes": "; ".join(slot.get("notes", [])) if isinstance(slot.get("notes", []), list) else (slot.get("notes") or "")
        })
    df_ros = pd.DataFrame(ros_rows, columns=["Date","DOW","Shift","Role","Label","SlotIdx","StaffID","StaffName","Duty","Notes"])
    if not df_ros.empty:
        df_ros["Date2"] = pd.to_datetime(df_ros["Date"])
        df_ros.sort_values(["Date2","Role","Shift","SlotIdx"], inplace=True)
        df_ros.drop(columns=["Date2"], inplace=True)

    # Week sheets
    weeksheets = week_grid_sheets(assignments, cfg, start, weeks)

    # Write workbook
    with pd.ExcelWriter(buf, engine="xlsxwriter") as writer:
        if not df_cov.empty:
            df_cov.to_excel(writer, sheet_name="Coverage", index=False)
        else:
            pd.DataFrame([{"Info":"No coverage data"}]).to_excel(writer, sheet_name="Coverage", index=False)

        if not df_ros.empty:
            df_ros.to_excel(writer, sheet_name="Roster", index=False)
        else:
            pd.DataFrame([{"Info":"No roster data"}]).to_excel(writer, sheet_name="Roster", index=False)

        # Accept dict or list for compatibility
        if isinstance(weeksheets, list):
            # convert list-of-dates per week into minimal tables
            for i, days in enumerate(weeksheets):
                df = pd.DataFrame({"Date":[d.strftime("%Y-%m-%d") for d in days]})
                df.to_excel(writer, sheet_name=f"Week {i+1}", index=False)
        elif isinstance(weeksheets, dict):
            for name, df in weeksheets.items():
                (df if isinstance(df, pd.DataFrame) else pd.DataFrame(df)).to_excel(writer, sheet_name=name, index=False)
        else:
            # fallback
            for i in range(weeks):
                pd.DataFrame({"Info":["No data"]}).to_excel(writer, sheet_name=f"Week {i+1}", index=False)
