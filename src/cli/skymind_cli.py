#   src/cli/skymind_cli.py
import argparse
import argparse
import json
import pathlib
import sys
from typing import List

from skymind_viewer.replay import ReplayStream
from skymind_viewer.renderer import Renderer
from skymind_viewer.layers.tasks import TaskQueueLayer
from skymind_viewer.layers.links import LinksLayer
from skymind_viewer.layers.overlay import MetricsOverlay

def viewer_replay(args: argparse.Namespace):
    rs = ReplayStream(args.file)
    renderer = Renderer(
        rs,
        size=(args.width, args.height),
        bg_color=tuple(args.bg_color),
        headless=args.headless
    )
    if args.show_queues:
        renderer.add_layer(TaskQueueLayer())
    if args.show_links:
        renderer.add_layer(LinksLayer(dash=args.dashed_links))
    if args.overlay:
        renderer.add_layer(MetricsOverlay())
    renderer.run(fps=args.fps)

def viewer_stats(args: argparse.Namespace):
    from tools.viewer_stats import main as stats_main
    stats_main(args.files, args.out)

def viewer_gridsearch(args: argparse.Namespace):
    from tools.viewer_gridsearch import main as grid_main
    import glob
    files: List[str] = []
    for p in args.files:
        files.extend(glob.glob(p))
    grid_main(files, args.sizes, args.bgs, args.fps)

def build_parser():
    ap = argparse.ArgumentParser("skymind_cli")
    sub = ap.add_subparsers(dest="cmd", required=True)

    # viewer-replay
    v = sub.add_parser("viewer-replay")
    v.add_argument("--file", required=True, help="Replay JSONL file")
    v.add_argument("--fps", type=int, default=30)
    v.add_argument("--width", type=int, default=1024)
    v.add_argument("--height", type=int, default=768)
    v.add_argument("--bg-color", nargs=3, type=int, default=[20, 20, 24], help="RGB background")
    v.add_argument("--headless", action="store_true", help="Run without window (for CI/grid search)")
    v.add_argument("--show-queues", action="store_true", help="Show task queues")
    v.add_argument("--show-links", action="store_true", help="Show communication paths")
    v.add_argument("--dashed-links", action="store_true", help="Dashed style for links")
    v.add_argument("--overlay", action="store_true", help="Enable metrics overlay layer")
    v.set_defaults(func=viewer_replay)

    # viewer-stats
    s = sub.add_parser("viewer-stats")
    s.add_argument("--files", nargs="+", required=True, help="Glob patterns for JSONL replays")
    s.add_argument("--out", required=True, help="Output CSV path")
    s.set_defaults(func=viewer_stats)

    # viewer-gridsearch
    g = sub.add_parser("viewer-gridsearch")
    g.add_argument("--files", nargs="+", required=True, help="Replay JSONL paths or glob patterns")
    g.add_argument("--sizes", nargs="+", default=["1024x768", "1280x800"])
    g.add_argument("--bgs", nargs="+", default=["dark", "#0f0f14"])
    g.add_argument("--fps", nargs="+", type=int, default=[30])
    g.set_defaults(func=viewer_gridsearch)

    return ap

def main():
    ap = build_parser()
    args = ap.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()
