from __future__ import annotations

from collections import defaultdict
from datetime import date
from io import BytesIO
from typing import Dict, List, Optional

import pandas as pd

from .model import Assignment, ScheduleResult, StaffMember
from .engine import OPEN_LABEL


def _roster_rows(result: ScheduleResult, staff_lookup: Dict[str, StaffMember]):
    for assignment in result.assignments:
        slot = assignment.slot
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


def export_schedule_to_excel(
    result: ScheduleResult,
    staff: Dict[str, StaffMember],
    *,
    file_path: Optional[str] = None,
) -> bytes:
    """
    Write the schedule to an Excel workbook.
    Returns the bytes buffer; optionally writes to `file_path`.
    """
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="xlsxwriter") as writer:
        all_dates = sorted({assignment.slot.date for assignment in result.assignments})

        roster_df = pd.DataFrame(list(_roster_rows(result, staff)))
        if not roster_df.empty:
            roster_df.sort_values(["Date", "Role", "Duty", "Slot"], inplace=True)
        roster_df.to_excel(writer, sheet_name="Roster", index=False)

        coverage_df = pd.DataFrame(list(_coverage_rows(result)))
        coverage_df.to_excel(writer, sheet_name="Coverage", index=False)

        summary_df = pd.DataFrame(list(_summary_rows(result, staff)))
        summary_df.to_excel(writer, sheet_name="Summary", index=False)

        role_tables = []
        for role_name, label in [("RN", "RN"), ("Tech", "Tech"), ("Admin", "Admin")]:
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

    data = buf.getvalue()
    if file_path:
        with open(file_path, "wb") as f:
            f.write(data)
    return data
