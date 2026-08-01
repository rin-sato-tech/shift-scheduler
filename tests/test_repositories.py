from __future__ import annotations

import sqlite3
from datetime import date

import pytest

from src.models import (
    DayOffRequest,
    Employee,
    ScheduleAssignment,
    StaffingRequirement,
)
from src.repositories import (
    create_day_off_request,
    create_employee,
    create_schedule_assignment,
    delete_day_off_request,
    get_employee,
    list_day_off_requests,
    list_employees,
    list_schedule_assignments,
    list_staffing_requirements,
    set_employee_active,
    update_employee,
    upsert_staffing_requirement,
)


def make_employee(
    employee_id: str = "E001",
) -> Employee:
    return Employee(
        employee_id=employee_id,
        name="佐藤",
        is_manager=True,
        contract_days=20,
        can_work_early=True,
        can_work_late=True,
        is_active=True,
    )


def test_create_and_get_employee(
    initialized_test_db,
) -> None:
    employee = make_employee()

    create_employee(employee)

    actual = get_employee("E001")

    assert actual == employee


def test_list_active_employees(
    initialized_test_db,
) -> None:
    create_employee(make_employee("E001"))
    create_employee(make_employee("E002"))

    set_employee_active(
        "E002",
        is_active=False,
    )

    employees = list_employees(active_only=True)

    assert [employee.employee_id for employee in employees] == [
        "E001"
    ]


def test_update_employee(
    initialized_test_db,
) -> None:
    create_employee(make_employee())

    updated = Employee(
        employee_id="E001",
        name="佐藤太郎",
        is_manager=False,
        contract_days=18,
        can_work_early=True,
        can_work_late=False,
        is_active=True,
    )

    result = update_employee(updated)

    assert result is True
    assert get_employee("E001") == updated


def test_create_and_list_day_off_request(
    initialized_test_db,
) -> None:
    create_employee(make_employee())

    request = DayOffRequest(
        employee_id="E001",
        target_date=date(2026, 8, 10),
    )

    create_day_off_request(request)

    requests = list_day_off_requests(
        "2026-08",
        employee_id="E001",
    )

    assert requests == [request]


def test_duplicate_day_off_request_fails(
    initialized_test_db,
) -> None:
    create_employee(make_employee())

    request = DayOffRequest(
        employee_id="E001",
        target_date=date(2026, 8, 10),
    )

    create_day_off_request(request)

    with pytest.raises(sqlite3.IntegrityError):
        create_day_off_request(request)


def test_delete_day_off_request(
    initialized_test_db,
) -> None:
    create_employee(make_employee())

    request = DayOffRequest(
        employee_id="E001",
        target_date=date(2026, 8, 10),
    )

    create_day_off_request(request)

    deleted = delete_day_off_request(
        "E001",
        date(2026, 8, 10),
    )

    assert deleted is True
    assert list_day_off_requests("2026-08") == []


def test_upsert_staffing_requirement(
    initialized_test_db,
) -> None:
    original = StaffingRequirement(
        target_date=date(2026, 8, 1),
        shift_type="early",
        required_count=2,
        required_manager_count=1,
    )

    upsert_staffing_requirement(original)

    updated = StaffingRequirement(
        target_date=date(2026, 8, 1),
        shift_type="early",
        required_count=3,
        required_manager_count=1,
    )

    upsert_staffing_requirement(updated)

    requirements = list_staffing_requirements(
        "2026-08"
    )

    assert requirements == [updated]


def test_manager_count_cannot_exceed_required_count(
    initialized_test_db,
) -> None:
    requirement = StaffingRequirement(
        target_date=date(2026, 8, 1),
        shift_type="early",
        required_count=1,
        required_manager_count=2,
    )

    with pytest.raises(sqlite3.IntegrityError):
        upsert_staffing_requirement(requirement)


def test_employee_cannot_have_two_shifts_same_day(
    initialized_test_db,
) -> None:
    create_employee(make_employee())

    early = ScheduleAssignment(
        target_date=date(2026, 8, 1),
        shift_type="early",
        employee_id="E001",
    )

    late = ScheduleAssignment(
        target_date=date(2026, 8, 1),
        shift_type="late",
        employee_id="E001",
    )

    create_schedule_assignment(early)

    with pytest.raises(sqlite3.IntegrityError):
        create_schedule_assignment(late)


def test_schedule_requires_existing_employee(
    initialized_test_db,
) -> None:
    assignment = ScheduleAssignment(
        target_date=date(2026, 8, 1),
        shift_type="early",
        employee_id="UNKNOWN",
    )

    with pytest.raises(sqlite3.IntegrityError):
        create_schedule_assignment(assignment)


def test_schedule_list_is_filtered_by_month(
    initialized_test_db,
) -> None:
    create_employee(make_employee())

    august = ScheduleAssignment(
        target_date=date(2026, 8, 1),
        shift_type="early",
        employee_id="E001",
    )

    september = ScheduleAssignment(
        target_date=date(2026, 9, 1),
        shift_type="early",
        employee_id="E001",
    )

    create_schedule_assignment(august)
    create_schedule_assignment(september)

    assignments = list_schedule_assignments("2026-08")

    assert assignments == [august]

