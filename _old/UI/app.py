# UI/app.py
import json
from io import BytesIO
from math import ceil
from datetime import datetime, date, timedelta
from pathlib import Path

import pandas as pd
import streamlit as st
import requests

st.set_page_config(page_title="ShiftPilot — Census → Staffing (v10)", layout="wide")
st.title("ShiftPilot — Census → Staffing (v10)")

DOWS  = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]
ROLES = ["Tech","RN","Admin"]

def _default_shifts_df() -> pd.DataFrame:
    return pd.DataFrame([
        {"name":"S1","start":"06:00","end":"10:30","spans_midnight":0},
        {"name":"S2","start":"10:30","end":"15:00","spans_midnight":0},
        {"name":"S3","start":"15:00","end":"19:30","spans_midnight":0},
        {"name":"S4","start":"19:30","end":"00:00","spans_midnight":0},
        {"name":"S5","start":"00:00","end":"04:30","spans_midnight":1},
    ])

def _default_staff_df() -> pd.DataFrame:
    return pd.DataFrame([
        {"id":"a","name":"Ava","role":"Tech","Mon":1,"Tue":1,"Wed":1,"Thu":1,"Fri":1,"Sat":1,"Sun":0,"can_open":False,"can_close":False,"can_bleach":True},
        {"id":"b","name":"Ben","role":"Tech","Mon":1,"Tue":1,"Wed":1,"Thu":1,"Fri":1,"Sat":0,"Sun":0,"can_open":False,"can_close":True,"can_bleach":False},
        {"id":"c","name":"Casey","role":"RN","Mon":1,"Tue":1,"Wed":1,"Thu":1,"Fri":1,"Sat":1,"Sun":0,"can_open":False,"can_close":False,"can_bleach":False},
        {"id":"d","name":"Drew","role":"Admin","Mon":1,"Tue":1,"Wed":1,"Thu":1,"Fri":1,"Sat":0,"Sun":0,"can_open":False,"can_close":False,"can_bleach":False},
    ])

def _default_census_df(shift_names: list[str]) -> pd.DataFrame:
    rows = []
    for d in DOWS:
        row = {"Day": d}
        for s in shift_names:
            row[s] = 0
        rows.append(row)
    return pd.DataFrame(rows)

def _df_from_state(key: str, default_factory) -> pd.DataFrame:
    """Return a copy of the DataFrame stored in session state or build a default."""
    val = st.session_state.get(key)
    if isinstance(val, pd.DataFrame):
        return val.copy()
    if val is None:
        default_df = default_factory()
    else:
        try:
            default_df = pd.DataFrame(val)
        except Exception:
            default_df = default_factory()
    return default_df.copy()

def _set_df_state(key: str, df: pd.DataFrame) -> None:
    """Persist a DataFrame copy into session state."""
    st.session_state[key] = df.copy()

def _init_state():
    defaults = {
        "config": None,
        "excel_bytes": None,
        "excel_name": "schedule_v2.xlsx",
        "shifts_df_value": _default_shifts_df(),
        "census_df_value": _default_census_df(_default_shifts_df()["name"].tolist()),
        "staff_df_value": _default_staff_df(),
        "pto_df_value": pd.DataFrame([{"id":"", "date":""}]),
        # rotation UI state
        "bleach_rotation_order": [],
        "bleach_rotation_cursor": 0,
        "bleach_days": [],  # e.g., ["Tue","Thu"]
        # Sidebar defaults
        "clinic_name": "Census Clinic",
        "timezone": "America/Chicago",
        "patients_per_tech": 4,
        "techs_per_rn": 3,
        "max_techs_per_day": 24,
        "min_rn_per_shift": 1,
        "enforce_day_cap": False,
        "sunday_makeup_enabled": False,
        "tech_max": 2,
        "rn_max": 2,
        "admin_max": 1,
        "same_day_gap": 0.0,
        "work_days_mode": "hard",
        "role_tech_days": 4,
        "role_rn_days": 4,
        "role_admin_days": 5,
        "soft_penalty_exceed_week": 1.0,
        # hydration queue
        "_pending_hydrate": False,
        "_hydrate_values": {},
    }
    for k,v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

_init_state()

def validate_config(cfg: dict, api_url: str):
    try:
        r = requests.post(f"{api_url}/validate", json={"config": cfg}, timeout=20)
        if r.status_code == 200:
            return True, []
        try:
            detail = r.json().get("detail")
        except Exception:
            detail = None
        if isinstance(detail, dict) and "errors" in detail:
            return False, detail["errors"]
        return False, [str(detail or r.text)]
    except Exception as e:
        return False, [str(e)]

def df_or_empty(df):
    return df if isinstance(df, pd.DataFrame) else pd.DataFrame()

def _records(df: pd.DataFrame):
    return df_or_empty(df).to_dict("records")

# ---------- Hydration (safe: before widgets render) ----------
def _build_hydration_values(cfg: dict) -> dict:
    vals = {}
    snap = cfg.get("ui_snapshot", {})

    # tables
    if "shifts_df" in snap:
        vals["shifts_df_value"] = pd.DataFrame(snap["shifts_df"])
    if "census_df" in snap:
        vals["census_df_value"] = pd.DataFrame(snap["census_df"])
    if "staff_df" in snap:
        vals["staff_df_value"] = pd.DataFrame(snap["staff_df"])
    if "pto_rows" in snap:
        vals["pto_df_value"] = pd.DataFrame(snap["pto_rows"])

    # rotation + days
    rot = (cfg.get("constraints", {}) or {}).get("bleach_rotation", {}) or {}
    vals["bleach_rotation_order"] = [str(x) for x in rot.get("order", [])]
    vals["bleach_rotation_cursor"] = int(rot.get("cursor", 0))
    vals["bleach_days"] = list((cfg.get("constraints", {}) or {}).get("bleach_days", []))

    # sidebar
    clinic = cfg.get("clinic", {})
    vals["clinic_name"] = clinic.get("name", "Clinic")
    vals["timezone"] = clinic.get("timezone", "America/Chicago")

    cst = cfg.get("constraints", {}) or {}
    vals["same_day_gap"] = float(cst.get("min_gap_same_day_hours", 0.0))
    per_day = cst.get("max_shifts_per_day_by_role", {}) or {}
    vals["tech_max"] = int(per_day.get("Tech", 2))
    vals["rn_max"]   = int(per_day.get("RN", 2))
    vals["admin_max"]= int(per_day.get("Admin", 1))

    wdw = cst.get("work_days_week", {}) or {}
    vals["work_days_mode"] = str(wdw.get("mode", "hard"))
    by_role = wdw.get("by_role", {}) or {}
    vals["role_tech_days"]  = int(by_role.get("Tech", 4))
    vals["role_rn_days"]    = int(by_role.get("RN", 4))
    vals["role_admin_days"] = int(by_role.get("Admin", 5))
    vals["soft_penalty_exceed_week"] = float((cst.get("soft_weights", {}) or {}).get("exceed_week_days", 1.0))

    # ratios from snapshot if present
    r = snap.get("ratios", {})
    if r:
        vals["patients_per_tech"]     = int(r.get("patients_per_tech", vals.get("patients_per_tech", st.session_state["patients_per_tech"])))
        vals["techs_per_rn"]          = int(r.get("techs_per_rn", vals.get("techs_per_rn", st.session_state["techs_per_rn"])))
        vals["max_techs_per_day"]     = int(r.get("max_techs_per_day", vals.get("max_techs_per_day", st.session_state["max_techs_per_day"])))
        vals["min_rn_per_shift"]      = int(r.get("min_rn_per_shift", vals.get("min_rn_per_shift", st.session_state["min_rn_per_shift"])))
        vals["enforce_day_cap"]       = bool(r.get("enforce_day_cap", vals.get("enforce_day_cap", st.session_state["enforce_day_cap"])))
        vals["sunday_makeup_enabled"] = bool(r.get("sunday_makeup_enabled", vals.get("sunday_makeup_enabled", st.session_state["sunday_makeup_enabled"])))

    return vals

def _queue_hydration(cfg: dict):
    st.session_state["config"] = cfg
    st.session_state["_hydrate_values"] = _build_hydration_values(cfg)
    st.session_state["_pending_hydrate"] = True
    st.rerun()

# Apply queued hydration BEFORE widgets
if st.session_state.get("_pending_hydrate"):
    vals = st.session_state.get("_hydrate_values", {}) or {}
    for k,v in vals.items():
        st.session_state[k] = v
    st.session_state["_pending_hydrate"] = False
    st.session_state["_hydrate_values"] = {}

# -----------------------------
# Build config from UI
# -----------------------------
def build_v2_config_from_ui(
    shifts_df: pd.DataFrame,
    census_df: pd.DataFrame,
    staff_df: pd.DataFrame,
    *,
    patients_per_tech: int,
    techs_per_rn: int,
    max_techs_per_day: int,
    min_rn_per_shift: int,
    enforce_day_cap: bool,
    sunday_makeup_enabled: bool,
    max_shifts_per_day_by_role: dict,
    min_gap_same_day_hours: float,
    work_days_mode: str,
    work_days_by_role: dict,
    work_days_per_person: dict,
    soft_penalty_exceed_week: float,
    clinic_name: str,
    timezone: str,
    bleach_rotation_order: list[str],
    bleach_rotation_cursor: int,
    bleach_days: list[str],
):
    # Shifts
    patient_shifts, shift_names = [], []
    if isinstance(shifts_df, pd.DataFrame) and not shifts_df.empty:
        for _, r in shifts_df.iterrows():
            name = str(r.get("name","")).strip()
            if not name: continue
            shift_names.append(name)
            patient_shifts.append({
                "name": name,
                "start": str(r.get("start","")),
                "end": str(r.get("end","")),
                "spans_midnight": str(r.get("spans_midnight","0")).lower() in ("1","true","yes","y"),
            })
    shift_names = shift_names[:5]

    # Week pattern + coverage inferred from census
    week_pattern = {d: [] for d in DOWS}
    max_counts = {s: {"Tech":0,"RN":0} for s in shift_names}
    if isinstance(census_df, pd.DataFrame) and not census_df.empty:
        for _, row in census_df.iterrows():
            day = str(row.get("Day","")).strip() or "Mon"
            if (day == "Sun") and (not sunday_makeup_enabled):
                continue
            per_shift, total_t = {}, 0
            for s in shift_names:
                p = int(row.get(s,0) or 0)
                t = ceil(p / patients_per_tech) if p>0 else 0
                per_shift[s] = t; total_t += t
            if enforce_day_cap and total_t > max_techs_per_day and total_t>0:
                factor = max_techs_per_day / total_t
                capped = {s: int(max(0, round(per_shift[s]*factor))) for s in per_shift}
                diff = max_techs_per_day - sum(capped.values())
                for s in per_shift:
                    if diff<=0: break
                    if per_shift[s]>0:
                        capped[s]+=1; diff-=1
                per_shift = capped
            for s, t in per_shift.items():
                if t>0:
                    if s not in week_pattern[day]:
                        week_pattern[day].append(s)
                    max_counts[s]["Tech"] = max(max_counts[s]["Tech"], t)
                    rn = max(min_rn_per_shift if t>0 else 0, ceil(t/techs_per_rn) if t>0 else 0)
                    max_counts[s]["RN"] = max(max_counts[s]["RN"], rn)
    coverage = []
    for s, counts in max_counts.items():
        reqs = []
        if counts["Tech"]>0: reqs.append({"label":"Tech","role":"Tech","count": int(counts["Tech"])})
        if counts["RN"]>0:   reqs.append({"label":"RN","role":"RN","count":   int(counts["RN"])})
        if reqs: coverage.append({"shift": s, "requirements": reqs})

    # Staff — only Techs keep duty flags; RN/Admin forced False
    staff = []
    if isinstance(staff_df, pd.DataFrame) and not staff_df.empty:
        for _, r in staff_df.iterrows():
            sid = str(r.get("id","")).strip()
            if not sid: continue
            role = str(r.get("role","Tech")).strip()
            avail = {d: bool(int(r.get(d,1))) if str(r.get(d,1)).strip()!="" else True for d in DOWS}
            can_open  = bool(r.get("can_open", False))  if role=="Tech" else False
            can_close = bool(r.get("can_close", False)) if role=="Tech" else False
            can_bleach= bool(r.get("can_bleach", False))if role=="Tech" else False
            prefs = {
                "can_open":  can_open,
                "can_close": can_close,
                "can_bleach":can_bleach,
                "weights": {"open":0.0,"close":0.0,"bleach":0.0,"days":{d:0.0 for d in DOWS}}
            }
            staff.append({"id": sid, "name": str(r.get("name","")), "roles":[role], "availability": avail, "preferences": prefs})

    constraints = {
        "min_rest_hours": 10,
        "max_hours_per_week": 48,
        "max_days_in_row": 6,
        "max_shifts_per_day_by_role": {
            "Tech": int(st.session_state["tech_max"]),
            "RN":   int(st.session_state["rn_max"]),
            "Admin":int(st.session_state["admin_max"]),
        },
        "min_gap_same_day_hours": float(st.session_state["same_day_gap"]),
        "work_days_week": {
            "mode": st.session_state["work_days_mode"],
            "by_role": {"Tech": int(st.session_state["role_tech_days"]),
                        "RN":   int(st.session_state["role_rn_days"]),
                        "Admin": int(st.session_state["role_admin_days"])},
            "per_person": {},
        },
        "soft_weights": { "exceed_week_days": float(st.session_state["soft_penalty_exceed_week"]) },
        # NEW
        "bleach_days": [d for d in bleach_days if d in DOWS],
        "bleach_rotation": {
            "order": [str(x) for x in bleach_rotation_order if str(x).strip()],
            "cursor": int(bleach_rotation_cursor) if bleach_rotation_order else 0
        }
    }

    cfg = {
        "config_version": "2",
        "clinic": {"name": clinic_name or "Clinic", "timezone": timezone or "America/Chicago"},
        "roles": ROLES,
        "staff": staff,
        "patient_shifts": patient_shifts,
        "coverage": coverage,
        "week_pattern": week_pattern,
        "constraints": constraints,
        "penalties": {"unfilled": 5.0, "double_assignment": 2.0, "weekly_balance": 1.0},
        "ui_snapshot": {
            "shifts_df": _records(shifts_df),
            "census_df": _records(census_df),
            "staff_df":  _records(staff_df),
            "pto_rows":  _records(st.session_state.get("pto_df_value", pd.DataFrame())),
            "rot_order": [str(x) for x in bleach_rotation_order],
            "rot_cursor": int(bleach_rotation_cursor),
            "bleach_days": [d for d in bleach_days if d in DOWS],
            "ratios": {
                "patients_per_tech": patients_per_tech,
                "techs_per_rn": techs_per_rn,
                "max_techs_per_day": max_techs_per_day,
                "min_rn_per_shift": min_rn_per_shift,
                "enforce_day_cap": enforce_day_cap,
                "sunday_makeup_enabled": sunday_makeup_enabled,
            },
        }
    }
    return cfg

# -------------- Sidebar --------------
with st.sidebar:
    st.header("API")
    api_url = st.text_input("API URL", "http://127.0.0.1:8000")
    try:
        r = requests.get(f"{api_url}/health", timeout=3); r.raise_for_status()
        st.success("API healthy ✅")
    except Exception:
        st.error("API not reachable. Start it with:  `uvicorn api_main:app --reload`")
        st.stop()

    st.markdown("---")
    st.header("Clinic")
    clinic_name = st.text_input("Clinic name", key="clinic_name")
    timezone    = st.text_input("Timezone (IANA)", key="timezone")

    st.markdown("---")
    st.header("Bleach")
    st.caption("Choose clinic bleach day(s) and rotation.")
    bleach_days = st.multiselect("Bleach day(s)", DOWS, default=st.session_state.get("bleach_days", []), key="bleach_days")
    st.write("Rotation is managed in tab 5 below.")

    st.markdown("---")
    st.header("Ratios & caps")
    patients_per_tech   = st.number_input("Patients per Tech", min_value=1, max_value=10, step=1, key="patients_per_tech")
    techs_per_rn        = st.number_input("Techs per RN", min_value=1, max_value=8, step=1, key="techs_per_rn")
    max_techs_per_day   = st.number_input("Max Techs per DAY", min_value=1, max_value=200, step=1, key="max_techs_per_day")
    min_rn_per_shift    = st.number_input("Min RNs per shift (if any Techs)", min_value=0, max_value=10, step=1, key="min_rn_per_shift")
    enforce_day_cap     = st.checkbox("Enforce 24/day cap (proportional)", key="enforce_day_cap")
    sunday_makeup_enabled = st.checkbox("Enable Sunday (make-up) for this run", key="sunday_makeup_enabled")

    st.markdown("---")
    st.header("Per-person limits")
    tech_max   = st.number_input("Tech: max shifts/day", min_value=1, max_value=5, step=1, key="tech_max")
    rn_max     = st.number_input("RN: max shifts/day",   min_value=1, max_value=5, step=1, key="rn_max")
    admin_max  = st.number_input("Admin: max shifts/day",min_value=1, max_value=5, step=1, key="admin_max")
    same_day_gap = st.number_input("Min gap between same-day shifts (hrs)", min_value=0.0, max_value=8.0, step=0.5, key="same_day_gap")

    st.markdown("---")
    st.header("Work-days/week")
    work_days_mode = st.radio("Mode", options=["hard","soft","off"],
                              index=["hard","soft","off"].index(st.session_state["work_days_mode"]),
                              horizontal=True, key="work_days_mode")
    col = st.columns(3)
    with col[0]:
        role_tech_days  = st.number_input("Tech target", min_value=0, max_value=7, step=1, key="role_tech_days")
    with col[1]:
        role_rn_days    = st.number_input("RN target",   min_value=0, max_value=7, step=1, key="role_rn_days")
    with col[2]:
        role_admin_days = st.number_input("Admin target",min_value=0, max_value=7, step=1, key="role_admin_days")
    if work_days_mode == "soft":
        soft_penalty_exceed_week = st.number_input("Soft penalty per day over target", min_value=0.0, max_value=5.0, step=0.1, key="soft_penalty_exceed_week")

    st.markdown("---")
    st.header("Save / Load")

    with st.form("save_load_form"):
        cfg_dir = Path(st.text_input("Config folder", "saved_configs"))
        cfg_filename = st.text_input("File name", "clinic.config.v2.json")
        add_timestamp = st.checkbox("Timestamp filename", value=True)

        save_clicked = st.form_submit_button("Save All (JSON)", type="primary")
        load_clicked = st.form_submit_button("Load latest from folder")

    if save_clicked:
        shifts_df = st.session_state.get("shifts_df_value", pd.DataFrame())
        census_df = st.session_state.get("census_df_value", pd.DataFrame())
        staff_df  = st.session_state.get("staff_df_value", pd.DataFrame())
        cfg = build_v2_config_from_ui(
            shifts_df, census_df, staff_df,
            patients_per_tech=st.session_state["patients_per_tech"],
            techs_per_rn=st.session_state["techs_per_rn"],
            max_techs_per_day=st.session_state["max_techs_per_day"],
            min_rn_per_shift=st.session_state["min_rn_per_shift"],
            enforce_day_cap=st.session_state["enforce_day_cap"],
            sunday_makeup_enabled=st.session_state["sunday_makeup_enabled"],
            max_shifts_per_day_by_role={"Tech": int(st.session_state["tech_max"]), "RN": int(st.session_state["rn_max"]), "Admin": int(st.session_state["admin_max"])},
            min_gap_same_day_hours=float(st.session_state["same_day_gap"]),
            work_days_mode=st.session_state["work_days_mode"],
            work_days_by_role={"Tech": int(st.session_state["role_tech_days"]), "RN": int(st.session_state["role_rn_days"]), "Admin": int(st.session_state["role_admin_days"])},
            work_days_per_person={},
            soft_penalty_exceed_week=float(st.session_state["soft_penalty_exceed_week"]),
            clinic_name=st.session_state["clinic_name"], timezone=st.session_state["timezone"],
            bleach_rotation_order=st.session_state["bleach_rotation_order"],
            bleach_rotation_cursor=st.session_state["bleach_rotation_cursor"],
            bleach_days=st.session_state.get("bleach_days", []),
        )
        ok, errs = validate_config(cfg, api_url)
        if ok:
            cfg_dir.mkdir(parents=True, exist_ok=True)
            base = cfg_filename if cfg_filename.strip() else "clinic.config.v2.json"
            if add_timestamp:
                ts = datetime.now().strftime("%Y%m%d-%H%M%S")
                base = f"{Path(base).stem}.{ts}.json"
            path = cfg_dir / base
            path.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
            st.session_state["config"] = cfg
            st.success(f"Saved: {path}")
        else:
            st.error("Config has errors:"); [st.code(e) for e in errs]

    if load_clicked:
        cfg_dir.mkdir(parents=True, exist_ok=True)
        files = sorted(cfg_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        if files:
            cfg = json.loads(files[0].read_text(encoding="utf-8"))
            ok, errs = validate_config(cfg, api_url)
            if ok:
                _queue_hydration(cfg)  # safe rerun/hydration
            else:
                st.error("Config has errors:"); [st.code(e) for e in errs]
        else:
            st.warning(f"No .json found in {cfg_dir}")

    uploaded = st.file_uploader("Manual upload (JSON)", type=["json"])
    if uploaded is not None:
        try:
            cfg = json.loads(uploaded.getvalue().decode("utf-8"))
            ok, errs = validate_config(cfg, api_url)
            if ok:
                _queue_hydration(cfg)
            else:
                st.error("Config has errors:");  [st.code(e) for e in errs]
        except Exception as e:
            st.error(f"Invalid JSON: {e}")

# -----------------------------
# Tabs
# -----------------------------
tab_shifts, tab_census, tab_staff, tab_pto, tab_rotation, tab_generate, tab_results = st.tabs(
    ["1) Shifts", "2) Census", "3) Staff", "4) PTO", "5) Bleach Rotation", "6) Generate", "7) Results"]
)

with tab_shifts:
    st.subheader("Define up to 5 patient shifts")
    current_shifts = _df_from_state("shifts_df_value", _default_shifts_df)
    shifts_df = st.data_editor(current_shifts, num_rows="dynamic", key="shifts_editor", width="stretch")
    if isinstance(shifts_df, pd.DataFrame):
        _set_df_state("shifts_df_value", shifts_df)
    latest_shifts = _df_from_state("shifts_df_value", _default_shifts_df)
    shift_names = [s for s in latest_shifts["name"].astype(str).tolist() if s.strip()][:5]
    if not shift_names:
        st.stop()

with tab_census:
    st.subheader("Enter expected patient counts per day/shift")
    base = _df_from_state("census_df_value", lambda: _default_census_df(shift_names))
    desired_cols = ["Day"] + shift_names
    base = base.copy()
    for col in desired_cols:
        if col not in base.columns:
            base[col] = 0
    extra = [c for c in base.columns if c not in desired_cols]
    if extra:
        base = base.drop(columns=extra)
    base = base.reindex(columns=desired_cols, fill_value=0)
    census_df = st.data_editor(base, key="census_editor", width="stretch")
    if isinstance(census_df, pd.DataFrame):
        _set_df_state("census_df_value", census_df.reindex(columns=desired_cols, fill_value=0))
    else:
        _set_df_state("census_df_value", base)

with tab_staff:
    st.subheader("Staff roster")
    st.caption("Only Techs show duty flags (open/close/bleach). RN/Admin flags are always False.")
    base = _df_from_state("staff_df_value", _default_staff_df)
    col_config = {
        "role": st.column_config.SelectboxColumn("role", options=["Tech","RN","Admin"], default="Tech"),
        "can_open":  st.column_config.CheckboxColumn("can_open",  default=False),
        "can_close": st.column_config.CheckboxColumn("can_close", default=False),
        "can_bleach":st.column_config.CheckboxColumn("can_bleach",default=False),
    }
    staff_df = st.data_editor(base, num_rows="dynamic", key="staff_editor", column_config=col_config, width="stretch")
    if isinstance(staff_df, pd.DataFrame) and not staff_df.empty:
        staff_df.loc[staff_df["role"]!="Tech", ["can_open","can_close","can_bleach"]] = False
    if isinstance(staff_df, pd.DataFrame):
        _set_df_state("staff_df_value", staff_df)
    else:
        _set_df_state("staff_df_value", base)

with tab_pto:
    st.subheader("PTO (Paid Time Off)")
    st.caption("Rows: id = staff id (matches Staff tab), date = YYYY-MM-DD")
    default_pto = pd.DataFrame([{"id":"", "date":""}])
    base = _df_from_state("pto_df_value", lambda: default_pto)
    pto_df = st.data_editor(
        base,
        key="pto_df",
        num_rows="dynamic",
        width="stretch",
        column_config={
            "id": st.column_config.TextColumn("id"),
            "date": st.column_config.TextColumn("date (YYYY-MM-DD)"),
        }
    )
    if isinstance(pto_df, pd.DataFrame):
        cleaned = []
        for _, r in pto_df.iterrows():
            sid = str(r.get("id","")).strip()
            d = str(r.get("date","")).strip()
            if sid and d:
                cleaned.append({"id": sid, "date": d})
        _set_df_state("pto_df_value", pd.DataFrame(cleaned) if cleaned else default_pto)
    else:
        _set_df_state("pto_df_value", default_pto)

with tab_rotation:
    st.subheader("Bleach Rotation (Techs only)")
    st.caption("Order (top→bottom). The cursor points to the NEXT Tech to bleach on the next bleach day.")
    tech_ids = []
    sdf = st.session_state.get("staff_df_value", pd.DataFrame())
    if isinstance(sdf, pd.DataFrame) and not sdf.empty:
        tech_ids = [str(r["id"]) for _, r in sdf.iterrows() if str(r.get("role",""))=="Tech" and str(r.get("id","")).strip()]
    existing = [x for x in st.session_state.get("bleach_rotation_order", []) if x in tech_ids]
    missing  = [x for x in tech_ids if x not in existing]
    order_df = pd.DataFrame({"tech_id": existing + missing}) if (existing or missing) else pd.DataFrame({"tech_id": []})
    order_edit = st.data_editor(order_df, key="rot_order_df", num_rows="dynamic", width="stretch",
                                column_config={"tech_id": st.column_config.SelectboxColumn("tech_id", options=tech_ids)})
    cleaned_order = [str(x).strip() for x in order_edit["tech_id"].tolist() if str(x).strip()]
    st.session_state["bleach_rotation_order"] = cleaned_order

    st.session_state["bleach_rotation_cursor"] = st.number_input(
        "Rotation cursor (0-based; NEXT to bleach)", min_value=0,
        value=int(st.session_state.get("bleach_rotation_cursor", 0)),
        step=1, key="bleach_rotation_cursor_num"
    )

with tab_generate:
    st.subheader("Generate schedule")

    # Buffer inputs + click with a form so edits don't trigger runs
    with st.form("gen_form"):
        start_date = st.date_input("Start date", value=datetime.today().date())
        weeks      = st.number_input("Weeks", min_value=1, max_value=12, value=2, step=1)
        trials     = st.number_input("Trials (best-of)", min_value=1, max_value=200, value=40, step=1)
        gen_clicked = st.form_submit_button("Generate schedule now", type="primary")

    if not st.session_state.get("config"):
        st.info("No config loaded. Save or Load a config first.")
    elif gen_clicked:
        cfg = build_v2_config_from_ui(
            st.session_state.get("shifts_df_value", pd.DataFrame()),
            st.session_state.get("census_df_value", pd.DataFrame()),
            st.session_state.get("staff_df_value", pd.DataFrame()),
            patients_per_tech=st.session_state["patients_per_tech"],
            techs_per_rn=st.session_state["techs_per_rn"],
            max_techs_per_day=st.session_state["max_techs_per_day"],
            min_rn_per_shift=st.session_state["min_rn_per_shift"],
            enforce_day_cap=st.session_state["enforce_day_cap"],
            sunday_makeup_enabled=st.session_state["sunday_makeup_enabled"],
            max_shifts_per_day_by_role={"Tech": int(st.session_state["tech_max"]), "RN": int(st.session_state["rn_max"]), "Admin": int(st.session_state["admin_max"])},
            min_gap_same_day_hours=float(st.session_state["same_day_gap"]),
            work_days_mode=st.session_state["work_days_mode"],
            work_days_by_role={"Tech": int(st.session_state["role_tech_days"]), "RN": int(st.session_state["role_rn_days"]), "Admin": int(st.session_state["role_admin_days"])},
            work_days_per_person={},
            soft_penalty_exceed_week=float(st.session_state["soft_penalty_exceed_week"]),
            clinic_name=st.session_state["clinic_name"], timezone=st.session_state["timezone"],
            bleach_rotation_order=st.session_state["bleach_rotation_order"],
            bleach_rotation_cursor=st.session_state["bleach_rotation_cursor"],
            bleach_days=st.session_state.get("bleach_days", []),
        )
        st.session_state["config"] = cfg

        payload = {
            "config": cfg,
            "start":  start_date.strftime("%Y-%m-%d"),
            "weeks":  int(weeks),
            "trials": int(trials),
            "pto_rows": st.session_state.get("pto_df_value", pd.DataFrame()).to_dict("records"),
        }
        try:
            r = requests.post(f"{api_url}/generate", json=payload, timeout=180)
            if r.status_code != 200:
                st.error(f"API error: {r.status_code} {r.text}")
            else:
                st.session_state["excel_bytes"] = r.content
                st.session_state["excel_name"]  = "schedule_v2.xlsx"
                st.success("Generated schedule ✅ — see Results")

                # Advance bleach cursor by number of bleach days in horizon
                days = [start_date + timedelta(days=i) for i in range(int(weeks)*7)]
                if not st.session_state["sunday_makeup_enabled"]:
                    days = [d for d in days if d.weekday() != 6]  # drop Sundays
                num_bleach_days = sum(1 for d in days if DOWS[d.weekday()] in st.session_state.get("bleach_days", []))
                order = st.session_state.get("bleach_rotation_order", [])
                if order and num_bleach_days:
                    st.session_state["bleach_rotation_cursor"] = (st.session_state["bleach_rotation_cursor"] + num_bleach_days) % len(order)
                    st.info(f"Bleach rotation cursor advanced by {num_bleach_days}")
        except Exception as e:
            st.error(f"Request failed: {e}")


with tab_results:
    st.subheader("Results")
    if not st.session_state.get("excel_bytes"):
        st.info("Nothing generated yet.")
    else:
        st.download_button("Download Excel",
                           data=st.session_state["excel_bytes"],
                           file_name=st.session_state["excel_name"],
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        try:
            buf = BytesIO(st.session_state["excel_bytes"])
            cov = pd.read_excel(buf, sheet_name="Coverage")
            buf.seek(0); ros = pd.read_excel(buf, sheet_name="Roster")
            try:
                buf.seek(0); wk1 = pd.read_excel(buf, sheet_name="Week 1")
            except Exception:
                wk1 = None
            c1, c2 = st.columns(2)
            with c1:
                st.caption("Coverage"); st.dataframe(cov, width="stretch", height=420)
            with c2:
                st.caption("Roster");   st.dataframe(ros, width="stretch", height=420)
            if wk1 is not None:
                st.caption("Week 1"); st.dataframe(wk1, width="stretch", height=320)
        except Exception as e:
            st.error(f"Could not parse Excel to preview: {e}")
