from __future__ import annotations

import calendar
from collections import defaultdict
from datetime import date, timedelta

from src.models import (
    DayOffRequest,
    Employee,
    StaffingRequirement,
    ValidationIssue,
)


def get_month_dates(target_month: str) -> list[date]:
    try:
        year_text, month_text = target_month.split("-")
        year = int(year_text)
        month = int(month_text)
        last_day = calendar.monthrange(year, month)[1]
    except (ValueError, AttributeError) as exc:
        raise ValueError(
            "target_month must be in YYYY-MM format"
        ) from exc

    return [
        date(year, month, day)
        for day in range(1, last_day + 1)
    ]


def _build_day_off_set(
    requests: list[DayOffRequest],
) -> set[tuple[str, date]]:
    return {
        (request.employee_id, request.target_date)
        for request in requests
    }


def _build_requirement_map(
    requirements: list[StaffingRequirement],
) -> dict[tuple[date, str], StaffingRequirement]:
    return {
        (
            requirement.target_date,
            requirement.shift_type,
        ): requirement
        for requirement in requirements
    }


def validate_active_employees(
    employees: list[Employee],
) -> list[ValidationIssue]:
    active_employees = [
        employee
        for employee in employees
        if employee.is_active
    ]

    if active_employees:
        return []

    return [
        ValidationIssue(
            severity="error",
            rule_id="PV-01",
            message="有効な従業員が登録されていません。",
        )
    ]


def validate_active_managers(
    employees: list[Employee],
    requirements: list[StaffingRequirement],
) -> list[ValidationIssue]:
    manager_required = any(
        requirement.required_manager_count > 0
        for requirement in requirements
    )

    if not manager_required:
        return []

    has_active_manager = any(
        employee.is_active
        and employee.is_manager
        for employee in employees
    )

    if has_active_manager:
        return []

    return [
        ValidationIssue(
            severity="error",
            rule_id="PV-02",
            message=(
                "責任者配置が必要ですが、"
                "有効な責任者が登録されていません。"
            ),
        )
    ]


def validate_requirement_completeness(
    target_month: str,
    requirements: list[StaffingRequirement],
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    requirement_map = _build_requirement_map(requirements)

    for target_date in get_month_dates(target_month):
        for shift_type in ("early", "late"):
            key = (target_date, shift_type)

            if key in requirement_map:
                continue

            issues.append(
                ValidationIssue(
                    severity="error",
                    rule_id="PV-03",
                    target_date=target_date,
                    shift_type=shift_type,
                    message=(
                        f"{target_date.isoformat()}の"
                        f"{shift_type}について、"
                        "必要人数が設定されていません。"
                    ),
                )
            )

    return issues


def validate_requirement_values(
    requirements: list[StaffingRequirement],
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []

    for requirement in requirements:
        is_invalid = (
            requirement.required_count < 0
            or requirement.required_manager_count < 0
            or requirement.required_manager_count
            > requirement.required_count
        )

        if not is_invalid:
            continue

        issues.append(
            ValidationIssue(
                severity="error",
                rule_id="PV-09",
                target_date=requirement.target_date,
                shift_type=requirement.shift_type,
                message=(
                    "必要人数または必要責任者数の"
                    "設定が不正です。"
                ),
            )
        )

    return issues


def _can_work_shift(
    employee: Employee,
    shift_type: str,
) -> bool:
    if shift_type == "early":
        return employee.can_work_early

    if shift_type == "late":
        return employee.can_work_late

    raise ValueError(
        f"Unknown shift type: {shift_type}"
    )


def validate_available_employee_counts(
    employees: list[Employee],
    day_off_requests: list[DayOffRequest],
    requirements: list[StaffingRequirement],
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    day_off_set = _build_day_off_set(day_off_requests)

    active_employees = [
        employee
        for employee in employees
        if employee.is_active
    ]

    for requirement in requirements:
        available_employees = [
            employee
            for employee in active_employees
            if (
                employee.employee_id,
                requirement.target_date,
            )
            not in day_off_set
            and _can_work_shift(
                employee,
                requirement.shift_type,
            )
        ]

        available_count = len(available_employees)

        if available_count >= requirement.required_count:
            continue

        shortage = (
            requirement.required_count
            - available_count
        )

        issues.append(
            ValidationIssue(
                severity="error",
                rule_id="PV-04",
                target_date=requirement.target_date,
                shift_type=requirement.shift_type,
                message=(
                    f"必要人数は"
                    f"{requirement.required_count}人ですが、"
                    f"勤務可能者は{available_count}人です。"
                    f"{shortage}人不足しています。"
                ),
            )
        )

    return issues


def validate_available_manager_counts(
    employees: list[Employee],
    day_off_requests: list[DayOffRequest],
    requirements: list[StaffingRequirement],
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    day_off_set = _build_day_off_set(day_off_requests)

    active_managers = [
        employee
        for employee in employees
        if employee.is_active
        and employee.is_manager
    ]

    for requirement in requirements:
        if requirement.required_manager_count == 0:
            continue

        available_managers = [
            employee
            for employee in active_managers
            if (
                employee.employee_id,
                requirement.target_date,
            )
            not in day_off_set
            and _can_work_shift(
                employee,
                requirement.shift_type,
            )
        ]

        available_count = len(available_managers)

        if (
            available_count
            >= requirement.required_manager_count
        ):
            continue

        shortage = (
            requirement.required_manager_count
            - available_count
        )

        issues.append(
            ValidationIssue(
                severity="error",
                rule_id="PV-05",
                target_date=requirement.target_date,
                shift_type=requirement.shift_type,
                message=(
                    f"必要責任者数は"
                    f"{requirement.required_manager_count}人ですが、"
                    f"配置可能な責任者は"
                    f"{available_count}人です。"
                    f"{shortage}人不足しています。"
                ),
            )
        )

    return issues


def calculate_required_assignment_count(
    requirements: list[StaffingRequirement],
) -> int:
    return sum(
        requirement.required_count
        for requirement in requirements
    )


def calculate_total_contract_days(
    employees: list[Employee],
) -> int:
    return sum(
        employee.contract_days
        for employee in employees
        if employee.is_active
    )


def validate_contract_capacity(
    employees: list[Employee],
    requirements: list[StaffingRequirement],
) -> list[ValidationIssue]:
    required_count = calculate_required_assignment_count(
        requirements
    )
    contract_count = calculate_total_contract_days(
        employees
    )

    difference = contract_count - required_count

    if difference == 0:
        return []

    if difference < 0:
        return [
            ValidationIssue(
                severity="warning",
                rule_id="PV-06",
                message=(
                    f"必要勤務枠は{required_count}日ですが、"
                    f"契約勤務日数合計は"
                    f"{contract_count}日です。"
                    f"{abs(difference)}日不足しています。"
                    "一部従業員が契約日数を超える"
                    "可能性があります。"
                ),
            )
        ]

    return [
        ValidationIssue(
            severity="warning",
            rule_id="PV-07",
            message=(
                f"必要勤務枠は{required_count}日ですが、"
                f"契約勤務日数合計は"
                f"{contract_count}日です。"
                f"{difference}日余っています。"
                "一部従業員が契約日数に届かない"
                "可能性があります。"
            ),
        )
    ]


def validate_contract_days_for_month(
    target_month: str,
    employees: list[Employee],
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    month_day_count = len(get_month_dates(target_month))

    for employee in employees:
        if not employee.is_active:
            continue

        if employee.contract_days <= month_day_count:
            continue

        issues.append(
            ValidationIssue(
                severity="warning",
                rule_id="PV-08",
                employee_id=employee.employee_id,
                message=(
                    f"{employee.name}の契約勤務日数"
                    f"{employee.contract_days}日は、"
                    f"対象月の日数"
                    f"{month_day_count}日を超えています。"
                ),
            )
        )

    return issues


def _group_dates_by_week(
    dates: list[date],
) -> list[list[date]]:
    grouped: dict[
        tuple[int, int],
        list[date],
    ] = defaultdict(list)

    for target_date in dates:
        iso_year, iso_week, _ = (
            target_date.isocalendar()
        )
        grouped[(iso_year, iso_week)].append(
            target_date
        )

    return list(grouped.values())


def calculate_employee_monthly_week_capacity(
    target_month: str,
) -> int:
    month_dates = get_month_dates(target_month)
    weeks = _group_dates_by_week(month_dates)

    return sum(
        min(len(week_dates), 5)
        for week_dates in weeks
    )


def validate_total_weekly_capacity(
    target_month: str,
    employees: list[Employee],
    requirements: list[StaffingRequirement],
) -> list[ValidationIssue]:
    active_employee_count = sum(
        1
        for employee in employees
        if employee.is_active
    )

    per_employee_capacity = (
        calculate_employee_monthly_week_capacity(
            target_month
        )
    )

    total_capacity = (
        active_employee_count
        * per_employee_capacity
    )

    required_count = calculate_required_assignment_count(
        requirements
    )

    if total_capacity >= required_count:
        return []

    return [
        ValidationIssue(
            severity="error",
            rule_id="PV-10",
            message=(
                f"週5日上限を考慮した最大配置可能数は"
                f"{total_capacity}日ですが、"
                f"必要勤務枠は{required_count}日です。"
                "従業員数または必要人数設定を"
                "見直してください。"
            ),
        )
    ]


def validate_generation_inputs(
    target_month: str,
    employees: list[Employee],
    day_off_requests: list[DayOffRequest],
    requirements: list[StaffingRequirement],
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []

    issues.extend(
        validate_active_employees(employees)
    )
    issues.extend(
        validate_active_managers(
            employees,
            requirements,
        )
    )
    issues.extend(
        validate_requirement_completeness(
            target_month,
            requirements,
        )
    )
    issues.extend(
        validate_requirement_values(
            requirements
        )
    )
    issues.extend(
        validate_available_employee_counts(
            employees,
            day_off_requests,
            requirements,
        )
    )
    issues.extend(
        validate_available_manager_counts(
            employees,
            day_off_requests,
            requirements,
        )
    )
    issues.extend(
        validate_contract_capacity(
            employees,
            requirements,
        )
    )
    issues.extend(
        validate_contract_days_for_month(
            target_month,
            employees,
        )
    )
    issues.extend(
        validate_total_weekly_capacity(
            target_month,
            employees,
            requirements,
        )
    )

    return sorted(
        issues,
        key=lambda issue: (
            0 if issue.severity == "error" else 1,
            issue.target_date or date.max,
            issue.shift_type or "",
            issue.rule_id,
        ),
    )


def has_errors(
    issues: list[ValidationIssue],
) -> bool:
    return any(
        issue.severity == "error"
        for issue in issues
    )