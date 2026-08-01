from __future__ import annotations

import sqlite3
from datetime import date

import pytest

from src.db import get_connection
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
    save_generated_schedule,
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


def test_save_generated_schedule(
    initialized_test_db,
) -> None:
    create_employee(
        Employee(
            employee_id="E001",
            name="従業員1",
            is_manager=True,
            contract_days=2,
            can_work_early=True,
            can_work_late=True,
            is_active=True,
        )
    )

    assignments = [
        ScheduleAssignment(
            target_date=date(2026, 8, 1),
            shift_type="early",
            employee_id="E001",
            is_manual=False,
        ),
        ScheduleAssignment(
            target_date=date(2026, 8, 2),
            shift_type="late",
            employee_id="E001",
            is_manual=False,
        ),
    ]

    generation_id = save_generated_schedule(
        target_month="2026-08",
        solver_status="OPTIMAL",
        objective_value=0,
        max_deviation=0,
        total_deviation=0,
        assignments=assignments,
    )

    assert generation_id > 0

    saved_assignments = (
        list_schedule_assignments(
            "2026-08"
        )
    )

    assert saved_assignments == assignments

    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT
                target_month,
                solver_status,
                objective_value,
                max_deviation,
                total_deviation
            FROM schedule_generations
            WHERE generation_id = ?
            """,
            (generation_id,),
        ).fetchone()

    assert row is not None
    assert row["target_month"] == "2026-08"
    assert row["solver_status"] == "OPTIMAL"
    assert row["objective_value"] == 0
    assert row["max_deviation"] == 0
    assert row["total_deviation"] == 0


def test_save_generated_schedule_replaces_month(
    initialized_test_db,
) -> None:
    create_employee(
        Employee(
            employee_id="E001",
            name="従業員1",
            is_manager=False,
            contract_days=2,
            can_work_early=True,
            can_work_late=True,
            is_active=True,
        )
    )

    first_assignments = [
        ScheduleAssignment(
            target_date=date(2026, 8, 1),
            shift_type="early",
            employee_id="E001",
        )
    ]

    save_generated_schedule(
        target_month="2026-08",
        solver_status="OPTIMAL",
        objective_value=1,
        max_deviation=1,
        total_deviation=1,
        assignments=first_assignments,
    )

    second_assignments = [
        ScheduleAssignment(
            target_date=date(2026, 8, 2),
            shift_type="late",
            employee_id="E001",
        )
    ]

    second_generation_id = (
        save_generated_schedule(
            target_month="2026-08",
            solver_status="OPTIMAL",
            objective_value=0,
            max_deviation=0,
            total_deviation=0,
            assignments=second_assignments,
        )
    )

    saved_assignments = (
        list_schedule_assignments(
            "2026-08"
        )
    )

    assert saved_assignments == second_assignments

    with get_connection() as connection:
        generation_ids = connection.execute(
            """
            SELECT DISTINCT generation_id
            FROM schedules
            WHERE target_date >= ?
              AND target_date < ?
            """,
            (
                "2026-08-01",
                "2026-09-01",
            ),
        ).fetchall()

    assert len(generation_ids) == 1
    assert (
        generation_ids[0]["generation_id"]
        == second_generation_id
    )


def test_save_generated_schedule_rejects_other_month(
    initialized_test_db,
) -> None:
    assignments = [
        ScheduleAssignment(
            target_date=date(2026, 9, 1),
            shift_type="early",
            employee_id="E001",
        )
    ]

    with pytest.raises(
        ValueError,
        match="target month",
    ):
        save_generated_schedule(
            target_month="2026-08",
            solver_status="OPTIMAL",
            objective_value=0,
            max_deviation=0,
            total_deviation=0,
            assignments=assignments,
        )


def test_save_generated_schedule_rolls_back(
    initialized_test_db,
) -> None:
    create_employee(
        Employee(
            employee_id="E001",
            name="従業員1",
            is_manager=False,
            contract_days=1,
            can_work_early=True,
            can_work_late=True,
            is_active=True,
        )
    )

    invalid_assignments = [
        ScheduleAssignment(
            target_date=date(2026, 8, 1),
            shift_type="early",
            employee_id="E001",
        ),
        ScheduleAssignment(
            target_date=date(2026, 8, 1),
            shift_type="late",
            employee_id="E001",
        ),
    ]

    with pytest.raises(
        sqlite3.IntegrityError
    ):
        save_generated_schedule(
            target_month="2026-08",
            solver_status="OPTIMAL",
            objective_value=0,
            max_deviation=0,
            total_deviation=0,
            assignments=invalid_assignments,
        )

    with get_connection() as connection:
        generation_count = connection.execute(
            """
            SELECT COUNT(*)
            FROM schedule_generations
            """
        ).fetchone()[0]

        schedule_count = connection.execute(
            """
            SELECT COUNT(*)
            FROM schedules
            """
        ).fetchone()[0]

    assert generation_count == 0
    assert schedule_count == 0