from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from src.models import DayOffRequest
from src.repositories import (
    create_day_off_request,
    delete_day_off_request,
    get_employee,
    list_day_off_requests,
)


@dataclass(frozen=True)
class DayOffOperationResult:
    succeeded: bool
    message: str
    request: DayOffRequest | None = None


def belongs_to_month(
    target_date: date,
    target_month: str,
) -> bool:
    return (
        target_date.strftime("%Y-%m")
        == target_month
    )


def validate_target_month(
    target_month: str,
) -> str | None:
    try:
        year_text, month_text = (
            target_month.split("-")
        )

        if (
            len(year_text) != 4
            or len(month_text) != 2
        ):
            raise ValueError

        year = int(year_text)
        month = int(month_text)

        date(year, month, 1)

    except (
        ValueError,
        AttributeError,
    ):
        return (
            "対象月はYYYY-MM形式で"
            "指定してください。"
        )

    return None


def register_day_off_request(
    *,
    employee_id: str,
    target_date: date,
    target_month: str,
) -> DayOffOperationResult:
    month_error = validate_target_month(
        target_month
    )

    if month_error is not None:
        return DayOffOperationResult(
            succeeded=False,
            message=month_error,
        )

    employee = get_employee(employee_id)

    if employee is None:
        return DayOffOperationResult(
            succeeded=False,
            message=(
                "対象の従業員が"
                "見つかりませんでした。"
            ),
        )

    if not employee.is_active:
        return DayOffOperationResult(
            succeeded=False,
            message=(
                "無効な従業員には"
                "希望休を登録できません。"
            ),
        )

    if not belongs_to_month(
        target_date,
        target_month,
    ):
        return DayOffOperationResult(
            succeeded=False,
            message=(
                "希望休の日付は対象月内で"
                "指定してください。"
            ),
        )

    existing_requests = (
        list_day_off_requests(
            target_month,
            employee_id=employee_id,
        )
    )

    already_exists = any(
        request.target_date == target_date
        for request in existing_requests
    )

    if already_exists:
        return DayOffOperationResult(
            succeeded=False,
            message=(
                f"{target_date:%Y年%m月%d日}の"
                "希望休は既に登録されています。"
            ),
        )

    request = DayOffRequest(
        employee_id=employee_id,
        target_date=target_date,
    )

    create_day_off_request(request)

    return DayOffOperationResult(
        succeeded=True,
        message=(
            f"{employee.name}さんの"
            f"{target_date:%Y年%m月%d日}の"
            "希望休を登録しました。"
        ),
        request=request,
    )


def remove_day_off_request(
    *,
    employee_id: str,
    target_date: date,
) -> DayOffOperationResult:
    employee = get_employee(employee_id)

    if employee is None:
        return DayOffOperationResult(
            succeeded=False,
            message=(
                "対象の従業員が"
                "見つかりませんでした。"
            ),
        )

    target_month = target_date.strftime(
        "%Y-%m"
    )

    existing_requests = (
        list_day_off_requests(
            target_month,
            employee_id=employee_id,
        )
    )

    exists = any(
        request.target_date == target_date
        for request in existing_requests
    )

    if not exists:
        return DayOffOperationResult(
            succeeded=False,
            message=(
                "削除対象の希望休が"
                "見つかりませんでした。"
            ),
        )

    deleted = delete_day_off_request(
        employee_id,
        target_date,
    )

    if not deleted:
        return DayOffOperationResult(
            succeeded=False,
            message=(
                "希望休を削除できませんでした。"
            ),
        )

    request = DayOffRequest(
        employee_id=employee_id,
        target_date=target_date,
    )

    return DayOffOperationResult(
        succeeded=True,
        message=(
            f"{employee.name}さんの"
            f"{target_date:%Y年%m月%d日}の"
            "希望休を削除しました。"
        ),
        request=request,
    )


@dataclass(frozen=True)
class EmployeeDayOffSummary:
    employee_id: str
    employee_name: str
    request_count: int


def get_day_off_summaries(
    target_month: str,
) -> list[EmployeeDayOffSummary]:
    requests = list_day_off_requests(
        target_month
    )

    request_counts: dict[str, int] = {}

    for request in requests:
        request_counts[request.employee_id] = (
            request_counts.get(
                request.employee_id,
                0,
            )
            + 1
        )

    summaries: list[
        EmployeeDayOffSummary
    ] = []

    for employee_id, request_count in sorted(
        request_counts.items()
    ):
        employee = get_employee(employee_id)

        employee_name = (
            employee.name
            if employee is not None
            else "不明な従業員"
        )

        summaries.append(
            EmployeeDayOffSummary(
                employee_id=employee_id,
                employee_name=employee_name,
                request_count=request_count,
            )
        )

    return summaries