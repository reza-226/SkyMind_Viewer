from typing import Optional

import streamlit as st


def kpi_card(label: str, value: Optional[str], delta: Optional[str] = None) -> None:
    with st.container(border=True):
        st.markdown(f"**{label}**")
        if value is None:
            st.write("—")
        else:
            st.write(value)
        if delta:
            st.caption(delta)
