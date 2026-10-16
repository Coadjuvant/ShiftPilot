from __future__ import annotations

from datetime import date

from backend.scheduler.engine import OPEN_LABEL, generate_schedule
from backend.scheduler.tournament import run_tournament
from backend.scheduler.model import (
    ConstraintToggles,
    DailyRequirement,
    DAYS,
    PTOEntry,
    ScheduleConfig,
    StaffMember,
    StaffPreferences,
)


def _reqs(**overrides: int) -> list[DailyRequirement]:
    rows: list[DailyRequirement] = []
    for day in DAYS:
        rows.append(
            DailyRequirement(
                day_name=day,
                patient_count=overrides.get("patient_count", 0),
                tech_openers=overrides.get("tech_openers", 0),
                tech_mids=overrides.get("tech_mids", 0),
                tech_closers=overrides.get("tech_closers", 0),
                rn_count=overrides.get("rn_count", 0),
                admin_count=overrides.get("admin_count", 0),
            )
        )
    return rows


def _cfg(**kwargs) -> ScheduleConfig:
    return ScheduleConfig(
        clinic_name="Test Clinic",
        timezone="America/Chicago",
        start_date=date(2026, 5, 18),
        weeks=1,
        bleach_day="Thu",
        bleach_rotation=kwargs.pop("bleach_rotation", []),
        bleach_cursor=kwargs.pop("bleach_cursor", 0),
        patients_per_tech=kwargs.pop("patients_per_tech", 4),
        patients_per_rn=kwargs.pop("patients_per_rn", 12),
        techs_per_rn=kwargs.pop("techs_per_rn", 4),
        toggles=kwargs.pop("toggles", ConstraintToggles()),
        **kwargs,
    )


def _tech(
    staff_id: str,
    *,
    can_open: bool = True,
    can_close: bool = True,
    can_bleach: bool = False,
    availability: dict[str, bool] | None = None,
) -> StaffMember:
    return StaffMember(
        id=staff_id,
        name=staff_id.title(),
        role="Tech",
        can_open=can_open,
        can_close=can_close,
        can_bleach=can_bleach,
        availability=availability or {day: True for day in DAYS},
        preferences=StaffPreferences(),
    )


def test_patient_ratio_adds_mid_slots() -> None:
    staff = [_tech(f"tech{i}") for i in range(1, 5)]
    result = generate_schedule(
        staff,
        _reqs(patient_count=5, tech_openers=1),
        _cfg(patients_per_tech=2, patients_per_rn=0, techs_per_rn=0),
        rng_seed=1,
        scheduled_roles=["Tech"],
        score_roles=["Tech"],
    )

    monday_tech = [a for a in result.assignments if a.slot.day_name == "Mon" and a.slot.role == "Tech"]
    assert [a.slot.duty for a in monday_tech].count("open") == 1
    assert [a.slot.duty for a in monday_tech].count("mid") == 2


def test_pto_blocks_assignment_and_uses_float() -> None:
    staff = [_tech("ava")]
    result = generate_schedule(
        staff,
        _reqs(tech_openers=1),
        _cfg(),
        pto_entries=[PTOEntry(staff_id="ava", date=date(2026, 5, 18))],
        rng_seed=1,
        scheduled_roles=["Tech"],
        score_roles=["Tech"],
    )

    monday_open = next(a for a in result.assignments if a.slot.day_name == "Mon")
    assert monday_open.staff_id == OPEN_LABEL
    assert "Needs coverage" in monday_open.notes


def test_bleach_rotation_advances_after_assignment() -> None:
    staff = [
        _tech("ben", can_bleach=True),
        _tech("cory", can_bleach=True),
    ]
    result = generate_schedule(
        staff,
        _reqs(tech_closers=1),
        _cfg(bleach_rotation=["ben", "cory"], bleach_cursor=0),
        rng_seed=1,
        scheduled_roles=["Tech"],
        score_roles=["Tech"],
    )

    bleach = next(a for a in result.assignments if a.slot.is_bleach)
    assert bleach.staff_id == "ben"
    assert result.bleach_cursor == 1


def test_weekly_balance_does_not_hide_uneven_weeks_in_six_week_totals() -> None:
    staff = [_tech(f"tech-{i}", can_bleach=True) for i in range(1, 7)]
    cfg = ScheduleConfig(
        clinic_name="Weekly balance regression", timezone="America/Chicago",
        start_date=date(2026, 10, 19), weeks=6, bleach_day="Tue",
        bleach_rotation=[f"tech-{i}" for i in range(1, 5)],
        patients_per_tech=4, patients_per_rn=12, techs_per_rn=4,
        toggles=ConstraintToggles(enforce_three_day_cap=10, enforce_post_bleach_rest=10,
                                  enforce_alt_saturdays=5, limit_tech_four_days=10, limit_rn_four_days=0),
    )
    result, _ = run_tournament(staff, _reqs(tech_openers=1, tech_mids=1, tech_closers=1),
                               cfg, trials=10, base_seed=132796955, scheduled_roles=["Tech"])
    assert len(result.assignments) == 108
    assert all(a.staff_id != OPEN_LABEL for a in result.assignments)
    for member in staff:
        worked = [a.slot.day_index for a in result.assignments if a.staff_id == member.id]
        assert [sum(day // 6 == week for day in worked) for week in range(6)] == [3] * 6
        assert not any(day + 1 in worked and day + 2 in worked for day in worked)
        for assignment in result.assignments:
            if assignment.staff_id == member.id and assignment.slot.is_bleach:
                assert assignment.slot.day_index + 1 not in worked


def test_weekly_balance_respects_limited_availability_and_pto() -> None:
    staff = [_tech("limited", availability={day: day == "Mon" for day in DAYS}), _tech("available")]
    cfg = _cfg(toggles=ConstraintToggles(0, 0, 0, 0, 0))
    result = generate_schedule(staff, _reqs(tech_openers=1), cfg,
                               pto_entries=[PTOEntry("limited", cfg.start_date)],
                               rng_seed=42, scheduled_roles=["Tech"])
    assert all(a.staff_id == "available" for a in result.assignments)


def test_tournament_prioritizes_coverage_over_balance_score(monkeypatch) -> None:
    import copy
    import backend.scheduler.tournament as tournament
    covered = generate_schedule([_tech("available")], _reqs(tech_openers=1),
                                _cfg(toggles=ConstraintToggles(0, 0, 0, 0, 0)),
                                scheduled_roles=["Tech"], rng_seed=1)
    uncovered = copy.deepcopy(covered)
    uncovered.assignments[-1].staff_id = OPEN_LABEL
    uncovered.total_penalty = 0
    covered.total_penalty = 1000
    results = iter([uncovered, covered])
    monkeypatch.setattr(tournament, "generate_schedule", lambda *a, **kw: next(results))
    selected, _ = tournament.run_tournament([], [], _cfg(), trials=2, base_seed=1)
    assert selected is covered


def test_hard_four_day_cap_prevents_fifth_day() -> None:
    staff = [_tech("ava")]
    result = generate_schedule(
        staff,
        _reqs(tech_mids=1),
        _cfg(toggles=ConstraintToggles(limit_tech_four_days=10)),
        rng_seed=1,
        scheduled_roles=["Tech"],
        score_roles=["Tech"],
    )

    filled = [a for a in result.assignments if a.staff_id == "ava"]
    floats = [a for a in result.assignments if a.staff_id == OPEN_LABEL]
    assert len(filled) == 4
    assert len(floats) == 2
