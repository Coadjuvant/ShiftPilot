from datetime import date
from io import BytesIO
import xml.etree.ElementTree as ET
from zipfile import ZipFile

import pytest

from backend.scheduler.export import export_schedule_to_excel
from backend.scheduler.model import Assignment, ScheduleResult, ScheduleSlot, StaffMember


@pytest.mark.parametrize("text", ["=1+1", "+1+1", "-1+1", "@SUM(1,1)", "https://example.invalid/staff"])
def test_export_preserves_untrusted_text_without_formulas_or_links(text):
    staff = StaffMember(id="tech", name=text, role="Tech")
    slot = ScheduleSlot(0, date(2026, 10, 26), "Mon", "Tech", "mid", 1)
    result = ScheduleResult([Assignment(slot, staff.id, notes=[text])], 0, 0.0, {staff.id: 1})
    data = export_schedule_to_excel(result, {staff.id: staff})
    ns = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    with ZipFile(BytesIO(data)) as archive:
        strings = ET.fromstring(archive.read("xl/sharedStrings.xml"))
        assert text in ["".join(item.itertext()) for item in strings.findall("s:si", ns)]
        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        sheets = {item.attrib["name"] for item in workbook.findall("s:sheets/s:sheet", ns)}
        assert {"Roster Matrix", "Roster", "Summary", "Tech Schedule", "Matrix", "Notes"} <= sheets
        for name in archive.namelist():
            if name.startswith("xl/worksheets/") and name.endswith(".xml"):
                sheet = ET.fromstring(archive.read(name))
                assert not sheet.findall(".//s:f", ns), name
                assert not sheet.findall(".//s:hyperlink", ns), name

