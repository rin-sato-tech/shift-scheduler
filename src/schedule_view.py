from __future__ import annotations

import calendar
from datetime import date

import pandas as pd

from src.models import (
    Employee,
    EmployeeScheduleSummary,
    ScheduleAssignment,
)


WEEKDAY_LABELS = (
    "月",
    "火",
    "水",
    "木",
    "金",
    "土",
    "日",
)

SHIFT_LABELS = {
    "early": "早番",
    "late": "遅番",
    "off": "休み",
}


def build_month_schedule_table(
    *,
    year: int,
    month: int,
    assignments: list[ScheduleAssignment],
    employee_map: dict[str, Employee],
    show_manual_mark: bool = False,
) -> pd.DataFrame:
    """月間シフトを日付・早番・遅番の表に変換する。"""

    last_day = calendar.monthrange(
        year,
        month,
    )[1]

    grouped: dict[
        tuple[date, str],
        list[str],
    ] = {}

    for assignment in assignments:
        employee = employee_map.get(
            assignment.employee_id
        )

        employee_name = (
            employee.name
            if employee is not None
            else assignment.employee_id
        )

        if (
            show_manual_mark
            and assignment.is_manual
        ):
            employee_name = (
                f"{employee_name} ※"
            )

        key = (
            assignment.target_date,
            assignment.shift_type,
        )

        grouped.setdefault(
            key,
            [],
        ).append(employee_name)

    rows = []

    for day in range(
        1,
        last_day + 1,
    ):
        target_date = date(
            year,
            month,
            day,
        )

        rows.append(
            {
                "日付": target_date,
                "曜日": WEEKDAY_LABELS[
                    target_date.weekday()
                ],
                "早番": "、".join(
                    grouped.get(
                        (
                            target_date,
                            "early",
                        ),
                        [],
                    )
                ),
                "遅番": "、".join(
                    grouped.get(
                        (
                            target_date,
                            "late",
                        ),
                        [],
                    )
                ),
            }
        )

    return pd.DataFrame(
        rows,
        columns=[
            "日付",
            "曜日",
            "早番",
            "遅番",
        ],
    )


def build_assignment_dataframe(
    *,
    assignments: list[ScheduleAssignment],
    employee_map: dict[str, Employee],
) -> pd.DataFrame:
    """配置データを1配置1行の表に変換する。"""

    rows = []

    for assignment in assignments:
        employee = employee_map.get(
            assignment.employee_id
        )

        rows.append(
            {
                "日付": assignment.target_date,
                "曜日": WEEKDAY_LABELS[
                    assignment.target_date.weekday()
                ],
                "シフト": SHIFT_LABELS.get(
                    assignment.shift_type,
                    assignment.shift_type,
                ),
                "従業員ID": (
                    assignment.employee_id
                ),
                "氏名": (
                    employee.name
                    if employee is not None
                    else "不明"
                ),
                "責任者": (
                    "はい"
                    if (
                        employee is not None
                        and employee.is_manager
                    )
                    else "いいえ"
                ),
                "手動変更": (
                    "はい"
                    if assignment.is_manual
                    else "いいえ"
                ),
            }
        )

    return pd.DataFrame(
        rows,
        columns=[
            "日付",
            "曜日",
            "シフト",
            "従業員ID",
            "氏名",
            "責任者",
            "手動変更",
        ],
    )


def build_summary_dataframe(
    summaries: list[EmployeeScheduleSummary],
) -> pd.DataFrame:
    """従業員別勤務集計を画面表示用の表に変換する。"""

    rows = []

    for summary in summaries:
        rows.append(
            {
                "従業員ID": (
                    summary.employee_id
                ),
                "氏名": (
                    summary.employee_name
                ),
                "契約勤務日数": (
                    summary.contract_days
                ),
                "割当勤務日数": (
                    summary.assigned_days
                ),
                "差": summary.difference,
                "早番": summary.early_count,
                "遅番": summary.late_count,
                "最大連続勤務": (
                    summary.max_consecutive_days
                ),
                "責任者配置": (
                    summary.manager_assignment_count
                ),
            }
        )

    return pd.DataFrame(
        rows,
        columns=[
            "従業員ID",
            "氏名",
            "契約勤務日数",
            "割当勤務日数",
            "差",
            "早番",
            "遅番",
            "最大連続勤務",
            "責任者配置",
        ],
    )


def assignment_key(
    assignment: ScheduleAssignment,
) -> tuple[date, str]:
    """日付と従業員IDから配置比較用キーを作る。"""

    return (
        assignment.target_date,
        assignment.employee_id,
    )


def build_change_dataframe(
    *,
    original: list[ScheduleAssignment],
    draft: list[ScheduleAssignment],
    employee_map: dict[str, Employee],
) -> pd.DataFrame:
    """変更前と編集案の差分を表に変換する。"""

    original_map = {
        assignment_key(assignment):
        assignment
        for assignment in original
    }

    draft_map = {
        assignment_key(assignment):
        assignment
        for assignment in draft
    }

    all_keys = sorted(
        set(original_map)
        | set(draft_map)
    )

    rows = []

    for key in all_keys:
        before = original_map.get(key)
        after = draft_map.get(key)

        before_shift = (
            before.shift_type
            if before is not None
            else "off"
        )

        after_shift = (
            after.shift_type
            if after is not None
            else "off"
        )

        if before_shift == after_shift:
            continue

        target_date, employee_id = key

        employee = employee_map.get(
            employee_id
        )

        rows.append(
            {
                "日付": target_date,
                "曜日": WEEKDAY_LABELS[
                    target_date.weekday()
                ],
                "従業員ID": employee_id,
                "氏名": (
                    employee.name
                    if employee is not None
                    else "不明"
                ),
                "変更前": SHIFT_LABELS.get(
                    before_shift,
                    before_shift,
                ),
                "変更後": SHIFT_LABELS.get(
                    after_shift,
                    after_shift,
                ),
            }
        )

    return pd.DataFrame(
        rows,
        columns=[
            "日付",
            "曜日",
            "従業員ID",
            "氏名",
            "変更前",
            "変更後",
        ],
    )
