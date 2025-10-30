from pathlib import Path

import streamlit as st


def run(base_path: Path) -> None:
    st.header("Strategy Diagnostics")
    st.info("جایگزین با نمودارهای مرتبط با استراتژی در نسخه بعد.")
