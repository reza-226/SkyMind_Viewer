# src/main.py یا src/simulator/scheduler.py
import yaml
from src.strategies.strategy_f import StrategyF

def load_config(path: str):
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def build_strategy(cfg: dict):
    strategy_name = cfg.get('strategy', 'StrategyF')
    strategy_cfg  = cfg.get('config', {})
    # فقط StrategyF فعلاً
    if strategy_name == 'StrategyF':
        return StrategyF(config=strategy_cfg)
    raise ValueError(f"Unknown strategy: {strategy_name}")

def run_simulation(demo_yaml_path: str):
    cfg = load_config(demo_yaml_path)
    strategy = build_strategy(cfg)

    # ... ساخت env و تولید tasks در هر تیک ...
    # مثال فراخوانی:
    # env_view = {...}  # شامل executors و time.tick
    # tasks = [ {...}, {...}, {...} ]
    decisions = strategy.step(tasks, env_view)
    # اگر تصمیم‌ها dict هستند:
    for tid, dec in decisions.items():
        # اعمال تصمیم dec روی شبیه‌ساز
        pass
