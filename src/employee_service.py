from __future__ import annotations

from dataclasses import dataclass

from src.models import Employee
from src.repositories import (
    create_employee,
    get_employee,
    set_employee_active,
    update_employee,
)


@dataclass(frozen=True)
class EmployeeOperationResult:
    succeeded: bool
    message: str
    employee: Employee | None = None


import re


_EMPLOYEE_ID_PATTERN = re.compile(
    r"^[A-Za-z0-9_-]+$"
)


def normalize_employee_id(
    employee_id: str,
) -> str:
    return employee_id.strip()


def validate_employee_id(
    employee_id: str,
) -> str | None:
    normalized = normalize_employee_id(
        employee_id
    )

    if not normalized:
        return "従業員IDを入力してください。"

    if len(normalized) > 30:
        return (
            "従業員IDは30文字以内で"
            "入力してください。"
        )

    if not _EMPLOYEE_ID_PATTERN.fullmatch(
        normalized
    ):
        return (
            "従業員IDは半角英数字、"
            "ハイフン、アンダースコアのみ"
            "使用できます。"
        )

    return None


def normalize_employee_name(
    name: str,
) -> str:
    return name.strip()


def validate_employee_name(
    name: str,
) -> str | None:
    normalized = normalize_employee_name(name)

    if not normalized:
        return "従業員名を入力してください。"

    if len(normalized) > 50:
        return (
            "従業員名は50文字以内で"
            "入力してください。"
        )

    return None


def validate_contract_days(
    contract_days: int,
) -> str | None:
    if contract_days < 0:
        return (
            "契約勤務日数は0以上で"
            "入力してください。"
        )

    if contract_days > 31:
        return (
            "契約勤務日数は31以下で"
            "入力してください。"
        )

    return None


def register_employee(
    *,
    employee_id: str,
    name: str,
    is_manager: bool,
    contract_days: int,
    can_work_early: bool,
    can_work_late: bool,
) -> EmployeeOperationResult:
    normalized_id = normalize_employee_id(
        employee_id
    )
    normalized_name = normalize_employee_name(
        name
    )

    employee_id_error = validate_employee_id(
        normalized_id
    )
    if employee_id_error is not None:
        return EmployeeOperationResult(
            succeeded=False,
            message=employee_id_error,
        )

    name_error = validate_employee_name(
        normalized_name
    )
    if name_error is not None:
        return EmployeeOperationResult(
            succeeded=False,
            message=name_error,
        )

    contract_days_error = (
        validate_contract_days(contract_days)
    )
    if contract_days_error is not None:
        return EmployeeOperationResult(
            succeeded=False,
            message=contract_days_error,
        )

    if not (
        can_work_early
        or can_work_late
    ):
        return EmployeeOperationResult(
            succeeded=False,
            message=(
                "早番または遅番の少なくとも"
                "一方を勤務可能にしてください。"
            ),
        )

    if get_employee(normalized_id) is not None:
        return EmployeeOperationResult(
            succeeded=False,
            message=(
                f"従業員ID「{normalized_id}」は"
                "既に登録されています。"
            ),
        )

    employee = Employee(
        employee_id=normalized_id,
        name=normalized_name,
        is_manager=is_manager,
        contract_days=contract_days,
        can_work_early=can_work_early,
        can_work_late=can_work_late,
        is_active=True,
    )

    create_employee(employee)

    return EmployeeOperationResult(
        succeeded=True,
        message=(
            f"従業員「{normalized_name}」を"
            "登録しました。"
        ),
        employee=employee,
    )


def edit_employee(
    *,
    employee_id: str,
    name: str,
    is_manager: bool,
    contract_days: int,
    can_work_early: bool,
    can_work_late: bool,
) -> EmployeeOperationResult:
    existing = get_employee(employee_id)

    if existing is None:
        return EmployeeOperationResult(
            succeeded=False,
            message=(
                "対象の従業員が"
                "見つかりませんでした。"
            ),
        )

    normalized_name = normalize_employee_name(
        name
    )

    name_error = validate_employee_name(
        normalized_name
    )
    if name_error is not None:
        return EmployeeOperationResult(
            succeeded=False,
            message=name_error,
        )

    contract_days_error = (
        validate_contract_days(contract_days)
    )
    if contract_days_error is not None:
        return EmployeeOperationResult(
            succeeded=False,
            message=contract_days_error,
        )

    if not (
        can_work_early
        or can_work_late
    ):
        return EmployeeOperationResult(
            succeeded=False,
            message=(
                "早番または遅番の少なくとも"
                "一方を勤務可能にしてください。"
            ),
        )

    updated_employee = Employee(
        employee_id=existing.employee_id,
        name=normalized_name,
        is_manager=is_manager,
        contract_days=contract_days,
        can_work_early=can_work_early,
        can_work_late=can_work_late,
        is_active=existing.is_active,
    )

    updated = update_employee(
        updated_employee
    )

    if not updated:
        return EmployeeOperationResult(
            succeeded=False,
            message=(
                "従業員情報を更新できませんでした。"
            ),
        )

    return EmployeeOperationResult(
        succeeded=True,
        message=(
            f"従業員「{normalized_name}」の"
            "情報を更新しました。"
        ),
        employee=updated_employee,
    )


def change_employee_active_status(
    *,
    employee_id: str,
    is_active: bool,
) -> EmployeeOperationResult:
    employee = get_employee(employee_id)

    if employee is None:
        return EmployeeOperationResult(
            succeeded=False,
            message=(
                "対象の従業員が"
                "見つかりませんでした。"
            ),
        )

    if employee.is_active == is_active:
        status_label = (
            "有効"
            if is_active
            else "無効"
        )

        return EmployeeOperationResult(
            succeeded=True,
            message=(
                f"従業員「{employee.name}」は"
                f"既に{status_label}です。"
            ),
            employee=employee,
        )

    updated = set_employee_active(
        employee_id,
        is_active=is_active,
    )

    if not updated:
        return EmployeeOperationResult(
            succeeded=False,
            message=(
                "有効状態を変更できませんでした。"
            ),
        )

    updated_employee = Employee(
        employee_id=employee.employee_id,
        name=employee.name,
        is_manager=employee.is_manager,
        contract_days=employee.contract_days,
        can_work_early=employee.can_work_early,
        can_work_late=employee.can_work_late,
        is_active=is_active,
    )

    status_label = (
        "有効"
        if is_active
        else "無効"
    )

    return EmployeeOperationResult(
        succeeded=True,
        message=(
            f"従業員「{employee.name}」を"
            f"{status_label}に変更しました。"
        ),
        employee=updated_employee,
    )
