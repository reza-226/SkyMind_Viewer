# sim/core/metrics.py
from dataclasses import dataclass
from typing import List, Dict
from sim.models.task import Task

@dataclass
class Metrics:
    n_tasks: int
    n_success: int
    success_rate: float
    avg_latency_s: float
    p95_latency_s: float
    avg_energy_wh: float

    @staticmethod
    def from_tasks(tasks: List[Task]) -> "Metrics":
        if not tasks:
            return Metrics(0,0,0.0,0.0,0.0,0.0)
        lats = [t.delays.queue_s + t.delays.uplink_s + t.delays.processing_s + t.delays.downlink_s for t in tasks]
        en = [t.energy.ue_wh + t.energy.uav_wh + t.energy.fog_wh + t.energy.edge_wh + t.energy.cloud_wh for t in tasks]
        succ = sum(1 for t in tasks if t.success)
        lats_sorted = sorted(lats)
        idx = max(0, int(0.95*(len(lats_sorted)-1)))
        p95 = lats_sorted[idx]
        return Metrics(
            n_tasks=len(tasks),
            n_success=succ,
            success_rate=(succ/len(tasks)) if tasks else 0.0,
            avg_latency_s=sum(lats)/len(lats),
            p95_latency_s=p95,
            avg_energy_wh=(sum(en)/len(en)) if en else 0.0
        )

    def to_dict(self) -> Dict:
        return {
            "n_tasks": self.n_tasks,
            "n_success": self.n_success,
            "success_rate": self.success_rate,
            "avg_latency_s": self.avg_latency_s,
            "p95_latency_s": self.p95_latency_s,
            "avg_energy_wh": self.avg_energy_wh
        }
