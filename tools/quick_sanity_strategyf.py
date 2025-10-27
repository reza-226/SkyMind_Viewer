# tools/quick_sanity_strategyf.py
from __future__ import annotations
import sys
from pathlib import Path

# Ensure repo root is on PYTHONPATH so "sim" package can be imported
repo_root = Path(__file__).resolve().parents[1]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from sim.strategies.strategy_f import StrategyF  # noqa: E402


def main():
    env_view = {
        'tick': 0,
        'executors': [
            {'id': 'uav-1', 'cpu_free': 2000, 'mem_free': 2048, 'bw_free': 50, 'reputation': 0.8},
            {'id': 'edge-1', 'cpu_free': 4000, 'mem_free': 4096, 'bw_free': 100, 'reputation': 0.6},
        ]
    }

    tasks = [
        {'id': '0-0', 'cycles_required': 800_000, 'mem_required_kb': 512, 'size_kb': 200, 'deadline_tick': 10, 'min_reputation': 0.7},
        {'id': '0-1', 'cycles_required': 300_000, 'mem_required_kb': 256, 'size_kb': 100, 'deadline_tick': 12, 'min_reputation': 0.5},
        {'id': '0-2', 'cycles_required': 200_000, 'mem_required_kb': 128, 'size_kb': 50,  'deadline_tick': 8,  'min_reputation': 0.55},
    ]

    # Map to expected key if StrategyF uses 'min_rep'
    for t in tasks:
        if 'min_reputation' in t:
            t['min_rep'] = t.pop('min_reputation')

    sf = StrategyF(config={
        'load_balance_weight': 0.55,
        'use_saturation_penalty': True,
        'dynamic_norm_per_assign': True
    })

    decisions = sf.step(tasks, env_view)
    print(decisions)


if __name__ == '__main__':
    main()
