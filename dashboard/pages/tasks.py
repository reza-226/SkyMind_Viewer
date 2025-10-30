from pathlib import Path

import streamlit as st


def run(base_path: Path) -> None:
    st.header("Tasks Analytics")
    st.info("نمایش DAG و آمار تکمیل وظایف در نسخه بعد کامل می‌شود.")
