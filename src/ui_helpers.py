from __future__ import annotations

from datetime import date
from typing import Literal

import streamlit as st

from src.models import ValidationIssue


FlashLevel = Literal[
    "success",
    "warning",
    "error",
    "info",
]


def select_target_month(
    *,
    key_prefix: str,
    year_range_before: int = 1,
    year_range_after: int = 2,
) -> tuple[int, int, str]:
    today = date.today()

    year_options = list(
        range(
            today.year - year_range_before,
            today.year + year_range_after + 1,
        )
    )

    year_column, month_column = st.columns(2)

    selected_year = year_column.selectbox(
        "対象年",
        options=year_options,
        index=year_options.index(today.year),
        key=f"{key_prefix}_year",
    )

    selected_month = month_column.selectbox(
        "対象月",
        options=list(range(1, 13)),
        index=today.month - 1,
        format_func=lambda value: f"{value}月",
        key=f"{key_prefix}_month",
    )

    target_month = (
        f"{selected_year:04d}-"
        f"{selected_month:02d}"
    )

    return (
        selected_year,
        selected_month,
        target_month,
    )


def show_validation_issues(
    issues: list[ValidationIssue],
    *,
    empty_message: str = (
        "制約違反や警告はありません。"
    ),
) -> None:
    errors = [
        issue
        for issue in issues
        if issue.severity == "error"
    ]

    warnings = [
        issue
        for issue in issues
        if issue.severity == "warning"
    ]

    if not errors and not warnings:
        st.success(empty_message)
        return

    if errors:
        st.error(
            f"エラーが{len(errors)}件あります。"
        )

        with st.expander(
            "エラーの詳細を表示",
            expanded=True,
        ):
            for issue in errors:
                st.markdown(
                    format_validation_issue(
                        issue
                    )
                )

    if warnings:
        st.warning(
            f"警告が{len(warnings)}件あります。"
        )

        with st.expander(
            "警告の詳細を表示",
        ):
            for issue in warnings:
                st.markdown(
                    format_validation_issue(
                        issue
                    )
                )


def format_validation_issue(
    issue: ValidationIssue,
) -> str:
    """ValidationIssueを画面表示用の文字列に変換する。"""

    details = []

    if issue.target_date is not None:
        details.append(
            issue.target_date.strftime(
                "%Y/%m/%d"
            )
        )

    if issue.shift_type is not None:
        shift_label = {
            "early": "早番",
            "late": "遅番",
        }.get(
            issue.shift_type,
            issue.shift_type,
        )

        details.append(shift_label)

    if issue.employee_id is not None:
        details.append(issue.employee_id)

    detail_text = (
        f"（{'・'.join(details)}）"
        if details
        else ""
    )

    return (
        f"- **{issue.rule_id}**"
        f"{detail_text}："
        f"{issue.message}"
    )


def set_flash_message(
    *,
    key: str,
    message: str,
    level: FlashLevel = "success",
) -> None:
    """次回の再描画後に表示するメッセージを保存する。"""

    st.session_state[key] = {
        "message": message,
        "level": level,
    }


def show_flash_message(
    *,
    key: str,
) -> None:
    """保存済みFlashメッセージを一度だけ表示する。"""

    flash = st.session_state.pop(
        key,
        None,
    )

    if not isinstance(flash, dict):
        return

    message = str(
        flash.get("message", "")
    )

    level = flash.get(
        "level",
        "info",
    )

    if not message:
        return

    if level == "success":
        st.success(message)
    elif level == "warning":
        st.warning(message)
    elif level == "error":
        st.error(message)
    else:
        st.info(message)
