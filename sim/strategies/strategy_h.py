# sim/strategies/strategy_h.py
from typing import Dict, Any, List
from math import exp
from sim.strategies.base import StrategyBase, AssignmentDecision
from sim.models.task import Task, ExecutionLocation
from sim.models.delay import uplink_delay_s, downlink_delay_s, processing_delay_s
from sim.utils.geo import distance_m

class StrategyH(StrategyBase):
    name = "H"

    def decide(self, task: Task, env_view: Dict[str, Any]) -> AssignmentDecision:
        candidates: List[AssignmentDecision] = []
        dev = env_view["devices"][task.source_id]

        # Local
        proc = processing_delay_s(task.cycles_required, dev.cpu_cps)
        candidates.append(AssignmentDecision(ExecutionLocation.LOCAL, task.source_id, "local_proc", proc))

        # UAVs
        for u in env_view["uavs"].values():
            d = distance_m(dev.pos, u.pos)
            eff_mbps = env_view["bw"].ue_to_uav_mbps * exp(-env_view["bw"].uav_pathloss_alpha_per_m * d)
            up = uplink_delay_s(task.size_kb/1024.0, eff_mbps)
            proc = processing_delay_s(task.cycles_required, u.cpu_cps)
            down = downlink_delay_s((task.size_kb/1024.0)*0.05, env_view["bw"].result_down_mbps)
            candidates.append(AssignmentDecision(ExecutionLocation.UAV, u.id, "uav_proc", up + proc + down))

        # Fog
        for f in env_view["fogs"].values():
            d = distance_m(dev.pos, f.pos)
            eff_mbps = env_view["bw"].ue_to_fog_mbps * exp(-env_view["bw"].fog_pathloss_alpha_per_m * d)
            up = uplink_delay_s(task.size_kb/1024.0, eff_mbps)
            proc = processing_delay_s(task.cycles_required, f.cpu_cps)
            down = downlink_delay_s((task.size_kb/1024.0)*0.05, env_view["bw"].result_down_mbps)
            candidates.append(AssignmentDecision(ExecutionLocation.FOG, f.id, "fog_proc", up + proc + down))

        # Edge
        for e in env_view["edges"].values():
            d = distance_m(dev.pos, e.pos)
            eff_mbps = env_view["bw"].ue_to_edge_mbps * exp(-env_view["bw"].edge_pathloss_alpha_per_m * d)
            up = uplink_delay_s(task.size_kb/1024.0, eff_mbps)
            proc = processing_delay_s(task.cycles_required, e.cpu_cps)
            down = downlink_delay_s((task.size_kb/1024.0)*0.05, env_view["bw"].result_down_mbps)
            candidates.append(AssignmentDecision(ExecutionLocation.EDGE, e.id, "edge_proc", up + proc + down))

        # Cloud (constant path)
        if env_view["cloud"] is not None:
            c = env_view["cloud"]
            up = uplink_delay_s(task.size_kb/1024.0, env_view["bw"].ue_to_cloud_mbps, propagation_ms=20.0)
            proc = processing_delay_s(task.cycles_required, c.cpu_cps)
            down = downlink_delay_s((task.size_kb/1024.0)*0.05, env_view["bw"].result_down_mbps, propagation_ms=20.0)
            candidates.append(AssignmentDecision(ExecutionLocation.CLOUD, c.id, "cloud_proc", up + proc + down))

        best = min(candidates, key=lambda d: d.est_latency_s)
        return best
