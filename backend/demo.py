from __future__ import annotations

from datetime import date

from scheduler import (
    run_tournament,
    export_schedule_to_excel,
)
from scheduler.model import (
    DailyRequirement,
    ScheduleConfig,
    StaffMember,
    StaffPreferences,
    ConstraintToggles,
    PTOEntry,
)


def build_sample_staff():
    prefs_open = StaffPreferences(open_mwf=0.5, open_tts=1.0, mid_mwf=1.0, mid_tts=1.0, close_mwf=1.5, close_tts=1.5)
    prefs_close = StaffPreferences(open_mwf=2.0, open_tts=2.0, mid_mwf=1.0, mid_tts=1.0, close_mwf=0.5, close_tts=0.5)
    staff = [
        StaffMember(id="ava", name="Ava", role="Tech", can_open=True, can_close=False, can_bleach=False, preferences=prefs_open),
        StaffMember(id="ben", name="Ben", role="Tech", can_open=False, can_close=True, can_bleach=True, preferences=prefs_close),
        StaffMember(id="cory", name="Cory", role="Tech", can_open=True, can_close=True, can_bleach=True),
        StaffMember(id="dana", name="Tech Dana", role="Tech", can_open=False, can_close=True, can_bleach=False),
        StaffMember(id="riley", name="Riley", role="RN"),
        StaffMember(id="sasha", name="Sasha", role="RN"),
        StaffMember(id="alex", name="Alex", role="Admin"),
    ]
    return staff


def build_requirements():
    base_patients = [18, 20, 22, 20, 24, 16]
    reqs = []
    for day_name, patients in zip(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat"], base_patients):
        reqs.append(
            DailyRequirement(
                day_name=day_name,
                patient_count=patients,
                tech_openers=2,
                tech_mids=4,
                tech_closers=2,
                rn_count=2,
                admin_count=1,
            )
        )
    return reqs


def main():
    staff = build_sample_staff()
    requirements = build_requirements()
    cfg = ScheduleConfig(
        clinic_name="Demo Clinic",
        timezone="America/Chicago",
        start_date=date(2025, 11, 3),
        weeks=1,
        bleach_day="Thu",
        bleach_rotation=["ben", "cory", "dana"],
        bleach_cursor=0,
        toggles=ConstraintToggles(
            enforce_three_day_cap=True,
            enforce_post_bleach_rest=True,
            enforce_alt_saturdays=True,
        ),
    )
    pto = [PTOEntry(staff_id="ava", date=date(2025, 11, 6))]
    result, winning_seed = run_tournament(staff, requirements, cfg, pto_entries=pto, trials=10)
    staff_lookup = {s.id: s for s in staff}
    data = export_schedule_to_excel(result, staff_lookup, file_path="schedule_demo.xlsx")
    print(
        f"Generated {len(result.assignments)} assignments, bytes={len(data)}, "
        f"next_bleach_cursor={result.bleach_cursor}, seed={winning_seed}"
    )


if __name__ == "__main__":
    main()
