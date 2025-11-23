from __future__ import annotations

from datetime import date
from typing import Dict, List, Optional

try:
    from pydantic import BaseModel, Field  # type: ignore
except Exception:
    # Minimal fallback when pydantic is not available (prevents editor/linter errors).
    # This does not replicate pydantic's validation; it's only to allow imports and defaults.
    from typing import Any, Callable, Optional

    class BaseModel:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)

    def Field(*, default: Any = None, default_factory: Optional[Callable[[], Any]] = None, **kwargs):
        # If a default_factory is provided, use it to produce a default value now.
        # This mirrors common usage in the file and prevents unresolved import errors.
        if default_factory is not None:
            return default_factory()
        return default

from backend.scheduler.model import DAYS


class StaffPreferencesIn(BaseModel):
    open_mwf: float = 1.0
    open_tts: float = 1.0
    mid_mwf: float = 1.0
    mid_tts: float = 1.0
    close_mwf: float = 1.0
    close_tts: float = 1.0


class StaffMemberIn(BaseModel):
    id: str
    name: str
    role: str = "Tech"
    can_open: bool = False
    can_close: bool = False
    can_bleach: bool = False
    availability: Dict[str, bool] = Field(
        default_factory=lambda: {day: True for day in DAYS}
    )
    preferences: StaffPreferencesIn = Field(default_factory=StaffPreferencesIn)


class RequirementIn(BaseModel):
    day_name: str
    patient_count: int = 0
    tech_openers: int = 0
    tech_mids: int = 0
    tech_closers: int = 0
    rn_count: int = 0
    admin_count: int = 0


class ConstraintTogglesIn(BaseModel):
    enforce_three_day_cap: bool = True
    enforce_post_bleach_rest: bool = True
    enforce_alt_saturdays: bool = True
    limit_tech_four_days: bool = True
    limit_rn_four_days: bool = True


class ScheduleConfigIn(BaseModel):
    clinic_name: str
    timezone: str
    start_date: date
    weeks: int = 1
    bleach_day: str = "Thu"
    bleach_rotation: List[str] = Field(default_factory=list)
    bleach_cursor: int = 0
    patients_per_tech: int = 4
    patients_per_rn: int = 12
    techs_per_rn: int = 4
    toggles: ConstraintTogglesIn = Field(default_factory=ConstraintTogglesIn)


class PTOEntryIn(BaseModel):
    staff_id: str
    date: date


class ScheduleRequest(BaseModel):
    staff: List[StaffMemberIn]
    requirements: List[RequirementIn]
    config: ScheduleConfigIn
    pto: List[PTOEntryIn] = Field(default_factory=list)
    tournament_trials: int = 20
    base_seed: Optional[int] = None
    export_roles: List[str] = Field(default_factory=list)


class AssignmentOut(BaseModel):
    date: date
    day_name: str
    role: str
    duty: str
    staff_id: Optional[str]
    notes: List[str] = Field(default_factory=list)
    slot_index: int
    is_bleach: bool


class ScheduleResponse(BaseModel):
    bleach_cursor: int
    winning_seed: Optional[int]
    assignments: List[AssignmentOut]
    total_penalty: float
    stats: Dict[str, float]
    excel: Optional[str]


class ConfigClinic(BaseModel):
    name: str
    timezone: str


class ConfigSchedule(BaseModel):
    start: date
    weeks: int


class ConfigRatios(BaseModel):
    patients_per_tech: int
    patients_per_rn: int
    techs_per_rn: int


class ConfigConstraints(BaseModel):
    enforce_three_day_cap: bool
    enforce_post_bleach_rest: bool
    enforce_alt_saturdays: bool
    limit_tech_four_days: bool
    limit_rn_four_days: bool


class ConfigBleach(BaseModel):
    day: str
    rotation: List[str]
    cursor: int = 0


class ConfigTournament(BaseModel):
    trials: int = 20
    last_seed: int = 0


class ConfigPayload(BaseModel):
    clinic: ConfigClinic
    schedule: ConfigSchedule
    ratios: ConfigRatios
    constraints: ConfigConstraints
    bleach: ConfigBleach
    tournament: ConfigTournament
    staff: List[Dict[str, object]]
    demand: List[Dict[str, object]]
    pto: List[Dict[str, object]] = Field(default_factory=list)


class SaveConfigRequest(BaseModel):
    payload: ConfigPayload
    filename: Optional[str] = None
