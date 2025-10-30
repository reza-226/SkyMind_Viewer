from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict, Optional
import math

import plotly.express as px
import streamlit as st

try:
    from .data_loader import get_sample_paths, load_csv, load_json
    from .widgets.kpi import kpi_card
except ImportError:
    from data_loader import get_sample_paths, load_csv, load_json  # type: ignore
    from widgets.kpi import kpi_card  # type: ignore

_PERSIAN_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")

TRANSLATIONS: Dict[str, Dict[str, Any]] = {
    "fa": {
        "pages": {
            "home": "صفحه اصلی",
            "results": "کاوش نتایج",
            "simulation": "کنترل شبیه‌سازی",
            "strategy": "تشخیص استراتژی",
            "tasks": "تحلیل وظایف",
            "environment": "محیط",
            "registry": "رجیستری",
            "settings": "تنظیمات",
        },
        "sidebar": {
            "title": "SkyMind",
            "navigation": "ناوبری",
            "version": "نسخه MVP داشبورد",
        },
        "home": {
            "title": "SkyMind Viewer",
            "subtitle": "نسخهٔ اولیه داشبورد جهت بررسی سریع خروجی‌ها با ساختار ران‌ها.",
            "kpi_total": "تعداد وظایف",
            "kpi_completed": "وظایف تکمیل‌شده",
            "kpi_energy": "انرژی مصرفی",
            "energy_unit": "کیلوژول",
            "metadata_delta": "از فراداده ران",
            "run_summary": "پیش‌نمایش خلاصه ران",
            "stats_snapshot": "برش وضعیت رصدگر",
            "no_data": "داده‌ای برای نمایش وجود ندارد.",
        },
        "results": {
            "title": "کاوش نتایج",
            "tabs": ["خلاصه", "مسیر و محیط", "انرژی و منابع", "تشخیص استراتژی"],
            "aggregate": "شاخص‌های تجمیعی",
            "trajectory": "پیش‌نمایش مسیر (نمونه)",
            "trajectory_info": "برای نمایش مسیرها نیاز به ادغام فایل‌های GeoJSON یا لاگ‌های موقعیت است.",
            "energy": "پروفایل انرژی",
            "energy_warning": "ستون‌های لازم در tasks.csv یافت نشد.",
            "strategy_info": "لاگ‌های strategyf_core.log اینجا قابل مصورسازی خواهد بود.",
        },
        "simulation": {
            "title": "کنترل شبیه‌سازی",
            "info": "در نسخه MVP فرم صرفاً نمایشی است.",
            "scenario": "سناریو",
            "speed": "ضریب سرعت",
            "tag": "برچسب دلخواه",
            "submit": "اجرای شبیه‌سازی",
            "success": "درخواست ارسال شد (نمونه).",
        },
        "environment": {
            "title": "گزارش‌های محیط",
            "warning": "environment_metrics.log یافت نشد.",
        },
        "registry": {
            "title": "نمای رجیستری",
            "warning": "پوشه registry یافت نشد.",
        },
        "settings": {
            "title": "تنظیمات",
            "dark_mode": "فعال‌سازی حالت تاریک",
            "persist": "ذخیره فیلترها",
            "more": "تنظیمات بیشتر در نسخه‌های بعد اضافه می‌شود.",
        },
        "placeholders": {
            "strategy": "صفحه اختصاصی تحلیل استراتژی در نسخه بعدی اضافه می‌شود.",
            "tasks": "نمودارهای DAG و زمان اتمام وظایف در نسخه بعد در دسترس خواهد بود.",
        },
        "labels": {
            "unknown_page": "صفحه ناشناخته: {page}",
        },
    },
    "en": {
        "pages": {
            "home": "Home",
            "results": "Results Explorer",
            "simulation": "Simulation Control",
            "strategy": "Strategy Diagnostics",
            "tasks": "Tasks Analytics",
            "environment": "Environment",
            "registry": "Registry",
            "settings": "Settings",
        },
        "sidebar": {
            "title": "SkyMind",
            "navigation": "Navigation",
            "version": "Dashboard MVP",
        },
        "home": {
            "title": "SkyMind Viewer",
            "subtitle": "Early dashboard draft for quick inspection of run outputs.",
            "kpi_total": "Total Tasks",
            "kpi_completed": "Completed Tasks",
            "kpi_energy": "Energy Used",
            "energy_unit": "kJ",
            "metadata_delta": "from run metadata",
            "run_summary": "Run Summary Preview",
            "stats_snapshot": "Viewer Stats Snapshot",
            "no_data": "No data available.",
        },
        "results": {
            "title": "Results Explorer",
            "tabs": ["Summary", "Trajectory & Environment", "Energy & Resources", "Strategy Diagnostics"],
            "aggregate": "Aggregate Metrics",
            "trajectory": "Trajectory Snapshot (Placeholder)",
            "trajectory_info": "Trajectory visualization requires GeoJSON merges or position logs.",
            "energy": "Energy Profile",
            "energy_warning": "Required columns missing from tasks.csv.",
            "strategy_info": "strategyf_core.log visualizations will appear here.",
        },
        "simulation": {
            "title": "Simulation Control",
            "info": "Form is informational in this MVP.",
            "scenario": "Scenario",
            "speed": "Speed multiplier",
            "tag": "Custom tag",
            "submit": "Run Simulation",
            "success": "Trigger enqueued (placeholder).",
        },
        "environment": {
            "title": "Environment Logs",
            "warning": "environment_metrics.log not found.",
        },
        "registry": {
            "title": "Registry Overview",
            "warning": "registry directory not found.",
        },
        "settings": {
            "title": "Settings",
            "dark_mode": "Enable dark mode",
            "persist": "Persist filters",
            "more": "More options will follow in later versions.",
        },
        "placeholders": {
            "strategy": "Strategy insights will arrive in a future version.",
            "tasks": "Task DAG analytics are planned for a future release.",
        },
        "labels": {
            "unknown_page": "Unknown page: {page}",
        },
    },
}


def get_language_dict(language: str) -> Dict[str, Any]:
    return TRANSLATIONS.get(language, TRANSLATIONS["fa"])


def format_number(value: Optional[Any], language: str) -> str:
    if value is None:
        return "—"
    try:
        num = float(value)
    except (TypeError, ValueError):
        return str(value)
    if math.isnan(num):
        return "—"
    formatted = f"{num:,.2f}".rstrip("0").rstrip(".")
    if language == "fa":
        return formatted.translate(_PERSIAN_DIGITS)
    return formatted


def to_locale_digits(text: str, language: str) -> str:
    if language == "fa":
        return str(text).translate(_PERSIAN_DIGITS)
    return str(text)


def localize_value(value: Any, language: str) -> str:
    if value is None:
        return "—"
    if isinstance(value, (int, float)):
        return format_number(value, language)
    if isinstance(value, str) and not value:
        return "—"
    return to_locale_digits(value, language)


def localize_dataframe(df, language: str):
    if df is None or getattr(df, "empty", False):
        return df
    if language != "fa":
        return df
    localized = df.copy()
    return localized.applymap(lambda v: localize_value(v, language))


def render_home(base_path: Path, labels: Dict[str, Any], language: str) -> None:
    st.header(labels["home"]["title"])
    st.write(labels["home"]["subtitle"])

    paths = get_sample_paths(base_path)
    results_df = load_csv(paths["results_csv"])
    stats_df = load_csv(paths["viewer_stats"])
    metadata = load_json(paths["run_metadata"])

    cols = st.columns(3)
    total_tasks = metadata.get("tasks_total") if metadata else None
    completed = metadata.get("tasks_completed") if metadata else None
    energy = metadata.get("energy_total_kj") if metadata else None

    with cols[0]:
        kpi_card(labels["home"]["kpi_total"], format_number(total_tasks, language), delta=labels["home"]["metadata_delta"])
    with cols[1]:
        kpi_card(labels["home"]["kpi_completed"], format_number(completed, language))
    with cols[2]:
        energy_text = format_number(energy, language)
        kpi_card(
            labels["home"]["kpi_energy"],
            f"{energy_text} {labels['home']['energy_unit']}" if energy is not None else "—",
        )

    st.subheader(labels["home"]["run_summary"])
    localized_results = localize_dataframe(results_df, language)
    if localized_results is not None and not localized_results.empty:
        st.dataframe(localized_results, use_container_width=True)
    else:
        st.info(labels["home"]["no_data"])

    st.subheader(labels["home"]["stats_snapshot"])
    localized_stats = localize_dataframe(stats_df, language)
    if localized_stats is not None and not localized_stats.empty:
        st.dataframe(localized_stats, use_container_width=True)
    else:
        st.info(labels["home"]["no_data"])


def render_results_tabs(base_path: Path, labels: Dict[str, Any], language: str) -> None:
    st.header(labels["results"]["title"])

    paths = get_sample_paths(base_path)
    results_df = load_csv(paths["results_csv"])
    tasks_df = load_csv(paths["tasks_csv"])

    tab_summary, tab_traj, tab_energy, tab_strategy = st.tabs(labels["results"]["tabs"])

    with tab_summary:
        st.subheader(labels["results"]["aggregate"])
        if results_df is not None and not results_df.empty:
            summary_df = results_df.describe()
            st.dataframe(localize_dataframe(summary_df, language), use_container_width=True)
        else:
            st.info(labels["home"]["no_data"])

    with tab_traj:
        st.subheader(labels["results"]["trajectory"])
        st.info(labels["results"]["trajectory_info"])

    with tab_energy:
        st.subheader(labels["results"]["energy"])
        if tasks_df is not None and {"tick", "energy_kj"} <= set(tasks_df.columns):
            fig = px.line(tasks_df, x="tick", y="energy_kj", title=labels["results"]["energy"])
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning(labels["results"]["energy_warning"])

    with tab_strategy:
        st.subheader(labels["results"]["tabs"][-1])
        st.info(labels["results"]["strategy_info"])


def render_simulation_control(labels: Dict[str, Any], language: str) -> None:
    st.header(labels["simulation"]["title"])
    st.info(labels["simulation"]["info"])
    with st.form("sim_control"):
        st.selectbox(labels["simulation"]["scenario"], options=["demo.yml", "custom.yml"])
        st.slider(labels["simulation"]["speed"], min_value=0.5, max_value=3.0, value=1.0, step=0.5)
        st.text_input(labels["simulation"]["tag"], value="quick-test")
        submitted = st.form_submit_button(labels["simulation"]["submit"])
        if submitted:
            st.success(labels["simulation"]["success"])


def render_environment(base_path: Path, labels: Dict[str, Any], language: str) -> None:
    st.header(labels["environment"]["title"])
    paths = get_sample_paths(base_path)
    env_log_path = paths["environment_log"]
    if env_log_path.exists():
        with env_log_path.open(encoding="utf-8") as handle:
            content = handle.read()
        st.text(content if language == "en" else to_locale_digits(content, language))
    else:
        st.warning(labels["environment"]["warning"])


def render_registry(base_path: Path, labels: Dict[str, Any], language: str) -> None:
    st.header(labels["registry"]["title"])
    registry_dir = base_path / "registry"
    if not registry_dir.exists():
        st.warning(labels["registry"]["warning"])
        return

    for file in registry_dir.rglob("*.*"):
        relative = str(file.relative_to(base_path))
        st.write(to_locale_digits(relative, language))


def render_settings(labels: Dict[str, Any], language: str) -> None:
    st.header(labels["settings"]["title"])
    st.checkbox(labels["settings"]["dark_mode"], value=False)
    st.checkbox(labels["settings"]["persist"], value=True)
    st.write(labels["settings"]["more"])


def render_strategy_placeholder(labels: Dict[str, Any], language: str) -> None:
    st.info(labels["placeholders"]["strategy"])


def render_tasks_placeholder(labels: Dict[str, Any], language: str) -> None:
    st.info(labels["placeholders"]["tasks"])


PAGE_RENDERERS: Dict[str, Callable[[Path, Dict[str, Any], str], None]] = {
    "home": render_home,
    "results": render_results_tabs,
    "environment": render_environment,
    "registry": render_registry,
}

STATIC_RENDERERS: Dict[str, Callable[[Dict[str, Any], str], None]] = {
    "simulation": render_simulation_control,
    "strategy": render_strategy_placeholder,
    "tasks": render_tasks_placeholder,
    "settings": render_settings,
}


def render_page(page_key: str, base_path: Path, labels: Dict[str, Any], language: str) -> None:
    if page_key in PAGE_RENDERERS:
        PAGE_RENDERERS[page_key](base_path, labels, language)
    elif page_key in STATIC_RENDERERS:
        STATIC_RENDERERS[page_key](labels, language)
    else:
        st.error(labels["labels"]["unknown_page"].format(page=page_key))


def navigation_sidebar(page_titles: Dict[str, str], labels: Dict[str, Any]) -> str:
    with st.sidebar:
        st.title(labels["sidebar"]["title"])
        selected = st.radio(
            labels["sidebar"]["navigation"],
            options=list(page_titles.keys()),
            format_func=lambda key: page_titles[key],
        )
        st.markdown("---")
        st.caption(labels["sidebar"]["version"])
    return selected
