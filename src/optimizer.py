from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta

from ortools.sat.python import cp_model

from src.models import (
    DayOffRequest,
    Employee,
    ScheduleAssignment,
    ScheduleGenerationResult,
    SolverStatus,
    StaffingRequirement,
)


def _convert_solver_status(
    status: cp_model.CpSolverStatus,
) -> SolverStatus:
    status_map: dict[int, SolverStatus] = {
        cp_model.OPTIMAL: "OPTIMAL",
        cp_model.FEASIBLE: "FEASIBLE",
        cp_model.INFEASIBLE: "INFEASIBLE",
        cp_model.MODEL_INVALID: "MODEL_INVALID",
        cp_model.UNKNOWN: "UNKNOWN",
    }

    return status_map.get(status, "UNKNOWN")


def _week_start(target_date: date) -> date:
    return target_date - timedelta(
        days=target_date.weekday()
    )

def generate_schedule(
    target_month: str,
    employees: list[Employee],
    day_off_requests: list[DayOffRequest],
    requirements: list[StaffingRequirement],
    *,
    max_time_seconds: float = 30.0,
    num_search_workers: int = 1,
) -> ScheduleGenerationResult:

    active_employees = [
        employee
        for employee in employees
        if employee.is_active
    ]

    dates = sorted({
        requirement.target_date
        for requirement in requirements
    })

    shift_types = ("early", "late")

    employee_map = {
        employee.employee_id: employee
        for employee in active_employees
    }

    day_off_set = {
        (
            request.employee_id,
            request.target_date,
        )
        for request in day_off_requests
    }

    requirement_map = {
        (
            requirement.target_date,
            requirement.shift_type,
        ): requirement
        for requirement in requirements
    }

    employee_ids = [
        employee.employee_id
        for employee in active_employees
    ]

    model = cp_model.CpModel()

    work: dict[
        tuple[str, date, str],
        cp_model.IntVar,
    ] = {}

    for employee_id in employee_ids:
        for target_date in dates:
            for shift_type in shift_types:
                variable_name = (
                    f"work_"
                    f"{employee_id}_"
                    f"{target_date.isoformat()}_"
                    f"{shift_type}"
                )

                work[
                    (
                        employee_id,
                        target_date,
                        shift_type,
                    )
                ] = model.new_bool_var(variable_name)

    for employee_id in employee_ids:
        for target_date in dates:
            model.add(
                sum(
                    work[
                        (
                            employee_id,
                            target_date,
                            shift_type,
                        )
                    ]
                    for shift_type in shift_types
                )
                <= 1
            )

    for employee_id, target_date in day_off_set:
        if employee_id not in employee_map:
            continue

        for shift_type in shift_types:
            key = (
                employee_id,
                target_date,
                shift_type,
            )

            if key in work:
                model.add(work[key] == 0)

    for employee in active_employees:
        for target_date in dates:
            if not employee.can_work_early:
                model.add(
                    work[
                        (
                            employee.employee_id,
                            target_date,
                            "early",
                        )
                    ]
                    == 0
                )

            if not employee.can_work_late:
                model.add(
                    work[
                        (
                            employee.employee_id,
                            target_date,
                            "late",
                        )
                    ]
                    == 0
                )

    for requirement in requirements:
        model.add(
            sum(
                work[
                    (
                        employee_id,
                        requirement.target_date,
                        requirement.shift_type,
                    )
                ]
                for employee_id in employee_ids
            )
            == requirement.required_count
        )

    manager_ids = [
        employee.employee_id
        for employee in active_employees
        if employee.is_manager
    ]

    for requirement in requirements:
        if requirement.required_manager_count == 0:
            continue

        model.add(
            sum(
                work[
                    (
                        employee_id,
                        requirement.target_date,
                        requirement.shift_type,
                    )
                ]
                for employee_id in manager_ids
            )
            >= requirement.required_manager_count
        )

    works_day: dict[
        tuple[str, date],
        cp_model.IntVar,
    ] = {}

    for employee_id in employee_ids:
        for target_date in dates:
            day_variable = model.new_bool_var(
                f"works_day_"
                f"{employee_id}_"
                f"{target_date.isoformat()}"
            )

            works_day[
                (
                    employee_id,
                    target_date,
                )
            ] = day_variable

            model.add(
                day_variable
                == sum(
                    work[
                        (
                            employee_id,
                            target_date,
                            shift_type,
                        )
                    ]
                    for shift_type in shift_types
                )
            )



    dates_by_week: dict[date, list[date]] = defaultdict(list)

    for target_date in dates:
        dates_by_week[
            _week_start(target_date)
        ].append(target_date)
    for employee_id in employee_ids:
        for week_dates in dates_by_week.values():
            model.add(
                sum(
                    works_day[
                        (
                            employee_id,
                            target_date,
                        )
                    ]
                    for target_date in week_dates
                )
                <= 5
            )

    sorted_dates = sorted(dates)
    date_set = set(sorted_dates)

    for employee_id in employee_ids:
        for start_date in sorted_dates:
            window = [
                start_date + timedelta(days=offset)
                for offset in range(6)
            ]

            if not all(
                target_date in date_set
                for target_date in window
            ):
                continue

            model.add(
                sum(
                    works_day[
                        (
                            employee_id,
                            target_date,
                        )
                    ]
                    for target_date in window
                )
                <= 5
            )

    assigned_days: dict[str, cp_model.IntVar] = {}

    month_day_count = len(dates)

    for employee_id in employee_ids:
        variable = model.new_int_var(
            0,
            month_day_count,
            f"assigned_days_{employee_id}",
        )

        assigned_days[employee_id] = variable

        model.add(
            variable
            == sum(
                works_day[
                    (
                        employee_id,
                        target_date,
                    )
                ]
                for target_date in dates
            )
        )

    deviations: dict[str, cp_model.IntVar] = {}

    for employee in active_employees:
        deviation = model.new_int_var(
            0,
            month_day_count,
            f"deviation_{employee.employee_id}",
        )

        deviations[employee.employee_id] = deviation

        model.add_abs_equality(
            deviation,
            assigned_days[employee.employee_id]
            - employee.contract_days,
        )

    max_deviation = model.new_int_var(
        0,
        month_day_count,
        "max_deviation",
    )

    for deviation in deviations.values():
        model.add(max_deviation >= deviation)

    maximum_total_deviation = (
        len(active_employees)
        * month_day_count
    )

    total_deviation = model.new_int_var(
        0,
        maximum_total_deviation,
        "total_deviation",
    )

    model.add(
        total_deviation
        == sum(deviations.values())
    )

    max_deviation_weight = (
        maximum_total_deviation + 1
    )

    objective_expression = (
        max_deviation * max_deviation_weight
        + total_deviation
    )

    model.minimize(objective_expression)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = (
        max_time_seconds
    )
    solver.parameters.num_search_workers = (
        num_search_workers
    )

    status = solver.solve(model)

    solver_status = _convert_solver_status(status)

    if solver_status not in (
        "OPTIMAL",
        "FEASIBLE",
    ):
        return ScheduleGenerationResult(
            status=solver_status,
            assignments=(),
            objective_value=None,
            max_deviation=None,
            total_deviation=None,
        )

    assignments: list[ScheduleAssignment] = []

    for employee_id in employee_ids:
        for target_date in dates:
            for shift_type in shift_types:
                variable = work[
                    (
                        employee_id,
                        target_date,
                        shift_type,
                    )
                ]

                if solver.value(variable) != 1:
                    continue

                assignments.append(
                    ScheduleAssignment(
                        target_date=target_date,
                        shift_type=shift_type,
                        employee_id=employee_id,
                        is_manual=False,
                    )
                )

    shift_order = {
        "early": 0,
        "late": 1,
    }

    assignments.sort(
        key=lambda assignment: (
            assignment.target_date,
            shift_order[assignment.shift_type],
            assignment.employee_id,
        )
    )

    return ScheduleGenerationResult(
        status=solver_status,
        assignments=tuple(assignments),
        objective_value=int(
            round(solver.objective_value)
        ),
        max_deviation=solver.value(
            max_deviation
        ),
        total_deviation=solver.value(
            total_deviation
        ),
    )