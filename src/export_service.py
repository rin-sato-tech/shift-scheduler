from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date

import pandas as pd

from src.models import (
    Employee,
    EmployeeScheduleSummary,
    ScheduleAssignment,
)
from src.repositories import (
    list_employees,
    list_schedule_assignments,
)
from src.schedule_service import (
    get_month_employee_summaries,
)

@dataclass(frozen=True)
class ScheduleExportData:
    target_month: str
    schedule_table: pd.DataFrame
    assignment_detail: pd.DataFrame
    employee_summary: pd.DataFrame


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
}


def build_schedule_export_table(
    *,
    target_month: str,
    assignments: list[
        ScheduleAssignment
    ],
    employee_map: dict[str, Employee],
) -> pd.DataFrame:
    year, month = parse_target_month(
        target_month
    )

    last_day = calendar.monthrange(
        year,
        month,
    )[1]

    assignment_map: dict[
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

        if assignment.is_manual:
            employee_name = (
                f"{employee_name}※"
            )

        key = (
            assignment.target_date,
            assignment.shift_type,
        )

        assignment_map.setdefault(
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
                "日付": (
                    target_date.strftime(
                        "%Y/%m/%d"
                    )
                ),
                "曜日": WEEKDAY_LABELS[
                    target_date.weekday()
                ],
                "早番": "、".join(
                    assignment_map.get(
                        (
                            target_date,
                            "early",
                        ),
                        [],
                    )
                ),
                "遅番": "、".join(
                    assignment_map.get(
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


def build_assignment_detail(
    *,
    assignments: list[
        ScheduleAssignment
    ],
    employee_map: dict[str, Employee],
) -> pd.DataFrame:
    rows = []

    for assignment in assignments:
        employee = employee_map.get(
            assignment.employee_id
        )

        rows.append(
            {
                "日付": (
                    assignment.target_date
                    .strftime("%Y/%m/%d")
                ),
                "曜日": WEEKDAY_LABELS[
                    assignment.target_date
                    .weekday()
                ],
                "シフト": SHIFT_LABELS[
                    assignment.shift_type
                ],
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


def build_employee_summary_table(
    summaries: list[
        EmployeeScheduleSummary
    ],
) -> pd.DataFrame:
    rows = [
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
            "早番回数": (
                summary.early_count
            ),
            "遅番回数": (
                summary.late_count
            ),
            "最大連続勤務日数": (
                summary.max_consecutive_days
            ),
            "責任者配置回数": (
                summary
                .manager_assignment_count
            ),
        }
        for summary in summaries
    ]

    return pd.DataFrame(
        rows,
        columns=[
            "従業員ID",
            "氏名",
            "契約勤務日数",
            "割当勤務日数",
            "差",
            "早番回数",
            "遅番回数",
            "最大連続勤務日数",
            "責任者配置回数",
        ],
    )


def get_schedule_export_data(
    target_month: str,
) -> ScheduleExportData:
    parse_target_month(target_month)

    employees = list_employees()
    assignments = (
        list_schedule_assignments(
            target_month
        )
    )
    summaries = (
        get_month_employee_summaries(
            target_month
        )
    )

    employee_map = {
        employee.employee_id: employee
        for employee in employees
    }

    return ScheduleExportData(
        target_month=target_month,
        schedule_table=(
            build_schedule_export_table(
                target_month=target_month,
                assignments=assignments,
                employee_map=employee_map,
            )
        ),
        assignment_detail=(
            build_assignment_detail(
                assignments=assignments,
                employee_map=employee_map,
            )
        ),
        employee_summary=(
            build_employee_summary_table(
                summaries
            )
        ),
    )


def dataframe_to_csv_bytes(
    dataframe: pd.DataFrame,
) -> bytes:
    csv_text = dataframe.to_csv(
        index=False,
        lineterminator="\n",
    )

    return csv_text.encode(
        "utf-8-sig"
    )


def build_export_filename(
    *,
    target_month: str,
    data_type: str,
) -> str:
    safe_month = target_month.replace(
        "-",
        "",
    )

    return (
        f"shift_{data_type}_"
        f"{safe_month}.csv"
    )
