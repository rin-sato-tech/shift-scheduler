from __future__ import annotations

from src.models import (
    ValidationIssue,
    EmployeeScheduleSummary,
    ValidationIssue,
)
from src.repositories import (
    list_day_off_requests,
    list_employees,
    list_schedule_assignments,
    list_staffing_requirements,
)
from src.validation import (
    validate_generation_inputs,
    build_employee_schedule_summaries,
    validate_schedule,
)


def validate_month_generation_inputs(
    target_month: str,
) -> list[ValidationIssue]:
    employees = list_employees()
    day_off_requests = list_day_off_requests(
        target_month
    )
    requirements = list_staffing_requirements(
        target_month
    )

    return validate_generation_inputs(
        target_month,
        employees,
        day_off_requests,
        requirements,
    )


def validate_month_schedule(
    target_month: str,
) -> list[ValidationIssue]:
    employees = list_employees()
    day_off_requests = list_day_off_requests(
        target_month
    )
    requirements = list_staffing_requirements(
        target_month
    )
    assignments = list_schedule_assignments(
        target_month
    )

    return validate_schedule(
        assignments,
        employees,
        day_off_requests,
        requirements,
    )


def get_month_employee_summaries(
    target_month: str,
) -> list[EmployeeScheduleSummary]:
    employees = list_employees()
    assignments = list_schedule_assignments(
        target_month
    )

    return build_employee_schedule_summaries(
        assignments,
        employees,
    )