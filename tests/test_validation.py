from __future__ import annotations

from datetime import date

from src.models import (
    DayOffRequest,
    Employee,
    StaffingRequirement,
)
from src.validation import (
    has_errors,
    validate_active_employees,
    validate_active_managers,
    validate_available_employee_counts,
    validate_available_manager_counts,
    validate_contract_capacity,
    validate_generation_inputs,
    validate_requirement_completeness,
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


def make_requirement(
    target_date: date,
    shift_type: str,
    *,
    required_count: int = 2,
    required_manager_count: int = 1,
) -> StaffingRequirement:
    return StaffingRequirement(
        target_date=target_date,
        shift_type=shift_type,
        required_count=required_count,
        required_manager_count=required_manager_count,
    )


def test_no_active_employees_is_error() -> None:
    employees = [
        make_employee(
            "E001",
            is_active=False,
        )
    ]

    issues = validate_active_employees(employees)

    assert len(issues) == 1
    assert issues[0].severity == "error"
    assert issues[0].rule_id == "PV-01"


def test_no_manager_is_error_when_manager_required() -> None:
    employees = [
        make_employee("E001"),
        make_employee("E002"),
    ]

    requirements = [
        make_requirement(
            date(2026, 8, 1),
            "early",
            required_manager_count=1,
        )
    ]

    issues = validate_active_managers(
        employees,
        requirements,
    )

    assert len(issues) == 1
    assert issues[0].rule_id == "PV-02"


def test_no_manager_is_allowed_when_not_required() -> None:
    employees = [
        make_employee("E001"),
    ]

    requirements = [
        make_requirement(
            date(2026, 8, 1),
            "early",
            required_manager_count=0,
        )
    ]

    issues = validate_active_managers(
        employees,
        requirements,
    )

    assert issues == []


def test_missing_requirements_are_reported() -> None:
    requirements = [
        make_requirement(
            date(2026, 8, 1),
            "early",
        )
    ]

    issues = validate_requirement_completeness(
        "2026-08",
        requirements,
    )

    assert len(issues) == 61
    assert all(
        issue.rule_id == "PV-03"
        for issue in issues
    )


def test_employee_shortage_is_reported() -> None:
    employees = [
        make_employee("E001"),
        make_employee("E002"),
    ]

    day_off_requests = [
        DayOffRequest(
            employee_id="E002",
            target_date=date(2026, 8, 1),
        )
    ]

    requirements = [
        make_requirement(
            date(2026, 8, 1),
            "early",
            required_count=2,
            required_manager_count=0,
        )
    ]

    issues = validate_available_employee_counts(
        employees,
        day_off_requests,
        requirements,
    )

    assert len(issues) == 1
    assert issues[0].rule_id == "PV-04"


def test_shift_availability_is_considered() -> None:
    employees = [
        make_employee(
            "E001",
            can_work_early=True,
            can_work_late=False,
        ),
        make_employee(
            "E002",
            can_work_early=False,
            can_work_late=True,
        ),
    ]

    requirements = [
        make_requirement(
            date(2026, 8, 1),
            "early",
            required_count=2,
            required_manager_count=0,
        )
    ]

    issues = validate_available_employee_counts(
        employees,
        [],
        requirements,
    )

    assert len(issues) == 1
    assert issues[0].rule_id == "PV-04"


def test_manager_shortage_is_reported() -> None:
    employees = [
        make_employee(
            "E001",
            is_manager=True,
        ),
        make_employee("E002"),
    ]

    day_off_requests = [
        DayOffRequest(
            employee_id="E001",
            target_date=date(2026, 8, 1),
        )
    ]

    requirements = [
        make_requirement(
            date(2026, 8, 1),
            "early",
            required_count=1,
            required_manager_count=1,
        )
    ]

    issues = validate_available_manager_counts(
        employees,
        day_off_requests,
        requirements,
    )

    assert len(issues) == 1
    assert issues[0].rule_id == "PV-05"


def test_contract_capacity_shortage_is_warning() -> None:
    employees = [
        make_employee(
            "E001",
            contract_days=10,
        ),
        make_employee(
            "E002",
            contract_days=10,
        ),
    ]

    requirements = [
        make_requirement(
            date(2026, 8, 1),
            "early",
            required_count=25,
            required_manager_count=0,
        )
    ]

    issues = validate_contract_capacity(
        employees,
        requirements,
    )

    assert len(issues) == 1
    assert issues[0].severity == "warning"
    assert issues[0].rule_id == "PV-06"


def make_month_requirements(
    year: int,
    month: int,
    *,
    required_count: int = 2,
    required_manager_count: int = 1,
) -> list[StaffingRequirement]:
    import calendar

    last_day = calendar.monthrange(
        year,
        month,
    )[1]

    return [
        make_requirement(
            date(year, month, day),
            shift_type,
            required_count=required_count,
            required_manager_count=required_manager_count,
        )
        for day in range(1, last_day + 1)
        for shift_type in ("early", "late")
    ]


def test_valid_inputs_have_no_errors() -> None:
    employees = [
        make_employee(
            "E001",
            is_manager=True,
            contract_days=13,
        ),
        make_employee(
            "E002",
            is_manager=True,
            contract_days=13,
        ),
        make_employee(
            "E003",
            is_manager=True,
            contract_days=13,
        ),
        make_employee(
            "E004",
            is_manager=True,
            contract_days=13,
        ),
        make_employee(
            "E005",
            contract_days=12,
        ),
        make_employee(
            "E006",
            contract_days=12,
        ),
        make_employee(
            "E007",
            contract_days=12,
        ),
        make_employee(
            "E008",
            contract_days=12,
        ),
        make_employee(
            "E009",
            contract_days=12,
        ),
        make_employee(
            "E010",
            contract_days=12,
        ),
    ]

    requirements = make_month_requirements(
        2026,
        8,
    )

    issues = validate_generation_inputs(
        "2026-08",
        employees,
        [],
        requirements,
    )

    assert has_errors(issues) is False


