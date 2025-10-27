# sim/strategies/__init__.py
from importlib import import_module

REGISTRY = {}

def _register_default():
    try:
        mod = import_module("sim.strategies.strategy_f")
        REGISTRY["F"] = getattr(mod, "StrategyF")
    except Exception:
        pass
    try:
        mod = import_module("sim.strategies.strategy_noop")
        REGISTRY["Noop"] = getattr(mod, "StrategyNoop")
    except Exception:
        pass

_register_default()

def make_strategy(name: str, cfg=None):
    name = (name or "Noop")
    if name in REGISTRY:
        cls = REGISTRY[name]
        try:
            return cls(cfg=cfg)
        except Exception:
            return cls()
    # fallback: dynamic load
    mod_name = f"sim.strategies.strategy_{name.lower()}"
    cls_name = f"Strategy{name.upper()}"
    mod = import_module(mod_name)
    cls = getattr(mod, cls_name)
    try:
        return cls(cfg=cfg)
    except Exception:
        return cls()
