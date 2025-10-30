# app.py
import streamlit as st
from pathlib import Path
import base64
import os

# ---------------------------------------
# تنظیمات اولیه صفحه
# ---------------------------------------
st.set_page_config(page_title="SkyMind Viewer", layout="wide")

# تضمین نمایش سایدبار حتی در صورت مشکل CSS
st.sidebar.markdown(
    "<style>[data-testid='stSidebar']{display:block!important;opacity:1!important;visibility:visible!important;}</style>",
    unsafe_allow_html=True
)

# ---------------------------------------
# i18n ساده (در صورت نبود ماژول پروژه)
# اگر i18n واقعی دارید، ایمپورت کنید و این بخش را بردارید.
# ---------------------------------------
def get_lang():
    return st.session_state.get("lang", "fa")

def set_lang(lang):
    st.session_state["lang"] = lang

def is_rtl():
    return get_lang() == "fa"

def t(key):
    # نگاشت نمونه؛ در پروژه واقعی از دیکشنری/فایل‌های ترجمه استفاده کنید
    translations = {
        "fa": {
            "title": "نمایشگر SkyMind",
            "subtitle": "تحلیل اجرای شبیه‌ساز، ایجاد اسنپ‌شات و مقایسه کنار هم",
            "cdn_info": "استفاده از فونت‌های CDN (فایل‌های محلی یافت نشدند).",
            "local_ok": "فونت‌های محلی یافت شد و تزریق شدند.",
            "local_fail": "فونت‌های محلی یافت نشدند؛ CDN اعمال شد.",
            "lang_label": "Language / زبان",
        },
        "en": {
            "title": "SkyMind Viewer",
            "subtitle": "Analyze simulator runs, create snapshots and compare side-by-side",
            "cdn_info": "Using CDN fonts (local .woff2 not found).",
            "local_ok": "Local fonts found and injected.",
            "local_fail": "Local fonts not found; CDN applied.",
            "lang_label": "Language / زبان",
        }
    }
    lang = get_lang()
    return translations.get(lang, translations["fa"]).get(key, key)

# ---------------------------------------
# سوئیچر زبان در سایدبار
# ---------------------------------------
st.session_state.setdefault("lang", "fa")
def _on_lang_change():
    lang = st.session_state["_lang_widget"]
    set_lang(lang)
st.sidebar.selectbox(
    label=t("lang_label"),
    options=["fa", "en"],
    index=(0 if get_lang() == "fa" else 1),
    format_func=lambda x: "🇮🇷 فارسی" if x == "fa" else "🇺🇸 English",
    key="_lang_widget",
    on_change=_on_lang_change
)

rtl = is_rtl()
font_family = "Vazirmatn" if rtl else "Inter"

# ---------------------------------------
# مسیرهای کاندید برای فونت‌های محلی
# شامل مسیر ویندوزی که دادید + مسیرهای رایج پروژه
# ---------------------------------------
FONTS_ROOTS = []

# مسیر محیطی اختیاری (در صورت تنظیم)
ENV_DIR = os.environ.get("SKYMIND_FONTS_DIR")
if ENV_DIR:
    FONTS_ROOTS.append(Path(ENV_DIR))

# مسیر صریحی که شما گفتید (Windows)
FONTS_ROOTS.append(Path("D:/Payannameh/SkyMind_Viewer/scripts/static/fonts"))

# مسیرهای نسبی معمول پروژه
FONTS_ROOTS.append(Path("scripts/static/fonts"))
FONTS_ROOTS.append(Path("assets/fonts"))

# حذف مسیرهای تکراری و نرمال‌سازی
def unique_paths(paths):
    seen = set()
    out = []
    for p in paths:
        p = p.resolve() if p.exists() else p
        if str(p) not in seen:
            seen.add(str(p))
            out.append(p)
    return out

FONTS_ROOTS = unique_paths(FONTS_ROOTS)

# ---------------------------------------
# ابزارهای تزریق فونت
# ---------------------------------------
def _b64_font(path: Path) -> str:
    with path.open("rb") as f:
        return base64.b64encode(f.read()).decode("ascii")

def _font_face_from_file(path: Path, family: str, weight: str = "400", style: str = "normal") -> str:
    b64 = _b64_font(path)
    return f"""
    @font-face {{
      font-family: '{family}';
      src: url(data:font/woff2;base64,{b64}) format('woff2');
      font-weight: {weight};
      font-style: {style};
      font-display: swap;
    }}
    """

def inject_global_css(rtl: bool, family_stack: str):
    direction = "rtl" if rtl else "ltr"
    align = "right" if rtl else "left"
    st.markdown(f"""
    <style>
    html, body {{
      direction: {direction};
      text-align: {align};
      font-family: {family_stack} !important;
    }}
    /* اطمینان از اعمال فونت بر کنترل‌های عمومی */
    .stButton>button, .stTextInput input, .stSelectbox div, .stCheckbox label, .stRadio div, .stMarkdown, .stTable {{
      font-family: {family_stack} !important;
    }}
    /* نمونه برای پلا‌تلی/ویزیول‌ها */
    .plotly .main-svg, .js-plotly-plot {{
      font-family: {family_stack} !important;
    }}
    </style>
    """, unsafe_allow_html=True)

def find_local_font_files_for_family(family: str):
    """
    سعی می‌کند بهترین مجموعه فایل‌ها را برای خانواده داده‌شده پیدا کند.
    اولویت:
    - فایل متغیر (wght) اگر موجود باشد => یک @font-face با بازه وزن
    - Regular + Bold اگر موجود باشد
    - هر دو فایل اولی که پیدا شد (به‌صورت 400/700)
    """
    candidates_variable = [
        f"{family}[wght].woff2",
        f"{family}-VariableFont_wght.woff2",
    ]
    candidates_regular_bold = [
        (f"{family}-Regular.woff2", "400"),
        (f"{family}-Bold.woff2", "700"),
    ]

    # جستجو برای variable
    for root in FONTS_ROOTS:
        for name in candidates_variable:
            p = root / name
            if p.exists():
                return {"mode": "variable", "files": [{"path": p, "weight_range": "100 900"}]}

    # جستجو برای Regular/Bold صریح
    found_rb = []
    for root in FONTS_ROOTS:
        reg = root / candidates_regular_bold[0][0]
        bold = root / candidates_regular_bold[1][0]
        if reg.exists():
            found_rb.append({"path": reg, "weight": "400"})
        if bold.exists():
            found_rb.append({"path": bold, "weight": "700"})
        if len(found_rb) >= 2:
            return {"mode": "pair", "files": found_rb}

    # جستجوی آزاد: هر woff2 با نام خانواده
    free_found = []
    for root in FONTS_ROOTS:
        if not root.exists():
            continue
        for p in root.glob(f"{family}*.woff2"):
            free_found.append(p)
        if free_found:
            break

    if free_found:
        # اگر فقط یک فایل داریم، به‌عنوان Regular 400 می‌گیریم
        if len(free_found) == 1:
            return {"mode": "pair", "files": [{"path": free_found[0], "weight": "400"}]}
        else:
            # دو فایل اول را به 400 و 700 نگاشت می‌کنیم
            return {"mode": "pair", "files": [
                {"path": free_found[0], "weight": "400"},
                {"path": free_found[1], "weight": "700"},
            ]}

    return None

def inject_local_font_css(family: str, rtl: bool) -> bool:
    """
    تلاش برای تزریق فونت‌های محلی به‌صورت data URI.
    در صورت موفقیت True برمی‌گرداند.
    """
    fi = find_local_font_files_for_family(family)
    if not fi:
        return False

    css_faces = ""
    if fi["mode"] == "variable":
        p = fi["files"][0]["path"]
        b64 = _b64_font(p)
        css_faces += f"""
        @font-face {{
          font-family: '{family}';
          src: url(data:font/woff2;base64,{b64}) format('woff2');
          font-weight: {fi['files'][0]['weight_range']};
          font-style: normal;
          font-display: swap;
        }}
        """
    else:
        for item in fi["files"]:
            css_faces += _font_face_from_file(item["path"], family, item.get("weight", "400"), "normal")

    # فونت fallback برای سازگاری
    stack = f"'{family}', 'Segoe UI', Tahoma, Arial, sans-serif"
    st.markdown(f"<style>{css_faces}</style>", unsafe_allow_html=True)
    inject_global_css(rtl=rtl, family_stack=stack)
    return True

def inject_cdn_font_css(family: str, rtl: bool):
    # استفاده از Google Fonts به‌عنوان fallback
    if family.lower() == "vazirmatn":
        css_import = "@import url('https://fonts.googleapis.com/css2?family=Vazirmatn:wght@400;700&display=swap');"
    else:
        css_import = "@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700&display=swap');"

    stack = f"'{family}', 'Segoe UI', Tahoma, Arial, sans-serif"
    st.markdown(f"<style>{css_import}</style>", unsafe_allow_html=True)
    inject_global_css(rtl=rtl, family_stack=stack)

# ---------------------------------------
# تزریق فونت‌ها: تلاش محلی سپس CDN
# ---------------------------------------
try:
    ok = inject_local_font_css(font_family, rtl)
    if ok:
        st.sidebar.success(t("local_ok"))
    else:
        inject_cdn_font_css(font_family, rtl)
        st.sidebar.info(t("cdn_info"))
except Exception as e:
    # در صورت هرگونه خطا، به CDN برگرد
    inject_cdn_font_css(font_family, rtl)
    st.sidebar.error(f"Font/CSS injection failed: {e}")
    st.sidebar.info(t("cdn_info"))

# ---------------------------------------
# محتوای صفحه
# ---------------------------------------
st.header(t("title"))
st.caption(t("subtitle"))

# مثال محتوای تستی
col1, col2 = st.columns(2)
with col1:
    st.subheader("Controls")
    st.text_input("نام وظیفه" if rtl else "Task name")
    st.selectbox("گزینه‌ها" if rtl else "Options", ["A", "B", "C"])
    st.button("اجرا" if rtl else "Run")

with col2:
    st.subheader("Status")
    st.write("Ready." if not rtl else "آماده.")
