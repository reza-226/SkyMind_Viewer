# tools/fix_invalid_escape.py
from pathlib import Path

path = Path("tools/hud_viewer_streamlit.py")
src = path.read_text(encoding="utf-8")

# "\s" داخل متن فایل را به "\\s" تبدیل می‌کنیم
patched = src.replace("[,\\s;|]+", "[,\\\\s;|]+")

if patched != src:
    path.write_text(patched, encoding="utf-8")
    print("Patched: replaced [,\\s;|]+ with [,\\\\s;|]+")
else:
    print("No change made. Pattern not found or already patched.")
