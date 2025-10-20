# src/tools/viewer_stats.py
from __future__ import annotations

import csv
import glob
from typing import List, Dict

from skymind_viewer.replay import ReplayStream
from skymind_viewer.validation import validate_events

def summarize_file(path: str) -> Dict[str, object]:
    rs = ReplayStream(path)
    val = validate_events(rs.events)
    counters = val.counters
    # up to 3 error samples (first messages)
    error_samples = "; ".join(val.errors[:3])
    return {
        "file": path,
        "events": rs.total,
        "duration": round(rs.duration(), 4),
        "errors": counters.get("__errors__", 0),
        "warnings": counters.get("__warnings__", 0),
        "entities": counters.get("__entities__", 0),
        "tasks": counters.get("__tasks__", 0),
        "entity_created": counters.get("entity_created", 0),
        "uav_pose": counters.get("uav_pose", 0),
        "task_submit": counters.get("task_submit", 0),
        "task_assigned": counters.get("task_assigned", 0),
        "task_completed": counters.get("task_completed", 0),
        "offload_decision": counters.get("offload_decision", 0),
        "link_up": counters.get("link_up", 0),
        "link_down": counters.get("link_down", 0),
        "error_samples": error_samples,
    }

def write_csv(rows: List[Dict[str, object]], out_path: str):
    if not rows:
        return
    fieldnames = list(rows[0].keys())
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)

def main(patterns: List[str], out_path: str):
    files: List[str] = []
    for p in patterns:
        files.extend(glob.glob(p))
    rows = [summarize_file(fp) for fp in files]
    write_csv(rows, out_path)

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser("viewer-stats")
    ap.add_argument("--files", nargs="+", required=True, help="Glob patterns for replay JSONL files")
    ap.add_argument("--out", required=True, help="Output CSV path")
    args = ap.parse_args()
    main(args.files, args.out)
