from __future__ import annotations

from src.models import (
    ValidationIssue,
    EmployeeScheduleSummary,
    ScheduleGenerationServiceResult,
)
from src.optimizer import generate_schedule
from src.repositories import (
    create_schedule_generation,
    list_day_off_requests,
    list_employees,
    list_schedule_assignments,
    list_staffing_requirements,
    replace_month_schedule_assignments,
)
from src.validation import (
    validate_generation_inputs,
    build_employee_schedule_summaries,
    has_errors,
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


def generate_month_schedule(
    target_month: str,
    *,
    max_time_seconds: float = 30.0,
    num_search_workers: int = 8,
) -> ScheduleGenerationServiceResult:
    employees = list_employees()
    day_off_requests = list_day_off_requests(
        target_month
    )
    requirements = list_staffing_requirements(
        target_month
    )

    pre_issues = validate_generation_inputs(
        target_month,
        employees,
        day_off_requests,
        requirements,
    )

    if has_errors(pre_issues):
        return ScheduleGenerationServiceResult(
            generated=False,
            solver_result=None,
            validation_issues=tuple(pre_issues),
            generation_id=None,
        )

    solver_result = generate_schedule(
        target_month,
        employees,
        day_off_requests,
        requirements,
        max_time_seconds=max_time_seconds,
        num_search_workers=num_search_workers,
    )

    if solver_result.status not in (
        "OPTIMAL",
        "FEASIBLE",
    ):
        generation_id = create_schedule_generation(
            target_month=target_month,
            solver_status=solver_result.status,
        )

        return ScheduleGenerationServiceResult(
            generated=False,
            solver_result=solver_result,
            validation_issues=tuple(pre_issues),
            generation_id=generation_id,
        )

    post_issues = validate_schedule(
        list(solver_result.assignments),
        employees,
        day_off_requests,
        requirements,
    )

    all_issues = [
        *pre_issues,
        *post_issues,
    ]

    if has_errors(post_issues):
        return ScheduleGenerationServiceResult(
            generated=False,
            solver_result=solver_result,
            validation_issues=tuple(all_issues),
            generation_id=None,
        )

    generation_id = create_schedule_generation(
        target_month=target_month,
        solver_status=solver_result.status,
        objective_value=solver_result.objective_value,
        max_deviation=solver_result.max_deviation,
        total_deviation=solver_result.total_deviation,
    )

    replace_month_schedule_assignments(
        target_month,
        solver_result.assignments,
        generation_id=generation_id,
    )

    return ScheduleGenerationServiceResult(
        generated=True,
        solver_result=solver_result,
        validation_issues=tuple(all_issues),
        generation_id=generation_id,
    )