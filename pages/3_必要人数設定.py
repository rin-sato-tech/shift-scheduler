from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from src.db import init_db
from src.models import StaffingRequirement
from src.staffing_service import (
    get_complete_month_requirements,
    save_month_staffing_requirements,
)


MESSAGE_KEY = (
    "staffing_operation_message"
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
}


def set_operation_message(
    message: str,
) -> None:
    st.session_state[
        MESSAGE_KEY
    ] = message


def show_operation_message() -> None:
    message = st.session_state.pop(
        MESSAGE_KEY,
        None,
    )

    if message is not None:
        st.success(message)


def build_staffing_dataframe(
    target_month: str,
) -> pd.DataFrame:
    requirements = (
        get_complete_month_requirements(
            target_month
        )
    )

    override = st.session_state.get(
        f"staffing_override_{target_month}"
    )

    rows = []

    for requirement in requirements:
        required_count = (
            requirement.required_count
        )
        manager_count = (
            requirement
            .required_manager_count
        )

        if override is not None:
            required_count = override[
                "required_count"
            ]
            manager_count = override[
                "required_manager_count"
            ]

        rows.append(
            {
                "日付": requirement.target_date,
                "曜日": WEEKDAY_LABELS[
                    requirement
                    .target_date
                    .weekday()
                ],
                "シフト": SHIFT_LABELS[
                    requirement.shift_type
                ],
                "シフトコード": (
                    requirement.shift_type
                ),
                "必要人数": required_count,
                "必要責任者数": (
                    manager_count
                ),
            }
        )

    return pd.DataFrame(rows)


def dataframe_to_requirements(
    dataframe: pd.DataFrame,
) -> list[StaffingRequirement]:
    requirements = []

    for row in dataframe.to_dict(
        orient="records"
    ):
        target_date = row["日付"]

        if isinstance(
            target_date,
            pd.Timestamp,
        ):
            target_date = target_date.date()

        requirements.append(
            StaffingRequirement(
                target_date=target_date,
                shift_type=(
                    row["シフトコード"]
                ),
                required_count=int(
                    row["必要人数"]
                ),
                required_manager_count=int(
                    row["必要責任者数"]
                ),
            )
        )

    return requirements


init_db()

st.set_page_config(
    page_title="必要人数設定",
    page_icon="🧑‍🤝‍🧑",
    layout="wide",
)

st.title("必要人数設定")

st.caption(
    "日付・シフトごとの必要人数と"
    "必要責任者数を設定します。"
)

show_operation_message()

today = date.today()

year_options = list(
    range(
        today.year - 1,
        today.year + 3,
    )
)

year_column, month_column = (
    st.columns(2)
)

selected_year = (
    year_column.selectbox(
        "対象年",
        options=year_options,
        index=year_options.index(
            today.year
        ),
    )
)

selected_month = (
    month_column.selectbox(
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

st.divider()
st.subheader("一括設定")

bulk_column1, bulk_column2 = (
    st.columns(2)
)

bulk_required_count = (
    bulk_column1.number_input(
        "全シフトの必要人数",
        min_value=0,
        max_value=20,
        value=2,
        step=1,
    )
)

bulk_manager_count = (
    bulk_column2.number_input(
        "全シフトの必要責任者数",
        min_value=0,
        max_value=20,
        value=1,
        step=1,
    )
)

if st.button(
    "表全体に一括反映"
):
    if (
        bulk_manager_count
        > bulk_required_count
    ):
        st.error(
            "必要責任者数は"
            "必要人数以下にしてください。"
        )
    else:
        st.session_state[
            f"staffing_override_"
            f"{target_month}"
        ] = {
            "required_count": int(
                bulk_required_count
            ),
            "required_manager_count": int(
                bulk_manager_count
            ),
        }

        st.session_state.pop(
            f"staffing_editor_"
            f"{target_month}",
            None,
        )

        st.rerun()

staffing_df = build_staffing_dataframe(
    target_month
)

st.divider()
st.subheader("日付・シフト別設定")

edited_df = st.data_editor(
    staffing_df,
    width="stretch",
    hide_index=True,
    num_rows="fixed",
    disabled=[
        "日付",
        "曜日",
        "シフト",
        "シフトコード",
    ],
    column_config={
        "日付": st.column_config.DateColumn(
            "日付",
            format="YYYY/MM/DD",
        ),
        "曜日": st.column_config.TextColumn(
            "曜日",
            width="small",
        ),
        "シフト": st.column_config.TextColumn(
            "シフト",
            width="small",
        ),
        "シフトコード": None,
        "必要人数": (
            st.column_config.NumberColumn(
                "必要人数",
                min_value=0,
                max_value=20,
                step=1,
                required=True,
            )
        ),
        "必要責任者数": (
            st.column_config.NumberColumn(
                "必要責任者数",
                min_value=0,
                max_value=20,
                step=1,
                required=True,
            )
        ),
    },
    key=f"staffing_editor_{target_month}",
)

invalid_rows = edited_df[
    edited_df["必要責任者数"]
    > edited_df["必要人数"]
]

if not invalid_rows.empty:
    st.error(
        f"{len(invalid_rows)}件で"
        "必要責任者数が必要人数を"
        "超えています。"
    )

total_required = int(
    edited_df["必要人数"].sum()
)

total_manager_required = int(
    edited_df[
        "必要責任者数"
    ].sum()
)

maximum_required = int(
    edited_df["必要人数"].max()
)

metric1, metric2, metric3 = (
    st.columns(3)
)

metric1.metric(
    "月間必要勤務枠",
    total_required,
)

metric2.metric(
    "月間責任者枠",
    total_manager_required,
)

metric3.metric(
    "1シフト最大人数",
    maximum_required,
)

button_column1, button_column2 = (
    st.columns(2)
)

if button_column1.button(
    "必要人数設定を保存",
    type="primary",
    disabled=not invalid_rows.empty,
):
    requirements = (
        dataframe_to_requirements(
            edited_df
        )
    )

    result = (
        save_month_staffing_requirements(
            target_month=target_month,
            requirements=requirements,
        )
    )

    if result.succeeded:
        st.session_state.pop(
            f"staffing_override_"
            f"{target_month}",
            None,
        )

        st.session_state.pop(
            f"staffing_editor_"
            f"{target_month}",
            None,
        )

        set_operation_message(
            result.message
        )
        st.rerun()

    else:
        st.error(result.message)

if button_column2.button(
    "保存済みの内容に戻す"
):
    st.session_state.pop(
        f"staffing_override_"
        f"{target_month}",
        None,
    )

    st.session_state.pop(
        f"staffing_editor_"
        f"{target_month}",
        None,
    )

    st.rerun()