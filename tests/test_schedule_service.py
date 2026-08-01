from __future__ import annotations

import calendar
from datetime import date

from src.db import get_connection
from src.models import (
    Employee,
    StaffingRequirement,
)
from src.repositories import (
    create_employee,
    list_schedule_assignments,
    upsert_staffing_requirements,
)
from src.schedule_service import (
    generate_month_schedule,
)
from src.validation import has_errors


TARGET_MONTH = "2026-08"


def make_employee(
    employee_id: str,
    *,
    is_manager: bool = False,
    contract_days: int = 16,
    can_work_early: bool = True,
    can_work_late: bool = True,
    is_active: bool = True,
) -> Employee:
    """テスト用従業員を作成する。"""

    return Employee(
        employee_id=employee_id,
        name=f"従業員{employee_id}",
        is_manager=is_manager,
        contract_days=contract_days,
        can_work_early=can_work_early,
        can_work_late=can_work_late,
        is_active=is_active,
    )


def make_month_requirements(
    year: int,
    month: int,
    *,
    required_count: int = 1,
    required_manager_count: int = 0,
) -> list[StaffingRequirement]:
    """対象月の早番・遅番の必要人数を作成する。"""

    last_day = calendar.monthrange(
        year,
        month,
    )[1]

    return [
        StaffingRequirement(
            target_date=date(year, month, day),
            shift_type=shift_type,
            required_count=required_count,
            required_manager_count=required_manager_count,
        )
        for day in range(1, last_day + 1)
        for shift_type in ("early", "late")
    ]


def register_basic_employees() -> list[Employee]:
    """生成可能な基本従業員データをDBへ登録する。"""

    employees = [
        make_employee(
            "E001",
            is_manager=True,
        ),
        make_employee(
            "E002",
            is_manager=True,
        ),
        make_employee("E003"),
        make_employee("E004"),
    ]

    for employee in employees:
        create_employee(employee)

    return employees


def register_month_requirements() -> list[StaffingRequirement]:
    """2026年8月の必要人数をDBへ登録する。"""

    requirements = make_month_requirements(
        2026,
        8,
        required_count=1,
        required_manager_count=0,
    )

    upsert_staffing_requirements(requirements)

    return requirements


def test_generate_month_schedule_succeeds(
    initialized_test_db,
) -> None:
    """入力が正常なら月間シフトを生成・保存できる。"""

    register_basic_employees()
    requirements = register_month_requirements()

    result = generate_month_schedule(
        TARGET_MONTH,
        max_time_seconds=3,
        num_search_workers=1,
    )

    assert result.generated is True
    assert result.generation_id is not None
    assert result.solver_result is not None

    assert result.solver_result.status in {
        "OPTIMAL",
        "FEASIBLE",
    }

    assert not has_errors(
        list(result.validation_issues)
    )

    assignments = list_schedule_assignments(
        TARGET_MONTH
    )

    expected_assignment_count = sum(
        requirement.required_count
        for requirement in requirements
    )

    assert len(assignments) == expected_assignment_count
    assert len(assignments) == 62


def test_generated_assignments_are_not_manual(
    initialized_test_db,
) -> None:
    """自動生成された配置の手動変更フラグはFalseになる。"""

    register_basic_employees()
    register_month_requirements()

    result = generate_month_schedule(
        TARGET_MONTH,
        max_time_seconds=3,
        num_search_workers=1,
    )

    assert result.generated is True

    assignments = list_schedule_assignments(
        TARGET_MONTH
    )

    assert assignments
    assert all(
        assignment.is_manual is False
        for assignment in assignments
    )


def test_generation_history_is_saved(
    initialized_test_db,
) -> None:
    """生成成功時に生成履歴が保存される。"""

    register_basic_employees()
    register_month_requirements()

    result = generate_month_schedule(
        TARGET_MONTH,
        max_time_seconds=3,
        num_search_workers=1,
    )

    assert result.generated is True
    assert result.generation_id is not None

    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT
                generation_id,
                target_month,
                solver_status,
                objective_value,
                max_deviation,
                total_deviation
            FROM schedule_generations
            WHERE generation_id = ?
            """,
            (result.generation_id,),
        ).fetchone()

    assert row is not None
    assert row["target_month"] == TARGET_MONTH
    assert row["solver_status"] in {
        "OPTIMAL",
        "FEASIBLE",
    }
    assert row["objective_value"] is not None
    assert row["max_deviation"] is not None
    assert row["total_deviation"] is not None


def test_saved_assignments_reference_generation(
    initialized_test_db,
) -> None:
    """保存された全シフトが生成履歴に関連付く。"""

    register_basic_employees()
    register_month_requirements()

    result = generate_month_schedule(
        TARGET_MONTH,
        max_time_seconds=3,
        num_search_workers=1,
    )

    assert result.generated is True
    assert result.generation_id is not None

    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT DISTINCT generation_id
            FROM schedules
            WHERE target_date >= ?
              AND target_date < ?
            """,
            (
                "2026-08-01",
                "2026-09-01",
            ),
        ).fetchall()

    assert len(rows) == 1
    assert rows[0]["generation_id"] == result.generation_id


def test_generation_stops_when_input_has_errors(
    initialized_test_db,
) -> None:
    """事前検証エラーがあればSolverを実行・保存しない。"""

    result = generate_month_schedule(
        TARGET_MONTH,
        max_time_seconds=3,
        num_search_workers=1,
    )

    assert result.generated is False
    assert result.solver_result is None
    assert result.generation_id is None

    assert has_errors(
        list(result.validation_issues)
    )

    assignments = list_schedule_assignments(
        TARGET_MONTH
    )

    assert assignments == []

    with get_connection() as connection:
        generation_count = connection.execute(
            """
            SELECT COUNT(*)
            FROM schedule_generations
            """
        ).fetchone()[0]

    assert generation_count == 0


def test_second_generation_replaces_month_schedule(
    initialized_test_db,
) -> None:
    """再生成時は対象月の既存シフトを置き換える。"""

    register_basic_employees()
    register_month_requirements()

    first_result = generate_month_schedule(
        TARGET_MONTH,
        max_time_seconds=3,
        num_search_workers=1,
    )

    assert first_result.generated is True
    assert first_result.generation_id is not None

    first_assignments = list_schedule_assignments(
        TARGET_MONTH
    )

    second_result = generate_month_schedule(
        TARGET_MONTH,
        max_time_seconds=3,
        num_search_workers=1,
    )

    assert second_result.generated is True
    assert second_result.generation_id is not None

    second_assignments = list_schedule_assignments(
        TARGET_MONTH
    )

    assert (
        second_result.generation_id
        != first_result.generation_id
    )

    assert len(first_assignments) == 62
    assert len(second_assignments) == 62

    with get_connection() as connection:
        schedule_generation_ids = connection.execute(
            """
            SELECT DISTINCT generation_id
            FROM schedules
            WHERE target_date >= ?
              AND target_date < ?
            """,
            (
                "2026-08-01",
                "2026-09-01",
            ),
        ).fetchall()

        generation_count = connection.execute(
            """
            SELECT COUNT(*)
            FROM schedule_generations
            WHERE target_month = ?
            """,
            (TARGET_MONTH,),
        ).fetchone()[0]

    # 現在のシフトは2回目の生成結果だけに関連付く
    assert len(schedule_generation_ids) == 1
    assert (
        schedule_generation_ids[0]["generation_id"]
        == second_result.generation_id
    )

    # 生成履歴自体は2件残る
    assert generation_count == 2