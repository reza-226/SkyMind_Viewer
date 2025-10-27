# sim/utils/seed.py
from __future__ import annotations
import os
import random

try:
    import numpy as np
except Exception:
    np = None

DEFAULT_SEED = 42

def set_seed(seed: int | None) -> int:
    # 1) ENV has highest priority
    env_seed = os.getenv("SIM_SEED")
    if env_seed is not None:
        try:
            seed_val = int(env_seed)
        except ValueError:
            seed_val = DEFAULT_SEED
    # 2) explicit arg
    elif seed is not None:
        seed_val = int(seed)
    # 3) fallback default
    else:
        seed_val = DEFAULT_SEED

    random.seed(seed_val)
    if np is not None:
        np.random.seed(seed_val)
    return seed_val
