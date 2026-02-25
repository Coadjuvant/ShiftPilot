from __future__ import annotations

from collections import defaultdict
from datetime import date
from io import BytesIO
from typing import Dict, Iterable, List, Optional, Set

import pandas as pd

from .model import Assignment, ScheduleResult, StaffMember
from .engine import OPEN_LABEL

LEGACY_OPEN_LABEL = "OPEN"
UNFILLED_LABEL = "UNFILLED"


def _is_open_staff_id(staff_id: object) -> bool:
    if staff_id is None:
        return False
    text = str(staff_id).strip()
    if not text:
        return False
    return text.upper() in {OPEN_LABEL.upper(), LEGACY_OPEN_LABEL}


def _is_unfilled_staff_id(staff_id: object) -> bool:
    if staff_id is None:
        return True
    text = str(staff_id).strip()
    if not text:
        return True
    return text.upper() in {OPEN_LABEL.upper(), LEGACY_OPEN_LABEL}


def _shift_label(assignment: Assignment) -> str:
    slot = assignment.slot
    if slot.is_bleach:
        return "Bleach"
    duty = (slot.duty or "").lower()
    if duty == "open":
        return f"Open {slot.slot_index}" if slot.slot_index and slot.slot_index > 1 else "Open"
    if duty == "mid":
        return f"Mid {slot.slot_index}" if slot.slot_index and slot.slot_index > 1 else "Mid"
    if duty == "close":
        return f"Close {slot.slot_index}" if slot.slot_index and slot.slot_index > 1 else "Close"
    base = slot.duty.capitalize() if slot.duty else "Shift"
    if slot.slot_index and slot.slot_index > 1:
        return f"{base} {slot.slot_index}"
    return base


def _roster_rows(result: ScheduleResult, staff_lookup: Dict[str, StaffMember], allowed_roles: Set[str]):
    for assignment in result.assignments:
        slot = assignment.slot
        if allowed_roles and slot.role not in allowed_roles:
            continue
        normalized_staff_id = OPEN_LABEL if _is_open_staff_id(assignment.staff_id) else (assignment.staff_id or "")
        staff = staff_lookup.get(normalized_staff_id or "", None)
        yield {
            "Date": slot.date.strftime("%Y-%m-%d"),
            "Day": slot.day_name,
            "Role": slot.role,
            "Duty": ("bleach" if slot.is_bleach else slot.duty) or "",
            "Slot": slot.slot_index,
            "StaffID": normalized_staff_id or "",
            "StaffName": staff.name if staff else normalized_staff_id or "",
            "Notes": "; ".join(assignment.notes) if assignment.notes else "",
        }


def _coverage_rows(result: ScheduleResult):
    day_role_counts: Dict[tuple, int] = {}
    for assignment in result.assignments:
        slot = assignment.slot
        key = (slot.date.strftime("%Y-%m-%d"), slot.day_name, slot.role, slot.duty)
        filled = not _is_unfilled_staff_id(assignment.staff_id)
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
        if _is_unfilled_staff_id(assignment.staff_id):
            notes_by_date[date_str].add(f"Open slot: {slot.role} {_shift_label(assignment)}")
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
        if _is_unfilled_staff_id(assignment.staff_id):
            out[date_str].add(f"Open slot: {slot.role} {_shift_label(assignment)}")
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
        if _is_open_staff_id(assignment.staff_id):
            staff_id = OPEN_LABEL
        elif assignment.staff_id is None or not str(assignment.staff_id).strip():
            staff_id = ""
        else:
            staff_id = str(assignment.staff_id)
        text = _shift_label(assignment)
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
    if entries.get(""):
        row = {"Name": UNFILLED_LABEL, "Role": role}
        for dt, label in zip(dates, date_labels):
            cell = "\n".join(entries[""].get(dt, []))
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
        duty_label = _shift_label(assignment)
        col = f"{slot.role}-{duty_label}-{slot.slot_index}"
        cols.add(col)
        if _is_open_staff_id(assignment.staff_id):
            name = OPEN_LABEL
        elif assignment.staff_id is None or not str(assignment.staff_id).strip():
            name = UNFILLED_LABEL
        else:
            staff_id = str(assignment.staff_id)
            name = staff_lookup.get(
                staff_id,
                StaffMember(id=staff_id, name=staff_id, role=slot.role),
            ).name
        data[date_str][col] = name

    def _col_key(col: str):
        # col format: Role-Duty-idx
        try:
            role, duty, idx = col.split("-", 2)
            idx_val = float(idx)
        except ValueError:
            role, duty, idx_val = col, "", 0
        duty_l = duty.lower()
        if duty_l.startswith("open"):
            base = 1
        elif duty_l.startswith("mid"):
            base = 2
        elif duty_l.startswith("bleach"):
            base = 3.5
        elif duty_l.startswith("close"):
            base = 4
        else:
            base = 5
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


def _per_staff_long(
    assignments: List[Assignment],
    staff_lookup: Dict[str, StaffMember],
) -> pd.DataFrame:
    rows: List[Dict[str, object]] = []
    for assignment in assignments:
        slot = assignment.slot
        if _is_open_staff_id(assignment.staff_id):
            staff_id = OPEN_LABEL
            staff_name = OPEN_LABEL
            role_label = "FLOAT"
        elif assignment.staff_id is None or not str(assignment.staff_id).strip():
            staff_id = UNFILLED_LABEL
            staff_name = UNFILLED_LABEL
            role_label = "UNFILLED"
        else:
            staff_id = str(assignment.staff_id)
            member = staff_lookup.get(staff_id)
            staff_name = member.name if member and member.name else staff_id
            role_label = member.role if member and member.role else slot.role

        rows.append(
            {
                "StaffName": staff_name,
                "StaffID": staff_id,
                "StaffRole": role_label,
                "Date": slot.date.strftime("%Y-%m-%d"),
                "Day": slot.day_name,
                "Shift": _shift_label(assignment),
                "Role": slot.role,
                "Duty": ("bleach" if slot.is_bleach else slot.duty) or "",
                "Slot": slot.slot_index,
                "Notes": "; ".join(assignment.notes) if assignment.notes else "",
            }
        )

    if not rows:
        return pd.DataFrame(
            columns=[
                "StaffName",
                "StaffID",
                "StaffRole",
                "Date",
                "Day",
                "Shift",
                "Role",
                "Duty",
                "Slot",
                "Notes",
            ]
        )

    out = pd.DataFrame(rows)
    out.sort_values(["StaffName", "Date", "Slot", "Role"], inplace=True)
    return out


def _per_staff_wide(
    assignments: List[Assignment],
    staff_lookup: Dict[str, StaffMember],
    *,
    allowed_roles: Set[str],
) -> pd.DataFrame:
    if not assignments:
        return pd.DataFrame()

    all_dates = sorted({assignment.slot.date for assignment in assignments})
    day_by_date = {
        dt: next((a.slot.day_name for a in assignments if a.slot.date == dt), dt.strftime("%a"))
        for dt in all_dates
    }
    date_cols = {dt: f"{dt.strftime('%Y-%m-%d')} ({day_by_date[dt]})" for dt in all_dates}

    cells: Dict[str, Dict[date, List[str]]] = defaultdict(lambda: defaultdict(list))
    row_meta: Dict[str, Dict[str, str]] = {}

    def ensure_row(row_id: str, name: str, role: str) -> None:
        row_meta[row_id] = {
            "StaffName": name,
            "StaffID": row_id,
            "StaffRole": role,
        }

    # Include configured staff for exported roles so blank rows (days off) are still visible.
    configured_staff = sorted(
        [s for s in staff_lookup.values() if s.role in allowed_roles],
        key=lambda s: ((s.name or s.id).lower(), s.id),
    )
    for member in configured_staff:
        ensure_row(member.id, member.name or member.id, member.role or "")

    for assignment in assignments:
        slot = assignment.slot
        if _is_open_staff_id(assignment.staff_id):
            row_id = OPEN_LABEL
            ensure_row(row_id, OPEN_LABEL, "FLOAT")
        elif assignment.staff_id is None or not str(assignment.staff_id).strip():
            row_id = UNFILLED_LABEL
            ensure_row(row_id, UNFILLED_LABEL, "UNFILLED")
        else:
            row_id = str(assignment.staff_id)
            member = staff_lookup.get(row_id)
            ensure_row(row_id, member.name if member and member.name else row_id, member.role if member and member.role else slot.role)

        cells[row_id][slot.date].append(_shift_label(assignment))

    def _row_sort_key(item: tuple[str, Dict[str, str]]) -> tuple[int, str]:
        row_id, meta = item
        if row_id == OPEN_LABEL:
            return (1, meta["StaffName"].lower())
        if row_id == UNFILLED_LABEL:
            return (2, meta["StaffName"].lower())
        return (0, meta["StaffName"].lower())

    rows: List[Dict[str, str]] = []
    for row_id, meta in sorted(row_meta.items(), key=_row_sort_key):
        row: Dict[str, str] = {
            "StaffName": meta["StaffName"],
            "StaffID": meta["StaffID"],
            "StaffRole": meta["StaffRole"],
        }
        for dt in all_dates:
            row[date_cols[dt]] = "\n".join(cells.get(row_id, {}).get(dt, []))
        rows.append(row)

    return pd.DataFrame(rows)


def _cell_width(value: object) -> int:
    if value is None:
        return 0
    text = str(value)
    if not text:
        return 0
    lines = text.replace("\t", "    ").splitlines() or [text]
    return max(len(line) for line in lines)


def _autofit_dataframe_sheet(
    writer: pd.ExcelWriter,
    sheet_name: str,
    df: pd.DataFrame,
    *,
    min_width: int = 8,
    max_width: int = 60,
) -> None:
    sheet = writer.sheets.get(sheet_name)
    if sheet is None or df is None:
        return
    for col_idx, col_name in enumerate(df.columns):
        header_w = _cell_width(col_name)
        data_w = 0
        if not df.empty:
            data_w = max((_cell_width(v) for v in df[col_name].tolist()), default=0)
        width = max(header_w, data_w) + 2
        width = max(min_width, min(max_width, width))
        sheet.set_column(col_idx, col_idx, width)


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
    allowed_roles = ({r for r in export_roles} if export_roles else {"RN", "Tech", "Admin"})
    # filter assignments by allowed roles
    filtered_assignments = [a for a in result.assignments if a.slot.role in allowed_roles]
    # recompute stats for filtered roles (filled slots only)
    filtered_stats: Dict[str, int] = defaultdict(int)
    for a in filtered_assignments:
        if not _is_unfilled_staff_id(a.staff_id):
            filtered_stats[str(a.staff_id)] += 1

    class _FilteredResult:
        def __init__(self, assignments, stats):
            self.assignments = assignments
            self.stats = stats

    filtered_result = _FilteredResult(filtered_assignments, filtered_stats)

    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="xlsxwriter") as writer:
        all_dates = sorted({assignment.slot.date for assignment in filtered_assignments})

        # Roster Matrix first
        roster_matrix = _roster_matrix(
            filtered_assignments,
            staff,
            _notes_map(filtered_result),
            _pto_notes_map(pto_entries, staff),
        )
        if not roster_matrix.empty:
            roster_matrix.to_excel(writer, sheet_name="Roster Matrix", index=False)
            _autofit_dataframe_sheet(writer, "Roster Matrix", roster_matrix)

        roster_df = pd.DataFrame(list(_roster_rows(filtered_result, staff, allowed_roles)))
        if not roster_df.empty:
            roster_df.sort_values(["Date", "Role", "Duty", "Slot"], inplace=True)
        roster_df.to_excel(writer, sheet_name="Roster", index=False)
        _autofit_dataframe_sheet(writer, "Roster", roster_df)

        per_staff_long_df = _per_staff_long(filtered_assignments, staff)
        per_staff_long_df.to_excel(writer, sheet_name="Per Staff Long", index=False)
        _autofit_dataframe_sheet(writer, "Per Staff Long", per_staff_long_df)

        per_staff_wide_df = _per_staff_wide(filtered_assignments, staff, allowed_roles=allowed_roles)
        per_staff_wide_df.to_excel(writer, sheet_name="Per Staff Wide", index=False)
        _autofit_dataframe_sheet(writer, "Per Staff Wide", per_staff_wide_df)

        coverage_df = pd.DataFrame(list(_coverage_rows(filtered_result)))
        coverage_df.to_excel(writer, sheet_name="Coverage", index=False)
        _autofit_dataframe_sheet(writer, "Coverage", coverage_df)

        summary_df = pd.DataFrame(list(_summary_rows(filtered_result, staff)))
        summary_df.to_excel(writer, sheet_name="Summary", index=False)
        _autofit_dataframe_sheet(writer, "Summary", summary_df)

        note_df = pd.DataFrame(_note_rows(filtered_result, staff))
        if not note_df.empty:
            note_df.to_excel(writer, sheet_name="Notes", index=False)
            _autofit_dataframe_sheet(writer, "Notes", note_df)

        role_tables = []
        for role_name, label in [("RN", "RN"), ("Tech", "Tech"), ("Admin", "Admin")]:
            if role_name not in allowed_roles:
                continue
            table = _role_matrix(result.assignments, staff, role=role_name, dates=all_dates)
            if not table.empty:
                role_tables.append((label, table))
                sheet_name = f"{label} Schedule"
                table.to_excel(writer, sheet_name=sheet_name, index=False)
                _autofit_dataframe_sheet(writer, sheet_name, table)

        if role_tables:
            matrix_sheet = writer.book.add_worksheet("Matrix")
            writer.sheets["Matrix"] = matrix_sheet
            current_row = 0
            matrix_col_widths: Dict[int, int] = defaultdict(int)
            for label, table in role_tables:
                title = f"{label} Schedule"
                matrix_sheet.write(current_row, 0, title)
                matrix_col_widths[0] = max(matrix_col_widths[0], _cell_width(title) + 2)
                table.to_excel(
                    writer,
                    sheet_name="Matrix",
                    startrow=current_row + 1,
                    startcol=0,
                    index=False,
                )
                for col_idx, col_name in enumerate(table.columns):
                    header_w = _cell_width(col_name)
                    data_w = 0
                    if not table.empty:
                        data_w = max((_cell_width(v) for v in table[col_name].tolist()), default=0)
                    matrix_col_widths[col_idx] = max(matrix_col_widths[col_idx], header_w, data_w)
                current_row += len(table.index) + 3
            for col_idx, raw_width in matrix_col_widths.items():
                width = max(8, min(60, raw_width + 2))
                matrix_sheet.set_column(col_idx, col_idx, width)

        info_df = pd.DataFrame(
            [
                {"Metric": "Bleach Cursor", "Value": result.bleach_cursor},
                {"Metric": "Total Penalty", "Value": result.total_penalty},
                {"Metric": "Seed", "Value": result.seed if result.seed is not None else ""},
            ]
        )
        info_df.to_excel(writer, sheet_name="Meta", index=False)
        _autofit_dataframe_sheet(writer, "Meta", info_df)

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
