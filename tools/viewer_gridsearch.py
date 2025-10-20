# src/tools/viewer_gridsearch.py
from __future__ import annotations

import itertools
import time
import glob
from typing import Dict, List, Tuple

from skymind_viewer.replay import ReplayStream
from skymind_viewer.renderer import Renderer
from skymind_viewer.layers.tasks import TaskQueueLayer
from skymind_viewer.layers.links import LinksLayer

def run_config(file_path: str, size: Tuple[int, int], bg_color: Tuple[int, int, int], fps: int) -> Dict[str, object]:
    rs = ReplayStream(file_path)
    # headless run with minimal layers
    r = Renderer(rs, size=size, bg_color=bg_color, headless=True)
    r.add_layer(TaskQueueLayer())
    r.add_layer(LinksLayer())
    # run a short loop stepping through events quickly
    start = time.time()
    steps = 0
    for _ in range(min(rs.total, 500)):  # cap to 500 events
        rs.emit_current()
        steps += 1
        rs.step(+1)
    elapsed = time.time() - start
    return {
        "file": file_path,
        "steps": steps,
        "elapsed_sec": round(elapsed, 4),
        "fps_target": fps,
        "size": f"{size[0]}x{size[1]}",
        "bg": f"{bg_color}",
        "ok": True,
    }

def main(files: List[str], sizes: List[str], bgs: List[str], fps_list: List[int]):
    size_vals = []
    for s in sizes:
        w, h = s.lower().split("x")
        size_vals.append((int(w), int(h)))
    bg_vals = []
    for b in bgs:
        if b.startswith("#") and len(b) == 7:
            # hex #rrggbb
            r = int(b[1:3], 16); g = int(b[3:5], 16); bl = int(b[5:7], 16)
            bg_vals.append((r, g, bl))
        else:
            presets = {
                "dark": (20, 20, 24),
                "light": (240, 240, 240),
                "black": (0, 0, 0),
                "white": (255, 255, 255),
                "navy": (12, 20, 60),
            }
            bg_vals.append(presets.get(b.lower(), (20, 20, 24)))

    results: List[Dict[str, object]] = []
    for fp in files:
        for sz, bg, fps in itertools.product(size_vals, bg_vals, fps_list):
            results.append(run_config(fp, sz, bg, fps))

    # print TSV to stdout
    import csv, sys
    w = csv.DictWriter(sys.stdout, fieldnames=list(results[0].keys()), delimiter="\t")
    w.writeheader()
    for r in results:
        w.writerow(r)

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser("viewer-gridsearch")
    ap.add_argument("--files", nargs="+", required=True, help="Replay JSONL paths or glob patterns")
    ap.add_argument("--sizes", nargs="+", default=["1024x768", "1280x800"], help="Window sizes WxH")
    ap.add_argument("--bgs", nargs="+", default=["dark", "#0f0f14"], help="Background colors: presets or #rrggbb")
    ap.add_argument("--fps", nargs="+", type=int, default=[30], help="FPS targets (used for reporting)")
    args = ap.parse_args()

    files: List[str] = []
    for p in args.files:
        import glob as _g
        files.extend(_g.glob(p))

    main(files, args.sizes, args.bgs, args.fps)
