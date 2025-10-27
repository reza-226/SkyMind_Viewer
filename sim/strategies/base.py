# sim/strategies/base.py
from dataclasses import dataclass
from typing import Optional, Dict, Any
from sim.models.task import Task, ExecutionLocation

@dataclass
class AssignmentDecision:
    executor: ExecutionLocation
    executor_id: Optional[str]
    reason: str
    est_latency_s: float

class StrategyBase:
    name = "base"

    def decide(self, task: Task, env_view: Dict[str, Any]) -> Optional[AssignmentDecision]:
        raise NotImplementedError
