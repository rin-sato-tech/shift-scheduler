from __future__ import annotations

from datetime import date

from src.day_off_service import (
    register_day_off_request,
    remove_day_off_request,
)
from src.models import Employee
from src.repositories import (
    create_employee,
    list_day_off_requests,
)


def create_test_employee(
    *,
    employee_id: str = "E001",
    is_active: bool = True,
) -> None:
    create_employee(
        Employee(
            employee_id=employee_id,
            name="山田太郎",
            is_manager=False,
            contract_days=15,
            can_work_early=True,
            can_work_late=True,
            is_active=is_active,
        )
    )


def test_register_day_off_request(
    initialized_test_db,
) -> None:
    create_test_employee()

    result = register_day_off_request(
        employee_id="E001",
        target_date=date(2026, 8, 10),
        target_month="2026-08",
    )

    assert result.succeeded is True
    assert result.request is not None

    requests = list_day_off_requests(
        "2026-08"
    )

    assert requests == [
        result.request
    ]


def test_register_day_off_rejects_duplicate(
    initialized_test_db,
) -> None:
    create_test_employee()

    first = register_day_off_request(
        employee_id="E001",
        target_date=date(2026, 8, 10),
        target_month="2026-08",
    )

    second = register_day_off_request(
        employee_id="E001",
        target_date=date(2026, 8, 10),
        target_month="2026-08",
    )

    assert first.succeeded is True
    assert second.succeeded is False
    assert "既に登録" in second.message

    requests = list_day_off_requests(
        "2026-08"
    )

    assert len(requests) == 1


def test_register_day_off_rejects_other_month(
    initialized_test_db,
) -> None:
    create_test_employee()

    result = register_day_off_request(
        employee_id="E001",
        target_date=date(2026, 9, 1),
        target_month="2026-08",
    )

    assert result.succeeded is False
    assert "対象月内" in result.message

    assert (
        list_day_off_requests("2026-08")
        == []
    )


def test_register_day_off_rejects_inactive_employee(
    initialized_test_db,
) -> None:
    create_test_employee(
        is_active=False
    )

    result = register_day_off_request(
        employee_id="E001",
        target_date=date(2026, 8, 10),
        target_month="2026-08",
    )

    assert result.succeeded is False
    assert "無効な従業員" in result.message


def test_register_day_off_rejects_missing_employee(
    initialized_test_db,
) -> None:
    result = register_day_off_request(
        employee_id="E999",
        target_date=date(2026, 8, 10),
        target_month="2026-08",
    )

    assert result.succeeded is False
    assert "見つかりません" in result.message


def test_remove_day_off_request(
    initialized_test_db,
) -> None:
    create_test_employee()

    register_day_off_request(
        employee_id="E001",
        target_date=date(2026, 8, 10),
        target_month="2026-08",
    )

    result = remove_day_off_request(
        employee_id="E001",
        target_date=date(2026, 8, 10),
    )

    assert result.succeeded is True

    assert (
        list_day_off_requests("2026-08")
        == []
    )


def test_remove_missing_day_off_request(
    initialized_test_db,
) -> None:
    create_test_employee()

    result = remove_day_off_request(
        employee_id="E001",
        target_date=date(2026, 8, 10),
    )

    assert result.succeeded is False
    assert "見つかりません" in result.message