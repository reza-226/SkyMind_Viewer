from pathlib import Path

from ..layout import render_results_tabs


def run(base_path: Path) -> None:
    render_results_tabs(base_path)
