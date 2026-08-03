from datetime import date

from src.models import (
    Employee,
    EmployeeScheduleSummary,
    ScheduleAssignment,
)
from src.schedule_view import (
    build_assignment_dataframe,
    build_change_dataframe,
    build_employee_schedule_table,
    build_month_schedule_table,
    build_summary_dataframe,
)


def make_employee(
    employee_id: str = "E001",
    name: str = "山田太郎",
) -> Employee:
    return Employee(
        employee_id=employee_id,
        name=name,
        is_manager=True,
        contract_days=20,
        can_work_early=True,
        can_work_late=True,
        is_active=True,
    )


def test_build_month_schedule_table() -> None:
    employee = make_employee()

    assignments = [
        ScheduleAssignment(
            target_date=date(2026, 8, 1),
            shift_type="early",
            employee_id="E001",
        )
    ]

    dataframe = build_month_schedule_table(
        year=2026,
        month=8,
        assignments=assignments,
        employee_map={
            "E001": employee,
        },
    )

    assert len(dataframe) == 31
    assert dataframe.iloc[0]["日付"] == date(
        2026,
        8,
        1,
    )
    assert dataframe.iloc[0]["早番"] == (
        "山田太郎"
    )
    assert dataframe.iloc[0]["遅番"] == ""


def test_build_month_schedule_table_shows_manual_mark() -> None:
    employee = make_employee()

    assignments = [
        ScheduleAssignment(
            target_date=date(2026, 8, 1),
            shift_type="late",
            employee_id="E001",
            is_manual=True,
        )
    ]

    dataframe = build_month_schedule_table(
        year=2026,
        month=8,
        assignments=assignments,
        employee_map={
            "E001": employee,
        },
        show_manual_mark=True,
    )

    assert dataframe.iloc[0]["遅番"] == (
        "山田太郎 ※"
    )


def test_build_assignment_dataframe() -> None:
    employee = make_employee()

    assignments = [
        ScheduleAssignment(
            target_date=date(2026, 8, 1),
            shift_type="early",
            employee_id="E001",
            is_manual=True,
        )
    ]

    dataframe = build_assignment_dataframe(
        assignments=assignments,
        employee_map={
            "E001": employee,
        },
    )

    assert len(dataframe) == 1
    assert dataframe.iloc[0]["シフト"] == (
        "早番"
    )
    assert dataframe.iloc[0]["責任者"] == (
        "はい"
    )
    assert dataframe.iloc[0]["手動変更"] == (
        "はい"
    )


def test_build_change_dataframe() -> None:
    employee = make_employee()

    original = [
        ScheduleAssignment(
            target_date=date(2026, 8, 1),
            shift_type="early",
            employee_id="E001",
        )
    ]

    draft = [
        ScheduleAssignment(
            target_date=date(2026, 8, 1),
            shift_type="late",
            employee_id="E001",
            is_manual=True,
        )
    ]

    dataframe = build_change_dataframe(
        original=original,
        draft=draft,
        employee_map={
            "E001": employee,
        },
    )

    assert len(dataframe) == 1
    assert dataframe.iloc[0]["変更前"] == (
        "早番"
    )
    assert dataframe.iloc[0]["変更後"] == (
        "遅番"
    )


def test_build_summary_dataframe() -> None:
    summary = EmployeeScheduleSummary(
        employee_id="E001",
        employee_name="山田太郎",
        contract_days=20,
        assigned_days=19,
        difference=-1,
        early_count=10,
        late_count=9,
        max_consecutive_days=5,
        manager_assignment_count=19,
    )

    dataframe = build_summary_dataframe(
        [summary]
    )

    assert len(dataframe) == 1
    assert dataframe.iloc[0][
        "割当勤務日数"
    ] == 19
    assert dataframe.iloc[0]["差"] == -1


def test_build_employee_schedule_table() -> None:
    employee1 = make_employee(
        employee_id="E001",
        name="山田太郎",
    )
    employee2 = make_employee(
        employee_id="E002",
        name="佐藤花子",
    )

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
        ScheduleAssignment(
            target_date=date(2026, 8, 1),
            shift_type="late",
            employee_id="E002",
        ),
    ]

    dataframe = build_employee_schedule_table(
        year=2026,
        month=8,
        assignments=assignments,
        employee_map={
            "E001": employee1,
            "E002": employee2,
        },
    )

    assert len(dataframe) == 2

    assert dataframe.iloc[0]["従業員"] == (
        "E001｜山田太郎"
    )
    assert dataframe.iloc[0]["1(土)"] == "早"
    assert dataframe.iloc[0]["2(日)"] == "遅"
    assert dataframe.iloc[0]["3(月)"] == "休"

    assert dataframe.iloc[1]["従業員"] == (
        "E002｜佐藤花子"
    )
    assert dataframe.iloc[1]["1(土)"] == "遅"
    assert dataframe.iloc[1]["2(日)"] == "休"


def test_build_employee_schedule_table_shows_manual_mark() -> None:
    employee = make_employee()

    assignments = [
        ScheduleAssignment(
            target_date=date(2026, 8, 1),
            shift_type="early",
            employee_id="E001",
            is_manual=True,
        )
    ]

    dataframe = build_employee_schedule_table(
        year=2026,
        month=8,
        assignments=assignments,
        employee_map={
            "E001": employee,
        },
        show_manual_mark=True,
    )

    assert dataframe.iloc[0]["1(土)"] == "早※"
