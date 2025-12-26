"""
Data structures for the scheduler.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Dict, List, Optional

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
MWF = {"Mon", "Wed", "Fri"}
TTS = {"Tue", "Thu", "Sat"}


@dataclass
class StaffPreferences:
    """Role preference weights (lower is more preferred)."""

    open_mwf: float = 1.0
    open_tts: float = 1.0
    mid_mwf: float = 1.0
    mid_tts: float = 1.0
    close_mwf: float = 1.0
    close_tts: float = 1.0

    def weight_for(self, duty: str, day_name: str) -> float:
        duty = duty.lower()
        if day_name in MWF:
            if duty == "open":
                return self.open_mwf
            if duty == "mid":
                return self.mid_mwf
            if duty == "close":
                return self.close_mwf
        else:
            if duty == "open":
                return self.open_tts
            if duty == "mid":
                return self.mid_tts
            if duty == "close":
                return self.close_tts
        return 1.0


@dataclass
class StaffMember:
    id: str
    name: str
    role: str  # Tech | RN | Admin
    can_open: bool = False
    can_close: bool = False
    can_bleach: bool = False
    availability: Dict[str, bool] = field(default_factory=lambda: {d: True for d in DAYS})
    preferences: StaffPreferences = field(default_factory=StaffPreferences)


@dataclass
class DailyRequirement:
    day_name: str  # Mon..Sat
    patient_count: int
    tech_openers: int
    tech_mids: int
    tech_closers: int
    rn_count: int
    admin_count: int


@dataclass
class ConstraintToggles:
    enforce_three_day_cap: bool = True
    enforce_post_bleach_rest: bool = True
    enforce_alt_saturdays: bool = True
    limit_tech_four_days: bool = False
    limit_rn_four_days: bool = False


@dataclass
class ScheduleConfig:
    clinic_name: str
    timezone: str
    start_date: date
    weeks: int
    bleach_day: str  # Mon..Sat
    bleach_rotation: List[str]
    bleach_cursor: int = 0
    bleach_frequency: str = "weekly"
    patients_per_tech: int = 4
    patients_per_rn: int = 12
    techs_per_rn: int = 4
    toggles: ConstraintToggles = field(default_factory=ConstraintToggles)


@dataclass
class PTOEntry:
    staff_id: str
    date: date

    def as_dict(self) -> Dict[str, str]:
        d = self.date.isoformat() if isinstance(self.date, (date, datetime)) else self.date
        return {"staff_id": self.staff_id, "date": d}


@dataclass
class ScheduleSlot:
    day_index: int
    date: date
    day_name: str
    role: str
    duty: str  # open | mid | close | bleach
    slot_index: int
    is_bleach: bool = False


@dataclass
class Assignment:
    slot: ScheduleSlot
    staff_id: Optional[str]
    notes: List[str] = field(default_factory=list)


@dataclass
class ScheduleResult:
    assignments: List[Assignment]
    bleach_cursor: int
    total_penalty: float
    stats: Dict[str, float]
    seed: Optional[int] = None
