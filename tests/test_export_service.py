from __future__ import annotations

from datetime import date

import pandas as pd

from src.export_service import (
    build_assignment_detail,
    build_employee_calendar_export,
    build_employee_schedule_export_table,
    build_employee_summary_table,
    build_export_filename,
    build_schedule_export_table,
    dataframe_to_csv_bytes,
)
from src.models import (
    Employee,
    EmployeeScheduleSummary,
    ScheduleAssignment,
)


def make_employees() -> list[Employee]:
    return [
        Employee(
            employee_id="E001",
            name="山田 太郎",
            is_manager=True,
            contract_days=2,
            can_work_early=True,
            can_work_late=True,
            is_active=True,
        ),
        Employee(
            employee_id="E002",
            name="佐藤 花子",
            is_manager=False,
            contract_days=2,
            can_work_early=True,
            can_work_late=True,
            is_active=True,
        ),
    ]


def test_build_schedule_export_table() -> None:
    employees = make_employees()

    employee_map = {
        employee.employee_id: employee
        for employee in employees
    }

    assignments = [
        ScheduleAssignment(
            target_date=date(2026, 8, 1),
            shift_type="early",
            employee_id="E001",
        ),
        ScheduleAssignment(
            target_date=date(2026, 8, 1),
            shift_type="late",
            employee_id="E002",
            is_manual=True,
        ),
    ]

    dataframe = (
        build_schedule_export_table(
            target_month="2026-08",
            assignments=assignments,
            employee_map=employee_map,
        )
    )

    assert len(dataframe) == 31
    assert dataframe.iloc[0]["日付"] == (
        "2026/08/01"
    )
    assert dataframe.iloc[0]["早番"] == (
        "山田 太郎"
    )
    assert dataframe.iloc[0]["遅番"] == (
        "佐藤 花子※"
    )


def test_build_assignment_detail() -> None:
    employees = make_employees()

    employee_map = {
        employee.employee_id: employee
        for employee in employees
    }

    assignments = [
        ScheduleAssignment(
            target_date=date(2026, 8, 1),
            shift_type="early",
            employee_id="E001",
            is_manual=True,
        )
    ]

    dataframe = build_assignment_detail(
        assignments=assignments,
        employee_map=employee_map,
    )

    assert len(dataframe) == 1
    assert (
        dataframe.iloc[0]["シフト"]
        == "早番"
    )
    assert (
        dataframe.iloc[0]["責任者"]
        == "はい"
    )
    assert (
        dataframe.iloc[0]["手動変更"]
        == "はい"
    )


def test_build_employee_summary_table() -> None:
    summaries = [
        EmployeeScheduleSummary(
            employee_id="E001",
            employee_name="山田 太郎",
            contract_days=20,
            assigned_days=19,
            difference=-1,
            early_count=10,
            late_count=9,
            max_consecutive_days=5,
            manager_assignment_count=19,
        )
    ]

    dataframe = (
        build_employee_summary_table(
            summaries
        )
    )

    assert len(dataframe) == 1
    assert (
        dataframe.iloc[0]["割当勤務日数"]
        == 19
    )
    assert dataframe.iloc[0]["差"] == -1


def test_dataframe_to_csv_bytes() -> None:
    dataframe = pd.DataFrame(
        [
            {
                "氏名": "山田 太郎",
            }
        ]
    )

    csv_bytes = dataframe_to_csv_bytes(
        dataframe
    )

    assert csv_bytes.startswith(
        b"\xef\xbb\xbf"
    )

    decoded = csv_bytes.decode(
        "utf-8-sig"
    )

    assert "山田 太郎" in decoded


def test_csv_does_not_include_index() -> None:
    dataframe = pd.DataFrame(
        [
            {
                "従業員ID": "E001",
            }
        ]
    )

    decoded = dataframe_to_csv_bytes(
        dataframe
    ).decode("utf-8-sig")

    first_line = decoded.splitlines()[0]

    assert first_line == "従業員ID"


def test_build_export_filename() -> None:
    filename = build_export_filename(
        target_month="2026-08",
        data_type="monthly",
    )

    assert filename == (
        "shift_monthly_202608.csv"
    )


def make_employee(
    employee_id: str = "E001",
    name: str = "山田太郎",
) -> Employee:
    """テスト用の従業員を作成する。"""

    return Employee(
        employee_id=employee_id,
        name=name,
        is_manager=True,
        contract_days=20,
        can_work_early=True,
        can_work_late=True,
        is_active=True,
    )


def test_build_employee_schedule_export_table() -> None:
    employee = make_employee()

    assignments = [
        ScheduleAssignment(
            target_date=date(2026, 8, 1),
            shift_type="early",
            employee_id="E001",
        ),
        ScheduleAssignment(
            target_date=date(2026, 8, 2),
            shift_type="late",
            employee_id="E001",
        ),
    ]

    dataframe = (
        build_employee_schedule_export_table(
            target_month="2026-08",
            assignments=assignments,
            employee_map={
                "E001": employee,
            },
        )
    )

    assert dataframe.iloc[0]["従業員ID"] == "E001"
    assert dataframe.iloc[0]["氏名"] == "山田太郎"
    assert dataframe.iloc[0]["1(土)"] == "早"
    assert dataframe.iloc[0]["2(日)"] == "遅"
    assert dataframe.iloc[0]["3(月)"] == "休"


def test_build_employee_calendar_export() -> None:
    employee = make_employee()

    assignments = [
        ScheduleAssignment(
            target_date=date(2026, 8, 1),
            shift_type="early",
            employee_id="E001",
        ),
        ScheduleAssignment(
            target_date=date(2026, 8, 3),
            shift_type="late",
            employee_id="E001",
        ),
    ]

    dataframe = build_employee_calendar_export(
        target_month="2026-08",
        employee=employee,
        assignments=assignments,
    )

    assert dataframe.iloc[0]["土"] == (
        "1日 早番"
    )
    assert dataframe.iloc[0]["日"] == (
        "2日 休み"
    )
    assert dataframe.iloc[1]["月"] == (
        "3日 遅番"
    )