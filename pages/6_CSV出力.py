from __future__ import annotations

from datetime import date

import streamlit as st

from src.db import init_db
from src.export_service import (
    build_export_filename,
    dataframe_to_csv_bytes,
    get_schedule_export_data,
)
from src.repositories import (
    list_schedule_assignments,
)

init_db()

st.set_page_config(
    page_title="CSV出力",
    page_icon="📥",
    layout="wide",
)

st.title("CSV出力")

st.caption(
    "保存済みの月間シフトと"
    "勤務集計をCSV形式で出力します。"
)

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
        key="export_year",
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
        key="export_month",
    )
)

target_month = (
    f"{selected_year:04d}-"
    f"{selected_month:02d}"
)

assignments = list_schedule_assignments(
    target_month
)

if not assignments:
    st.warning(
        "対象月のシフトが"
        "保存されていません。"
        "先にシフト生成画面で"
        "シフトを生成してください。"
    )
    st.stop()

export_data = get_schedule_export_data(
    target_month
)

st.success(
    f"{selected_year}年"
    f"{selected_month}月の"
    f"{len(assignments)}件の配置を"
    "出力できます。"
)

st.divider()
st.subheader("月間シフト表")

st.caption(
    "日付ごとの早番・遅番を"
    "横並びで出力します。"
    "※は手動変更された配置です。"
)

st.dataframe(
    export_data.schedule_table,
    width="stretch",
    hide_index=True,
)

st.download_button(
    label="月間シフト表をダウンロード",
    data=dataframe_to_csv_bytes(
        export_data.schedule_table
    ),
    file_name=build_export_filename(
        target_month=target_month,
        data_type="monthly",
    ),
    mime="text/csv",
    type="primary",
)

st.divider()
st.subheader("配置明細")

st.caption(
    "1件の配置を1行として出力します。"
)

st.dataframe(
    export_data.assignment_detail,
    width="stretch",
    hide_index=True,
)

st.download_button(
    label="配置明細をダウンロード",
    data=dataframe_to_csv_bytes(
        export_data.assignment_detail
    ),
    file_name=build_export_filename(
        target_month=target_month,
        data_type="detail",
    ),
    mime="text/csv",
)

st.divider()
st.subheader("従業員別勤務集計")

st.caption(
    "契約勤務日数との差、"
    "早番・遅番回数、"
    "最大連続勤務日数を出力します。"
)

st.dataframe(
    export_data.employee_summary,
    width="stretch",
    hide_index=True,
)

st.download_button(
    label="勤務集計をダウンロード",
    data=dataframe_to_csv_bytes(
        export_data.employee_summary
    ),
    file_name=build_export_filename(
        target_month=target_month,
        data_type="summary",
    ),
    mime="text/csv",
)