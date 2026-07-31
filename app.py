import streamlit as st


st.set_page_config(
    page_title="シフト自動作成",
    page_icon="📅",
    layout="wide",
)

st.title("シフト自動作成デモ")

st.write(
    "従業員情報、希望休、必要人数をもとに、"
    "1か月分のシフトを自動生成するデモアプリです。"
)

st.info("現在はプロジェクト準備段階です。")