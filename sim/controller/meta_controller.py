# sim/controller/meta_controller.py
from typing import Dict, Any, Optional, List
from collections import deque
from sim.strategies.strategy_h import StrategyH
from sim.strategies.strategy_f import StrategyF
from sim.strategies.strategy_d import StrategyD

class MetaController:
    def __init__(self, thresholds: Dict[str, float]):
        self.thresholds = thresholds
        self.strat_h = StrategyH()
        self.strat_f = StrategyF()
        self.strat_d = StrategyD()
        self.lat_hist = deque(maxlen=50)
        self.last_choice = "H"

    def select_strategy(self, env_view: Dict[str, Any]) -> str:
        # Compute indicators
        avg_lat = sum(self.lat_hist)/len(self.lat_hist) if self.lat_hist else 0.0
        ratio_rep = env_view.get("ratio_rep_tasks", 0.0)

        if ratio_rep >= self.thresholds.get("reputation_task_ratio", 0.3):
            self.last_choice = "F"
        elif avg_lat >= self.thresholds.get("latency_high_s", 3.0):
            self.last_choice = "D"
        else:
            self.last_choice = "H"
        return self.last_choice

    def get_strategy(self, name: Optional[str] = None):
        use = name or self.last_choice
        if use == "F":
            return self.strat_f
        if use == "D":
            return self.strat_d
        return self.strat_h

    def update_feedback(self, finished_task_latency_s: float):
        self.lat_hist.append(finished_task_latency_s)
