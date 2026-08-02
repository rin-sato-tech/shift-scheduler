from __future__ import annotations

import calendar
from datetime import date

import streamlit as st

from src.db import init_db
from src.manual_schedule_service import (
    apply_manual_change,
    save_manual_schedule,
    validate_manual_schedule,
)
from src.models import ScheduleAssignment
from src.repositories import (
    list_employees,
    list_schedule_assignments,
)
from src.schedule_view import (
    build_change_dataframe,
    build_month_schedule_table,
)
from src.ui_helpers import (
    select_target_month,
    set_flash_message,
    show_flash_message,
    show_validation_issues,
)
from src.validation import has_errors

init_db()

st.set_page_config(
    page_title="シフト手動変更",
    page_icon="✏️",
    layout="wide",
)

st.title("シフト手動変更")

st.caption("生成済みシフトを変更し、制約を再検証して保存します。")

show_flash_message(key="manual_schedule_flash")

selected_year, selected_month, target_month = (
    select_target_month(key_prefix="manual")
)

draft_key = (f"manual_schedule_draft_{target_month}")
original_key = (f"manual_schedule_original_{target_month}")

saved_assignments = (
    list_schedule_assignments(target_month)
)

if not saved_assignments:
    st.warning(
        "対象月のシフトがまだ生成されていません。"
        "先にシフト生成画面で自動生成してください。"
    )
    st.stop()

if draft_key not in st.session_state:
    st.session_state[draft_key] = (
        saved_assignments.copy()
    )

if original_key not in st.session_state:
    st.session_state[original_key] = (
        saved_assignments.copy()
    )

draft_assignments: list[
    ScheduleAssignment
] = st.session_state[draft_key]

employees = list_employees()

active_employees = [
    employee for employee in employees
    if employee.is_active
]

employee_map = {
    employee.employee_id: employee
    for employee in employees
}

st.subheader("編集中のシフト")

st.caption("※は手動変更された配置です。")

draft_df = build_month_schedule_table(
    year=selected_year,
    month=selected_month,
    assignments=draft_assignments,
    employee_map=employee_map,
    show_manual_mark=True,
)

st.dataframe(
    draft_df,
    width="stretch",
    hide_index=True,
)

st.divider()
st.subheader("配置を変更")

last_day = calendar.monthrange(
    selected_year,
    selected_month,
)[1]

month_start = date(
    selected_year,
    selected_month,
    1,
)

month_end = date(
    selected_year,
    selected_month,
    last_day,
)

employee_options = {
    (
        f"{employee.employee_id}｜{employee.name}"
    ): employee.employee_id
    for employee in active_employees
}

if not employee_options:
    st.warning(
        "配置を変更できる有効な従業員がいません。"
        "従業員管理画面で従業員を再有効化してください。"
    )
    st.stop()

with st.form(
    key=f"manual_change_form_{target_month}"
):
    (
        date_column,
        employee_column,
        shift_column,
    ) = st.columns(3)

    selected_date = date_column.date_input(
        "変更日",
        value=month_start,
        min_value=month_start,
        max_value=month_end,
        format="YYYY/MM/DD",
        key=f"manual_change_date_{target_month}",
    )

    selected_employee_label = (
        employee_column.selectbox(
            "従業員",
            options=list(employee_options.keys()),
            key=f"manual_change_employee_{target_month}",
        )
    )

    new_shift_label = shift_column.selectbox(
        "変更後",
        options=[
            "早番",
            "遅番",
            "休み",
        ],
        key=f"manual_change_shift_{target_month}",
    )

    change_submitted = (
        st.form_submit_button(
            "編集案へ反映",
            type="primary",
        )
    )

shift_value_map = {
    "早番": "early",
    "遅番": "late",
    "休み": "off",
}

if change_submitted:
    employee_id = employee_options[
        selected_employee_label
    ]

    result = apply_manual_change(
        target_month=target_month,
        assignments=draft_assignments,
        employee_id=employee_id,
        target_date=selected_date,
        new_shift=shift_value_map[new_shift_label],
    )

    if result.succeeded:
        st.session_state[draft_key] = list(
            result.assignments
        )

        set_flash_message(
            key="manual_schedule_flash",
            message=result.message,
        )

        st.rerun()
    else:
        st.error(result.message)

selected_employee_id = employee_options[
    selected_employee_label
]

current_assignment = next(
    (
        assignment
        for assignment in draft_assignments
        if (
            assignment.employee_id == selected_employee_id
            and assignment.target_date == selected_date
        )
    ),
    None,
)

current_shift = (
    "休み"
    if current_assignment is None
    else (
        "早番"
        if current_assignment.shift_type == "early"
        else "遅番"
    )
)

st.info(f"現在の配置：{current_shift}")

st.divider()
st.subheader("編集案の検証")

draft_issues = validate_manual_schedule(
    target_month=target_month,
    assignments=draft_assignments,
)

show_validation_issues(
    draft_issues,
    empty_message="編集案に制約違反や警告はありません。",
)

original_assignments = st.session_state[original_key]

change_df = build_change_dataframe(
    original=original_assignments,
    draft=draft_assignments,
    employee_map=employee_map,
)

st.subheader("変更内容")

if change_df.empty:
    st.info("まだ変更されていません。")
else:
    st.dataframe(
        change_df,
        width="stretch",
        hide_index=True,
    )

has_draft_errors = has_errors(
    draft_issues
)

has_changes = not change_df.empty

save_column, reset_column = st.columns(2)

if save_column.button(
    "手動変更を保存",
    type="primary",
    disabled=(
        has_draft_errors
        or not has_changes
    ),
):
    result = save_manual_schedule(
        target_month=target_month,
        assignments=draft_assignments,
    )

    if result.succeeded:
        st.session_state.pop(
            draft_key,
            None,
        )
        st.session_state.pop(
            original_key,
            None,
        )

        set_flash_message(
            key="manual_schedule_flash",
            message=result.message,
        )

        st.rerun()

    else:
        st.error(result.message)

if reset_column.button(
    "編集案を破棄",
    disabled=not has_changes,
):
    st.session_state.pop(
        draft_key,
        None,
    )

    st.session_state.pop(
        original_key,
        None,
    )

    set_flash_message(
        key="manual_schedule_flash",
        message="編集案を破棄し、保存済みシフトへ戻しました。",
        level="info",
    )

    st.rerun()
