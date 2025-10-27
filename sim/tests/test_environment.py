# sim/tests/test_environment.py
def test_imports():
    from sim.core.environment import Environment
    from sim.config import DefaultConfig
    env = Environment(DefaultConfig())
    assert len(env.devices) >= 1
    assert len(env.uavs) >= 1
