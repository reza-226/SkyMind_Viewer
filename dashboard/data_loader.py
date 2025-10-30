import json
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd
import streamlit as st


def load_csv(path: Path, *, index_col: Optional[str] = None) -> Optional[pd.DataFrame]:
    if not path.exists():
        st.warning(f"فایل پیدا نشد: {path}")
        return None
    try:
        return pd.read_csv(path, index_col=index_col)
    except Exception as exc:
        st.error(f"خواندن CSV ناموفق بود: {path}\n{exc}")
        return None


def load_json(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        st.warning(f"فایل پیدا نشد: {path}")
        return None
    try:
        with path.open(encoding="utf-8") as handle:
            return json.load(handle)
    except Exception as exc:
        st.error(f"خواندن JSON ناموفق بود: {path}\n{exc}")
        return None


def get_sample_paths(base: Path) -> Dict[str, Path]:
    return {
        "results_csv": base / "results" / "run_2025-10-23.csv",
        "viewer_stats": base / "runs" / "viewer_stats.csv",
        "run_metadata": base
        / "runs_dev"
        / "run_2025-09-18_scenario-fogAerial"
        / "run_metadata.json",
        "tasks_csv": base
        / "runs_dev"
        / "run_2025-09-18_scenario-fogAerial"
        / "tasks.csv",
        "environment_log": base
        / "runs_dev"
        / "run_2025-09-18_scenario-fogAerial"
        / "logs"
        / "environment_metrics.log",
        "strategy_log": base
        / "runs_dev"
        / "run_2025-09-18_scenario-fogAerial"
        / "logs"
        / "strategyf_core.log",
    }
