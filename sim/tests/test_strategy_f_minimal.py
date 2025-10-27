# tests/test_strategy_f_minimal.py
import unittest
from sim.strategies.strategy_f import StrategyF

class DummyWorld:
    def __init__(self, tasks):
        self.tick = 0
        self.task_queue = tasks
        self.ues = []
        self.uavs = []
        self.bs = []

    def get_pending_tasks(self):
        return list(self.task_queue)

class DummyTask:
    def __init__(self, id, ue_id, size_kb, cycles, created_tick, deadline_tick):
        self.id = id
        self.ue_id = ue_id
        self.size_kb = size_kb
        self.cycles = cycles
        self.created_tick = created_tick
        self.deadline_tick = deadline_tick

class TestStrategyF(unittest.TestCase):
    def test_tick_with_tasks(self):
        tasks = [
            DummyTask("t0", "ue-1", 500, 400000, 0, 10),
            DummyTask("t1", "ue-2", 200, 160000, 0, 8),
        ]
        world = DummyWorld(tasks)
        s = StrategyF()
        actions = s.tick(world)
        self.assertTrue(len(actions) > 0, "StrategyF should produce actions when tasks exist")

if __name__ == "__main__":
    unittest.main()
