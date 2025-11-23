from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Dict, List
from pathlib import Path
import json
import sys

import pandas as pd
import streamlit as st  # type: ignore[import]

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.scheduler import (
    ConstraintToggles,
    DailyRequirement,
    PTOEntry,
    ScheduleConfig,
    StaffMember,
    StaffPreferences,
    export_schedule_to_excel,
    run_tournament,
)
from backend.scheduler.model import DAYS

st.set_page_config(page_title="Clinic Scheduler", layout="wide")
st.title("Clinic Scheduler")


def apply_theme() -> None:
    if st.session_state.get("dark_mode", False):
        st.markdown(
            """
            <style>
            body { background-color: #0f172a; color: #e2e8f0; }
            .stApp { background-color: #0f172a; color: #e2e8f0; }
            div[data-testid="stVerticalBlock"] { background-color: transparent; }
            </style>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            """
            <style>
            body { background-color: #f8fafc; color: #0f172a; }
            .stApp { background-color: #f8fafc; color: #0f172a; }
            </style>
            """,
            unsafe_allow_html=True,
        )


def init_defaults() -> None:
    defaults = {
        "clinic_name": "Demo Clinic",
        "timezone": "America/Chicago",
        "start_date": date.today(),
        "weeks": 6,
        "patients_per_tech": 4,
        "patients_per_rn": 12,
        "techs_per_rn": 4,
        "enforce_three_day_cap": True,
        "enforce_post_bleach_rest": True,
        "enforce_alt_saturdays": True,
        "limit_tech_four_days": True,
        "limit_rn_four_days": True,
        "bleach_day": "Thu",
        "bleach_cursor": 0,
        "tournament_trials": 20,
        "tournament_seed": 0,
        "config_folder": "configs",
        "config_filename": "",
        "last_seed": 0,
        "pref_selected_staff": [],
        "dark_mode": False,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


init_defaults()

if "_pending_state" in st.session_state:
    for _k, _v in st.session_state["_pending_state"].items():
        st.session_state[_k] = _v
    del st.session_state["_pending_state"]


def default_staff_df() -> pd.DataFrame:
    columns = ["id","name","role","can_open","can_close","can_bleach"] + DAYS + [
        "open_mwf","open_tts","mid_mwf","mid_tts","close_mwf","close_tts"
    ]
    return pd.DataFrame(columns=columns)


def default_demand_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"Day": day, "Patients": 16, "Tech_Open": 1, "Tech_Mid": 2, "Tech_Close": 1, "RN_Count": 1, "Admin_Count": 1}
            for day in DAYS
        ]
    )


def default_pto_df() -> pd.DataFrame:
    return pd.DataFrame([{"staff_id": "", "start_date": pd.NaT, "end_date": pd.NaT}])


def _coerce_editor_df(value, fallback: pd.DataFrame) -> pd.DataFrame:
    if isinstance(value, pd.DataFrame):
        return value.copy()
    if value is None:
        return fallback.copy()
    try:
        if isinstance(value, dict):
            if all(isinstance(v, dict) for v in value.values()):
                df = pd.DataFrame(list(value.values()))
            else:
                df = pd.DataFrame(value)
        else:
            df = pd.DataFrame(value)
    except Exception:
        try:
            df = pd.DataFrame.from_records(value)  # type: ignore[arg-type]
        except Exception:
            return fallback.copy()
    if df.empty and not fallback.empty:
        return fallback.copy()
    return df


if "staff_df" not in st.session_state:
    st.session_state["staff_df"] = default_staff_df()
if "demand_df" not in st.session_state:
    st.session_state["demand_df"] = default_demand_df()
if "pto_df" not in st.session_state:
    st.session_state["pto_df"] = default_pto_df()

# Apply deferred widget updates before rendering widgets
if "next_bleach_cursor" in st.session_state:
    st.session_state["bleach_cursor"] = st.session_state.pop("next_bleach_cursor")
if "next_tournament_seed" in st.session_state:
    st.session_state["tournament_seed"] = st.session_state.pop("next_tournament_seed")


with st.sidebar:
    st.header("Configuration")
    st.checkbox("Dark mode", key="dark_mode")
    clinic_name = st.text_input("Clinic name", key="clinic_name")
    timezone = st.text_input("Timezone", key="timezone")
    start_date = st.date_input("Schedule start", key="start_date")
    weeks = st.number_input("Weeks", min_value=1, max_value=12, step=1, key="weeks")

    st.subheader("Ratios")
    patients_per_tech = st.number_input(
        "Patients per Tech", min_value=1, max_value=6, step=1, key="patients_per_tech"
    )
    patients_per_rn = st.number_input(
        "Patients per RN", min_value=1, max_value=15, step=1, key="patients_per_rn"
    )
    techs_per_rn = st.number_input(
        "Techs per RN", min_value=1, max_value=6, step=1, key="techs_per_rn"
    )

    st.subheader("Constraints")
    enforce_three_day = st.checkbox(
        "Limit to 2 consecutive days", key="enforce_three_day_cap"
    )
    enforce_post_bleach = st.checkbox(
        "No shift day after bleach", key="enforce_post_bleach_rest"
    )
    enforce_alt_sat = st.checkbox(
        "No consecutive Saturdays", key="enforce_alt_saturdays"
    )
    limit_tech = st.checkbox(
        "Limit Techs to 4 days/week", key="limit_tech_four_days"
    )
    limit_rn = st.checkbox(
        "Limit RNs to 4 days/week", key="limit_rn_four_days"
    )

    st.subheader("Bleach Rotation")
    bleach_day = st.selectbox(
        "Bleach Day",
        options=DAYS,
        index=DAYS.index(st.session_state["bleach_day"]) if st.session_state["bleach_day"] in DAYS else 0,
        key="bleach_day",
    )

staff_df = st.session_state["staff_df"]
demands_df = st.session_state["demand_df"]
pto_df = st.session_state["pto_df"]

apply_theme()

tab_staff, tab_demand, tab_prefs, tab_pto, tab_run, tab_config = st.tabs(
    ["Staff", "Demand", "Preferences Summary", "PTO", "Run Scheduler", "Config"]
)

st.toggle("Dark mode", key="dark_mode")
with tab_staff:
    st.subheader("Staff Roster")
    base_columns = ["id", "name", "role", "can_open", "can_close", "can_bleach"] + DAYS
    pref_columns = ["open_mwf", "open_tts", "mid_mwf", "mid_tts", "close_mwf", "close_tts"]

    def _blank_staff_row() -> Dict[str, object]:
        row: Dict[str, object] = {
            "id": "",
            "name": "",
            "role": "",
            "can_open": False,
            "can_close": False,
            "can_bleach": False,
        }
        for day in DAYS:
            row[day] = False
        return row

    editor_key = "staff_editor_df"
    if editor_key not in st.session_state:
        st.session_state[editor_key] = staff_df[base_columns].reset_index(drop=True).copy()

    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        if st.button("Add blank row", help="Insert an empty staff row"):
            editor_df = st.session_state[editor_key].copy()
            editor_df = pd.concat([editor_df, pd.DataFrame([_blank_staff_row()])[base_columns]], ignore_index=True)
            st.session_state[editor_key] = editor_df
        if st.button("Clear all rows", type="secondary"):
            st.session_state[editor_key] = pd.DataFrame([_blank_staff_row()])[base_columns]
    with col2:
        current_df = st.session_state[editor_key]
        row_labels = [f"{idx}: {row.get('id') or '(blank)'}" for idx, row in current_df.iterrows()]
        to_delete = st.selectbox("Delete row", options=row_labels if row_labels else ["(none)"])
        if st.button("Remove selected", key="remove_staff_row") and row_labels:
            try:
                idx = int(to_delete.split(":")[0])
                st.session_state[editor_key] = current_df.drop(index=idx).reset_index(drop=True)
            except Exception:
                st.warning("Could not delete that row.")
    with col3:
        st.caption("Use 'Add blank row' to insert entries; remove via selector; changes persist until you click 'Apply staff changes'.")

    editor_df = st.session_state[editor_key].copy()
    editor_df = editor_df.reindex(columns=base_columns).reset_index(drop=True)
    for col in ["id", "name", "role"]:
        editor_df[col] = editor_df[col].fillna("").astype(str)
    for col in DAYS + ["can_open", "can_close", "can_bleach"]:
        if col not in editor_df:
            editor_df[col] = False
        editor_df[col] = editor_df[col].fillna(False).astype(bool)

    col_config = {
        "id": st.column_config.TextColumn("ID"),
        "name": st.column_config.TextColumn("Name"),
        "role": st.column_config.SelectboxColumn("Role", options=["Tech", "RN", "Admin"]),
        "can_open": st.column_config.CheckboxColumn("Can Open"),
        "can_close": st.column_config.CheckboxColumn("Can Close"),
        "can_bleach": st.column_config.CheckboxColumn("Can Bleach"),
    }
    for day in DAYS:
        col_config[day] = st.column_config.CheckboxColumn(day)

    editor_output = st.data_editor(
        editor_df,
        key="staff_editor",
        num_rows="fixed",
        width="stretch",
        hide_index=True,
        column_order=base_columns,
        column_config=col_config,
    )
    st.session_state[editor_key] = _coerce_editor_df(editor_output, editor_df).reset_index(drop=True)

    if st.button("Apply staff changes", type="primary"):
        edited_display = st.session_state[editor_key].copy()
        existing_pref = {
            str(row.get("id", "")).strip(): {pref: float(row.get(pref, 0.0) or 0.0) for pref in pref_columns}
            for _, row in staff_df.iterrows()
            if str(row.get("id", "")).strip()
        }
        merged_rows: List[Dict[str, object]] = []
        for _, row in edited_display.iterrows():
            record = _blank_staff_row().copy()
            for col in base_columns:
                value = row.get(col, record.get(col))
                if col in DAYS or col in ["can_open", "can_close", "can_bleach"]:
                    record[col] = bool(value)
                elif col == "role":
                    record[col] = str(value or "Tech").strip() or "Tech"
                elif col in ["name", "id"]:
                    record[col] = str(value or "").strip()
                else:
                    record[col] = value
            staff_id = str(record.get("id", "")).strip()
            pref_values = existing_pref.get(staff_id, {}) if staff_id else {}
            for pref in pref_columns:
                record[pref] = float(pref_values.get(pref, 0.0))
            merged_rows.append(record)
        if not merged_rows:
            merged_rows.append({**_blank_staff_row(), **{pref: 0.0 for pref in pref_columns}})
        merged_df = pd.DataFrame(merged_rows, columns=base_columns + pref_columns)
        st.session_state["staff_df"] = merged_df
        staff_df = merged_df.copy()

with tab_demand:
    st.subheader("Daily Requirements")
    demand_display = demands_df.copy()
    edited_demand = st.data_editor(
        demand_display,
        key="demand_editor",
        num_rows="dynamic",
        width="stretch",
        hide_index=True,
    )
    edited_demand = _coerce_editor_df(edited_demand, demand_display)
    demand_rows = []
    for day in DAYS:
        match = edited_demand[edited_demand["Day"] == day]
        if not match.empty:
            row = match.iloc[0].to_dict()
        else:
            row = {"Day": day}
        row["Patients"] = int(row.get("Patients", 0) or 0)
        row["Tech_Open"] = int(row.get("Tech_Open", 0) or 0)
        row["Tech_Mid"] = int(row.get("Tech_Mid", 0) or 0)
        row["Tech_Close"] = int(row.get("Tech_Close", 0) or 0)
        row["RN_Count"] = int(row.get("RN_Count", 0) or 0)
        row["Admin_Count"] = int(row.get("Admin_Count", 0) or 0)
        demand_rows.append(row)
    merged_demand = pd.DataFrame(demand_rows)
    st.session_state["demand_df"] = merged_demand
    demands_df = st.session_state["demand_df"]

with tab_prefs:
    st.subheader("Preference Weights")
    st.caption(
        "Adjust duty preference modifiers (negative = strongly prefers, positive = dislikes). "
        "Values apply separately to Monday/Wednesday/Friday vs Tuesday/Thursday/Saturday rotations. "
        "A value of 0 means neutral."
    )
    pref_columns = [
        "open_mwf",
        "open_tts",
        "mid_mwf",
        "mid_tts",
        "close_mwf",
        "close_tts",
    ]
    option_map = {
        f"{(row.get('name') or row['id']).strip()} ({row['role']})": row["id"]
        for _, row in staff_df.iterrows()
    }
    current_selection = st.session_state.get("pref_selected_staff", [])
    # Drop any selections that no longer exist in the roster
    current_selection = [sid for sid in current_selection if sid in option_map.values()]
    st.session_state["pref_selected_staff"] = current_selection
    default_labels = [label for label, sid in option_map.items() if sid in current_selection]
    selected_labels = st.multiselect(
        "Staff with custom preferences",
        options=list(option_map.keys()),
        default=default_labels,
    )
    selected_ids = [option_map[label] for label in selected_labels]
    st.session_state["pref_selected_staff"] = selected_ids

    updated_staff_df = st.session_state["staff_df"].copy()
    id_to_index = {str(row["id"]): idx for idx, row in updated_staff_df.iterrows()}

    for staff_id in selected_ids:
        idx = id_to_index.get(staff_id)
        if idx is None:
            continue
        row = updated_staff_df.loc[idx]
        display_name = str(row.get("name", staff_id)).strip() or staff_id
        role = str(row.get("role", "Tech"))
        with st.expander(f"{display_name} ({role})", expanded=False):
            st.caption("Set preference modifiers (step 0.25). Negative = likes, positive = dislikes, 0 = neutral.")
            col_left, col_right = st.columns(2)
            with col_left:
                updated_staff_df.at[idx, "open_mwf"] = st.slider(
                    "Open (Mon/Wed/Fri)",
                    -5.0,
                    5.0,
                    float(row.get("open_mwf", 0.0) or 0.0),
                    0.25,
                    key=f"pref_open_mwf_{staff_id}",
                )
                updated_staff_df.at[idx, "mid_mwf"] = st.slider(
                    "Mid (Mon/Wed/Fri)",
                    -5.0,
                    5.0,
                    float(row.get("mid_mwf", 0.0) or 0.0),
                    0.25,
                    key=f"pref_mid_mwf_{staff_id}",
                )
                updated_staff_df.at[idx, "close_mwf"] = st.slider(
                    "Close (Mon/Wed/Fri)",
                    -5.0,
                    5.0,
                    float(row.get("close_mwf", 0.0) or 0.0),
                    0.25,
                    key=f"pref_close_mwf_{staff_id}",
                )
            with col_right:
                updated_staff_df.at[idx, "open_tts"] = st.slider(
                    "Open (Tue/Thu/Sat)",
                    -5.0,
                    5.0,
                    float(row.get("open_tts", 0.0) or 0.0),
                    0.25,
                    key=f"pref_open_tts_{staff_id}",
                )
                updated_staff_df.at[idx, "mid_tts"] = st.slider(
                    "Mid (Tue/Thu/Sat)",
                    -5.0,
                    5.0,
                    float(row.get("mid_tts", 0.0) or 0.0),
                    0.25,
                    key=f"pref_mid_tts_{staff_id}",
                )
                updated_staff_df.at[idx, "close_tts"] = st.slider(
                    "Close (Tue/Thu/Sat)",
                    -5.0,
                    5.0,
                    float(row.get("close_tts", 0.0) or 0.0),
                    0.25,
                    key=f"pref_close_tts_{staff_id}",
                )
            if st.button(f"Reset {display_name}", key=f"reset_pref_{staff_id}"):
                for col in pref_columns:
                    updated_staff_df.at[idx, col] = 0.0
                st.session_state["pref_selected_staff"] = [
                    sid for sid in st.session_state["pref_selected_staff"] if sid != staff_id
                ]
                st.rerun()

    if selected_ids:
        mask = ~updated_staff_df["id"].isin(selected_ids)
        for col in pref_columns:
            updated_staff_df.loc[mask, col] = 0.0
    else:
        for col in pref_columns:
            updated_staff_df[col] = 0.0

    st.session_state["staff_df"] = updated_staff_df
    staff_df = updated_staff_df

with tab_pto:
    st.subheader("PTO (single day or range)")
    working_pto_df = st.session_state["pto_df"].copy()
    for col in ["start_date", "end_date"]:
        if col in working_pto_df:
            working_pto_df[col] = pd.to_datetime(working_pto_df[col], errors="coerce")
    st.data_editor(
        working_pto_df,
        key="pto_editor",
        num_rows="dynamic",
        width="stretch",
        column_config={
            "start_date": st.column_config.DateColumn("Start"),
            "end_date": st.column_config.DateColumn("End"),
        },
    )
    pto_widget_value = st.session_state.get("pto_editor")
    updated_pto = _coerce_editor_df(pto_widget_value, working_pto_df)
    for col in ["start_date", "end_date"]:
        if col in updated_pto:
            updated_pto[col] = pd.to_datetime(updated_pto[col], errors="coerce")
    st.session_state["pto_df"] = updated_pto
    pto_df = st.session_state["pto_df"]


def build_staff_members(df: pd.DataFrame) -> List[StaffMember]:
    records: List[StaffMember] = []
    for _, row in df.iterrows():
        staff_id = str(row.get("id", "")).strip()
        if not staff_id:
            continue
        role = str(row.get("role", "Tech")).strip() or "Tech"
        availability = {}
        for day in DAYS:
            value = row.get(day, True)
            if pd.isna(value):
                availability[day] = False
            else:
                availability[day] = bool(value)
        prefs = StaffPreferences(
            open_mwf=float(row.get("open_mwf", 1.0) or 1.0),
            open_tts=float(row.get("open_tts", 1.0) or 1.0),
            mid_mwf=float(row.get("mid_mwf", 1.0) or 1.0),
            mid_tts=float(row.get("mid_tts", 1.0) or 1.0),
            close_mwf=float(row.get("close_mwf", 1.0) or 1.0),
            close_tts=float(row.get("close_tts", 1.0) or 1.0),
        )
        records.append(
            StaffMember(
                id=staff_id,
                name=str(row.get("name", "")).strip(),
                role=role,
                can_open=bool(row.get("can_open", False)),
                can_close=bool(row.get("can_close", False)),
                can_bleach=bool(row.get("can_bleach", False)) if role == "Tech" else False,
                availability=availability,
                preferences=prefs,
            )
        )
    return records


def build_requirements(df: pd.DataFrame) -> List[DailyRequirement]:
    reqs: List[DailyRequirement] = []
    for day in DAYS:
        match = df[df["Day"] == day]
        if match.empty:
            raise ValueError(f"Requirement missing for {day}")
        row = match.iloc[0]
        reqs.append(
            DailyRequirement(
                day_name=day,
                patient_count=int(row.get("Patients", 0) or 0),
                tech_openers=int(row.get("Tech_Open", 0) or 0),
                tech_mids=int(row.get("Tech_Mid", 0) or 0),
                tech_closers=int(row.get("Tech_Close", 0) or 0),
                rn_count=int(row.get("RN_Count", 0) or 0),
                admin_count=int(row.get("Admin_Count", 0) or 0),
            )
        )
    return reqs


def build_pto_entries(df: pd.DataFrame) -> List[PTOEntry]:
    entries: List[PTOEntry] = []
    for _, row in df.iterrows():
        staff_id = str(row.get("staff_id", "")).strip()
        if not staff_id:
            continue
        start_val = row.get("start_date")
        end_val = row.get("end_date") or start_val
        if start_val is None or pd.isna(start_val):
            continue
        start_dt = pd.to_datetime(start_val).date()
        end_dt = pd.to_datetime(end_val).date() if end_val and not pd.isna(end_val) else start_dt
        if end_dt < start_dt:
            start_dt, end_dt = end_dt, start_dt
        current = start_dt
        while current <= end_dt:
            entries.append(PTOEntry(staff_id=staff_id, date=current))
            current += timedelta(days=1)
    return entries


def slugify(name: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "-" for ch in name)
    cleaned = cleaned.strip("-")
    return cleaned or "clinic"


def current_config_payload() -> Dict:
    staff_df = st.session_state["staff_df"].copy()
    demand_df = st.session_state["demand_df"].copy()
    pto_df = st.session_state["pto_df"].copy()
    pto_records = []
    for _, row in pto_df.iterrows():
        start_val = row.get("start_date")
        end_val = row.get("end_date")
        if isinstance(start_val, pd.Timestamp):
            start_val = start_val.to_pydatetime().date()
        if isinstance(end_val, pd.Timestamp):
            end_val = end_val.to_pydatetime().date()
        pto_records.append(
            {
                "staff_id": row.get("staff_id", ""),
                "start_date": start_val.isoformat() if isinstance(start_val, date) else "",
                "end_date": end_val.isoformat() if isinstance(end_val, date) else "",
            }
        )
    return {
        "clinic": {
            "name": st.session_state["clinic_name"],
            "timezone": st.session_state["timezone"],
        },
        "schedule": {
            "start": st.session_state["start_date"].isoformat(),
            "weeks": int(st.session_state["weeks"]),
        },
        "ratios": {
            "patients_per_tech": int(st.session_state["patients_per_tech"]),
            "patients_per_rn": int(st.session_state["patients_per_rn"]),
            "techs_per_rn": int(st.session_state["techs_per_rn"]),
        },
        "constraints": {
            "enforce_three_day_cap": bool(st.session_state["enforce_three_day_cap"]),
            "enforce_post_bleach_rest": bool(st.session_state["enforce_post_bleach_rest"]),
            "enforce_alt_saturdays": bool(st.session_state["enforce_alt_saturdays"]),
            "limit_tech_four_days": bool(st.session_state["limit_tech_four_days"]),
            "limit_rn_four_days": bool(st.session_state["limit_rn_four_days"]),
        },
        "bleach": {
            "day": st.session_state["bleach_day"],
            "rotation": list(st.session_state.get("bleach_selection", [])),
            "cursor": int(st.session_state.get("bleach_cursor", 0)),
        },
        "tournament": {
            "trials": int(st.session_state.get("tournament_trials", 20)),
            "last_seed": int(st.session_state.get("tournament_seed", 0)),
        },
        "staff": staff_df.to_dict("records"),
        "demand": demand_df.to_dict("records"),
        "pto": pto_records,
    }


def apply_config(config: Dict) -> None:
    clinic = config.get("clinic", {})
    schedule = config.get("schedule", {})
    ratios = config.get("ratios", {})
    constraints = config.get("constraints", {})
    bleach = config.get("bleach", {})
    tournament = config.get("tournament", {})

    pending = st.session_state.get("_pending_state", {}).copy()
    pending["clinic_name"] = clinic.get("name", st.session_state["clinic_name"])
    pending["timezone"] = clinic.get("timezone", st.session_state["timezone"])
    if "start" in schedule:
        pending["start_date"] = date.fromisoformat(schedule["start"])
    pending["weeks"] = int(schedule.get("weeks", st.session_state["weeks"]))
    pending["patients_per_tech"] = int(ratios.get("patients_per_tech", st.session_state["patients_per_tech"]))
    pending["patients_per_rn"] = int(ratios.get("patients_per_rn", st.session_state["patients_per_rn"]))
    pending["techs_per_rn"] = int(ratios.get("techs_per_rn", st.session_state["techs_per_rn"]))
    pending["enforce_three_day_cap"] = bool(
        constraints.get("enforce_three_day_cap", st.session_state["enforce_three_day_cap"])
    )
    pending["enforce_post_bleach_rest"] = bool(
        constraints.get("enforce_post_bleach_rest", st.session_state["enforce_post_bleach_rest"])
    )
    pending["enforce_alt_saturdays"] = bool(
        constraints.get("enforce_alt_saturdays", st.session_state["enforce_alt_saturdays"])
    )
    pending["limit_tech_four_days"] = bool(
        constraints.get("limit_tech_four_days", st.session_state["limit_tech_four_days"])
    )
    pending["limit_rn_four_days"] = bool(
        constraints.get("limit_rn_four_days", st.session_state["limit_rn_four_days"])
    )
    pending["bleach_day"] = bleach.get("day", st.session_state["bleach_day"])
    pending["bleach_cursor"] = int(bleach.get("cursor", st.session_state["bleach_cursor"]))
    pending["bleach_selection"] = list(bleach.get("rotation", st.session_state.get("bleach_selection", [])))
    pending["tournament_trials"] = int(tournament.get("trials", st.session_state["tournament_trials"]))
    pending["tournament_seed"] = int(tournament.get("last_seed", st.session_state["tournament_seed"]))
    st.session_state["_pending_state"] = pending

    staff_records = config.get("staff", [])
    demand_records = config.get("demand", [])
    pto_records = config.get("pto", [])

    if staff_records:
        st.session_state["staff_df"] = pd.DataFrame(staff_records)
    else:
        st.session_state["staff_df"] = default_staff_df()

    if demand_records:
        st.session_state["demand_df"] = pd.DataFrame(demand_records)
    else:
        st.session_state["demand_df"] = default_demand_df()

    if pto_records:
        pto_df = pd.DataFrame(pto_records)
        for col in ["start_date", "end_date"]:
            if col in pto_df:
                pto_df[col] = pd.to_datetime(pto_df[col], errors="coerce")
        st.session_state["pto_df"] = pto_df
    else:
        st.session_state["pto_df"] = default_pto_df()

    pref_cols = ["open_mwf","open_tts","mid_mwf","mid_tts","close_mwf","close_tts"]
    pref_selected = st.session_state.get("pref_selected_staff", [])
    pref_selected = [
        row["id"]
        for _, row in st.session_state["staff_df"].iterrows()
        if any(float(row.get(col,0) or 0) != 0 for col in pref_cols)
    ]
    st.session_state["pref_selected_staff"] = pref_selected

    for key in ["staff_editor","staff_editor_df","demand_editor","prefs_editor","pto_editor"]:
        if key in st.session_state:
            del st.session_state[key]

    st.rerun()
with tab_run:
    st.subheader("Bleach Rotation Order")
    bleach_candidates = [row["id"] for _, row in staff_df.iterrows() if row.get("can_bleach", False)]
    existing_rotation = [sid for sid in st.session_state.get("bleach_selection", bleach_candidates) if sid in bleach_candidates]
    if not existing_rotation:
        existing_rotation = bleach_candidates
    rotation_selection = st.multiselect(
        "Eligible Tech IDs",
        options=bleach_candidates,
        default=existing_rotation,
        key="bleach_selection",
    )
    bleach_cursor = st.number_input(
        "Rotation cursor (0 = start)", min_value=0, value=st.session_state["bleach_cursor"], step=1, key="bleach_cursor"
    )

    st.subheader("Tournament Settings")
    tournament_trials = st.number_input(
        "Iterations per run",
        min_value=1,
        max_value=200,
        step=1,
        value=st.session_state["tournament_trials"],
        key="tournament_trials",
    )
    base_seed_input = st.number_input(
        "Starting seed (0 = random)",
        min_value=0,
        step=1,
        value=st.session_state["tournament_seed"],
        key="tournament_seed",
    )

    st.markdown("---")
    if st.button("Generate Schedule", type="primary"):
        try:
            staff_members = build_staff_members(staff_df)
            requirements = build_requirements(demands_df)
            pto_entries = build_pto_entries(pto_df)
            base_seed = int(base_seed_input) if int(base_seed_input) > 0 else None
            cfg = ScheduleConfig(
                clinic_name=clinic_name,
                timezone=timezone,
                start_date=start_date,
                weeks=int(weeks),
                bleach_day=bleach_day,
                bleach_rotation=list(rotation_selection),
                bleach_cursor=int(bleach_cursor),
                patients_per_tech=int(patients_per_tech),
                patients_per_rn=int(patients_per_rn),
                techs_per_rn=int(techs_per_rn),
                toggles=ConstraintToggles(
                    enforce_three_day_cap=enforce_three_day,
                    enforce_post_bleach_rest=enforce_post_bleach,
                    enforce_alt_saturdays=enforce_alt_sat,
                    limit_tech_four_days=limit_tech,
                    limit_rn_four_days=limit_rn,
                ),
            )
            result, winning_seed = run_tournament(
                staff_members,
                requirements,
                cfg,
                pto_entries=pto_entries,
                trials=int(tournament_trials),
                base_seed=base_seed,
            )
            staff_map = {s.id: s for s in staff_members}
            excel_bytes = export_schedule_to_excel(result, staff_map)
            st.session_state["schedule_result"] = result
            st.session_state["schedule_excel"] = excel_bytes
            st.session_state["next_bleach_cursor"] = result.bleach_cursor
            st.session_state["next_tournament_seed"] = winning_seed
            st.session_state["last_seed"] = winning_seed
            st.success(f"Schedule generated. Next bleach cursor: {result.bleach_cursor} | Winning seed: {winning_seed}")
            roster_preview = pd.DataFrame(
                [
                    {
                        "Date": assign.slot.date,
                        "Day": assign.slot.day_name,
                        "Role": assign.slot.role,
                        "Duty": "bleach" if assign.slot.is_bleach else assign.slot.duty,
                        "Staff": staff_map[assign.staff_id].name if assign.staff_id in staff_map else (assign.staff_id or ""),
                        "Notes": "; ".join(assign.notes),
                    }
                    for assign in result.assignments
                ]
            )
            st.dataframe(roster_preview, width="stretch", hide_index=True)
            st.download_button(
                "Download Excel",
                data=excel_bytes,
                file_name="schedule.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
            summary_df = pd.DataFrame(
                [{"Staff": staff_map[sid].name if sid in staff_map else sid, "Shifts": total} for sid, total in result.stats.items()]
            )
            st.bar_chart(summary_df.set_index("Staff"))
        except Exception as exc:
            st.error(f"Failed to generate schedule: {exc}")

with tab_config:
    st.subheader("Save / Load Config")
    folder_input = st.text_input("Config folder", key="config_folder")
    config_folder_path = Path(folder_input).expanduser()
    filename_input = st.text_input("File name (optional, .json)", key="config_filename")

    if st.button("Save Config"):
        try:
            config_data = current_config_payload()
            config_folder_path.mkdir(parents=True, exist_ok=True)
            filename = filename_input.strip()
            if not filename:
                stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
                filename = f"{slugify(st.session_state['clinic_name'])}.{stamp}.json"
            if not filename.endswith(".json"):
                filename += ".json"
            target_path = config_folder_path / filename
            target_path.write_text(json.dumps(config_data, indent=2))
            st.success(f"Saved config to {target_path}")
        except Exception as exc:
            st.error(f"Failed to save config: {exc}")

    existing_configs = []
    if config_folder_path.exists():
        existing_configs = sorted(config_folder_path.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)

    if existing_configs:
        options = [p.name for p in existing_configs]
        selected_name = st.selectbox("Existing configs", options, key="config_selected")
        if st.button("Load Selected", type="primary"):
            try:
                selected_path = config_folder_path / selected_name
                cfg = json.loads(selected_path.read_text())
                apply_config(cfg)
            except Exception as exc:
                st.error(f"Failed to load config: {exc}")
    else:
        st.info("No config files found in the selected folder.")
