from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date
from typing import Iterable

from src.models import StaffingRequirement
from src.repositories import (
    list_staffing_requirements,
    upsert_staffing_requirements,
)


SHIFT_TYPES = ("early", "late")


@dataclass(frozen=True)
class StaffingOperationResult:
    succeeded: bool
    message: str
    requirements: tuple[
        StaffingRequirement, ...
    ] = ()


def parse_target_month(
    target_month: str,
) -> tuple[int, int]:
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
    ) as exc:
        raise ValueError(
            "target_month must be "
            "in YYYY-MM format"
        ) from exc

    return year, month


def get_month_dates(
    target_month: str,
) -> list[date]:
    year, month = parse_target_month(
        target_month
    )

    last_day = calendar.monthrange(
        year,
        month,
    )[1]

    return [
        date(year, month, day)
        for day in range(
            1,
            last_day + 1,
        )
    ]


def build_default_requirements(
    target_month: str,
    *,
    required_count: int = 2,
    required_manager_count: int = 1,
) -> list[StaffingRequirement]:
    return [
        StaffingRequirement(
            target_date=target_date,
            shift_type=shift_type,
            required_count=required_count,
            required_manager_count=(
                required_manager_count
            ),
        )
        for target_date in get_month_dates(
            target_month
        )
        for shift_type in SHIFT_TYPES
    ]


def get_complete_month_requirements(
    target_month: str,
) -> list[StaffingRequirement]:
    existing = list_staffing_requirements(
        target_month
    )

    existing_map = {
        (
            requirement.target_date,
            requirement.shift_type,
        ): requirement
        for requirement in existing
    }

    defaults = build_default_requirements(
        target_month
    )

    return [
        existing_map.get(
            (
                requirement.target_date,
                requirement.shift_type,
            ),
            requirement,
        )
        for requirement in defaults
    ]


def validate_staffing_requirements(
    target_month: str,
    requirements: Iterable[
        StaffingRequirement
    ],
) -> list[str]:
    requirement_list = list(requirements)
    month_dates = set(
        get_month_dates(target_month)
    )

    errors: list[str] = []
    seen_keys: set[
        tuple[date, str]
    ] = set()

    for requirement in requirement_list:
        key = (
            requirement.target_date,
            requirement.shift_type,
        )

        if key in seen_keys:
            errors.append(
                f"{requirement.target_date}"
                f"・{requirement.shift_type}が"
                "重複しています。"
            )

        seen_keys.add(key)

        if (
            requirement.target_date
            not in month_dates
        ):
            errors.append(
                f"{requirement.target_date}は"
                "対象月外です。"
            )

        if (
            requirement.shift_type
            not in SHIFT_TYPES
        ):
            errors.append(
                f"不正なシフト種別です："
                f"{requirement.shift_type}"
            )

        if requirement.required_count < 0:
            errors.append(
                f"{requirement.target_date}・"
                f"{requirement.shift_type}の"
                "必要人数は0以上にしてください。"
            )

        if (
            requirement.required_manager_count
            < 0
        ):
            errors.append(
                f"{requirement.target_date}・"
                f"{requirement.shift_type}の"
                "必要責任者数は0以上に"
                "してください。"
            )

        if (
            requirement.required_manager_count
            > requirement.required_count
        ):
            errors.append(
                f"{requirement.target_date}・"
                f"{requirement.shift_type}で、"
                "必要責任者数が必要人数を"
                "超えています。"
            )

    expected_keys = {
        (
            target_date,
            shift_type,
        )
        for target_date in month_dates
        for shift_type in SHIFT_TYPES
    }

    missing_keys = (
        expected_keys - seen_keys
    )

    if missing_keys:
        errors.append(
            f"{len(missing_keys)}件の"
            "必要人数設定が不足しています。"
        )

    return errors


def save_month_staffing_requirements(
    *,
    target_month: str,
    requirements: Iterable[
        StaffingRequirement
    ],
) -> StaffingOperationResult:
    requirement_list = list(
        requirements
    )

    try:
        errors = (
            validate_staffing_requirements(
                target_month,
                requirement_list,
            )
        )
    except ValueError as exc:
        return StaffingOperationResult(
            succeeded=False,
            message=str(exc),
        )

    if errors:
        return StaffingOperationResult(
            succeeded=False,
            message="\n".join(errors),
        )

    upsert_staffing_requirements(
        requirement_list
    )

    return StaffingOperationResult(
        succeeded=True,
        message=(
            f"{target_month}の必要人数設定を"
            "保存しました。"
        ),
        requirements=tuple(
            requirement_list
        ),
    )