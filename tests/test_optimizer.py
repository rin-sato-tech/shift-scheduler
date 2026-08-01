from __future__ import annotations

from datetime import date, timedelta

from src.models import (
    DayOffRequest,
    Employee,
    StaffingRequirement,
)
from src.optimizer import generate_schedule
from src.validation import (
    has_errors,
    validate_schedule,
)


def make_employee(
    employee_id: str,
    *,
    is_manager: bool = False,
    contract_days: int = 1,
    can_work_early: bool = True,
    can_work_late: bool = True,
) -> Employee:
    return Employee(
        employee_id=employee_id,
        name=employee_id,
        is_manager=is_manager,
        contract_days=contract_days,
        can_work_early=can_work_early,
        can_work_late=can_work_late,
        is_active=True,
    )


def make_requirement(
    target_date: date,
    shift_type: str,
    *,
    required_count: int = 1,
    required_manager_count: int = 0,
) -> StaffingRequirement:
    return StaffingRequirement(
        target_date=target_date,
        shift_type=shift_type,
        required_count=required_count,
        required_manager_count=required_manager_count,
    )


def test_generate_basic_schedule() -> None:
    employees = [
        make_employee(
            "E001",
            is_manager=True,
        ),
        make_employee("E002"),
    ]

    requirements = [
        make_requirement(
            date(2026, 8, 1),
            "early",
            required_count=1,
            required_manager_count=1,
        ),
        make_requirement(
            date(2026, 8, 1),
            "late",
            required_count=1,
            required_manager_count=0,
        ),
    ]

    result = generate_schedule(
        "2026-08",
        employees,
        [],
        requirements,
        max_time_seconds=5,
        num_search_workers=1,
    )

    assert result.status in (
        "OPTIMAL",
        "FEASIBLE",
    )
    assert len(result.assignments) == 2

    issues = validate_schedule(
        list(result.assignments),
        employees,
        [],
        requirements,
    )

    assert has_errors(issues) is False


def test_day_off_is_respected() -> None:
    employees = [
        make_employee("E001"),
        make_employee("E002"),
    ]

    requests = [
        DayOffRequest(
            employee_id="E001",
            target_date=date(2026, 8, 1),
        )
    ]

    requirements = [
        make_requirement(
            date(2026, 8, 1),
            "early",
        )
    ]

    result = generate_schedule(
        "2026-08",
        employees,
        requests,
        requirements,
        max_time_seconds=5,
        num_search_workers=1,
    )

    assigned_ids = {
        assignment.employee_id
        for assignment in result.assignments
    }

    assert "E001" not in assigned_ids
    assert "E002" in assigned_ids


def test_manager_is_assigned_when_required() -> None:
    employees = [
        make_employee(
            "E001",
            is_manager=True,
        ),
        make_employee("E002"),
    ]

    requirements = [
        make_requirement(
            date(2026, 8, 1),
            "early",
            required_count=1,
            required_manager_count=1,
        )
    ]

    result = generate_schedule(
        "2026-08",
        employees,
        [],
        requirements,
        max_time_seconds=5,
        num_search_workers=1,
    )

    assert result.assignments[0].employee_id == "E001"


def test_infeasible_when_staff_is_insufficient() -> None:
    employees = [
        make_employee("E001"),
    ]

    requirements = [
        make_requirement(
            date(2026, 8, 1),
            "early",
            required_count=2,
        )
    ]

    result = generate_schedule(
        "2026-08",
        employees,
        [],
        requirements,
        max_time_seconds=5,
        num_search_workers=1,
    )

    assert result.status == "INFEASIBLE"
    assert result.assignments == ()


def test_weekly_limit_is_respected() -> None:
    start_date = date(2026, 8, 3)

    employees = [
        make_employee(
            "E001",
            contract_days=3,
        ),
        make_employee(
            "E002",
            contract_days=3,
        ),
    ]

    requirements = [
        make_requirement(
            start_date + timedelta(days=offset),
            "early",
        )
        for offset in range(6)
    ]

    result = generate_schedule(
        "2026-08",
        employees,
        [],
        requirements,
        max_time_seconds=5,
        num_search_workers=1,
    )

    counts = {
        employee.employee_id: 0
        for employee in employees
    }

    for assignment in result.assignments:
        counts[assignment.employee_id] += 1

    assert max(counts.values()) <= 5


def test_six_consecutive_days_are_avoided() -> None:
    start_date = date(2026, 8, 1)

    employees = [
        make_employee(
            "E001",
            contract_days=3,
        ),
        make_employee(
            "E002",
            contract_days=3,
        ),
    ]

    requirements = [
        make_requirement(
            start_date + timedelta(days=offset),
            "early",
        )
        for offset in range(6)
    ]

    result = generate_schedule(
        "2026-08",
        employees,
        [],
        requirements,
        max_time_seconds=5,
        num_search_workers=1,
    )

    issues = validate_schedule(
        list(result.assignments),
        employees,
        [],
        requirements,
    )

    assert not any(
        issue.rule_id == "HC-07"
        for issue in issues
    )


def test_contract_days_are_balanced() -> None:
    employees = [
        make_employee(
            "E001",
            contract_days=2,
        ),
        make_employee(
            "E002",
            contract_days=2,
        ),
    ]

    requirements = [
        make_requirement(
            date(2026, 8, day),
            "early",
        )
        for day in range(1, 5)
    ]

    result = generate_schedule(
        "2026-08",
        employees,
        [],
        requirements,
        max_time_seconds=5,
        num_search_workers=1,
    )

    counts = {
        "E001": 0,
        "E002": 0,
    }

    for assignment in result.assignments:
        counts[assignment.employee_id] += 1

    assert counts == {
        "E001": 2,
        "E002": 2,
    }
    assert result.max_deviation == 0
    assert result.total_deviation == 0