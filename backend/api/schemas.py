from __future__ import annotations

from datetime import date
from typing import Dict, List, Optional, Literal

try:
    from pydantic import BaseModel, Field, conint, constr  # type: ignore
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
    def conint(*, **kwargs):  # type: ignore
        return int
    def constr(*, **kwargs):  # type: ignore
        return str

from backend.scheduler.model import DAYS

DayName = Literal["Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
RoleName = Literal["Tech", "RN", "Admin"]
BleachFrequency = Literal["weekly", "quarterly", "custom"]
UserRole = Literal["user", "admin"]


class BaseSchema(BaseModel):
    class Config:
        extra = "forbid"
        anystr_strip_whitespace = True


class StaffPreferencesIn(BaseSchema):
    open_mwf: float = 1.0
    open_tts: float = 1.0
    mid_mwf: float = 1.0
    mid_tts: float = 1.0
    close_mwf: float = 1.0
    close_tts: float = 1.0


class StaffMemberIn(BaseSchema):
    id: constr(min_length=1, max_length=64)
    name: constr(min_length=1, max_length=80)
    role: RoleName = "Tech"
    can_open: bool = False
    can_close: bool = False
    can_bleach: bool = False
    availability: Dict[DayName, bool] = Field(
        default_factory=lambda: {day: True for day in DAYS}
    )
    preferences: StaffPreferencesIn = Field(default_factory=StaffPreferencesIn)


class RequirementIn(BaseSchema):
    day_name: DayName
    patient_count: conint(ge=0) = 0
    tech_openers: conint(ge=0) = 0
    tech_mids: conint(ge=0) = 0
    tech_closers: conint(ge=0) = 0
    rn_count: conint(ge=0) = 0
    admin_count: conint(ge=0) = 0


class ConstraintTogglesIn(BaseSchema):
    enforce_three_day_cap: bool = True
    enforce_post_bleach_rest: bool = True
    enforce_alt_saturdays: bool = True
    limit_tech_four_days: bool = True
    limit_rn_four_days: bool = True


class ScheduleConfigIn(BaseSchema):
    clinic_name: constr(min_length=1, max_length=80)
    timezone: constr(min_length=1, max_length=48)
    start_date: date
    weeks: conint(ge=1) = 1
    bleach_day: DayName = "Thu"
    bleach_rotation: List[constr(min_length=1, max_length=64)] = Field(default_factory=list)
    bleach_cursor: conint(ge=0) = 0
    bleach_frequency: BleachFrequency = "weekly"
    patients_per_tech: conint(ge=0) = 4
    patients_per_rn: conint(ge=0) = 12
    techs_per_rn: conint(ge=0) = 4
    toggles: ConstraintTogglesIn = Field(default_factory=ConstraintTogglesIn)


class PTOEntryIn(BaseSchema):
    staff_id: constr(min_length=1, max_length=64)
    date: date


class ScheduleRequest(BaseSchema):
    staff: List[StaffMemberIn]
    requirements: List[RequirementIn]
    config: ScheduleConfigIn
    pto: List[PTOEntryIn] = Field(default_factory=list)
    tournament_trials: conint(ge=1) = 20
    base_seed: Optional[conint(ge=0)] = None
    export_roles: List[RoleName] = Field(default_factory=list)


class AssignmentOut(BaseSchema):
    date: date
    day_name: DayName
    role: RoleName
    duty: str
    staff_id: Optional[str]
    notes: List[str] = Field(default_factory=list)
    slot_index: conint(ge=0)
    is_bleach: bool


class ScheduleResponse(BaseSchema):
    bleach_cursor: conint(ge=0)
    winning_seed: Optional[int]
    assignments: List[AssignmentOut]
    total_penalty: float
    stats: Dict[str, float]
    excel: Optional[str]


class ConfigClinic(BaseSchema):
    name: constr(min_length=1, max_length=80)
    timezone: constr(min_length=1, max_length=48)


class ConfigSchedule(BaseSchema):
    start: date
    weeks: conint(ge=1)
    bleach_frequency: BleachFrequency = "weekly"


class ConfigRatios(BaseSchema):
    patients_per_tech: conint(ge=0)
    patients_per_rn: conint(ge=0)
    techs_per_rn: conint(ge=0)


class ConfigConstraints(BaseSchema):
    enforce_three_day_cap: bool
    enforce_post_bleach_rest: bool
    enforce_alt_saturdays: bool
    limit_tech_four_days: bool
    limit_rn_four_days: bool


class ConfigBleach(BaseSchema):
    day: DayName
    rotation: List[constr(min_length=1, max_length=64)]
    cursor: conint(ge=0) = 0
    frequency: Optional[BleachFrequency] = None


class ConfigTournament(BaseSchema):
    trials: conint(ge=1) = 20
    last_seed: conint(ge=0) = 0


class ConfigPayload(BaseSchema):
    clinic: ConfigClinic
    schedule: ConfigSchedule
    ratios: ConfigRatios
    constraints: ConfigConstraints
    bleach: ConfigBleach
    tournament: ConfigTournament
    export_roles: List[RoleName] = Field(default_factory=list)
    staff: List[Dict[str, object]]
    demand: List[Dict[str, object]]
    pto: List[Dict[str, object]] = Field(default_factory=list)


class SaveConfigRequest(BaseSchema):
    payload: ConfigPayload
    filename: Optional[constr(min_length=1, max_length=128)] = None


class LoginRequest(BaseSchema):
    username: constr(min_length=3, max_length=64)
    password: constr(min_length=4, max_length=128)


class LoginResponse(BaseSchema):
    token: str


class InviteRequest(BaseSchema):
    username: constr(min_length=0, max_length=64) = ""  # optional; if blank, server will auto-generate
    license_key: constr(min_length=1, max_length=64)
    role: UserRole = "user"


class SetupRequest(BaseSchema):
    invite_token: constr(min_length=8, max_length=128)
    username: constr(min_length=3, max_length=64)
    password: constr(min_length=4, max_length=128)


class UserInfo(BaseSchema):
    sub: str
    username: str
    role: UserRole = "user"
