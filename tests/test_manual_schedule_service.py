from __future__ import annotations

from datetime import date

from src.manual_schedule_service import (
    apply_manual_change,
    save_manual_schedule,
    validate_manual_schedule,
)
from src.models import (
    Employee,
    ScheduleAssignment,
    StaffingRequirement,
)
from src.repositories import (
    create_employee,
    list_schedule_assignments,
    replace_month_schedule_assignments,
    upsert_staffing_requirements,
)
from src.validation import has_errors

TARGET_MONTH = "2026-08"


def register_employees() -> None:
    employees = [
        Employee(
            employee_id="E001",
            name="山田太郎",
            is_manager=True,
            contract_days=1,
            can_work_early=True,
            can_work_late=True,
            is_active=True,
        ),
        Employee(
            employee_id="E002",
            name="佐藤花子",
            is_manager=True,
            contract_days=1,
            can_work_early=True,
            can_work_late=True,
            is_active=True,
        ),
    ]

    for employee in employees:
        create_employee(employee)


def register_requirements() -> None:
    requirements = [
        StaffingRequirement(
            target_date=date(2026, 8, 1),
            shift_type="early",
            required_count=1,
            required_manager_count=1,
        ),
        StaffingRequirement(
            target_date=date(2026, 8, 1),
            shift_type="late",
            required_count=1,
            required_manager_count=1,
        ),
    ]

    upsert_staffing_requirements(
        requirements
    )


def save_initial_schedule() -> None:
    assignments = [
        ScheduleAssignment(
            target_date=date(2026, 8, 1),
            shift_type="early",
            employee_id="E001",
        ),
        ScheduleAssignment(
            target_date=date(2026, 8, 1),
            shift_type="late",
            employee_id="E002",
        ),
    ]

    replace_month_schedule_assignments(
        TARGET_MONTH,
        assignments,
    )


def test_apply_manual_change(
    initialized_test_db,
) -> None:
    register_employees()

    assignments = [
        ScheduleAssignment(
            target_date=date(2026, 8, 1),
            shift_type="early",
            employee_id="E001",
        )
    ]

    result = apply_manual_change(
        target_month=TARGET_MONTH,
        assignments=assignments,
        employee_id="E001",
        target_date=date(2026, 8, 1),
        new_shift="late",
    )

    assert result.succeeded is True
    assert len(result.assignments) == 1

    changed = result.assignments[0]

    assert changed.shift_type == "late"
    assert changed.is_manual is True


def test_apply_manual_change_to_off(
    initialized_test_db,
) -> None:
    register_employees()

    assignments = [
        ScheduleAssignment(
            target_date=date(2026, 8, 1),
            shift_type="early",
            employee_id="E001",
        )
    ]

    result = apply_manual_change(
        target_month=TARGET_MONTH,
        assignments=assignments,
        employee_id="E001",
        target_date=date(2026, 8, 1),
        new_shift="off",
    )

    assert result.succeeded is True
    assert result.assignments == ()


def test_rejects_unavailable_shift(
    initialized_test_db,
) -> None:
    create_employee(
        Employee(
            employee_id="E001",
            name="山田太郎",
            is_manager=False,
            contract_days=1,
            can_work_early=True,
            can_work_late=False,
            is_active=True,
        )
    )

    result = apply_manual_change(
        target_month=TARGET_MONTH,
        assignments=[],
        employee_id="E001",
        target_date=date(2026, 8, 1),
        new_shift="late",
    )

    assert result.succeeded is False
    assert "遅番勤務不可" in result.message


def test_manual_schedule_detects_staff_shortage(
    initialized_test_db,
) -> None:
    register_employees()
    register_requirements()

    assignments = [
        ScheduleAssignment(
            target_date=date(2026, 8, 1),
            shift_type="early",
            employee_id="E001",
        ),
        ScheduleAssignment(
            target_date=date(2026, 8, 1),
            shift_type="late",
            employee_id="E002",
        ),
    ]

    result = apply_manual_change(
        target_month=TARGET_MONTH,
        assignments=assignments,
        employee_id="E001",
        target_date=date(2026, 8, 1),
        new_shift="off",
    )

    issues = validate_manual_schedule(
        target_month=TARGET_MONTH,
        assignments=list(
            result.assignments
        ),
    )

    assert has_errors(issues) is True
    assert any(
        issue.rule_id == "HC-04"
        for issue in issues
    )


def test_save_manual_schedule(
    initialized_test_db,
) -> None:
    register_employees()
    register_requirements()
    save_initial_schedule()

    assignments = (
        list_schedule_assignments(
            TARGET_MONTH
        )
    )

    first_change = apply_manual_change(
        target_month=TARGET_MONTH,
        assignments=assignments,
        employee_id="E001",
        target_date=date(2026, 8, 1),
        new_shift="late",
    )

    second_change = apply_manual_change(
        target_month=TARGET_MONTH,
        assignments=list(
            first_change.assignments
        ),
        employee_id="E002",
        target_date=date(2026, 8, 1),
        new_shift="early",
    )

    save_result = save_manual_schedule(
        target_month=TARGET_MONTH,
        assignments=list(
            second_change.assignments
        ),
    )

    assert save_result.succeeded is True

    saved = list_schedule_assignments(
        TARGET_MONTH
    )

    saved_map = {
        assignment.employee_id: assignment
        for assignment in saved
    }

    assert (
        saved_map["E001"].shift_type
        == "late"
    )
    assert (
        saved_map["E002"].shift_type
        == "early"
    )
    assert saved_map["E001"].is_manual is True
    assert saved_map["E002"].is_manual is True


def test_does_not_save_invalid_manual_schedule(
    initialized_test_db,
) -> None:
    register_employees()
    register_requirements()
    save_initial_schedule()

    original = list_schedule_assignments(
        TARGET_MONTH
    )

    changed = apply_manual_change(
        target_month=TARGET_MONTH,
        assignments=original,
        employee_id="E001",
        target_date=date(2026, 8, 1),
        new_shift="off",
    )

    save_result = save_manual_schedule(
        target_month=TARGET_MONTH,
        assignments=list(
            changed.assignments
        ),
    )

    assert save_result.succeeded is False

    saved = list_schedule_assignments(
        TARGET_MONTH
    )

    assert saved == original