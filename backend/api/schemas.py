from __future__ import annotations

from datetime import date
from typing import Dict, List, Optional, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, conint, constr, field_validator, model_validator

from backend.scheduler.model import DAYS

DayName = Literal["Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
RoleName = Literal["Tech", "RN", "Admin"]
BleachFrequency = Literal["weekly", "quarterly", "custom"]
UserRole = Literal["user", "admin"]


class BaseSchema(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, allow_inf_nan=False)


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
    enforce_three_day_cap: conint(ge=0, le=10) = 10
    enforce_post_bleach_rest: conint(ge=0, le=10) = 10
    enforce_alt_saturdays: conint(ge=0, le=10) = 10
    limit_tech_four_days: conint(ge=0, le=10) = 10
    limit_rn_four_days: conint(ge=0, le=10) = 10

    @field_validator("*", mode="before")
    def _coerce_legacy_bools(cls, value):
        if isinstance(value, bool):
            return 10 if value else 0
        if value is None:
            return 0
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0


class ScheduleConfigIn(BaseSchema):
    clinic_name: constr(min_length=1, max_length=80)
    timezone: constr(min_length=1, max_length=48)
    start_date: date
    weeks: conint(ge=1, le=26) = 1
    bleach_day: DayName = "Thu"
    bleach_rotation: List[constr(min_length=1, max_length=64)] = Field(default_factory=list)
    bleach_cursor: conint(ge=0) = 0
    bleach_frequency: BleachFrequency = "weekly"
    patients_per_tech: conint(ge=0) = 4
    patients_per_rn: conint(ge=0) = 12
    techs_per_rn: conint(ge=0) = 4
    toggles: ConstraintTogglesIn = Field(default_factory=ConstraintTogglesIn)

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value):
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError("Choose a valid timezone, such as America/Chicago")
        return value


class PTOEntryIn(BaseSchema):
    staff_id: constr(min_length=1, max_length=64)
    date: date


class FixedAssignmentIn(BaseSchema):
    date: date
    role: RoleName
    duty: constr(min_length=1, max_length=32)
    slot_index: conint(ge=0)
    staff_id: Optional[str] = None
    is_locked: bool = False


class ScheduleAdjustment(BaseSchema):
    assignments: List[FixedAssignmentIn] = Field(min_length=1, max_length=10000)


class ScheduleRequest(BaseSchema):
    staff: List[StaffMemberIn] = Field(min_length=1, max_length=200)
    requirements: List[RequirementIn] = Field(min_length=6, max_length=6)
    config: ScheduleConfigIn
    pto: List[PTOEntryIn] = Field(default_factory=list, max_length=10000)
    tournament_trials: conint(ge=1, le=500) = 250
    base_seed: Optional[conint(ge=0)] = None
    export_roles: List[RoleName] = Field(default_factory=list)
    scheduled_roles: List[RoleName] = Field(default_factory=lambda: ["Tech", "RN", "Admin"], min_length=1, max_length=3)
    fixed_assignments: List[FixedAssignmentIn] = Field(default_factory=list, max_length=10000)

    @model_validator(mode="after")
    def consistent_inputs(self):
        ids = [person.id for person in self.staff]
        if len(ids) != len(set(ids)):
            raise ValueError("Staff IDs must be unique")
        keys = [(a.date, a.role, a.duty, a.slot_index) for a in self.fixed_assignments]
        if len(keys) != len(set(keys)):
            raise ValueError("A slot can only have one fixed assignment")
        if any(a.staff_id and a.staff_id not in ids and a.staff_id not in {"FLOAT", "OPEN"} for a in self.fixed_assignments):
            raise ValueError("Fixed assignments must reference existing staff members")
        if {row.day_name for row in self.requirements} != set(DAYS):
            raise ValueError("Coverage needs must include each day from Mon to Sat exactly once")
        if any(entry.staff_id not in ids for entry in self.pto):
            raise ValueError("Time off must reference an existing staff member")
        if any(staff_id not in ids for staff_id in self.config.bleach_rotation):
            raise ValueError("Bleach rotation must reference existing staff members")
        if len(self.config.bleach_rotation) != len(set(self.config.bleach_rotation)):
            raise ValueError("Bleach rotation must not contain duplicate staff members")
        # Include automatically expanded ratio demand in the compute budget.
        slots = 0
        for row in self.requirements:
            tech = max(row.tech_openers + row.tech_mids + row.tech_closers,
                       -(-row.patient_count // self.config.patients_per_tech) if self.config.patients_per_tech else 0)
            rn = max(row.rn_count,
                     -(-row.patient_count // self.config.patients_per_rn) if self.config.patients_per_rn else 0,
                     -(-tech // self.config.techs_per_rn) if self.config.techs_per_rn else 0)
            slots += tech + rn + row.admin_count
        if slots * self.config.weeks > 10000 or slots * self.config.weeks * self.tournament_trials * len(ids) > 10000000:
            raise ValueError("This run is too large. Reduce weeks, coverage needs, or trials")
        return self


class AssignmentOut(BaseSchema):
    is_locked: bool = False
    date: date
    day_name: DayName
    role: RoleName
    duty: str
    staff_id: Optional[str]
    notes: List[str] = Field(default_factory=list)
    slot_index: conint(ge=0)
    is_bleach: bool


class ScheduleResponse(BaseSchema):
    version_id: str
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
    weeks: conint(ge=1, le=26)
    bleach_frequency: BleachFrequency = "weekly"


class ConfigRatios(BaseSchema):
    patients_per_tech: conint(ge=0)
    patients_per_rn: conint(ge=0)
    techs_per_rn: conint(ge=0)


class ConfigConstraints(ConstraintTogglesIn):
    pass


class ConfigBleach(BaseSchema):
    day: DayName
    rotation: List[constr(min_length=1, max_length=64)]
    cursor: conint(ge=0) = 0
    frequency: Optional[BleachFrequency] = None


class ConfigTournament(BaseSchema):
    # Loading/saving an old setup performs no scheduling work. Preserve its
    # value; ScheduleRequest enforces the limit when generation is requested.
    trials: conint(ge=1) = 250
    last_seed: conint(ge=0) = 0


class ConfigPayload(BaseSchema):
    clinic: ConfigClinic
    schedule: ConfigSchedule
    ratios: ConfigRatios
    constraints: ConfigConstraints
    bleach: ConfigBleach
    tournament: ConfigTournament
    export_roles: List[RoleName] = Field(default_factory=list)
    scheduled_roles: List[RoleName] = Field(default_factory=lambda: ["Tech", "RN", "Admin"])
    staff: List[Dict[str, object]]
    demand: List[Dict[str, object]]
    pto: List[Dict[str, object]] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def migrate_role_scope(cls, value):
        if isinstance(value, dict) and "scheduled_roles" not in value:
            return {**value, "scheduled_roles": value.get("export_roles") or ["Tech", "RN", "Admin"]}
        return value


class SaveConfigRequest(BaseSchema):
    payload: ConfigPayload
    filename: Optional[constr(min_length=1, max_length=128)] = None


class LoginRequest(BaseSchema):
    username: constr(min_length=3, max_length=64)
    password: constr(min_length=4, max_length=128, strip_whitespace=False)


class LoginResponse(BaseSchema):
    token: str


class InviteRequest(BaseSchema):
    username: constr(min_length=0, max_length=64) = ""  # optional; if blank, server will auto-generate
    license_key: constr(min_length=1, max_length=64)
    role: UserRole = "user"


class SetupRequest(BaseSchema):
    invite_token: constr(min_length=8, max_length=128)
    username: constr(min_length=3, max_length=64)
    password: constr(min_length=12, max_length=128, strip_whitespace=False)


class InviteLookupResponse(BaseSchema):
    username: str
    type: Literal["invite", "reset"]


class UserInfo(BaseSchema):
    sub: str
    username: str
    role: UserRole = "user"
