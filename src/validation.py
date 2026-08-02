from __future__ import annotations

import calendar
from collections import defaultdict
from datetime import date, timedelta

from src.models import (
    DayOffRequest,
    Employee,
    ScheduleAssignment,
    StaffingRequirement,
    ValidationIssue,
    EmployeeScheduleSummary,
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


SHIFT_LABELS = {
    "early": "早番",
    "late": "遅番",
}


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


def _build_employee_map(
    employees: list[Employee],
) -> dict[str, Employee]:
    return {
        employee.employee_id: employee
        for employee in employees
    }


def _group_assignments_by_employee(
    assignments: list[ScheduleAssignment],
) -> dict[str, list[ScheduleAssignment]]:
    grouped: dict[str, list[ScheduleAssignment]] = defaultdict(list)

    for assignment in assignments:
        grouped[assignment.employee_id].append(
            assignment
        )

    for employee_assignments in grouped.values():
        employee_assignments.sort(
            key=lambda assignment: assignment.target_date
        )

    return grouped


def _group_assignments_by_date_shift(
    assignments: list[ScheduleAssignment],
) -> dict[
    tuple[date, str],
    list[ScheduleAssignment],
]:
    grouped: dict[
        tuple[date, str],
        list[ScheduleAssignment],
    ] = defaultdict(list)

    for assignment in assignments:
        grouped[
            (
                assignment.target_date,
                assignment.shift_type,
            )
        ].append(assignment)

    return grouped


def validate_one_shift_per_day(
    assignments: list[ScheduleAssignment],
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    counts: dict[tuple[str, date], int] = defaultdict(int)

    for assignment in assignments:
        counts[
            (
                assignment.employee_id,
                assignment.target_date,
            )
        ] += 1

    for (
        employee_id,
        target_date,
    ), count in counts.items():
        if count <= 1:
            continue

        issues.append(
            ValidationIssue(
                severity="error",
                rule_id="HC-01",
                target_date=target_date,
                employee_id=employee_id,
                message=(
                    f"{employee_id}が同じ日に"
                    f"{count}シフト配置されています。"
                ),
            )
        )

    return issues


def validate_day_off_assignments(
    assignments: list[ScheduleAssignment],
    day_off_requests: list[DayOffRequest],
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    day_off_set = _build_day_off_set(day_off_requests)

    for assignment in assignments:
        key = (
            assignment.employee_id,
            assignment.target_date,
        )

        if key not in day_off_set:
            continue

        issues.append(
            ValidationIssue(
                severity="error",
                rule_id="HC-02",
                target_date=assignment.target_date,
                shift_type=assignment.shift_type,
                employee_id=assignment.employee_id,
                message=(
                    f"{assignment.employee_id}が"
                    "希望休日に配置されています。"
                ),
            )
        )

    return issues


def validate_shift_eligibility(
    assignments: list[ScheduleAssignment],
    employees: list[Employee],
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    employee_map = _build_employee_map(employees)

    for assignment in assignments:
        employee = employee_map.get(
            assignment.employee_id
        )

        if employee is None:
            continue

        if _can_work_shift(
            employee,
            assignment.shift_type,
        ):
            continue

        shift_label = SHIFT_LABELS[
            assignment.shift_type
        ]

        issues.append(
            ValidationIssue(
                severity="error",
                rule_id="HC-03",
                target_date=assignment.target_date,
                shift_type=assignment.shift_type,
                employee_id=assignment.employee_id,
                message=(
                    f"{employee.name}は"
                    f"{shift_label}勤務不可ですが、"
                    "配置されています。"
                ),
            )
        )

    return issues


def validate_required_staff_counts(
    assignments: list[ScheduleAssignment],
    requirements: list[StaffingRequirement],
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []

    assignment_map = (
        _group_assignments_by_date_shift(
            assignments
        )
    )

    for requirement in requirements:
        key = (
            requirement.target_date,
            requirement.shift_type,
        )

        assigned_count = len(
            assignment_map.get(key, [])
        )

        if assigned_count == requirement.required_count:
            continue

        shift_label = SHIFT_LABELS[
            requirement.shift_type
        ]

        if assigned_count < requirement.required_count:
            shortage = (
                requirement.required_count
                - assigned_count
            )

            message = (
                f"{shift_label}の必要人数は"
                f"{requirement.required_count}人ですが、"
                f"{assigned_count}人しか配置されていません。"
                f"{shortage}人不足しています。"
            )
        else:
            excess = (
                assigned_count
                - requirement.required_count
            )

            message = (
                f"{shift_label}の必要人数は"
                f"{requirement.required_count}人ですが、"
                f"{assigned_count}人配置されています。"
                f"{excess}人超過しています。"
            )

        issues.append(
            ValidationIssue(
                severity="error",
                rule_id="HC-04",
                target_date=requirement.target_date,
                shift_type=requirement.shift_type,
                message=message,
            )
        )

    return issues


def validate_required_manager_counts(
    assignments: list[ScheduleAssignment],
    employees: list[Employee],
    requirements: list[StaffingRequirement],
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    employee_map = _build_employee_map(employees)

    assignment_map = (
        _group_assignments_by_date_shift(
            assignments
        )
    )

    for requirement in requirements:
        key = (
            requirement.target_date,
            requirement.shift_type,
        )

        shift_assignments = assignment_map.get(
            key,
            [],
        )

        manager_count = sum(
            1
            for assignment in shift_assignments
            if (
                assignment.employee_id in employee_map
                and employee_map[
                    assignment.employee_id
                ].is_active
                and employee_map[
                    assignment.employee_id
                ].is_manager
            )
        )

        if (
            manager_count
            >= requirement.required_manager_count
        ):
            continue

        shortage = (
            requirement.required_manager_count
            - manager_count
        )

        issues.append(
            ValidationIssue(
                severity="error",
                rule_id="HC-05",
                target_date=requirement.target_date,
                shift_type=requirement.shift_type,
                message=(
                    f"必要責任者数は"
                    f"{requirement.required_manager_count}人ですが、"
                    f"{manager_count}人しか配置されていません。"
                    f"{shortage}人不足しています。"
                ),
            )
        )

    return issues


def _get_week_start(target_date: date) -> date:
    return target_date - timedelta(
        days=target_date.weekday()
    )


def validate_weekly_work_limit(
    assignments: list[ScheduleAssignment],
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []

    work_dates: dict[
        tuple[str, date],
        set[date],
    ] = defaultdict(set)

    for assignment in assignments:
        week_start = _get_week_start(
            assignment.target_date
        )

        work_dates[
            (
                assignment.employee_id,
                week_start,
            )
        ].add(assignment.target_date)

    for (
        employee_id,
        week_start,
    ), dates in work_dates.items():
        work_count = len(dates)

        if work_count <= 5:
            continue

        week_end = week_start + timedelta(days=6)

        issues.append(
            ValidationIssue(
                severity="error",
                rule_id="HC-06",
                target_date=week_start,
                employee_id=employee_id,
                message=(
                    f"{employee_id}は"
                    f"{week_start.isoformat()}から"
                    f"{week_end.isoformat()}の週に"
                    f"{work_count}日勤務しています。"
                    "週5日上限を超えています。"
                ),
            )
        )

    return issues


def calculate_max_consecutive_days(
    work_dates: set[date],
) -> int:
    if not work_dates:
        return 0

    sorted_dates = sorted(work_dates)

    max_count = 1
    current_count = 1

    for previous_date, current_date in zip(
        sorted_dates,
        sorted_dates[1:],
    ):
        if (
            current_date - previous_date
            == timedelta(days=1)
        ):
            current_count += 1
            max_count = max(
                max_count,
                current_count,
            )
        else:
            current_count = 1

    return max_count


def validate_consecutive_work_limit(
    assignments: list[ScheduleAssignment],
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    employee_dates: dict[str, set[date]] = defaultdict(set)

    for assignment in assignments:
        employee_dates[
            assignment.employee_id
        ].add(assignment.target_date)

    for employee_id, work_dates in employee_dates.items():
        sorted_dates = sorted(work_dates)

        if not sorted_dates:
            continue

        sequence_start = sorted_dates[0]
        previous_date = sorted_dates[0]
        sequence_count = 1

        for current_date in sorted_dates[1:] + [None]:
            is_consecutive = (
                current_date is not None
                and current_date - previous_date
                == timedelta(days=1)
            )

            if is_consecutive:
                sequence_count += 1
                previous_date = current_date
                continue

            if sequence_count > 5:
                issues.append(
                    ValidationIssue(
                        severity="error",
                        rule_id="HC-07",
                        target_date=sequence_start,
                        employee_id=employee_id,
                        message=(
                            f"{employee_id}は"
                            f"{sequence_start.isoformat()}から"
                            f"{previous_date.isoformat()}まで"
                            f"{sequence_count}日連続で"
                            "勤務しています。"
                        ),
                    )
                )

            if current_date is not None:
                sequence_start = current_date
                previous_date = current_date
                sequence_count = 1

    return issues


def validate_assigned_employees_active(
    assignments: list[ScheduleAssignment],
    employees: list[Employee],
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    employee_map = _build_employee_map(employees)

    for assignment in assignments:
        employee = employee_map.get(
            assignment.employee_id
        )

        if employee is None:
            issues.append(
                ValidationIssue(
                    severity="error",
                    rule_id="HC-08",
                    target_date=assignment.target_date,
                    shift_type=assignment.shift_type,
                    employee_id=assignment.employee_id,
                    message=(
                        f"存在しない従業員"
                        f"{assignment.employee_id}が"
                        "配置されています。"
                    ),
                )
            )
            continue

        if employee.is_active:
            continue

        issues.append(
            ValidationIssue(
                severity="error",
                rule_id="HC-08",
                target_date=assignment.target_date,
                shift_type=assignment.shift_type,
                employee_id=assignment.employee_id,
                message=(
                    f"無効な従業員"
                    f"{employee.name}が"
                    "配置されています。"
                ),
            )
        )

    return issues


CONTRACT_DAY_WARNING_THRESHOLD = 3


def validate_contract_day_deviation(
    assignments: list[ScheduleAssignment],
    employees: list[Employee],
    *,
    warning_threshold: int = (
        CONTRACT_DAY_WARNING_THRESHOLD
    ),
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    assigned_dates: dict[str, set[date]] = defaultdict(set)

    for assignment in assignments:
        assigned_dates[
            assignment.employee_id
        ].add(assignment.target_date)

    for employee in employees:
        if not employee.is_active:
            continue

        assigned_count = len(
            assigned_dates.get(
                employee.employee_id,
                set(),
            )
        )

        difference = (
            assigned_count
            - employee.contract_days
        )

        if abs(difference) < warning_threshold:
            continue

        if difference < 0:
            detail = (
                f"契約勤務日数より"
                f"{abs(difference)}日不足しています。"
            )
        else:
            detail = (
                f"契約勤務日数より"
                f"{difference}日超過しています。"
            )

        issues.append(
            ValidationIssue(
                severity="warning",
                rule_id="WR-01",
                employee_id=employee.employee_id,
                message=(
                    f"{employee.name}の割当勤務日数は"
                    f"{assigned_count}日です。"
                    f"{detail}"
                ),
            )
        )

    return issues


SHIFT_BALANCE_WARNING_THRESHOLD = 5


def validate_shift_balance(
    assignments: list[ScheduleAssignment],
    employees: list[Employee],
    *,
    warning_threshold: int = (
        SHIFT_BALANCE_WARNING_THRESHOLD
    ),
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []

    counts: dict[
        str,
        dict[str, int],
    ] = defaultdict(
        lambda: {
            "early": 0,
            "late": 0,
        }
    )

    for assignment in assignments:
        counts[assignment.employee_id][
            assignment.shift_type
        ] += 1

    for employee in employees:
        if (
            not employee.is_active
            or not employee.can_work_early
            or not employee.can_work_late
        ):
            continue

        early_count = counts[
            employee.employee_id
        ]["early"]
        late_count = counts[
            employee.employee_id
        ]["late"]

        difference = abs(
            early_count - late_count
        )

        if difference < warning_threshold:
            continue

        issues.append(
            ValidationIssue(
                severity="warning",
                rule_id="WR-02",
                employee_id=employee.employee_id,
                message=(
                    f"{employee.name}の勤務は、"
                    f"早番{early_count}回、"
                    f"遅番{late_count}回です。"
                    "シフト区分に偏りがあります。"
                ),
            )
        )

    return issues


MANAGER_BALANCE_WARNING_THRESHOLD = 5


def validate_manager_assignment_balance(
    assignments: list[ScheduleAssignment],
    employees: list[Employee],
    *,
    warning_threshold: int = (
        MANAGER_BALANCE_WARNING_THRESHOLD
    ),
) -> list[ValidationIssue]:
    active_managers = [
        employee
        for employee in employees
        if employee.is_active
        and employee.is_manager
    ]

    if len(active_managers) <= 1:
        return []

    manager_ids = {
        employee.employee_id
        for employee in active_managers
    }

    counts = {
        employee.employee_id: 0
        for employee in active_managers
    }

    for assignment in assignments:
        if assignment.employee_id in manager_ids:
            counts[assignment.employee_id] += 1

    maximum = max(counts.values())
    minimum = min(counts.values())

    if maximum - minimum < warning_threshold:
        return []

    return [
        ValidationIssue(
            severity="warning",
            rule_id="WR-03",
            message=(
                "責任者の配置回数に偏りがあります。"
                f"最多{maximum}回、最少{minimum}回です。"
            ),
        )
    ]


def build_employee_schedule_summaries(
    assignments: list[ScheduleAssignment],
    employees: list[Employee],
) -> list[EmployeeScheduleSummary]:
    employee_dates: dict[str, set[date]] = defaultdict(set)
    shift_counts: dict[
        str,
        dict[str, int],
    ] = defaultdict(
        lambda: {
            "early": 0,
            "late": 0,
        }
    )

    for assignment in assignments:
        employee_dates[
            assignment.employee_id
        ].add(assignment.target_date)

        shift_counts[
            assignment.employee_id
        ][assignment.shift_type] += 1

    summaries: list[EmployeeScheduleSummary] = []

    for employee in employees:
        if not employee.is_active:
            continue

        work_dates = employee_dates.get(
            employee.employee_id,
            set(),
        )

        assigned_days = len(work_dates)

        summaries.append(
            EmployeeScheduleSummary(
                employee_id=employee.employee_id,
                employee_name=employee.name,
                contract_days=employee.contract_days,
                assigned_days=assigned_days,
                difference=(
                    assigned_days
                    - employee.contract_days
                ),
                early_count=shift_counts[
                    employee.employee_id
                ]["early"],
                late_count=shift_counts[
                    employee.employee_id
                ]["late"],
                max_consecutive_days=(
                    calculate_max_consecutive_days(
                        work_dates
                    )
                ),
                manager_assignment_count=(
                    assigned_days
                    if employee.is_manager
                    else 0
                ),
            )
        )

    return sorted(
        summaries,
        key=lambda summary: summary.employee_id,
    )


def validate_schedule(
    assignments: list[ScheduleAssignment],
    employees: list[Employee],
    day_off_requests: list[DayOffRequest],
    requirements: list[StaffingRequirement],
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []

    issues.extend(
        validate_one_shift_per_day(assignments)
    )
    issues.extend(
        validate_day_off_assignments(
            assignments,
            day_off_requests,
        )
    )
    issues.extend(
        validate_shift_eligibility(
            assignments,
            employees,
        )
    )
    issues.extend(
        validate_required_staff_counts(
            assignments,
            requirements,
        )
    )
    issues.extend(
        validate_required_manager_counts(
            assignments,
            employees,
            requirements,
        )
    )
    issues.extend(
        validate_weekly_work_limit(assignments)
    )
    issues.extend(
        validate_consecutive_work_limit(
            assignments
        )
    )
    issues.extend(
        validate_assigned_employees_active(
            assignments,
            employees,
        )
    )
    issues.extend(
        validate_contract_day_deviation(
            assignments,
            employees,
        )
    )
    issues.extend(
        validate_shift_balance(
            assignments,
            employees,
        )
    )
    issues.extend(
        validate_manager_assignment_balance(
            assignments,
            employees,
        )
    )

    return sorted(
        issues,
        key=lambda issue: (
            0 if issue.severity == "error" else 1,
            issue.target_date or date.max,
            issue.shift_type or "",
            issue.employee_id or "",
            issue.rule_id,
        ),
    )
