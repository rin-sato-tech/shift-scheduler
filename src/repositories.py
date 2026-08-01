from __future__ import annotations

import sqlite3
from datetime import date, datetime
from typing import Iterable

from src.db import get_connection
from src.models import (
    DayOffRequest,
    Employee,
    ScheduleAssignment,
    StaffingRequirement,
)


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


# 月初・翌月月初を求める
def _month_bounds(target_month: str) -> tuple[date, date]:
    try:
        year_text, month_text = target_month.split("-")
        year = int(year_text)
        month = int(month_text)
        start_date = date(year, month, 1)
    except (ValueError, AttributeError) as exc:
        raise ValueError(
            "target_month must be in YYYY-MM format"
        ) from exc

    if month == 12:
        next_month = date(year + 1, 1, 1)
    else:
        next_month = date(year, month + 1, 1)

    return start_date, next_month


# DBレコードからモデルへ変換
def _row_to_employee(row: sqlite3.Row) -> Employee:
    return Employee(
        employee_id=row["employee_id"],
        name=row["name"],
        is_manager=bool(row["is_manager"]),
        contract_days=row["contract_days"],
        can_work_early=bool(row["can_work_early"]),
        can_work_late=bool(row["can_work_late"]),
        is_active=bool(row["is_active"]),
    )


def _row_to_day_off_request(
    row: sqlite3.Row,
) -> DayOffRequest:
    return DayOffRequest(
        employee_id=row["employee_id"],
        target_date=date.fromisoformat(row["target_date"]),
    )


def _row_to_staffing_requirement(
    row: sqlite3.Row,
) -> StaffingRequirement:
    return StaffingRequirement(
        target_date=date.fromisoformat(row["target_date"]),
        shift_type=row["shift_type"],
        required_count=row["required_count"],
        required_manager_count=row[
            "required_manager_count"
        ],
    )


def _row_to_schedule_assignment(
    row: sqlite3.Row,
) -> ScheduleAssignment:
    return ScheduleAssignment(
        target_date=date.fromisoformat(row["target_date"]),
        shift_type=row["shift_type"],
        employee_id=row["employee_id"],
        is_manual=bool(row["is_manual"]),
    )


# 従業員の登録処理
def create_employee(employee: Employee) -> None:
    now = _now_iso()

    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO employees (
                employee_id,
                name,
                is_manager,
                contract_days,
                can_work_early,
                can_work_late,
                is_active,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                employee.employee_id,
                employee.name,
                int(employee.is_manager),
                employee.contract_days,
                int(employee.can_work_early),
                int(employee.can_work_late),
                int(employee.is_active),
                now,
                now,
            ),
        )


# 従業員の取得処理
def get_employee(
    employee_id: str,
) -> Employee | None:
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT
                employee_id,
                name,
                is_manager,
                contract_days,
                can_work_early,
                can_work_late,
                is_active
            FROM employees
            WHERE employee_id = ?
            """,
            (employee_id,),
        ).fetchone()

    if row is None:
        return None

    return _row_to_employee(row)


def list_employees(
    *,
    active_only: bool = False,
) -> list[Employee]:
    query = """
        SELECT
            employee_id,
            name,
            is_manager,
            contract_days,
            can_work_early,
            can_work_late,
            is_active
        FROM employees
    """

    parameters: tuple[object, ...] = ()

    if active_only:
        query += " WHERE is_active = ?"
        parameters = (1,)

    query += " ORDER BY employee_id"

    with get_connection() as connection:
        rows = connection.execute(
            query,
            parameters,
        ).fetchall()

    return [_row_to_employee(row) for row in rows]


# 従業員の更新処理
def update_employee(employee: Employee) -> bool:
    now = _now_iso()

    with get_connection() as connection:
        cursor = connection.execute(
            """
            UPDATE employees
            SET
                name = ?,
                is_manager = ?,
                contract_days = ?,
                can_work_early = ?,
                can_work_late = ?,
                is_active = ?,
                updated_at = ?
            WHERE employee_id = ?
            """,
            (
                employee.name,
                int(employee.is_manager),
                employee.contract_days,
                int(employee.can_work_early),
                int(employee.can_work_late),
                int(employee.is_active),
                now,
                employee.employee_id,
            ),
        )

    return cursor.rowcount > 0


# 従業員の有効・無効を変更
def set_employee_active(
    employee_id: str,
    *,
    is_active: bool,
) -> bool:
    now = _now_iso()

    with get_connection() as connection:
        cursor = connection.execute(
            """
            UPDATE employees
            SET
                is_active = ?,
                updated_at = ?
            WHERE employee_id = ?
            """,
            (
                int(is_active),
                now,
                employee_id,
            ),
        )

    return cursor.rowcount > 0


# 希望休の登録処理
def create_day_off_request(
    request: DayOffRequest,
) -> None:
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO day_off_requests (
                employee_id,
                target_date,
                created_at
            )
            VALUES (?, ?, ?)
            """,
            (
                request.employee_id,
                request.target_date.isoformat(),
                _now_iso(),
            ),
        )


# 希望休の取得処理
def list_day_off_requests(
    target_month: str,
    *,
    employee_id: str | None = None,
) -> list[DayOffRequest]:
    start_date, next_month = _month_bounds(target_month)

    query = """
        SELECT
            employee_id,
            target_date
        FROM day_off_requests
        WHERE target_date >= ?
          AND target_date < ?
    """

    parameters: list[object] = [
        start_date.isoformat(),
        next_month.isoformat(),
    ]

    if employee_id is not None:
        query += " AND employee_id = ?"
        parameters.append(employee_id)

    query += " ORDER BY target_date, employee_id"

    with get_connection() as connection:
        rows = connection.execute(
            query,
            parameters,
        ).fetchall()

    return [
        _row_to_day_off_request(row)
        for row in rows
    ]


# 希望休の削除処理
def delete_day_off_request(
    employee_id: str,
    target_date: date,
) -> bool:
    with get_connection() as connection:
        cursor = connection.execute(
            """
            DELETE FROM day_off_requests
            WHERE employee_id = ?
              AND target_date = ?
            """,
            (
                employee_id,
                target_date.isoformat(),
            ),
        )

    return cursor.rowcount > 0


# 必要人数の登録・更新処理
def upsert_staffing_requirement(
    requirement: StaffingRequirement,
) -> None:
    now = _now_iso()

    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO staffing_requirements (
                target_date,
                shift_type,
                required_count,
                required_manager_count,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(target_date, shift_type)
            DO UPDATE SET
                required_count = excluded.required_count,
                required_manager_count =
                    excluded.required_manager_count,
                updated_at = excluded.updated_at
            """,
            (
                requirement.target_date.isoformat(),
                requirement.shift_type,
                requirement.required_count,
                requirement.required_manager_count,
                now,
                now,
            ),
        )


# 必要人数の月別取得処理
def list_staffing_requirements(
    target_month: str,
) -> list[StaffingRequirement]:
    start_date, next_month = _month_bounds(target_month)

    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT
                target_date,
                shift_type,
                required_count,
                required_manager_count
            FROM staffing_requirements
            WHERE target_date >= ?
              AND target_date < ?
            ORDER BY
                target_date,
                CASE shift_type
                    WHEN 'early' THEN 1
                    WHEN 'late' THEN 2
                END
            """,
            (
                start_date.isoformat(),
                next_month.isoformat(),
            ),
        ).fetchall()

    return [
        _row_to_staffing_requirement(row)
        for row in rows
    ]


# 1か月分の必要人数を一括登録
def upsert_staffing_requirements(
    requirements: Iterable[StaffingRequirement],
) -> None:
    now = _now_iso()

    values = [
        (
            requirement.target_date.isoformat(),
            requirement.shift_type,
            requirement.required_count,
            requirement.required_manager_count,
            now,
            now,
        )
        for requirement in requirements
    ]

    if not values:
        return

    with get_connection() as connection:
        connection.executemany(
            """
            INSERT INTO staffing_requirements (
                target_date,
                shift_type,
                required_count,
                required_manager_count,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(target_date, shift_type)
            DO UPDATE SET
                required_count = excluded.required_count,
                required_manager_count =
                    excluded.required_manager_count,
                updated_at = excluded.updated_at
            """,
            values,
        )


# シフト生成履歴を登録
def create_schedule_generation(
    *,
    target_month: str,
    solver_status: str,
    objective_value: int | None = None,
    max_deviation: int | None = None,
    total_deviation: int | None = None,
) -> int:
    _month_bounds(target_month)

    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO schedule_generations (
                target_month,
                solver_status,
                objective_value,
                max_deviation,
                total_deviation,
                generated_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                target_month,
                solver_status,
                objective_value,
                max_deviation,
                total_deviation,
                _now_iso(),
            ),
        )

        generation_id = cursor.lastrowid

    if generation_id is None:
        raise RuntimeError(
            "Failed to create schedule generation"
        )

    return generation_id


# シフト配置を取得
def list_schedule_assignments(
    target_month: str,
) -> list[ScheduleAssignment]:
    start_date, next_month = _month_bounds(target_month)

    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT
                target_date,
                shift_type,
                employee_id,
                is_manual
            FROM schedules
            WHERE target_date >= ?
              AND target_date < ?
            ORDER BY
                target_date,
                CASE shift_type
                    WHEN 'early' THEN 1
                    WHEN 'late' THEN 2
                END,
                employee_id
            """,
            (
                start_date.isoformat(),
                next_month.isoformat(),
            ),
        ).fetchall()

    return [
        _row_to_schedule_assignment(row)
        for row in rows
    ]


# シフト配置を1件追加
def create_schedule_assignment(
    assignment: ScheduleAssignment,
    *,
    generation_id: int | None = None,
) -> None:
    now = _now_iso()

    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO schedules (
                generation_id,
                target_date,
                shift_type,
                employee_id,
                is_manual,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                generation_id,
                assignment.target_date.isoformat(),
                assignment.shift_type,
                assignment.employee_id,
                int(assignment.is_manual),
                now,
                now,
            ),
        )


# シフト配置を削除
def delete_schedule_assignment(
    target_date: date,
    employee_id: str,
) -> bool:
    with get_connection() as connection:
        cursor = connection.execute(
            """
            DELETE FROM schedules
            WHERE target_date = ?
              AND employee_id = ?
            """,
            (
                target_date.isoformat(),
                employee_id,
            ),
        )

    return cursor.rowcount > 0


# 対象月のシフトを一括置換
def replace_month_schedule_assignments(
    target_month: str,
    assignments: Iterable[ScheduleAssignment],
    *,
    generation_id: int | None = None,
) -> None:
    start_date, next_month = _month_bounds(target_month)
    now = _now_iso()

    assignment_list = list(assignments)

    for assignment in assignment_list:
        if not (
            start_date
            <= assignment.target_date
            < next_month
        ):
            raise ValueError(
                "All assignments must belong "
                "to the target month"
            )

    values = [
        (
            generation_id,
            assignment.target_date.isoformat(),
            assignment.shift_type,
            assignment.employee_id,
            int(assignment.is_manual),
            now,
            now,
        )
        for assignment in assignment_list
    ]

    with get_connection() as connection:
        connection.execute(
            """
            DELETE FROM schedules
            WHERE target_date >= ?
              AND target_date < ?
            """,
            (
                start_date.isoformat(),
                next_month.isoformat(),
            ),
        )

        connection.executemany(
            """
            INSERT INTO schedules (
                generation_id,
                target_date,
                shift_type,
                employee_id,
                is_manual,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            values,
        )


# 対象月のシフトを全削除
def delete_month_schedule_assignments(
    target_month: str,
) -> int:
    start_date, next_month = _month_bounds(target_month)

    with get_connection() as connection:
        cursor = connection.execute(
            """
            DELETE FROM schedules
            WHERE target_date >= ?
              AND target_date < ?
            """,
            (
                start_date.isoformat(),
                next_month.isoformat(),
            ),
        )

    return cursor.rowcount
