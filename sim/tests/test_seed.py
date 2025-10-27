# sim/tests/test_seed.py
import os

from sim.config import set_seed


def test_set_seed_explicit():
    s = set_seed(123)
    assert isinstance(s, int)
    assert 0 <= s < 2**32


def test_set_seed_env(monkeypatch):
    monkeypatch.setenv("SIM_SEED", "777")
    s = set_seed(None)
    assert s == 777


def test_set_seed_default(monkeypatch):
    # وقتی ENV نیست و آرگومان None است، انتظار داریم مقدار معتبر برگردد (پیش‌فرض یا تصادفی)
    monkeypatch.delenv("SIM_SEED", raising=False)
    s = set_seed(None)
    assert isinstance(s, int)
    assert 0 <= s < 2**32


def test_reproducibility_numpy():
    try:
        import numpy as np
    except ImportError:
        return  # اگر numpy نصب نیست، این تست را رد می‌کنیم.
    set_seed(999)
    a = np.random.rand(5)
    set_seed(999)
    b = np.random.rand(5)
    assert (a == b).all()
