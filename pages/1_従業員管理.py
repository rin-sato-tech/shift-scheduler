from __future__ import annotations

import pandas as pd
import streamlit as st

from src.db import init_db
from src.employee_service import (
    change_employee_active_status,
    edit_employee,
    register_employee,
)
from src.repositories import list_employees
from src.ui_helpers import (
    set_flash_message,
    show_flash_message,
)


def build_employee_dataframe() -> pd.DataFrame:
    employees = list_employees()

    rows = [
        {
            "従業員ID": employee.employee_id,
            "氏名": employee.name,
            "責任者": (
                "はい" if employee.is_manager else "いいえ"
            ),
            "契約勤務日数": employee.contract_days,
            "早番": (
                "可" if employee.can_work_early else "不可"
            ),
            "遅番": (
                "可" if employee.can_work_late else "不可"
            ),
            "状態": (
                "有効" if employee.is_active else "無効"
            ),
        }
        for employee in employees
    ]

    return pd.DataFrame(
        rows,
        columns=[
            "従業員ID",
            "氏名",
            "責任者",
            "契約勤務日数",
            "早番",
            "遅番",
            "状態",
        ],
    )


init_db()

st.set_page_config(
    page_title="従業員管理",
    page_icon="👥",
    layout="wide",
)

st.title("従業員管理")
st.caption("従業員の登録、編集、有効状態の変更を行います。")

show_flash_message(key="employee_flash")

employees = list_employees()

active_count = sum(
    employee.is_active
    for employee in employees
)

manager_count = sum(
    employee.is_active and employee.is_manager
    for employee in employees
)

column1, column2, column3 = st.columns(3)
column1.metric(
    "登録従業員数",
    len(employees),
)
column2.metric(
    "有効従業員数",
    active_count,
)
column3.metric(
    "有効責任者数",
    manager_count,
)

st.subheader("従業員一覧")

employee_df = build_employee_dataframe()

if employee_df.empty:
    st.info("従業員はまだ登録されていません。")
else:
    st.dataframe(
        employee_df,
        width="stretch",
        hide_index=True,
    )

st.divider()
st.subheader("新規登録")

with st.form(
    "employee_create_form",
    clear_on_submit=True,
):
    id_column, name_column, contract_days_column = (
        st.columns(3)
    )

    create_id = id_column.text_input(
        "従業員ID",
        max_chars=30,
        placeholder="例：E001",
    )

    create_name = name_column.text_input(
        "氏名",
        max_chars=50,
        placeholder="例：山田太郎",
    )

    create_contract_days = (
        contract_days_column.number_input(
            "月間契約勤務日数",
            min_value=0,
            max_value=31,
            value=20,
            step=1,
        )
    )

    create_is_manager = st.checkbox("責任者として扱う")

    shift_column1, shift_column2 = (
        st.columns(2)
    )

    create_can_work_early = (
        shift_column1.checkbox(
            "早番勤務可能",
            value=True,
            key="create_can_work_early",
        )
    )

    create_can_work_late = (
        shift_column2.checkbox(
            "遅番勤務可能",
            value=True,
            key="create_can_work_late",
        )
    )

    create_submitted = (
        st.form_submit_button(
            "従業員を登録",
            type="primary",
        )
    )

if create_submitted:
    result = register_employee(
        employee_id=create_id,
        name=create_name,
        is_manager=create_is_manager,
        contract_days=int(create_contract_days),
        can_work_early=(create_can_work_early),
        can_work_late=(create_can_work_late),
    )

    if result.succeeded:
        set_flash_message(
            key="employee_flash",
            message=result.message,
        )
        st.rerun()
    else:
        st.error(result.message)

st.divider()
st.subheader("編集・状態変更")

employees = list_employees()

if not employees:
    st.info("編集対象の従業員がいません。")
    st.stop()

employee_options = {
    (
        f"{employee.employee_id}"
        f"｜{employee.name}"
        f"｜"
        f"{'有効' if employee.is_active else '無効'}"
    ): employee
    for employee in employees
}

selected_label = st.selectbox(
    "編集対象",
    options=list(employee_options.keys()),
)

selected_employee = employee_options[selected_label]

with st.form(
    key=f"employee_edit_form_{selected_employee.employee_id}"
):
    id_column, name_column, contract_days_column = (
        st.columns(3)
    )

    id_column.text_input(
        "従業員ID",
        value=selected_employee.employee_id,
        disabled=True,
    )

    edit_name = name_column.text_input(
        "氏名",
        value=selected_employee.name,
        max_chars=50,
    )

    edit_contract_days = (
        contract_days_column.number_input(
            "月間契約勤務日数",
            min_value=0,
            max_value=31,
            value=selected_employee.contract_days,
            step=1,
        )
    )

    edit_is_manager = st.checkbox(
        "責任者として扱う",
        value=selected_employee.is_manager,
    )

    edit_column1, edit_column2 = (
        st.columns(2)
    )

    edit_can_work_early = (
        edit_column1.checkbox(
            "早番勤務可能",
            value=selected_employee.can_work_early,
        )
    )

    edit_can_work_late = (
        edit_column2.checkbox(
            "遅番勤務可能",
            value=selected_employee.can_work_late,
        )
    )

    edit_submitted = (
        st.form_submit_button(
            "変更を保存",
            type="primary",
        )
    )

if edit_submitted:
    result = edit_employee(
        employee_id=selected_employee.employee_id,
        name=edit_name,
        is_manager=edit_is_manager,
        contract_days=int(edit_contract_days),
        can_work_early=edit_can_work_early,
        can_work_late=edit_can_work_late,
    )

    if result.succeeded:
        set_flash_message(
            key="employee_flash",
            message=result.message,
        )
        st.rerun()
    else:
        st.error(result.message)

st.markdown("#### 有効状態")

current_status = (
    "有効" if selected_employee.is_active else "無効"
)

st.write(f"現在の状態：**{current_status}**")

if selected_employee.is_active:
    st.warning(
        "無効化すると、以後の自動生成対象から除外されます。"
        "既存シフトは自動では削除されません。"
    )

    if st.button(
        "この従業員を無効化",
        type="secondary",
        key=f"deactivate_{selected_employee.employee_id}",
    ):
        result = (
            change_employee_active_status(
                employee_id=selected_employee.employee_id,
                is_active=False,
            )
        )

        set_flash_message(
            key="employee_flash",
            message=result.message,
            level="success" if result.succeeded else "error",
        )
        st.rerun()

else:
    if st.button(
        "この従業員を再有効化",
        type="primary",
        key=f"activate_{selected_employee.employee_id}",
    ):
        result = (
            change_employee_active_status(
                employee_id=selected_employee.employee_id,
                is_active=True,
            )
        )

        set_flash_message(
            key="employee_flash",
            message=result.message,
            level="success" if result.succeeded else "error",
        )
        st.rerun()
