# hud_viewer_streamlit.py
# Streamlit HUD Viewer with:
# - Persian/RTL UI
# - Robust font system (Embedded > Local > System)
# - Plotly template synced with Streamlit theme
# - KPI, time-range filtering
# - Charts with unique keys
# - Slideshow view (single chart per slide) with auto-advance

from __future__ import annotations

import os
import io
import re
import time
import base64
from pathlib import Path
from typing import Dict, List, Tuple, Optional

import numpy as np
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio

# ------------------------------------------------------------------------------------
# Page config
# ------------------------------------------------------------------------------------
st.set_page_config(
    page_title="HUD Viewer",
    page_icon="🛩️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ------------------------------------------------------------------------------------
# Query params utils
# ------------------------------------------------------------------------------------
def get_query_params() -> Dict[str, List[str]]:
    try:
        return dict(st.query_params)
    except Exception:
        return st.experimental_get_query_params() or {}

def set_query_params(**kwargs):
    try:
        st.query_params.clear()
        for k, v in kwargs.items():
            if v is None:
                continue
            st.query_params[k] = v
    except Exception:
        st.experimental_set_query_params(**{k: v for k, v in kwargs.items() if v is not None})

# ------------------------------------------------------------------------------------
# RTL + CSS
# ------------------------------------------------------------------------------------
def inject_rtl_css():
    css = """
    <style>
    html, body, [data-testid="stAppViewContainer"] { direction: rtl !important; }
    .st-emotion-cache-ue6h4q, .stText, .stMarkdown, .stMetric, .stSelectbox, .stSlider, .stButton { text-align: right !important; }
    .js-plotly-plot .plotly .gtitle { direction: rtl; }
    .js-plotly-plot .plotly .g-xtitle, .js-plotly-plot .plotly .g-ytitle { direction: rtl; }
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)

# ------------------------------------------------------------------------------------
# Font management
# ------------------------------------------------------------------------------------
FONT_EXTS = (".woff2", ".woff", ".ttf", ".otf")

def _weight_from_name(name: str) -> int:
    n = name.lower()
    if "100" in n or "thin" in n: return 100
    if "200" in n or "extralight" in n or "ultralight" in n: return 200
    if "300" in n or "light" in n: return 300
    if "500" in n or "medium" in n: return 500
    if "600" in n or "semibold" in n or "demibold" in n: return 600
    if "700" in n or "bold" in n: return 700
    if "800" in n or "extrabold" in n or "ultrabold" in n: return 800
    if "900" in n or "black" in n: return 900
    return 400

def _variant_key(stem: str) -> Tuple[str, int, str]:
    s = stem.lower()
    italic = "italic" in s or "oblique" in s or s.endswith("i")
    style = "italic" if italic else "normal"
    w = _weight_from_name(stem)
    label_map = {100:"Thin",200:"ExtraLight",300:"Light",400:"Regular",500:"Medium",600:"SemiBold",700:"Bold",800:"ExtraBold",900:"Black"}
    label = label_map.get(w, "Regular") + ("-Italic" if italic else "")
    return label, w, style

def _encode_file_to_dataurl(path: Path) -> str:
    fmt = path.suffix.lower().lstrip(".")
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("ascii")
    return f"data:font/{fmt};base64,{b64}"

def _collect_local_fonts() -> Dict[str, Dict[str, Dict[str, str]]]:
    search_dirs: List[Path] = []
    env_dir = os.getenv("SKYMIND_FONT_DIR")
    if env_dir:
        for part in env_dir.split(os.pathsep):
            p = Path(part.strip())
            if p.exists():
                search_dirs.append(p)
    for d in ["assets/fonts", "fonts", "static/fonts"]:
        p = Path(d)
        if p.exists():
            search_dirs.append(p)

    result: Dict[str, Dict[str, Dict[str, str]]] = {}
    for root in search_dirs:
        subs = [d for d in root.iterdir() if d.is_dir()]
        families = subs if subs else [root]

        for fam_dir in families:
            fam = fam_dir.name
            files = [p for p in fam_dir.rglob("*") if p.is_file() and p.suffix.lower() in FONT_EXTS]
            if not files:
                continue
            for p in files:
                key, weight, style = _variant_key(p.stem)
                fmt = p.suffix.lower().lstrip(".")
                try:
                    dataurl = _encode_file_to_dataurl(p)
                except Exception:
                    continue
                result.setdefault(fam, {})
                result[fam].setdefault(key, {})
                result[fam][key][fmt] = dataurl
                result[fam][key].setdefault("_meta_weight", str(weight))
                result[fam][key].setdefault("_meta_style", style)
    return result

def _load_embedded_fonts() -> Dict[str, Dict[str, Dict[str, str]]]:
    try:
        from tools.embedded_fonts import EMBEDDED_FONTS  # type: ignore
        enriched: Dict[str, Dict[str, Dict[str, str]]] = {}
        for fam, variants in EMBEDDED_FONTS.items():
            enriched[fam] = {}
            for vkey, fmts in variants.items():
                weight = 400
                style = "italic" if "italic" in vkey.lower() else "normal"
                m = re.search(r"(thin|100|extralight|200|light|300|regular|400|medium|500|semibold|600|bold|700|extrabold|800|black|900)", vkey, re.I)
                if m:
                    weight = _weight_from_name(m.group(1))
                enriched[fam][vkey] = dict(fmts)
                enriched[fam][vkey]["_meta_weight"] = str(weight)
                enriched[fam][vkey]["_meta_style"] = style
        return enriched
    except Exception:
        return {}

def build_font_css(family: str, source: str, fonts_map: Dict[str, Dict[str, Dict[str, str]]]) -> str:
    if family not in fonts_map:
        return ""
    rules = []
    for vkey, fmts in fonts_map[family].items():
        if not isinstance(fmts, dict):
            continue
        weight = fmts.get("_meta_weight", "400")
        style = fmts.get("_meta_style", "normal")
        src_parts = []
        for fmt in ["woff2", "woff", "ttf", "otf"]:
            if fmt in fmts:
                src_parts.append(f"url('{fmts[fmt]}') format('{fmt}')")
        if not src_parts:
            continue
        rule = f"""
        @font-face {{
            font-family: '{family}';
            src: {", ".join(src_parts)};
            font-weight: {weight};
            font-style: {style};
            font-display: swap;
        }}
        """
        rules.append(rule)

    body_css = f"""
    :root {{ --app-font: '{family}', 'Vazirmatn','IRANSans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, 'Noto Sans', 'Liberation Sans', sans-serif; }}
    html, body, [data-testid="stAppViewContainer"] * {{
        font-family: var(--app-font) !important;
        letter-spacing: 0.1px;
    }}
    """
    return "<style>\n" + "\n".join(rules) + "\n" + body_css + "\n</style>"

def apply_fonts() -> Tuple[str, str]:
    qp = get_query_params()
    url_font = None
    if "font" in qp and qp["font"]:
        url_font = qp["font"][0] if isinstance(qp["font"], list) else qp["font"]

    embedded = _load_embedded_fonts()
    local = _collect_local_fonts()

    candidate_family = url_font

    if candidate_family and candidate_family in embedded:
        st.markdown(build_font_css(candidate_family, "Embedded", embedded), unsafe_allow_html=True)
        return candidate_family, "Embedded"
    if candidate_family and candidate_family in local:
        st.markdown(build_font_css(candidate_family, "Local", local), unsafe_allow_html=True)
        return candidate_family, "Local"

    if embedded:
        fam = sorted(embedded.keys())[0]
        st.markdown(build_font_css(fam, "Embedded", embedded), unsafe_allow_html=True)
        return fam, "Embedded"
    if local:
        fam = sorted(local.keys())[0]
        st.markdown(build_font_css(fam, "Local", local), unsafe_allow_html=True)
        return fam, "Local"

    st.markdown("""
    <style>
    :root{ --app-font: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, 'Noto Sans', 'Liberation Sans', sans-serif; }
    html, body, [data-testid="stAppViewContainer"] * { font-family: var(--app-font) !important; }
    </style>
    """, unsafe_allow_html=True)
    return "System", "System"

# ------------------------------------------------------------------------------------
# Plotly template synced with Streamlit theme
# ------------------------------------------------------------------------------------
def get_theme_opt(key: str, default: Optional[str] = None) -> Optional[str]:
    try:
        return st.get_option(f"theme.{key}") or default
    except Exception:
        return default

def install_plotly_template(font_family: str):
    primary = get_theme_opt("primaryColor", "#2c7be5")
    bg = get_theme_opt("backgroundColor", "white")
    text = get_theme_opt("textColor", "#31333F")
    grid = "#E6E6E6"

    template = go.layout.Template(
        layout=go.Layout(
            font=dict(family=font_family, size=13, color=text),
            paper_bgcolor=bg,
            plot_bgcolor=bg,
            colorway=[primary, "#00A7B3", "#FF7A59", "#7C69EF", "#2EC4B6", "#FF9F1C", "#E71D36", "#8D99AE"],
            xaxis=dict(gridcolor=grid, zerolinecolor=grid, linecolor="#C8C8C8", ticks="outside"),
            yaxis=dict(gridcolor=grid, zerolinecolor=grid, linecolor="#C8C8C8", ticks="outside"),
            legend=dict(bgcolor=bg, orientation="h", yanchor="bottom", y=1.02, x=0),
            margin=dict(l=40, r=20, t=50, b=40),
        )
    )
    pio.templates["skymind"] = template
    pio.templates.default = "plotly_white+skymind"

# ------------------------------------------------------------------------------------
# Slideshow auto-refresh counter
# ------------------------------------------------------------------------------------
def slideshow_counter(interval_sec: float, key: str = "slideshow_timer") -> int:
    """
    Returns an incrementing counter at the given interval. Uses streamlit-autorefresh
    if available; otherwise falls back to st.rerun on a timer.
    """
    try:
        from streamlit_autorefresh import st_autorefresh  # type: ignore
        cnt = st_autorefresh(interval=int(interval_sec * 1000), key=key)
        return int(cnt or 0)
    except Exception:
        now = time.time()
        next_key = f"{key}_next"
        count_key = f"{key}_count"
        nxt = st.session_state.get(next_key, now + interval_sec)
        if now >= nxt:
            st.session_state[next_key] = now + interval_sec
            st.session_state[count_key] = st.session_state.get(count_key, 0) + 1
            try:
                st.rerun()
            except Exception:
                st.experimental_rerun()
        return int(st.session_state.get(count_key, 0))

# ------------------------------------------------------------------------------------
# Data helpers
# ------------------------------------------------------------------------------------
TIME_COL_CANDIDATES = ["time", "timestamp", "datetime", "date", "t", "Time", "Timestamp", "DateTime"]

def parse_csv(file: io.BytesIO) -> pd.DataFrame:
    """
    Robust CSV reader:
    - Tries multiple encodings.
    - Lets pandas infer the separator.
    - If still single-column, tries a set of separators and picks the best (max columns).
    - Falls back to regex [,\s;|]+ to handle mixed comma/space.
    """
    raw = file.read()
    text = None
    for enc in ("utf-8", "utf-8-sig", "cp1256", "latin1"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        text = raw.decode("utf-8", errors="ignore")
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # 1) Let pandas infer sep
    buf = io.StringIO(text)
    df = pd.DataFrame()
    try:
        df = pd.read_csv(buf, sep=None, engine="python")
    except Exception:
        pass

    # 2) If single column, try candidates and pick the widest
    if df.empty or df.shape[1] == 1:
        best_df, best_cols = None, 0
        for sep in [",", ";", "\t", "|", r"\s+", r"[,\s;|]+"]:
            try:
                trial = pd.read_csv(io.StringIO(text), sep=sep, engine="python")
                if trial.shape[1] > best_cols:
                    best_df, best_cols = trial, trial.shape[1]
            except Exception:
                continue
        if best_df is not None:
            df = best_df

    # 3) If header itself looks concatenated, re-parse with regex
    if df.shape[1] == 1 and (("," in df.columns[0]) or (" " in df.columns[0])):
        df = pd.read_csv(io.StringIO(text), sep=r"[,\s;|]+", engine="python")

    # Clean headers
    df.columns = [str(c).strip() for c in df.columns]

    # Convert object-like numerics
    for c in list(df.columns):
        s = df[c]
        if s.dtype == object:
            try:
                s2 = s.astype(str).str.replace("%", "", regex=False).str.replace("٪", "", regex=False)
                df[c] = pd.to_numeric(s2, errors="ignore")
            except Exception:
                pass
    return df

def ensure_time(df: pd.DataFrame) -> Tuple[pd.DataFrame, Optional[str]]:
    col = None
    for c in df.columns:
        if c in TIME_COL_CANDIDATES or c.lower() in [x.lower() for x in TIME_COL_CANDIDATES]:
            col = c
            break
    if col is None:
        for c in df.columns:
            if re.search(r"(time|sec|millis|ms)", c, re.I):
                col = c
                break
    if col is None:
        return df, None

    s = df[col]
    if pd.api.types.is_numeric_dtype(s):
        base = pd.to_datetime("1970-01-01")
        try:
            if s.max() > 1e12:
                t = pd.to_datetime(s, unit="ms")
            elif s.max() > 1e9:
                t = pd.to_datetime(s, unit="s")
            else:
                t = base + pd.to_timedelta(s - s.min(), unit="s")
        except Exception:
            t = base + pd.to_timedelta(np.arange(len(s)), unit="s")
        df = df.copy()
        df["__time__"] = t
        return df, "__time__"
    else:
        try:
            t = pd.to_datetime(s, errors="coerce")
            if t.notna().mean() > 0.7:
                df = df.copy()
                df["__time__"] = t
                return df, "__time__"
        except Exception:
            pass
    return df, None

def pick_columns(df: pd.DataFrame) -> Dict[str, str]:
    """
    Map expected signals to available columns.
    """
    colmap: Dict[str, str] = {}
    name_pairs = {
        "altitude": [r"alt", r"altitude", r"height", r"asl", r"baro", r"pos_z", r"\bz\b"],
        "speed": [r"speed", r"spd", r"airspeed", r"gs", r"velocity", r"speed_mps"],
        "pitch": [r"pitch", r"theta"],
        "roll": [r"roll", r"phi"],
        "yaw": [r"yaw", r"heading", r"psi", r"hdg"],
        "battery": [r"battery", r"batt", r"battery_pct", r"soc"],
    }
    for alias, patterns in name_pairs.items():
        for ptn in patterns:
            for c in df.columns:
                if re.fullmatch(ptn, c, re.I) or re.search(rf"\b{ptn}\b", c, re.I):
                    if pd.api.types.is_numeric_dtype(df[c]) or pd.api.types.is_integer_dtype(df[c]) or pd.api.types.is_float_dtype(df[c]):
                        colmap[alias] = c
                        break
            if alias in colmap:
                break
    return colmap

# ------------------------------------------------------------------------------------
# UI setup
# ------------------------------------------------------------------------------------
inject_rtl_css()
font_family, font_src = apply_fonts()
install_plotly_template(font_family)

st.sidebar.markdown("### تنظیمات نمایش")
st.sidebar.caption(f"fonts: {font_family} ({font_src})")

uploaded = st.sidebar.file_uploader("فایل CSV را اینجا بیندازید", type=["csv"], accept_multiple_files=False)

view_mode = st.sidebar.radio("حالت نمایش نمودار", options=["شبکه‌ای", "اسلایدشو"], index=1, help="در حالت اسلایدشو، هر بار یک نمودار نمایش داده می‌شود.")

# Slideshow controls
pause = st.sidebar.toggle("توقف اسلایدشو", value=False)
interval_sec = st.sidebar.slider("فاصله زمانی اسلایدها (ثانیه)", min_value=2, max_value=10, value=3, step=1)

st.sidebar.markdown("---")
st.sidebar.markdown("### KPI")
kpi_count = st.sidebar.selectbox("تعداد KPI در سطر", options=[1, 2, 3, 4], index=2)

# ------------------------------------------------------------------------------------
# Main area
# ------------------------------------------------------------------------------------
st.title("نمایشگر HUD / تحلیل پرواز")

if uploaded is None:
    st.info("برای شروع، یک فایل CSV بارگذاری کنید.")
    st.stop()

try:
    df = parse_csv(uploaded)
except Exception as e:
    st.error(f"خواندن فایل ناموفق بود: {e}")
    st.stop()

# Normalize column names
df.columns = [str(c).strip() for c in df.columns]

# Detect time
df, time_col = ensure_time(df)

# Determine numeric columns (after possible coercion)
num_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
if not num_cols:
    st.error("ستون عددی در فایل یافت نشد.")
    with st.expander("پیش‌نمایش فایل"):
        st.dataframe(df.head(200))
    st.stop()

# Time filter
if time_col is not None:
    tmin, tmax = df[time_col].min(), df[time_col].max()
    tstart, tend = st.slider(
        "بازه زمانی",
        min_value=pd.to_datetime(tmin).to_pydatetime(),
        max_value=pd.to_datetime(tmax).to_pydatetime(),
        value=(pd.to_datetime(tmin).to_pydatetime(), pd.to_datetime(tmax).to_pydatetime()),
        format="YYYY-MM-DD HH:mm:ss",
    )
    mask = (df[time_col] >= pd.to_datetime(tstart)) & (df[time_col] <= pd.to_datetime(tend))
    dff = df.loc[mask].reset_index(drop=True)
else:
    st.warning("ستون زمانی شناسایی نشد؛ تمام داده‌ها نمایش داده می‌شود.")
    dff = df.copy()

# Column mapping
colmap = pick_columns(dff)

# KPIs
def _fmt(v):
    try:
        return f"{float(v):,.2f}"
    except Exception:
        return "-"

kpi_items = []
if "speed" in colmap:
    kpi_items.append(("سرعت", dff[colmap["speed"]].iloc[-1], "m/s"))
if "altitude" in colmap:
    kpi_items.append(("ارتفاع", dff[colmap["altitude"]].iloc[-1], "m"))
if "battery" in colmap:
    kpi_items.append(("باتری", dff[colmap["battery"]].iloc[-1], "%"))
if time_col is not None and len(dff) > 1:
    duration = (dff[time_col].iloc[-1] - dff[time_col].iloc[0])
    seconds = int(getattr(duration, "total_seconds", lambda: np.nan)() or 0)
    kpi_items.append(("مدت بازه", f"{seconds}", "s"))
kpi_items.append(("تعداد نمونه", len(dff), ""))

cols = st.columns(kpi_count)
for i, (label, value, unit) in enumerate(kpi_items):
    cols[i % kpi_count].metric(label=label, value=f"{_fmt(value)} {unit}".strip())

st.markdown("---")

# Chart registry and draw function
def line_chart(dfX: pd.DataFrame, ycol: str, title: str, key: str):
    if time_col is not None:
        fig = px.line(dfX, x=time_col, y=ycol, title=title)
    else:
        fig = px.line(dfX.reset_index(), x="index", y=ycol, title=title, labels={"index": "Index"})
    st.plotly_chart(fig, use_container_width=True, key=key)

# Build available charts list based on colmap
available_charts: List[Tuple[str, str, str]] = []  # (alias, ycol, title)
if "altitude" in colmap:
    available_charts.append(("altitude", colmap["altitude"], "ارتفاع"))
if "speed" in colmap:
    available_charts.append(("speed", colmap["speed"], "سرعت"))
if "pitch" in colmap:
    available_charts.append(("pitch", colmap["pitch"], "گام (Pitch)"))
if "roll" in colmap:
    available_charts.append(("roll", colmap["roll"], "رُل (Roll)"))
if "yaw" in colmap:
    available_charts.append(("yaw", colmap["yaw"], "یاو/سربر (Yaw/Heading)"))
if "battery" in colmap:
    available_charts.append(("battery", colmap["battery"], "شارژ باتری (%)"))

if not available_charts:
    st.warning("ستون‌های استاندارد یافت نشد؛ نمایش عمومی ستون‌های عددی.")
    generic_cols = num_cols[:4]
    grid = st.columns(2)
    for i, c in enumerate(generic_cols):
        with grid[i % 2]:
            line_chart(dff, c, c, key=f"chart_generic_{i}")
    with st.expander("نمایش نمونه‌ای از داده‌ها"):
        st.dataframe(dff.head(200))
    st.stop()

# Sidebar: choose chart sequence
default_order = [a for a, _, _ in available_charts]
seq_selected = st.sidebar.multiselect(
    "ترتیب/انتخاب نمودارها برای اسلایدشو",
    options=default_order,
    default=default_order,
    help="اولویت اجرای اسلایدها بر اساس ترتیب انتخاب."
)

# Map selection back to full chart tuple list preserving order
chart_sequence: List[Tuple[str, str, str]] = [t for t in available_charts if t[0] in seq_selected]

# Render based on mode
if view_mode == "شبکه‌ای":
    # Show charts in grid (2 columns)
    c1, c2 = st.columns(2)
    for idx, (alias, ycol, title) in enumerate(chart_sequence):
        container = c1 if idx % 2 == 0 else c2
        with container:
            line_chart(dff, ycol, title, key=f"chart_{alias}")
else:
    # Slideshow: one chart per render
    total = len(chart_sequence)
    if total == 0:
        st.info("هیچ نموداری برای اسلایدشو انتخاب نشده است.")
    else:
        # Maintain slide index in session state
        if "slide_idx" not in st.session_state:
            st.session_state["slide_idx"] = 0

        # Auto-advance if not paused
        if not pause:
            cnt = slideshow_counter(interval_sec=interval_sec, key="slideshow_timer")
            st.session_state["slide_idx"] = cnt % total

        slide_idx = st.session_state["slide_idx"] % total
        alias, ycol, title = chart_sequence[slide_idx]

        # Header with status
        st.subheader(f"اسلاید {slide_idx + 1} از {total} — {title}")

        # Render the single chart
        line_chart(dff, ycol, title, key=f"chart_{alias}")

        # Controls: Prev / Next
        cc1, cc2, cc3 = st.columns(3)
        with cc1:
            if st.button("◀️ قبلی", use_container_width=True):
                st.session_state["slide_idx"] = (slide_idx - 1) % total
                st.rerun()
        with cc2:
            st.button("⏸️" + (" ادامه" if not pause else " ادامه"), disabled=True, use_container_width=True)
        with cc3:
            if st.button("بعدی ▶️", use_container_width=True):
                st.session_state["slide_idx"] = (slide_idx + 1) % total
                st.rerun()

        # Small caption
        st.caption(
            f"فاصله زمانی اسلایدها: {interval_sec} ثانیه | {'در حال اجرا' if not pause else 'متوقف'} | "
            f"برای تغییر ترتیب اسلایدها از سایدبار استفاده کنید."
        )

with st.expander("نمایش نمونه‌ای از داده‌ها"):
    st.dataframe(dff.head(200))

st.caption(
    "نکته: اگر streamlit-autorefresh نصب نباشد، از رفرش داخلی استفاده می‌شود. برای تغییر فونت از ?font=IRANSans استفاده کنید."
)
