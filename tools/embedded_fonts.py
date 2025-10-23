# tools/embed_fonts.py
# -*- coding: utf-8 -*-
"""
ابزار تولید فایل پایتونی embedded_fonts.py با فونت‌های Base64
روش استفاده:
  python tools/embed_fonts.py assets/fonts IRANSansX Vazirmatn
اگر نام خانواده‌ها را ندهید، همه فونت‌های موجود را Embed می‌کند.
"""

import os
import sys
import base64
import re
from typing import Dict, List, Tuple

WEIGHT_PATTERNS = [
    ("bold", "700"),
    ("semibold", "600"),
    ("medium", "500"),
    ("regular", "400"),
    ("book", "400"),
    ("normal", "400"),
]

VALID_EXTS = (".woff2", ".woff", ".ttf", ".otf")

def detect_weight(filename: str) -> str:
    lfn = filename.lower()
    for key, w in WEIGHT_PATTERNS:
        if key in lfn or re.search(rf"(\D){w}(\D)", lfn):
            return w
    # تلاش برای عدد وزن
    m = re.search(r"(\D)(\d{3})(\D)", lfn)
    if m:
        return m.group(2)
    return "400"

def ext_format(ext: str) -> str:
    ext = ext.lower()
    if ext == ".woff2": return "woff2"
    if ext == ".woff": return "woff"
    if ext == ".otf": return "opentype"
    return "truetype"

def collect_fonts(font_dirs: List[str], families_filter: List[str]) -> Dict[str, Dict[str, Dict[str, str]]]:
    result = {}
    for fd in font_dirs:
        if not os.path.isdir(fd):
            continue
        for root, _, files in os.walk(fd):
            for fn in files:
                lfn = fn.lower()
                if not lfn.endswith(VALID_EXTS):
                    continue
                full_path = os.path.join(root, fn)
                # نام خانواده را از نام فایل حدس می‌زنیم: بخش اول تا جداکننده خط تیره/خط زیر
                base = os.path.splitext(fn)[0]
                family_guess = re.split(r"[-_]", base)[0]
                family_guess = family_guess.strip()
                if families_filter:
                    # اگر فیلتر دادید، فقط خانواده‌هایی که شامل این کلیدواژه‌ها هستند
                    if not any(f.lower() in lfn for f in [fam.lower() for fam in families_filter]):
                        continue

                with open(full_path, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode("utf-8")
                w = detect_weight(fn)
                fmt = ext_format(os.path.splitext(fn)[1])

                fam = family_guess
                result.setdefault(fam, {})
                # اگر وزن تکراری است، اولویت با woff2
                if w in result[fam] and result[fam][w]["format"] != "woff2" and fmt == "woff2":
                    pass  # جایگزین می‌شود
                result[fam][w] = {"data": b64, "format": fmt}
    return result

def write_embedded_py(target_path: str, data: Dict[str, Dict[str, Dict[str, str]]]):
    with open(target_path, "w", encoding="utf-8") as f:
        f.write("# -*- coding: utf-8 -*-\n")
        f.write("# این فایل به صورت خودکار توسط tools/embed_fonts.py تولید شده است.\n")
        f.write("EMBEDDED_FONTS = {\n")
        for fam, weights in data.items():
            f.write(f"    {repr(fam)}: {{\n")
            for w, info in weights.items():
                fmt = info["format"]
                b64 = info["data"]
                f.write(f"        {repr(w)}: {{'format': {repr(fmt)}, 'data': {repr(b64)}}},\n")
            f.write("    },\n")
        f.write("}\n")

def main():
    if len(sys.argv) < 2:
        print("Usage: python tools/embed_fonts.py <font_dir1> [<font_dir2> ...] [FamilyFilter1 FamilyFilter2 ...]")
        print("Example: python tools/embed_fonts.py assets/fonts IRANSansX Vazirmatn")
        sys.exit(1)

    # جدا کردن مسیرها از فیلترها: هر آرگیومانی که پوشه موجود باشد، مسیر حساب می‌شود؛ بقیه فیلتر
    args = sys.argv[1:]
    font_dirs = [a for a in args if os.path.isdir(a)]
    families_filter = [a for a in args if not os.path.isdir(a)]

    if not font_dirs:
        print("هیچ پوشه فونتی یافت نشد.")
        sys.exit(1)

    data = collect_fonts(font_dirs, families_filter)
    if not data:
        print("هیچ فونتی برای Embed پیدا نشد.")
        sys.exit(1)

    # فایل خروجی
    script_dir = os.path.dirname(os.path.abspath(__file__))
    target_path = os.path.join(script_dir, "embedded_fonts.py")
    write_embedded_py(target_path, data)
    print(f"تمام شد. فایل تولید شد: {target_path}")

if __name__ == "__main__":
    main()
