from __future__ import annotations

import base64
from pathlib import Path
import sys
from typing import Dict, Optional

import streamlit as st

if __name__ == "__main__" and __package__ is None:
    current_dir = Path(__file__).resolve().parent
    if str(current_dir) not in sys.path:
        sys.path.append(str(current_dir))

try:
    from .layout import navigation_sidebar, render_page, get_language_dict
except ImportError:
    from layout import navigation_sidebar, render_page, get_language_dict  # type: ignore


LANG_OPTIONS: Dict[str, str] = {
    "fa": "فارسی",
    "en": "English",
}

FONT_CONFIG: Dict[str, Dict[str, Optional[str]]] = {
    "fa": {
        "family": "IranSans",
        "path": "assets/fonts/IRANSansWeb.woff2",
    },
    "en": {
        "family": "Roboto",
        "path": None,
    },
}

FONT_FORMAT_MAP = {
    "woff2": "woff2",
    "woff": "woff",
    "ttf": "truetype",
    "otf": "opentype",
}


def init_language() -> str:
    if "language" not in st.session_state:
        st.session_state.language = "fa"
    return st.session_state.language


def language_switcher() -> str:
    current = init_language()
    left, right = st.columns([0.7, 0.3])
    with right:
        selected = st.selectbox(
            "",
            options=list(LANG_OPTIONS.keys()),
            format_func=lambda key: LANG_OPTIONS[key],
            index=list(LANG_OPTIONS.keys()).index(current),
            label_visibility="collapsed",
        )
    if selected != st.session_state.language:
        st.session_state.language = selected
    return st.session_state.language


def get_font_css(font_family: str, font_path: Optional[Path]) -> str:
    if font_path and font_path.exists():
        encoded = base64.b64encode(font_path.read_bytes()).decode("utf-8")
        suffix = font_path.suffix.lstrip(".").lower() or "woff2"
        font_format = FONT_FORMAT_MAP.get(suffix, "woff2")
        source = f'url("data:font/{suffix};base64,{encoded}") format("{font_format}")'
    else:
        source = ""

    font_face = ""
    if source:
        font_face = f"""
        @font-face {{
            font-family: "{font_family}";
            src: {source};
            font-display: swap;
        }}
        """

    return f"""
    <style>
    {font_face}
    html, body, .stApp, div[data-testid="stAppViewContainer"], .block-container, * {{
        font-family: "{font_family}", sans-serif !important;
    }}
    </style>
    """


def apply_language_font(language: str, dashboard_root: Path) -> None:
    config = FONT_CONFIG.get(language, FONT_CONFIG["fa"])
    font_family = config["family"] or "sans-serif"
    font_path = config.get("path")
    resolved = dashboard_root / font_path if font_path else None

    if resolved and not resolved.exists() and language == "fa":
        with st.sidebar:
            st.warning(f"فونت فارسی با مسیر {resolved.name} پیدا نشد؛ فونت پیش‌فرض استفاده شد.")

    css = get_font_css(font_family, resolved)
    st.markdown(css, unsafe_allow_html=True)


def main() -> None:
    dashboard_root = Path(__file__).resolve().parent
    base_path = dashboard_root.parent

    st.set_page_config(
        page_title="SkyMind Viewer",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    language = language_switcher()
    apply_language_font(language, dashboard_root)

    labels = get_language_dict(language)
    pages = labels["pages"]

    selected_key = navigation_sidebar(pages, labels)
    render_page(selected_key, base_path, labels, language)


if __name__ == "__main__":
    main()
