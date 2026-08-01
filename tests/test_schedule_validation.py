from __future__ import annotations

from datetime import date, timedelta

from src.models import (
    DayOffRequest,
    Employee,
    ScheduleAssignment,
    StaffingRequirement,
)
from src.validation import (
    build_employee_schedule_summaries,
    calculate_max_consecutive_days,
    has_errors,
    validate_assigned_employees_active,
    validate_consecutive_work_limit,
    validate_day_off_assignments,
    validate_one_shift_per_day,
    validate_required_manager_counts,
    validate_required_staff_counts,
    validate_schedule,
    validate_shift_eligibility,
    validate_weekly_work_limit,
)


def make_employee(
    employee_id: str,
    *,
    is_manager: bool = False,
    contract_days: int = 20,
    can_work_early: bool = True,
    can_work_late: bool = True,
    is_active: bool = True,
) -> Employee:
    return Employee(
        employee_id=employee_id,
        name=employee_id,
        is_manager=is_manager,
        contract_days=contract_days,
        can_work_early=can_work_early,
        can_work_late=can_work_late,
        is_active=is_active,
    )


def make_assignment(
    target_date: date,
    employee_id: str,
    *,
    shift_type: str = "early",
) -> ScheduleAssignment:
    return ScheduleAssignment(
        target_date=target_date,
        shift_type=shift_type,
        employee_id=employee_id,
    )


def make_requirement(
    target_date: date,
    *,
    shift_type: str = "early",
    required_count: int = 2,
    required_manager_count: int = 1,
) -> StaffingRequirement:
    return StaffingRequirement(
        target_date=target_date,
        shift_type=shift_type,
        required_count=required_count,
        required_manager_count=required_manager_count,
    )


def test_two_shifts_same_day_is_error() -> None:
    assignments = [
        make_assignment(
            date(2026, 8, 1),
            "E001",
            shift_type="early",
        ),
        make_assignment(
            date(2026, 8, 1),
            "E001",
            shift_type="late",
        ),
    ]

    issues = validate_one_shift_per_day(
        assignments
    )

    assert len(issues) == 1
    assert issues[0].rule_id == "HC-01"


def test_day_off_assignment_is_error() -> None:
    assignments = [
        make_assignment(
            date(2026, 8, 1),
            "E001",
        )
    ]

    requests = [
        DayOffRequest(
            employee_id="E001",
            target_date=date(2026, 8, 1),
        )
    ]

    issues = validate_day_off_assignments(
        assignments,
        requests,
    )

    assert len(issues) == 1
    assert issues[0].rule_id == "HC-02"


def test_ineligible_shift_is_error() -> None:
    employees = [
        make_employee(
            "E001",
            can_work_early=False,
            can_work_late=True,
        )
    ]

    assignments = [
        make_assignment(
            date(2026, 8, 1),
            "E001",
            shift_type="early",
        )
    ]

    issues = validate_shift_eligibility(
        assignments,
        employees,
    )

    assert len(issues) == 1
    assert issues[0].rule_id == "HC-03"


def test_staff_shortage_is_error() -> None:
    assignments = [
        make_assignment(
            date(2026, 8, 1),
            "E001",
        )
    ]

    requirements = [
        make_requirement(
            date(2026, 8, 1),
            required_count=2,
            required_manager_count=0,
        )
    ]

    issues = validate_required_staff_counts(
        assignments,
        requirements,
    )

    assert len(issues) == 1
    assert issues[0].rule_id == "HC-04"


def test_staff_excess_is_error() -> None:
    assignments = [
        make_assignment(
            date(2026, 8, 1),
            "E001",
        ),
        make_assignment(
            date(2026, 8, 1),
            "E002",
        ),
        make_assignment(
            date(2026, 8, 1),
            "E003",
        ),
    ]

    requirements = [
        make_requirement(
            date(2026, 8, 1),
            required_count=2,
            required_manager_count=0,
        )
    ]

    issues = validate_required_staff_counts(
        assignments,
        requirements,
    )

    assert len(issues) == 1
    assert issues[0].rule_id == "HC-04"


def test_manager_shortage_is_error() -> None:
    employees = [
        make_employee("E001"),
        make_employee("E002"),
    ]

    assignments = [
        make_assignment(
            date(2026, 8, 1),
            "E001",
        ),
        make_assignment(
            date(2026, 8, 1),
            "E002",
        ),
    ]

    requirements = [
        make_requirement(
            date(2026, 8, 1),
            required_count=2,
            required_manager_count=1,
        )
    ]

    issues = validate_required_manager_counts(
        assignments,
        employees,
        requirements,
    )

    assert len(issues) == 1
    assert issues[0].rule_id == "HC-05"


def test_six_days_in_week_is_error() -> None:
    start_date = date(2026, 8, 3)

    assignments = [
        make_assignment(
            start_date + timedelta(days=offset),
            "E001",
        )
        for offset in range(6)
    ]

    issues = validate_weekly_work_limit(
        assignments
    )

    assert len(issues) == 1
    assert issues[0].rule_id == "HC-06"


def test_six_consecutive_days_is_error() -> None:
    start_date = date(2026, 8, 1)

    assignments = [
        make_assignment(
            start_date + timedelta(days=offset),
            "E001",
        )
        for offset in range(6)
    ]

    issues = validate_consecutive_work_limit(
        assignments
    )

    assert len(issues) == 1
    assert issues[0].rule_id == "HC-07"


def test_inactive_employee_is_error() -> None:
    employees = [
        make_employee(
            "E001",
            is_active=False,
        )
    ]
    assignments = [
        make_assignment(
            date(2026, 8, 1),
            "E001",
        )
    ]

    issues = validate_assigned_employees_active(
        assignments,
        employees,
    )

    assert len(issues) == 1
    assert issues[0].rule_id == "HC-08"


def test_inactive_manager_does_not_satisfy_requirement() -> None:
    employees = [
        make_employee(
            "E001",
            is_manager=True,
            is_active=False,
        ),
        make_employee("E002"),
    ]

    assignments = [
        make_assignment(
            date(2026, 8, 1),
            "E001",
        ),
        make_assignment(
            date(2026, 8, 1),
            "E002",
        ),
    ]

    requirements = [
        make_requirement(
            date(2026, 8, 1),
            required_count=2,
            required_manager_count=1,
        )
    ]

    issues = validate_required_manager_counts(
        assignments,
        employees,
        requirements,
    )

    assert len(issues) == 1
    assert issues[0].rule_id == "HC-05"


def test_employee_schedule_summary() -> None:
    employees = [
        make_employee(
            "E001",
            is_manager=True,
            contract_days=4,
        )
    ]

    assignments = [
        make_assignment(
            date(2026, 8, 1),
            "E001",
            shift_type="early",
        ),
        make_assignment(
            date(2026, 8, 2),
            "E001",
            shift_type="early",
        ),
        make_assignment(
            date(2026, 8, 4),
            "E001",
            shift_type="late",
        ),
    ]

    summaries = build_employee_schedule_summaries(
        assignments,
        employees,
    )

    summary = summaries[0]

    assert summary.assigned_days == 3
    assert summary.difference == -1
    assert summary.early_count == 2
    assert summary.late_count == 1
    assert summary.max_consecutive_days == 2
    assert summary.manager_assignment_count == 3


def test_valid_schedule_has_no_errors() -> None:
    employees = [
        make_employee(
            "E001",
            is_manager=True,
            contract_days=1,
        ),
        make_employee(
            "E002",
            contract_days=1,
        ),
        make_employee(
            "E003",
            is_manager=True,
            contract_days=1,
        ),
        make_employee(
            "E004",
            contract_days=1,
        ),
    ]

    assignments = [
        make_assignment(
            date(2026, 8, 1),
            "E001",
            shift_type="early",
        ),
        make_assignment(
            date(2026, 8, 1),
            "E002",
            shift_type="early",
        ),
        make_assignment(
            date(2026, 8, 1),
            "E003",
            shift_type="late",
        ),
        make_assignment(
            date(2026, 8, 1),
            "E004",
            shift_type="late",
        ),
    ]

    requirements = [
        make_requirement(
            date(2026, 8, 1),
            shift_type="early",
            required_count=2,
            required_manager_count=1,
        ),
        make_requirement(
            date(2026, 8, 1),
            shift_type="late",
            required_count=2,
            required_manager_count=1,
        ),
    ]

    issues = validate_schedule(
        assignments,
        employees,
        [],
        requirements,
    )

    assert has_errors(issues) is False