from __future__ import annotations

from datetime import date

from src.models import StaffingRequirement
from src.repositories import (
    list_staffing_requirements,
)
from src.staffing_service import (
    build_default_requirements,
    get_complete_month_requirements,
    get_month_dates,
    save_month_staffing_requirements,
    validate_staffing_requirements,
)

def test_get_month_dates() -> None:
    dates = get_month_dates("2026-02")

    assert len(dates) == 28
    assert dates[0] == date(2026, 2, 1)
    assert dates[-1] == date(
        2026,
        2,
        28,
    )


def test_get_month_dates_in_leap_year() -> None:
    dates = get_month_dates("2028-02")

    assert len(dates) == 29
    assert dates[-1] == date(
        2028,
        2,
        29,
    )


def test_build_default_requirements() -> None:
    requirements = (
        build_default_requirements(
            "2026-08"
        )
    )

    assert len(requirements) == 62

    assert all(
        requirement.required_count == 2
        for requirement in requirements
    )

    assert all(
        (
            requirement
            .required_manager_count
            == 1
        )
        for requirement in requirements
    )


def test_save_month_staffing_requirements(
    initialized_test_db,
) -> None:
    requirements = (
        build_default_requirements(
            "2026-08"
        )
    )

    result = (
        save_month_staffing_requirements(
            target_month="2026-08",
            requirements=requirements,
        )
    )

    assert result.succeeded is True

    saved = list_staffing_requirements(
        "2026-08"
    )

    assert len(saved) == 62
    assert saved == requirements


def test_rejects_manager_count_over_total(
    initialized_test_db,
) -> None:
    requirements = (
        build_default_requirements(
            "2026-08"
        )
    )

    requirements[0] = (
        StaffingRequirement(
            target_date=date(
                2026,
                8,
                1,
            ),
            shift_type="early",
            required_count=1,
            required_manager_count=2,
        )
    )

    result = (
        save_month_staffing_requirements(
            target_month="2026-08",
            requirements=requirements,
        )
    )

    assert result.succeeded is False
    assert (
        "必要人数を超えています"
        in result.message
    )


def test_rejects_missing_requirements(
    initialized_test_db,
) -> None:
    requirements = (
        build_default_requirements(
            "2026-08"
        )
    )

    result = (
        save_month_staffing_requirements(
            target_month="2026-08",
            requirements=requirements[:-1],
        )
    )

    assert result.succeeded is False
    assert "不足しています" in result.message


def test_rejects_other_month(
    initialized_test_db,
) -> None:
    requirements = (
        build_default_requirements(
            "2026-08"
        )
    )

    requirements[0] = (
        StaffingRequirement(
            target_date=date(
                2026,
                9,
                1,
            ),
            shift_type="early",
            required_count=2,
            required_manager_count=1,
        )
    )

    result = (
        save_month_staffing_requirements(
            target_month="2026-08",
            requirements=requirements,
        )
    )

    assert result.succeeded is False
    assert "対象月外" in result.message


def test_complete_requirements_use_existing_values(
    initialized_test_db,
) -> None:
    custom = StaffingRequirement(
        target_date=date(
            2026,
            8,
            1,
        ),
        shift_type="early",
        required_count=3,
        required_manager_count=2,
    )

    save_month_staffing_requirements(
        target_month="2026-08",
        requirements=[
            custom,
            *build_default_requirements(
                "2026-08"
            )[1:],
        ],
    )

    requirements = (
        get_complete_month_requirements(
            "2026-08"
        )
    )

    assert requirements[0] == custom
    assert len(requirements) == 62