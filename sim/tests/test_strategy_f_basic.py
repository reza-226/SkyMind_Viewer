# sim/tests/test_strategy_f_basic.py
import pytest
from sim.strategies.strategy_f import StrategyF

def test_returns_dict_and_accepts():
    sf = StrategyF({'load_balance_weight': 0.55, 'use_saturation_penalty': True, 'dynamic_norm_per_assign': True})
    env_view = {'tick': 0, 'executors': [
        {'id': 'u1', 'cpu_free': 2000, 'mem_free': 2048, 'bw_free': 50, 'reputation': 0.8},
        {'id': 'e1', 'cpu_free': 3000, 'mem_free': 4096, 'bw_free': 80, 'reputation': 0.6},
    ]}
    tasks = [
        {'id': '0-0', 'cycles_required': 400_000, 'mem_required_kb': 256, 'size_kb': 100, 'deadline_tick': 5, 'min_rep': 0.5},
        {'id': '0-1', 'cycles_required': 200_000, 'mem_required_kb': 128, 'size_kb': 50,  'deadline_tick': 5, 'min_rep': 0.55},
    ]
    decisions = sf.step(tasks, env_view)
    assert isinstance(decisions, dict)
    assert set(decisions.keys()) == {'0-0', '0-1'}
    assert all(d['status'] == 'accepted' for d in decisions.values())
