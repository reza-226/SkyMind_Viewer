# tools/hud_viewer_streamlit.py
# HUD Viewer with robust CSV parser, slideshow timing, RTL/font injection, and KPI/plots

import os
import io
import time
import base64
import json
from typing import Dict, List, Optional, Tuple

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

# Try optional autorefresh helper
try:
    from streamlit_autorefresh import st_autorefresh  # pip install streamlit-autorefresh
except Exception:
    st_autorefresh = None


# ---------------------------
# Font and RTL/CSS utilities
# ---------------------------
def _read_file_base64(path: str) -> Optional[str]:
    try:
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode("ascii")
    except Exception:
        return None

def _embedded_font_css(font_family: str = "IRANSans") -> Optional[str]:
    """
    Try to import an embedded_fonts module and build a @font-face CSS block.
    Accepts either tools.embedded_fonts or embedded_fonts.
    """
    mod = None
    for name in ("tools.embedded_fonts", "embedded_fonts"):
        try:
            mod = __import__(name, fromlist=["*"])
            break
        except Exception:
            pass
    if not mod:
        return None

    # Expect attributes like IRANSans_woff2 or a dict
    woff2_b64 = None
    if hasattr(mod, "FONTS"):
        # FONTS may be dict: {"IRANSans": {"woff2": "..."}}
        try:
            woff2_b64 = mod.FONTS.get(font_family, {}).get("woff2")
        except Exception:
            woff2_b64 = None
    if not woff2_b64 and hasattr(mod, f"{font_family}_woff2"):
        woff2_b64 = getattr(mod, f"{font_family}_woff2")

    if not woff2_b64:
        return None

    css = f"""
    @font-face {{
      font-family: '{font_family}';
      src: url(data:font/woff2;base64,{woff2_b64}) format('woff2');
      font-weight: normal;
      font-style: normal;
      font-display: swap;
    }}
    """
    return css

def _local_font_css(font_family: str = "IRANSans") -> Optional[str]:
    """
    Read local assets/fonts/<font>.woff2 and build a CSS block.
    """
    candidate_paths = [
        os.path.join("assets", "fonts", f"{font_family}.woff2"),
        os.path.join("src", "skymind_viewer", "assets", "fonts", f"{font_family}.woff2"),
    ]
    for p in candidate_paths:
        b64 = _read_file_base64(p)
        if b64:
            return f"""
            @font-face {{
              font-family: '{font_family}';
              src: url(data:font/woff2;base64,{b64}) format('woff2');
              font-weight: normal;
              font-style: normal;
              font-display: swap;
            }}
            """
    return None

def inject_global_css(lang: str = "fa", font_family: str = "IRANSans"):
    """
    Injects RTL + font CSS. Priority: embedded > local. Falls back to sans-serif if not found.
    """
    font_css = _embedded_font_css(font_family) or _local_font_css(font_family) or ""
    direction = "rtl" if lang.lower().startswith(("fa", "ar")) else "ltr"
    family = font_family if font_css else "system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif"

    base_css = f"""
    html, body, [class*="css"] {{
      direction: {direction};
      font-family: '{family}';
      -webkit-font-smoothing: antialiased;
      -moz-osx-font-smoothing: grayscale;
    }}
    .stPlotlyChart {{
      direction: ltr; /* keep plots LTR to avoid axis inversion */
    }}
    .kpi .stMetric {{
      direction: {direction};
    }}
    """
    st.markdown(f"<style>{font_css}\n{base_css}</style>", unsafe_allow_html=True)


# ---------------------------
# Slideshow timing helper
# ---------------------------
def slideshow_tick(interval_ms: int, limit: Optional[int] = None, key: str = "slideshow_autorefresh"):
    """
    If streamlit-autorefresh is installed, use it. Otherwise, emulate with st.rerun() and session_state timestamps.
    """
    if st_autorefresh:
        st_autorefresh(interval=interval_ms, limit=limit, key=key)
        return

    # Fallback: manual clock + st.rerun
    now = time.time()
    last_key = f"{key}_last"
    if last_key not in st.session_state:
        st.session_state[last_key] = now
        return
    if (now - st.session_state[last_key]) * 1000.0 >= max(100, interval_ms):
        st.session_state[last_key] = now
        # Trigger rerun
        try:
            st.rerun()
        except Exception:
            # older versions
            st.experimental_rerun()


# ---------------------------
# Robust CSV/JSONL parsing
# ---------------------------
def read_table_auto(path: str) -> pd.DataFrame:
    """
    Robust reader for telemetry logs:
    - Supports CSV with delimiters ',', ';', '\t' and whitespace-separated.
    - Supports JSONL (one JSON object per line).
    - Cleans column names and tries to fix single-column cases by splitting.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"Input path not found: {path}")

    ext = os.path.splitext(path)[1].lower()
    if ext in (".jsonl", ".ndjson", ".json"):
        # JSONL or NDJSON: each line a JSON object
        rows = []
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    rows.append(obj)
                except Exception:
                    # try relaxed parsing for non-JSON lines
                    pass
        df = pd.DataFrame(rows)
    else:
        # CSV-like
        tried = []

        def clean_df(df0: pd.DataFrame) -> pd.DataFrame:
            df = df0.copy()
            df.columns = [str(c).strip().lower().replace(".", "_").replace("-", "_") for c in df.columns]
            return df

        # Try common delimiters
        for sep in [",", ";", "\t"]:
            try:
                df = pd.read_csv(path, sep=sep, engine="python")
                df = clean_df(df)
                tried.append(sep)
                if df.shape[1] > 1:
                    break
            except Exception:
                continue
        else:
            # whitespace-delimited
            try:
                df = pd.read_csv(path, delim_whitespace=True, engine="python")
                df = clean_df(df)
                tried.append("whitespace")
            except Exception as e:
                raise RuntimeError(f"Failed to parse CSV. Tried {tried}. Error: {e}")

        # If still single-column, attempt smart split
        if df.shape[1] == 1:
            col = df.columns[0]
            # Split each row by any runs of whitespace
            split_rows = df[col].astype(str).str.strip().str.split(r"\s+", regex=True)
            max_len = split_rows.map(len).max()
            expanded = pd.DataFrame(split_rows.tolist())
            # infer headers if first row looks like header-like tokens
            header_candidates = expanded.iloc[0].tolist()
            header_ok = all(isinstance(x, str) and not x.isdigit() for x in header_candidates)
            if header_ok:
                expanded = expanded.iloc[1:].reset_index(drop=True)
                expanded.columns = [str(x).strip().lower() for x in header_candidates]
            else:
                expanded.columns = [f"col_{i}" for i in range(max_len)]
            df = expanded

        # final clean
        df = df.replace({np.nan: None})
        df.columns = [c.strip().lower() for c in df.columns]
    return df


def pick_columns(df: pd.DataFrame) -> Dict[str, Optional[str]]:
    """
    Map dataframe columns to semantic roles.
    """
    cols = set(df.columns)

    def find_any(cands: List[str]) -> Optional[str]:
        for c in cands:
            if c in cols:
                return c
        # try fuzzy: remove common suffixes
        for c in cols:
            cn = c.replace("-", "_")
            for cand in cands:
                if cand in cn:
                    return c
        return None

    mapping = {
        "time": find_any(["timestamp", "time", "t", "ts"]),
        "x": find_any(["pos_x", "x", "lon", "longitude"]),
        "y": find_any(["pos_y", "y", "lat", "latitude"]),
        "z": find_any(["pos_z", "z", "alt", "altitude", "height"]),
        "speed": find_any(["speed_mps", "speed", "vel", "velocity", "v"]),
        "battery": find_any(["battery_pct", "battery_percent", "battery", "soc"]),
    }
    return mapping


# ---------------------------
# HUD rendering
# ---------------------------
def render_kpis(df: pd.DataFrame, colmap: Dict[str, Optional[str]]):
    st.subheader("شاخص‌های کلیدی (KPI)")
    kpi_cols = st.columns(4)
    # Speed
    if colmap["speed"] and colmap["speed"] in df.columns:
        sp = pd.to_numeric(df[colmap["speed"]], errors="coerce")
        kpi_cols[0].metric("سرعت (m/s)", f"{np.nanmean(sp):.2f}")
    else:
        kpi_cols[0].metric("سرعت (m/s)", "—")
    # Altitude
    if colmap["z"] and colmap["z"] in df.columns:
        alt = pd.to_numeric(df[colmap["z"]], errors="coerce")
        kpi_cols[1].metric("ارتفاع (m)", f"{np.nanmean(alt):.1f}")
    else:
        kpi_cols[1].metric("ارتفاع (m)", "—")
    # Battery
    if colmap["battery"] and colmap["battery"] in df.columns:
        bat = pd.to_numeric(df[colmap["battery"]], errors="coerce")
        kpi_cols[2].metric("باتری (%)", f"{np.nanmean(bat):.1f}")
    else:
        kpi_cols[2].metric("باتری (%)", "—")
    # Samples
    kpi_cols[3].metric("نمونه‌ها", f"{len(df)}")


def render_plots(df: pd.DataFrame, colmap: Dict[str, Optional[str]]):
    st.subheader("نمودارها")
    # Time series: speed and battery if available
    ts_cols = st.columns(2)
    time_col = colmap["time"]

    def line_plot(y_col: Optional[str], title: str):
        if not y_col or y_col not in df.columns:
            st.info(f"{title}: ستون یافت نشد.")
            return
        y = pd.to_numeric(df[y_col], errors="coerce")
        if time_col and time_col in df.columns:
            x = df[time_col]
        else:
            x = np.arange(len(y))
        fig = px.line(x=x, y=y, labels={"x": "زمان/اندیس", "y": title}, title=title, template="plotly_white")
        st.plotly_chart(fig, use_container_width=True, theme="streamlit")

    with ts_cols[0]:
        line_plot(colmap["speed"], "سرعت (m/s)")
    with ts_cols[1]:
        line_plot(colmap["battery"], "باتری (%)")

    # 2D trajectory (X-Y)
    st.subheader("مسیر X-Y")
    if colmap["x"] and colmap["y"] and (colmap["x"] in df.columns) and (colmap["y"] in df.columns):
        x = pd.to_numeric(df[colmap["x"]], errors="coerce")
        y = pd.to_numeric(df[colmap["y"]], errors="coerce")
        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(x=x, y=y, mode="lines+markers", name="trajectory"))
        fig2.update_layout(title="مسیر دوبعدی", xaxis_title="X/Lon", yaxis_title="Y/Lat", template="plotly_white")
        st.plotly_chart(fig2, use_container_width=True, theme="streamlit")
    else:
        st.info("مسیر دوبعدی: ستون‌های X/Y یافت نشد.")


# ---------------------------
# Slideshow controller
# ---------------------------
def run_slideshow(df: pd.DataFrame, interval_ms: int = 1500, page_size: int = 50):
    """
    Paginate the dataframe and move forward periodically.
    """
    if "slide_idx" not in st.session_state:
        st.session_state["slide_idx"] = 0

    total_pages = max(1, int(np.ceil(len(df) / max(1, page_size))))
    # Controls
    c1, c2, c3 = st.columns([1, 2, 1])
    with c1:
        if st.button("⟵ قبلی", use_container_width=True):
            st.session_state["slide_idx"] = max(0, st.session_state["slide_idx"] - 1)
    with c2:
        st.write(f"صفحه {st.session_state['slide_idx']+1} از {total_pages}")
    with c3:
        if st.button("بعدی ⟶", use_container_width=True):
            st.session_state["slide_idx"] = min(total_pages - 1, st.session_state["slide_idx"] + 1)

    # Autoplay toggle
    autoplay = st.checkbox("پخش خودکار (Slideshow)", value=False)
    if autoplay:
        slideshow_tick(interval_ms=interval_ms, key="hud_slideshow")

    # Slice current window
    idx = st.session_state["slide_idx"]
    start = idx * page_size
    end = min(len(df), start + page_size)
    st.write(f"نمایش ردیف‌های {start} تا {end}")
    st.dataframe(df.iloc[start:end], use_container_width=True)


# ---------------------------
# App main
# ---------------------------
def main():
    st.set_page_config(page_title="SkyMind HUD Viewer", layout="wide")
    # Sidebar settings
    lang = st.sidebar.selectbox("زبان", options=["fa", "en"], index=0)
    font_family = st.sidebar.text_input("فونت", value="IRANSans")
    inject_global_css(lang=lang, font_family=font_family)

    st.title("HUD Viewer (Phase 7)")
    # Parse CLI args: streamlit passes everything after '--' to sys.argv
    replay_path = st.sidebar.text_input("مسیر فایل Replay/CSV/JSONL", value="data/replays/hud_demo_v0.2.2.jsonl")
    page_size = st.sidebar.number_input("اندازه صفحه (Slideshow)", min_value=10, max_value=500, value=50, step=10)
    interval_ms = st.sidebar.number_input("فاصله زمانی اسلاید (ms)", min_value=250, max_value=10000, value=1500, step=250)

    # Allow file upload too
    upload = st.file_uploader("آپلود فایل (CSV/JSONL)", type=["csv", "jsonl", "ndjson", "json"])
    df = None

    try:
        if upload is not None:
            # Read uploaded file
            tmp = io.BytesIO(upload.read())
            # Save to temporary path for uniform parsing
            tmp_path = os.path.join(st.session_state.get("_tmp_dir", "."), f"__upload__{upload.name}")
            with open(tmp_path, "wb") as f:
                f.write(tmp.getbuffer())
            df = read_table_auto(tmp_path)
            os.remove(tmp_path)
        else:
            df = read_table_auto(replay_path)
    except Exception as e:
        st.error(f"خطا در بارگذاری/پارس فایل: {e}")
        st.stop()

    if df is None or df.empty:
        st.warning("فایل خالی است یا داده‌ای یافت نشد.")
        st.stop()

    # Column mapping
    colmap = pick_columns(df)

    # KPIs and plots
    render_kpis(df, colmap)
    render_plots(df, colmap)

    # Slideshow paginated view
    st.markdown("---")
    run_slideshow(df, interval_ms=interval_ms, page_size=page_size)

    st.caption("Tips: اگر streamlit-autorefresh نصب نباشد، از st.rerun برای شبیه‌سازی زمان‌بندی استفاده می‌شود.")


if __name__ == "__main__":
    main()
