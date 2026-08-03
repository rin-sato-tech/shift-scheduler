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
from src.ui_helpers import (
    select_target_month,
    show_flash_message,
    set_flash_message,
)


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
        employee = get_employee(request.employee_id)

        rows.append(
            {
                "日付": request.target_date,
                "曜日": (
                    "月火水木金土日"[
                        request.target_date.weekday()
                    ]
                ),
                "従業員ID": request.employee_id,
                "氏名": (
                    employee.name if employee is not None else "不明"
                ),
                "状態": (
                    "有効"
                    if employee is not None and employee.is_active
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


def show_day_off_calendar(
    *,
    selected_year: int,
    selected_month: int,
    employee_id: str,
    registered_dates: set[date],
) -> set[date]:
    """カレンダー形式で希望休の日付を選択する。"""

    state_key = (
        f"selected_day_off_dates_"
        f"{selected_year}_{selected_month}_{employee_id}"
    )

    if state_key not in st.session_state:
        st.session_state[state_key] = set()

    selected_dates: set[date] = st.session_state[state_key]

    st.caption("日付をクリックすると、○（未選択）と×（希望休）が切り替わります。")

    weekday_labels = ["月", "火", "水", "木", "金", "土", "日"]
    weekday_columns = st.columns(7)

    for column, weekday_label in zip(
        weekday_columns,
        weekday_labels,
        strict=True,
    ):
        column.markdown(
            f"<div style='text-align:center; "
            f"font-weight:bold'>{weekday_label}</div>",
            unsafe_allow_html=True,
        )

    month_calendar = calendar.Calendar(
        firstweekday=calendar.MONDAY
    )

    for week_index, week in enumerate(
        month_calendar.monthdayscalendar(
            selected_year,
            selected_month,
        )
    ):
        day_columns = st.columns(7)

        for weekday_index, day_number in enumerate(week):
            column = day_columns[weekday_index]

            if day_number == 0:
                column.write("")
                continue

            target_date = date(
                selected_year,
                selected_month,
                day_number,
            )

            if target_date in registered_dates:
                column.button(
                    f"登録済 ×\n{day_number}",
                    key=(
                        f"registered_day_"
                        f"{employee_id}_{target_date}"
                    ),
                    disabled=True,
                    use_container_width=True,
                )
                continue

            is_selected = target_date in selected_dates
            symbol = "×" if is_selected else "○"

            clicked = column.button(
                f"{symbol}\n{day_number}",
                key=(
                    f"day_off_calendar_"
                    f"{employee_id}_{target_date}"
                ),
                use_container_width=True,
            )

            if clicked:
                if is_selected:
                    selected_dates.remove(target_date)
                else:
                    selected_dates.add(target_date)

                st.session_state[state_key] = selected_dates
                st.rerun()

    return selected_dates


init_db()

st.set_page_config(
    page_title="希望休入力",
    page_icon="📅",
    layout="wide",
)

st.title("希望休入力")
st.caption("従業員ごとの希望休を登録・削除します。")

show_flash_message(key="day_off_flash")

selected_year, selected_month, target_month = (
    select_target_month(key_prefix="day_off")
)

last_day = calendar.monthrange(selected_year, selected_month)[1]

month_start = date(selected_year, selected_month, 1)
month_end = date(selected_year, selected_month, last_day)

employees = list_employees()

active_employees = [
    employee for employee in employees
    if employee.is_active
]

requests = list_day_off_requests(target_month)

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
    st.warning("有効な従業員が登録されていません。")
else:
    employee_options = {
        f"{employee.employee_id}｜{employee.name}": (employee.employee_id)
        for employee in active_employees
    }

    selected_employee_label = st.selectbox(
        "従業員",
        options=list(employee_options.keys()),
        key=f"day_off_employee_{target_month}",
    )

    selected_employee_id = employee_options[
        selected_employee_label
    ]

    employee_requests = list_day_off_requests(
        target_month,
        employee_id=selected_employee_id,
    )

    registered_dates = {
        request.target_date
        for request in employee_requests
    }

    st.markdown("#### 希望休の日付")

    selected_dates = show_day_off_calendar(
        selected_year=selected_year,
        selected_month=selected_month,
        employee_id=selected_employee_id,
        registered_dates=registered_dates,
    )

    if selected_dates:
        selected_date_text = "、".join(
            target_date.strftime("%m月%d日")
            for target_date in sorted(selected_dates)
        )

        st.info(
            f"今回登録する希望休：{selected_date_text}"
        )
    else:
        st.caption("今回登録する日付は選択されていません。")

    create_submitted = st.button(
        "希望休を登録",
        type="primary",
        disabled=not selected_dates,
        key=f"register_day_off_{target_month}_{selected_employee_id}"
    )

    if create_submitted:
        succeeded_dates: list[date] = []
        error_messages: list[str] = []

        for selected_date in sorted(selected_dates):
            result = register_day_off_request(
                employee_id=selected_employee_id,
                target_date=selected_date,
                target_month=target_month,
            )

            if result.succeeded:
                succeeded_dates.append(selected_date)
            else:
                error_messages.append(result.message)

        if error_messages:
            for error_message in error_messages:
                st.error(error_message)

        if succeeded_dates:
            state_key = (
                f"selected_day_off_dates_"
                f"{selected_year}_{selected_month}_"
                f"{selected_employee_id}"
            )
            st.session_state[state_key] = set()

            set_flash_message(
                key="day_off_flash",
                message=(
                    f"{selected_employee_label}の希望休を"
                    f"{len(succeeded_dates)}件登録しました。"
                ),
            )
            st.rerun()

st.divider()

st.subheader("登録済み希望休")

filter_options = {
    "すべて": None,
    **{
        (
            f"{employee.employee_id}｜{employee.name}"
        ): employee.employee_id
        for employee in employees
    },
}

selected_filter_label = st.selectbox(
    "従業員で絞り込み",
    options=list(filter_options.keys()),
)

selected_filter_id = filter_options[selected_filter_label]

request_df = build_request_dataframe(
    target_month,
    employee_id=selected_filter_id,
)

if request_df.empty:
    st.info("対象月の希望休は、まだ登録されていません。")
else:
    st.dataframe(
        request_df,
        width="stretch",
        hide_index=True,
    )

st.markdown("#### 希望休を削除")

requests = list_day_off_requests(target_month)

if not requests:
    st.caption("削除できる希望休はありません。")
else:
    request_options = {}

    for request in requests:
        employee = get_employee(request.employee_id)

        employee_name = employee.name if employee is not None else "不明"

        label = (
            f"{request.target_date:%Y/%m/%d}"
            f"｜{request.employee_id}"
            f"｜{employee_name}"
        )

        request_options[label] = request

    selected_request_label = st.selectbox(
        "削除対象",
        options=list(request_options.keys()),
    )

    selected_request = request_options[selected_request_label]

    if st.button(
        "選択した希望休を削除",
        key=f"delete_day_off_{target_month}"
    ):
        result = remove_day_off_request(
            employee_id=(selected_request.employee_id),
            target_date=(selected_request.target_date),
        )

        if result.succeeded:
            set_flash_message(
                key="day_off_flash",
                message=result.message,
            )
            st.rerun()
        else:
            st.error(result.message)
