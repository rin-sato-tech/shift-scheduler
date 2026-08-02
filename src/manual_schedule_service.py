from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal

from src.models import (
    ScheduleAssignment,
    ValidationIssue,
)
from src.repositories import (
    get_month_schedule_generation_id,
    list_day_off_requests,
    list_employees,
    list_schedule_assignments,
    list_staffing_requirements,
    replace_month_schedule_assignments,
)
from src.validation import (
    has_errors,
    validate_schedule,
)


ManualShiftChoice = Literal[
    "early",
    "late",
    "off",
]


@dataclass(frozen=True)
class ManualScheduleResult:
    succeeded: bool
    message: str
    assignments: tuple[
        ScheduleAssignment, ...
    ]
    validation_issues: tuple[
        ValidationIssue, ...
    ] = ()


def belongs_to_month(
    target_date: date,
    target_month: str,
) -> bool:
    return (
        target_date.strftime("%Y-%m")
        == target_month
    )


def find_assignment(
    assignments: list[ScheduleAssignment],
    *,
    employee_id: str,
    target_date: date,
) -> ScheduleAssignment | None:
    return next(
        (
            assignment
            for assignment in assignments
            if (
                assignment.employee_id
                == employee_id
                and assignment.target_date
                == target_date
            )
        ),
        None,
    )


def get_shift_label(
    shift: ManualShiftChoice,
) -> str:
    labels = {
        "early": "早番",
        "late": "遅番",
        "off": "休み",
    }

    return labels[shift]


def apply_manual_change(
    *,
    target_month: str,
    assignments: list[ScheduleAssignment],
    employee_id: str,
    target_date: date,
    new_shift: ManualShiftChoice,
) -> ManualScheduleResult:
    if not belongs_to_month(
        target_date,
        target_month,
    ):
        return ManualScheduleResult(
            succeeded=False,
            message=(
                "変更対象の日付は"
                "対象月内で指定してください。"
            ),
            assignments=tuple(assignments),
        )

    employees = list_employees()

    employee = next(
        (
            employee
            for employee in employees
            if (
                employee.employee_id
                == employee_id
            )
        ),
        None,
    )

    if employee is None:
        return ManualScheduleResult(
            succeeded=False,
            message=(
                "対象の従業員が"
                "見つかりませんでした。"
            ),
            assignments=tuple(assignments),
        )

    if not employee.is_active:
        return ManualScheduleResult(
            succeeded=False,
            message=(
                "無効な従業員を"
                "新たに配置できません。"
            ),
            assignments=tuple(assignments),
        )

    if (
        new_shift == "early"
        and not employee.can_work_early
    ):
        return ManualScheduleResult(
            succeeded=False,
            message=(
                f"{employee.name}さんは"
                "早番勤務不可です。"
            ),
            assignments=tuple(assignments),
        )

    if (
        new_shift == "late"
        and not employee.can_work_late
    ):
        return ManualScheduleResult(
            succeeded=False,
            message=(
                f"{employee.name}さんは"
                "遅番勤務不可です。"
            ),
            assignments=tuple(assignments),
        )

    updated_assignments = [
        assignment
        for assignment in assignments
        if not (
            assignment.employee_id
            == employee_id
            and assignment.target_date
            == target_date
        )
    ]

    if new_shift != "off":
        updated_assignments.append(
            ScheduleAssignment(
                target_date=target_date,
                shift_type=new_shift,
                employee_id=employee_id,
                is_manual=True,
            )
        )

    shift_order = {
        "early": 0,
        "late": 1,
    }

    updated_assignments.sort(
        key=lambda assignment: (
            assignment.target_date,
            shift_order[
                assignment.shift_type
            ],
            assignment.employee_id,
        )
    )

    return ManualScheduleResult(
        succeeded=True,
        message=(
            f"{employee.name}さんの"
            f"{target_date:%Y年%m月%d日}を"
            f"{get_shift_label(new_shift)}に"
            "変更しました。"
        ),
        assignments=tuple(
            updated_assignments
        ),
    )


def validate_manual_schedule(
    *,
    target_month: str,
    assignments: list[
        ScheduleAssignment
    ],
) -> list[ValidationIssue]:
    employees = list_employees()

    day_off_requests = (
        list_day_off_requests(
            target_month
        )
    )

    requirements = (
        list_staffing_requirements(
            target_month
        )
    )

    return validate_schedule(
        assignments,
        employees,
        day_off_requests,
        requirements,
    )


def save_manual_schedule(
    *,
    target_month: str,
    assignments: list[
        ScheduleAssignment
    ],
) -> ManualScheduleResult:
    existing_assignments = (
        list_schedule_assignments(
            target_month
        )
    )

    if not existing_assignments:
        return ManualScheduleResult(
            succeeded=False,
            message=(
                "対象月のシフトが"
                "生成されていません。"
            ),
            assignments=tuple(assignments),
        )

    current_assignments = (
        list_schedule_assignments(
            target_month
        )
    )

    if not current_assignments:
        return ManualScheduleResult(
            succeeded=False,
            message=(
                "保存済みシフトが"
                "見つかりませんでした。"
            ),
            assignments=tuple(assignments),
        )

    issues = validate_manual_schedule(
        target_month=target_month,
        assignments=assignments,
    )

    if has_errors(issues):
        return ManualScheduleResult(
            succeeded=False,
            message=(
                "ハード制約違反があるため"
                "保存できません。"
            ),
            assignments=tuple(assignments),
            validation_issues=tuple(issues),
        )

    generation_id = (
        get_month_schedule_generation_id(
            target_month
        )
    )

    replace_month_schedule_assignments(
        target_month,
        assignments,
        generation_id=generation_id,
    )

    return ManualScheduleResult(
        succeeded=True,
        message=(
            f"{target_month}の"
            "手動変更を保存しました。"
        ),
        assignments=tuple(assignments),
        validation_issues=tuple(issues),
    )
