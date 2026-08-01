from __future__ import annotations

from src.models import ValidationIssue
from src.repositories import (
    list_day_off_requests,
    list_employees,
    list_staffing_requirements,
)
from src.validation import validate_generation_inputs


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