from __future__ import annotations

from collections import defaultdict
from datetime import date
from io import BytesIO
from typing import Dict, Iterable, List, Optional, Set

import pandas as pd

from .model import Assignment, ScheduleResult, StaffMember
from .engine import OPEN_LABEL


def _roster_rows(result: ScheduleResult, staff_lookup: Dict[str, StaffMember], allowed_roles: Set[str]):
    for assignment in result.assignments:
        slot = assignment.slot
        if allowed_roles and slot.role not in allowed_roles:
            continue
        staff = staff_lookup.get(assignment.staff_id or "", None)
        yield {
            "Date": slot.date.strftime("%Y-%m-%d"),
            "Day": slot.day_name,
            "Role": slot.role,
            "Duty": ("bleach" if slot.is_bleach else slot.duty) or "",
            "Slot": slot.slot_index,
            "StaffID": assignment.staff_id or "",
            "StaffName": staff.name if staff else assignment.staff_id or "",
            "Notes": "; ".join(assignment.notes) if assignment.notes else "",
        }


def _coverage_rows(result: ScheduleResult):
    day_role_counts: Dict[tuple, int] = {}
    for assignment in result.assignments:
        slot = assignment.slot
        key = (slot.date.strftime("%Y-%m-%d"), slot.day_name, slot.role, slot.duty)
        filled = assignment.staff_id not in (None, "", OPEN_LABEL)
        day_role_counts[key] = day_role_counts.get(key, 0) + (1 if filled else 0)
    for (date_str, day_name, role, duty), count in sorted(day_role_counts.items()):
        yield {
            "Date": date_str,
            "Day": day_name,
            "Role": role,
            "Duty": duty,
            "Filled": count,
        }


def _summary_rows(result: ScheduleResult, staff_lookup: Dict[str, StaffMember]):
    for staff_id, total in sorted(result.stats.items(), key=lambda x: x[0]):
        staff = staff_lookup.get(staff_id)
        yield {
            "StaffID": staff_id,
            "StaffName": staff.name if staff else "",
            "TotalShifts": total,
        }


def _note_rows(result: ScheduleResult, staff_lookup: Dict[str, StaffMember]) -> List[Dict[str, str]]:
    notes_by_date: Dict[str, Set[str]] = defaultdict(set)
    for assignment in result.assignments:
        slot = assignment.slot
        date_str = slot.date.strftime("%Y-%m-%d")
        if assignment.notes:
            for n in assignment.notes:
                notes_by_date[date_str].add(n)
        if assignment.staff_id in (None, "", OPEN_LABEL):
            notes_by_date[date_str].add(
                f"Open slot: {slot.role} {slot.duty or ''}#{slot.slot_index}".strip()
            )
    rows: List[Dict[str, str]] = []
    for date_str in sorted(notes_by_date.keys()):
        rows.append(
            {
                "Date": date_str,
                "Notes": "; ".join(sorted(notes_by_date[date_str])),
            }
        )
    return rows


def _notes_map(result: ScheduleResult) -> Dict[str, str]:
    out: Dict[str, Set[str]] = defaultdict(set)
    for assignment in result.assignments:
        slot = assignment.slot
        date_str = slot.date.strftime("%Y-%m-%d")
        if assignment.notes:
            for n in assignment.notes:
                out[date_str].add(n)
        if assignment.staff_id in (None, "", OPEN_LABEL):
            out[date_str].add(
                f"Open slot: {slot.role} {slot.duty or ''}#{slot.slot_index}".strip()
            )
    return {d: "; ".join(sorted(vals)) for d, vals in out.items()}


def _pto_notes_map(
    pto_entries: Iterable,
    staff_lookup: Dict[str, StaffMember],
) -> Dict[str, Set[str]]:
    out: Dict[str, Set[str]] = defaultdict(set)
    for entry in pto_entries or []:
        try:
            date_val = entry.date
        except AttributeError:
            continue
        date_str = date_val.strftime("%Y-%m-%d")
        staff_id = getattr(entry, "staff_id", "")
        name = staff_lookup.get(staff_id, StaffMember(id=staff_id, name=staff_id, role="")).name
        label = name or staff_id or "Unknown"
        out[date_str].add(f"{label} PTO")
    return out


def _role_matrix(
    assignments: List[Assignment],
    staff_lookup: Dict[str, StaffMember],
    *,
    role: str,
    dates: List[date],
) -> pd.DataFrame:
    if not dates:
        return pd.DataFrame()

    date_labels = [f"{dt.strftime('%a')} {dt.strftime('%m/%d')}" for dt in dates]
    entries: Dict[str, Dict[date, List[str]]] = defaultdict(lambda: defaultdict(list))

    for assignment in assignments:
        slot = assignment.slot
        if slot.role != role:
            continue
        staff_id = assignment.staff_id or OPEN_LABEL
        duty_label = "Bleach" if slot.is_bleach else (slot.duty.capitalize() if slot.duty else "Shift")
        if slot.slot_index:
            duty_label = f"{duty_label} #{slot.slot_index}"
        text = duty_label
        if assignment.notes:
            text += f" ({'; '.join(assignment.notes)})"
        entries[staff_id][slot.date].append(text)

    role_staff = [s for s in staff_lookup.values() if s.role == role]
    role_staff.sort(key=lambda s: (s.name or s.id).lower())
    rows = []

    for staff_member in role_staff:
        row = {"Name": staff_member.name or staff_member.id, "Role": staff_member.role}
        for dt, label in zip(dates, date_labels):
            cell = "\n".join(entries.get(staff_member.id, {}).get(dt, []))
            row[label] = cell
        rows.append(row)

    if entries.get(OPEN_LABEL):
        row = {"Name": OPEN_LABEL, "Role": role}
        for dt, label in zip(dates, date_labels):
            cell = "\n".join(entries[OPEN_LABEL].get(dt, []))
            row[label] = cell
        rows.append(row)

    return pd.DataFrame(rows)


def _roster_matrix(
    assignments: List[Assignment],
    staff_lookup: Dict[str, StaffMember],
    notes_map: Dict[str, str],
    pto_notes: Dict[str, Set[str]],
) -> pd.DataFrame:
    if not assignments:
        return pd.DataFrame()
    cols: Set[str] = set()
    data: Dict[str, Dict[str, str]] = defaultdict(dict)
    date_day: Dict[str, str] = {}
    for assignment in assignments:
        slot = assignment.slot
        date_str = slot.date.strftime("%Y-%m-%d")
        date_day[date_str] = slot.day_name
        duty_label = "Bleach" if slot.is_bleach else (slot.duty.capitalize() if slot.duty else "Duty")
        col = f"{slot.role}-{duty_label}-{slot.slot_index}"
        cols.add(col)
        name = (
            OPEN_LABEL
            if assignment.staff_id in (None, "", OPEN_LABEL)
            else staff_lookup.get(
                assignment.staff_id,
                StaffMember(id=assignment.staff_id, name=assignment.staff_id, role=slot.role),
            ).name
        )
        data[date_str][col] = name

    duty_priority = {"Open": 1, "Mid": 2, "Mid2": 2.5, "Mid3": 2.75, "Mid4": 2.8, "Bleach": 3.5, "Close": 4}

    def _col_key(col: str):
        # col format: Role-Duty-idx
        try:
            role, duty, idx = col.split("-")
            idx_val = float(idx)
        except ValueError:
            role, duty, idx_val = col, "", 0
        base = duty_priority.get(duty, 5)
        return (role, base, idx_val)

    ordered_cols = sorted(cols, key=_col_key)
    rows = []
    for date_str in sorted(data.keys()):
        row = {"Date": date_str, "Day": date_day.get(date_str, "")}
        for c in ordered_cols:
            row[c] = data[date_str].get(c, "")
        notes = set()
        if notes_map.get(date_str):
            notes.update([notes_map[date_str]])
        if pto_notes.get(date_str):
            notes.update(pto_notes[date_str])
        row["Notes"] = "; ".join(sorted(notes))
        rows.append(row)
    return pd.DataFrame(rows)


def export_schedule_to_excel(
    result: ScheduleResult,
    staff: Dict[str, StaffMember],
    *,
    export_roles: Optional[List[str]] = None,
    pto_entries: Optional[Iterable] = None,
    file_path: Optional[str] = None,
) -> bytes:
    """
    Write the schedule to an Excel workbook.
    Returns the bytes buffer; optionally writes to `file_path`.
    """
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="xlsxwriter") as writer:
        all_dates = sorted({assignment.slot.date for assignment in result.assignments})

        allowed_roles = (
            {r for r in export_roles} if export_roles else {"RN", "Tech", "Admin"}
        )

        # Roster Matrix first
        roster_matrix = _roster_matrix(
            result.assignments,
            staff,
            _notes_map(result),
            _pto_notes_map(pto_entries, staff),
        )
        if not roster_matrix.empty:
            roster_matrix.to_excel(writer, sheet_name="Roster Matrix", index=False)

        roster_df = pd.DataFrame(list(_roster_rows(result, staff, allowed_roles)))
        if not roster_df.empty:
            roster_df.sort_values(["Date", "Role", "Duty", "Slot"], inplace=True)
        roster_df.to_excel(writer, sheet_name="Roster", index=False)

        coverage_df = pd.DataFrame(list(_coverage_rows(result)))
        coverage_df.to_excel(writer, sheet_name="Coverage", index=False)

        summary_df = pd.DataFrame(list(_summary_rows(result, staff)))
        summary_df.to_excel(writer, sheet_name="Summary", index=False)

        note_df = pd.DataFrame(_note_rows(result, staff))
        if not note_df.empty:
            note_df.to_excel(writer, sheet_name="Notes", index=False)

        role_tables = []
        for role_name, label in [("RN", "RN"), ("Tech", "Tech"), ("Admin", "Admin")]:
            if role_name not in allowed_roles:
                continue
            table = _role_matrix(result.assignments, staff, role=role_name, dates=all_dates)
            if not table.empty:
                role_tables.append((label, table))
                table.to_excel(writer, sheet_name=f"{label} Schedule", index=False)

        if role_tables:
            matrix_sheet = writer.book.add_worksheet("Matrix")
            writer.sheets["Matrix"] = matrix_sheet
            current_row = 0
            for label, table in role_tables:
                matrix_sheet.write(current_row, 0, f"{label} Schedule")
                table.to_excel(
                    writer,
                    sheet_name="Matrix",
                    startrow=current_row + 1,
                    startcol=0,
                    index=False,
                )
                current_row += len(table.index) + 3

        info_df = pd.DataFrame(
            [
                {"Metric": "Bleach Cursor", "Value": result.bleach_cursor},
                {"Metric": "Total Penalty", "Value": result.total_penalty},
                {"Metric": "Seed", "Value": result.seed if result.seed is not None else ""},
            ]
        )
        info_df.to_excel(writer, sheet_name="Meta", index=False)

        # Hide Slot and StaffID columns in the Roster sheet
        if "Roster" in writer.sheets and not roster_df.empty:
            roster_sheet = writer.sheets["Roster"]
            try:
                slot_idx = roster_df.columns.get_loc("Slot")
                staff_idx = roster_df.columns.get_loc("StaffID")
                roster_sheet.set_column(slot_idx, slot_idx, None, None, {"hidden": True})
                roster_sheet.set_column(staff_idx, staff_idx, None, None, {"hidden": True})
            except Exception:
                pass

    data = buf.getvalue()
    if file_path:
        with open(file_path, "wb") as f:
            f.write(data)
    return data
