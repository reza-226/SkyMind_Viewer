from pathlib import Path

from ..layout import render_environment


def run(base_path: Path) -> None:
    render_environment(base_path)
