from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal


ShiftType = Literal["early", "late"]


@dataclass(frozen=True)
class Employee:
    employee_id: str
    name: str
    is_manager: bool
    contract_days: int
    can_work_early: bool
    can_work_late: bool
    is_active: bool


@dataclass(frozen=True)
class DayOffRequest:
    employee_id: str
    target_date: date


@dataclass(frozen=True)
class StaffingRequirement:
    target_date: date
    shift_type: ShiftType
    required_count: int
    required_manager_count: int


@dataclass(frozen=True)
class ScheduleAssignment:
    target_date: date
    shift_type: ShiftType
    employee_id: str
    is_manual: bool = False