from __future__ import annotations

import calendar
from datetime import date

import pandas as pd
import streamlit as st

from src.day_off_service import (
    register_day_off_request,
    remove_day_off_request,
)
from src.db import init_db
from src.repositories import (
    get_employee,
    list_day_off_requests,
    list_employees,
)


MESSAGE_KEY = "day_off_operation_message"
MESSAGE_TYPE_KEY = (
    "day_off_operation_message_type"
)


def set_operation_message(
    message: str,
    *,
    succeeded: bool,
) -> None:
    st.session_state[MESSAGE_KEY] = message
    st.session_state[MESSAGE_TYPE_KEY] = (
        "success"
        if succeeded
        else "error"
    )


def show_operation_message() -> None:
    message = st.session_state.pop(
        MESSAGE_KEY,
        None,
    )
    message_type = st.session_state.pop(
        MESSAGE_TYPE_KEY,
        None,
    )

    if message is None:
        return

    if message_type == "success":
        st.success(message)
    else:
        st.error(message)


def build_request_dataframe(
    target_month: str,
    *,
    employee_id: str | None = None,
) -> pd.DataFrame:
    requests = list_day_off_requests(
        target_month,
        employee_id=employee_id,
    )

    rows = []

    for request in requests:
        employee = get_employee(
            request.employee_id
        )

        rows.append(
            {
                "日付": request.target_date,
                "曜日": (
                    "月火水木金土日"[
                        request.target_date.weekday()
                    ]
                ),
                "従業員ID": (
                    request.employee_id
                ),
                "氏名": (
                    employee.name
                    if employee is not None
                    else "不明"
                ),
                "状態": (
                    "有効"
                    if (
                        employee is not None
                        and employee.is_active
                    )
                    else "無効"
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
            "状態",
        ],
    )


init_db()

st.set_page_config(
    page_title="希望休入力",
    page_icon="📅",
    layout="wide",
)

st.title("希望休入力")

st.caption(
    "従業員ごとの希望休を登録・削除します。"
)

show_operation_message()

today = date.today()

month_column1, month_column2 = (
    st.columns(2)
)

year_options = list(
    range(
        today.year - 1,
        today.year + 3,
    )
)

selected_year = (
    month_column1.selectbox(
        "対象年",
        options=year_options,
        index=year_options.index(
            today.year
        ),
    )
)

selected_month = (
    month_column2.selectbox(
        "対象月",
        options=list(range(1, 13)),
        index=today.month - 1,
        format_func=lambda value: (
            f"{value}月"
        ),
    )
)

target_month = (
    f"{selected_year:04d}-"
    f"{selected_month:02d}"
)

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

employees = list_employees()

active_employees = [
    employee
    for employee in employees
    if employee.is_active
]

requests = list_day_off_requests(
    target_month
)

request_employee_ids = {
    request.employee_id
    for request in requests
}

metric1, metric2, metric3 = st.columns(3)

metric1.metric(
    "有効従業員数",
    len(active_employees),
)

metric2.metric(
    "希望休登録件数",
    len(requests),
)

metric3.metric(
    "登録済み従業員数",
    len(request_employee_ids),
)

st.divider()
st.subheader("希望休を登録")

if not active_employees:
    st.warning(
        "有効な従業員が登録されていません。"
    )
else:
    employee_options = {
        (
            f"{employee.employee_id}"
            f"｜{employee.name}"
        ): employee.employee_id
        for employee in active_employees
    }

    with st.form(
        key=(
            "day_off_create_form_"
            f"{target_month}"
        )
    ):
        selected_employee_label = (
            st.selectbox(
                "従業員",
                options=list(
                    employee_options.keys()
                ),
            )
        )

        selected_date = st.date_input(
            "希望休の日付",
            value=month_start,
            min_value=month_start,
            max_value=month_end,
            format="YYYY/MM/DD",
            key=(
                "day_off_date_"
                f"{target_month}"
            ),
        )

        create_submitted = (
            st.form_submit_button(
                "希望休を登録",
                type="primary",
            )
        )

    if create_submitted:
        employee_id = employee_options[
            selected_employee_label
        ]

        result = register_day_off_request(
            employee_id=employee_id,
            target_date=selected_date,
            target_month=target_month,
        )

        if result.succeeded:
            set_operation_message(
                result.message,
                succeeded=True,
            )
            st.rerun()
        else:
            st.error(result.message)

st.divider()
st.subheader("登録済み希望休")

filter_options = {
    "すべて": None,
    **{
        (
            f"{employee.employee_id}"
            f"｜{employee.name}"
        ): employee.employee_id
        for employee in employees
    },
}

selected_filter_label = st.selectbox(
    "従業員で絞り込み",
    options=list(filter_options.keys()),
)

selected_filter_id = filter_options[
    selected_filter_label
]

request_df = build_request_dataframe(
    target_month,
    employee_id=selected_filter_id,
)

if request_df.empty:
    st.info(
        "対象月の希望休は"
        "まだ登録されていません。"
    )
else:
    st.dataframe(
        request_df,
        width="stretch",
        hide_index=True,
    )

st.markdown("#### 希望休を削除")

requests = list_day_off_requests(
    target_month
)

if not requests:
    st.caption(
        "削除できる希望休はありません。"
    )
else:
    request_options = {}

    for request in requests:
        employee = get_employee(
            request.employee_id
        )

        employee_name = (
            employee.name
            if employee is not None
            else "不明"
        )

        label = (
            f"{request.target_date:%Y/%m/%d}"
            f"｜{request.employee_id}"
            f"｜{employee_name}"
        )

        request_options[label] = request

    selected_request_label = st.selectbox(
        "削除対象",
        options=list(
            request_options.keys()
        ),
    )

    selected_request = request_options[
        selected_request_label
    ]

    if st.button(
        "選択した希望休を削除",
        key=(
            "delete_day_off_"
            f"{target_month}"
        ),
    ):
        result = remove_day_off_request(
            employee_id=(
                selected_request.employee_id
            ),
            target_date=(
                selected_request.target_date
            ),
        )

        if result.succeeded:
            set_operation_message(
                result.message,
                succeeded=True,
            )
            st.rerun()
        else:
            st.error(result.message)