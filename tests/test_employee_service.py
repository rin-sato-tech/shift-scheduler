from __future__ import annotations

from src.employee_service import (
    change_employee_active_status,
    edit_employee,
    register_employee,
)
from src.repositories import get_employee


def test_register_employee(
    initialized_test_db,
) -> None:
    result = register_employee(
        employee_id="E001",
        name="山田太郎",
        is_manager=True,
        contract_days=20,
        can_work_early=True,
        can_work_late=True,
    )

    assert result.succeeded is True
    assert result.employee is not None

    saved = get_employee("E001")

    assert saved is not None
    assert saved.name == "山田太郎"
    assert saved.is_manager is True
    assert saved.contract_days == 20
    assert saved.is_active is True


def test_register_employee_strips_text(
    initialized_test_db,
) -> None:
    result = register_employee(
        employee_id="  E001  ",
        name="  山田太郎  ",
        is_manager=False,
        contract_days=15,
        can_work_early=True,
        can_work_late=False,
    )

    assert result.succeeded is True

    saved = get_employee("E001")

    assert saved is not None
    assert saved.name == "山田太郎"


def test_register_employee_rejects_duplicate_id(
    initialized_test_db,
) -> None:
    first = register_employee(
        employee_id="E001",
        name="山田太郎",
        is_manager=False,
        contract_days=15,
        can_work_early=True,
        can_work_late=True,
    )

    second = register_employee(
        employee_id="E001",
        name="佐藤花子",
        is_manager=False,
        contract_days=15,
        can_work_early=True,
        can_work_late=True,
    )

    assert first.succeeded is True
    assert second.succeeded is False
    assert "既に登録" in second.message


def test_register_employee_requires_shift(
    initialized_test_db,
) -> None:
    result = register_employee(
        employee_id="E001",
        name="山田太郎",
        is_manager=False,
        contract_days=15,
        can_work_early=False,
        can_work_late=False,
    )

    assert result.succeeded is False
    assert "少なくとも一方" in result.message


def test_edit_employee(
    initialized_test_db,
) -> None:
    register_employee(
        employee_id="E001",
        name="山田太郎",
        is_manager=False,
        contract_days=15,
        can_work_early=True,
        can_work_late=True,
    )

    result = edit_employee(
        employee_id="E001",
        name="山田一郎",
        is_manager=True,
        contract_days=20,
        can_work_early=True,
        can_work_late=False,
    )

    assert result.succeeded is True

    saved = get_employee("E001")

    assert saved is not None
    assert saved.name == "山田一郎"
    assert saved.is_manager is True
    assert saved.contract_days == 20
    assert saved.can_work_late is False


def test_deactivate_employee(
    initialized_test_db,
) -> None:
    register_employee(
        employee_id="E001",
        name="山田太郎",
        is_manager=False,
        contract_days=15,
        can_work_early=True,
        can_work_late=True,
    )

    result = change_employee_active_status(
        employee_id="E001",
        is_active=False,
    )

    assert result.succeeded is True

    saved = get_employee("E001")

    assert saved is not None
    assert saved.is_active is False