# sim/strategies/strategy_d.py
from typing import Dict, Any, List
from math import exp
from sim.strategies.base import StrategyBase, AssignmentDecision
from sim.models.task import Task, ExecutionLocation
from sim.models.delay import uplink_delay_s, downlink_delay_s, processing_delay_s
from sim.utils.geo import distance_m

class StrategyD(StrategyBase):
    name = "D"

    def decide(self, task: Task, env_view: Dict[str, Any]) -> AssignmentDecision:
        tight = task.latency_slo_s <= 1.5
        uav_low = any(u.battery_wh <= env_view["meta"]["uav_low_battery_wh"] for u in env_view["uavs"].values())
        dev = env_view["devices"][task.source_id]
        candidates: List[AssignmentDecision] = []

        # Local
        proc_local = processing_delay_s(task.cycles_required, dev.cpu_cps)
        candidates.append(AssignmentDecision(ExecutionLocation.LOCAL, task.source_id, "local_proc", proc_local))

        def add(node, exec_loc, base_mbps, alpha, tag, prop_ms=5.0):
            d = distance_m(dev.pos, node.pos)
            eff_mbps = base_mbps * exp(-alpha * d)
            up = uplink_delay_s(task.size_kb/1024.0, eff_mbps, prop_ms)
            proc = processing_delay_s(task.cycles_required, node.cpu_cps)
            down = downlink_delay_s((task.size_kb/1024.0)*0.05, env_view["bw"].result_down_mbps, prop_ms)
            candidates.append(AssignmentDecision(exec_loc, node.id, tag, up+proc+down))

        for u in env_view["uavs"].values():
            if not uav_low:
                add(u, ExecutionLocation.UAV, env_view["bw"].ue_to_uav_mbps, env_view["bw"].uav_pathloss_alpha_per_m, "uav_proc")

        for f in env_view["fogs"].values():
            add(f, ExecutionLocation.FOG, env_view["bw"].ue_to_fog_mbps, env_view["bw"].fog_pathloss_alpha_per_m, "fog_proc")

        for e in env_view["edges"].values():
            add(e, ExecutionLocation.EDGE, env_view["bw"].ue_to_edge_mbps, env_view["bw"].edge_pathloss_alpha_per_m, "edge_proc")

        if env_view["cloud"] is not None:
            c = env_view["cloud"]
            up = uplink_delay_s(task.size_kb/1024.0, env_view["bw"].ue_to_cloud_mbps, propagation_ms=20.0)
            proc = processing_delay_s(task.cycles_required, c.cpu_cps)
            down = downlink_delay_s((task.size_kb/1024.0)*0.05, env_view["bw"].result_down_mbps, propagation_ms=20.0)
            candidates.append(AssignmentDecision(ExecutionLocation.CLOUD, c.id, "cloud_proc", up+proc+down))

        # Tight deadline → pick min processing delay
        if tight:
            return min(candidates, key=lambda d: d.est_latency_s)
        return min(candidates, key=lambda d: d.est_latency_s)
