# import
from __future__ import annotations

import calendar
from datetime import date

import pandas as pd
import streamlit as st

from src.db import init_db
from src.models import (
    Employee,
    EmployeeScheduleSummary,
    ScheduleAssignment,
)
from src.repositories import (
    list_day_off_requests,
    list_employees,
    list_schedule_assignments,
    list_staffing_requirements,
)
from src.schedule_service import (
    generate_month_schedule,
    get_month_employee_summaries,
    validate_month_generation_inputs,
    validate_month_schedule,
)
from src.ui_helpers import (
    select_target_month,
    show_validation_issues,
)
from src.validation import has_errors

# 定数
WEEKDAY_LABELS = (
    "月",
    "火",
    "水",
    "木",
    "金",
    "土",
    "日",
)

SOLVER_STATUS_LABELS = {
    "OPTIMAL": "最適解",
    "FEASIBLE": "実行可能解",
    "INFEASIBLE": "解なし",
    "MODEL_INVALID": "モデル不正",
    "UNKNOWN": "結果未確定",
}

# 表示補助関数
def build_schedule_table(
    *,
    year: int,
    month: int,
    assignments: list[
        ScheduleAssignment
    ],
    employee_map: dict[
        str,
        Employee,
    ],
) -> pd.DataFrame:
    last_day = calendar.monthrange(
        year,
        month,
    )[1]

    assignment_map: dict[
        tuple[date, str],
        list[str],
    ] = {}

    for assignment in assignments:
        key = (
            assignment.target_date,
            assignment.shift_type,
        )

        employee = employee_map.get(
            assignment.employee_id
        )

        employee_label = (
            employee.name
            if employee is not None
            else assignment.employee_id
        )

        assignment_map.setdefault(
            key,
            [],
        ).append(employee_label)

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

        early_names = assignment_map.get(
            (target_date, "early"),
            [],
        )

        late_names = assignment_map.get(
            (target_date, "late"),
            [],
        )

        rows.append(
            {
                "日付": target_date,
                "曜日": WEEKDAY_LABELS[
                    target_date.weekday()
                ],
                "早番": "、".join(
                    early_names
                ),
                "遅番": "、".join(
                    late_names
                ),
            }
        )

    return pd.DataFrame(rows)


def build_assignment_dataframe(
    assignments: list[
        ScheduleAssignment
    ],
    employee_map: dict[
        str,
        Employee,
    ],
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
                ),
                "曜日": WEEKDAY_LABELS[
                    assignment
                    .target_date
                    .weekday()
                ],
                "シフト": (
                    "早番"
                    if (
                        assignment.shift_type
                        == "early"
                    )
                    else "遅番"
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

    return pd.DataFrame(rows)


def build_summary_dataframe(
    summaries: list[
        EmployeeScheduleSummary
    ],
    employee_map: dict[
        str,
        Employee,
    ],
) -> pd.DataFrame:
    rows = []

    for summary in summaries:
        employee = employee_map.get(
            summary.employee_id
        )

        rows.append(
            {
                "従業員ID": (
                    summary.employee_id
                ),
                "氏名": (
                    employee.name
                    if employee is not None
                    else "不明"
                ),
                "契約勤務日数": (
                    employee.contract_days
                    if employee is not None
                    else 0
                ),
                "割当勤務日数": (
                    summary.assigned_days
                ),
                "差": (
                    summary.assigned_days
                    - (
                        employee.contract_days
                        if employee is not None
                        else 0
                    )
                ),
                "早番": (
                    summary.early_count
                ),
                "遅番": (
                    summary.late_count
                ),
                "最大連続勤務": (
                    summary
                    .max_consecutive_days
                ),
                "責任者配置": (
                    summary
                    .manager_assignment_count
                ),
            }
        )

    return pd.DataFrame(rows)


# DB初期化・ページ設定
init_db()

st.set_page_config(
    page_title="シフト生成",
    page_icon="🗓️",
    layout="wide",
)

st.title("シフト生成")
st.caption("従業員、希望休、必要人数設定をもとに月間シフトを自動生成します。")

# 対象年月選択
selected_year, selected_month, target_month = (
    select_target_month(
        key_prefix="generation",
    )
)

st.info(f"生成対象：{selected_year}年{selected_month}月")

# 入力データ件数
employees = list_employees()
active_employees = [
    employee for employee in employees
    if employee.is_active
]

active_managers = [
    employee for employee in active_employees
    if employee.is_manager
]

day_off_requests = list_day_off_requests(target_month)

requirements = list_staffing_requirements(target_month)

last_day = calendar.monthrange(
    selected_year,
    selected_month,
)[1]

expected_requirement_count = (last_day * 2)

st.subheader("入力データ状況")

metric1, metric2, metric3, metric4 = (st.columns(4))
metric1.metric(
    "有効従業員",
    len(active_employees),
)
metric2.metric(
    "有効責任者",
    len(active_managers),
)
metric3.metric(
    "希望休",
    len(day_off_requests),
)
metric4.metric(
    "必要人数設定",
    (
        f"{len(requirements)}"
        f" / {expected_requirement_count}"
    ),
)

if len(requirements) < expected_requirement_count:
    st.warning(
        "必要人数設定が不足しています。"
        "必要人数設定画面で対象月の全日付・全シフトを保存してください。"
    )

# 生成前検証
st.divider()
st.subheader("生成前チェック")

pre_issues = (
    validate_month_generation_inputs(target_month)
)

show_validation_issues(
    pre_issues,
    empty_message=("生成を妨げる入力エラーはありません。"),
)

has_pre_errors = has_errors(pre_issues)

# Solver設定・上書き確認
st.divider()
st.subheader("自動生成")

max_time_seconds = st.selectbox(
    "探索時間の上限",
    options=[3, 5, 10, 30],
    index=2,
    format_func=lambda value: (
        f"{value}秒"
    ),
)

existing_assignments = (
    list_schedule_assignments(target_month)
)

if existing_assignments:
    st.warning(
        "対象月には既に"
        f"{len(existing_assignments)}件の"
        "シフトが保存されています。"
        "再生成すると現在のシフトは新しい生成結果に置き換わります。"
    )

confirm_regeneration = True

if existing_assignments:
    confirm_regeneration = st.checkbox(
        "既存シフトを置き換えることを確認しました",
        key=f"confirm_generation_{target_month}",
    )

# 生成ボタン
generation_running_key = (
    f"generation_running_{target_month}"
)

is_generation_running = (
    st.session_state.get(
        generation_running_key,
        False,
    )
)

generation_disabled = (
    has_pre_errors
    or not confirm_regeneration
)

generate_clicked = st.button(
    "シフトを自動生成",
    type="primary",
    disabled=(
        generation_disabled
        or is_generation_running
    ),
)

if has_pre_errors:
    st.caption("生成前チェックのエラーを解消すると実行できます。")

if generate_clicked:
    st.session_state[
        generation_running_key
    ] = True

    try:
        with st.spinner(
            "シフトを生成しています..."
        ):
            result = (
                generate_month_schedule(
                    target_month,
                    max_time_seconds=float(
                        max_time_seconds
                    ),
                    num_search_workers=1,
                )
            )

        st.session_state[
            f"generation_result_{target_month}"
        ] = result

    finally:
        st.session_state[
            generation_running_key
        ] = False

    st.rerun()

# 生成結果
generation_result = (
    st.session_state.get(
        f"generation_result_{target_month}"
    )
)

if generation_result is not None:
    st.divider()
    st.subheader("生成結果")

    if generation_result.generated:
        st.success("シフトを生成し、データベースへ保存しました。")
    else:
        st.error("シフトを生成できませんでした。")

    solver_result = (
        generation_result.solver_result
    )

    if solver_result is None:
        st.info("入力エラーにより、""Solverは実行されませんでした。")
    else:
        solver_status = (
            solver_result.status
        )

        status_label = (
            SOLVER_STATUS_LABELS.get(
                solver_status,
                solver_status,
            )
        )

        result_column1, result_column2, (
            result_column3
        ) = st.columns(3)

        result_column1.metric(
            "Solver結果",
            status_label,
        )

        result_column2.metric(
            "最大契約日数乖離",
            (
                solver_result.max_deviation
                if (
                    solver_result
                    .max_deviation
                    is not None
                )
                else "-"
            ),
        )

        result_column3.metric(
            "乖離合計",
            (
                solver_result.total_deviation
                if (
                    solver_result
                    .total_deviation
                    is not None
                )
                else "-"
            ),
        )

        if solver_status == "FEASIBLE":
            st.info(
                "制約を満たすシフトが見つかりました。"
                "ただし、探索時間内に最適性の証明までは完了していません。"
            )
        elif solver_status == "INFEASIBLE":
            st.error(
                "すべてのハード制約を同時に満たすシフトが存在しません。"
            )
        elif solver_status == "UNKNOWN":
            st.warning(
                "探索時間内に実行可能解を確定できませんでした。"
                "探索時間を延ばして再実行してください。"
            )

    show_validation_issues(
        list(
            generation_result
            .validation_issues
        ),
        empty_message=(
            "生成結果に制約違反や警告はありません。"
        ),
    )

# 保存済みシフト取得

# 月間シフト表
assignments = list_schedule_assignments(
    target_month
)

employee_map = {
    employee.employee_id: employee
    for employee in list_employees()
}

st.divider()
st.subheader("月間シフト")

if not assignments:
    st.info("対象月のシフトはまだ生成されていません。")
else:
    schedule_df = build_schedule_table(
        year=selected_year,
        month=selected_month,
        assignments=assignments,
        employee_map=employee_map,
    )

    st.dataframe(
        schedule_df,
        width="stretch",
        hide_index=True,
        column_config={
            "日付": (
                st.column_config.DateColumn(
                    "日付",
                    format="MM/DD",
                )
            ),
            "曜日": (
                st.column_config.TextColumn(
                    "曜日",
                    width="small",
                )
            ),
            "早番": (
                st.column_config.TextColumn(
                    "早番"
                )
            ),
            "遅番": (
                st.column_config.TextColumn(
                    "遅番"
                )
            ),
        },
    )

if assignments:
    with st.expander(
        "配置明細を表示"
    ):
        assignment_df = (
            build_assignment_dataframe(
                assignments,
                employee_map,
            )
        )

        st.dataframe(
            assignment_df,
            width="stretch",
            hide_index=True,
        )

# 保存済みシフト検証
st.divider()
st.subheader("保存済みシフトの検証")

if not assignments:
    st.info("検証対象のシフトがありません。")
else:
    schedule_issues = (
        validate_month_schedule(
            target_month
        )
    )

    show_validation_issues(
        schedule_issues,
        empty_message=(
            "保存済みシフトはすべての検証を通過しています。"
        ),
    )

# 従業員別勤務集計
st.divider()
st.subheader("従業員別勤務集計")

if not assignments:
    st.info("集計対象のシフトがありません。")
else:
    summaries = (
        get_month_employee_summaries(
            target_month
        )
    )

    summary_df = (
        build_summary_dataframe(
            summaries,
            employee_map,
        )
    )

    st.dataframe(
        summary_df,
        width="stretch",
        hide_index=True,
    )

if assignments:
    total_assigned = sum(
        summary.assigned_days
        for summary in summaries
    )

    maximum_consecutive = max(
        (
            summary.max_consecutive_days
            for summary in summaries
        ),
        default=0,
    )

    summary_metric1, summary_metric2, (
        summary_metric3
    ) = st.columns(3)

    summary_metric1.metric(
        "配置件数",
        len(assignments),
    )

    summary_metric2.metric(
        "勤務日数合計",
        total_assigned,
    )

    summary_metric3.metric(
        "最大連続勤務",
        maximum_consecutive,
    )
