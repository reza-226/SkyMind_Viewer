# simulator.py
# A self-contained simulator scaffold that builds env_view for StrategyF,
# injects min_reputation into tasks, and runs per-tick decisions without relying on external YAML files.

import logging
import random
from typing import Any, Dict, List, Optional

try:
    # If StrategyF is in a local file named strategy_f.py
    from strategy_f import StrategyF
except ImportError:
    # If StrategyF resides in a package; adjust as needed
    from sim.strategies.strategy_f import StrategyF


class Simulator:
    """
    Minimal but robust simulator:
      - Holds UAV and EDGE resources.
      - Builds env_view with ['uavs', 'edges', 'executors'] for StrategyF.
      - Generates tasks per tick (configurable), injects min_reputation.
      - Calls StrategyF.step and applies decisions (placeholder).
    No external config files required; pass a Python dict or rely on defaults.
    """

    def __init__(self, strategy: StrategyF, config: Optional[Dict[str, Any]] = None):
        self.strategy = strategy
        self.config = config or {}
        self.uavs: List[Any] = []        # List of UAV objects or dicts
        self.edge_nodes: List[Any] = []  # List of EDGE objects or dicts
        self.tick: int = 0

        # Logging default level (you can override from outside)
        if not logging.getLogger().handlers:
            logging.basicConfig(level=logging.INFO)

    # ===== Resource management =====
    def add_uav(self, uav_obj: Any):
        """Register a UAV resource (object or dict)."""
        self.uavs.append(uav_obj)

    def add_edge(self, edge_obj: Any):
        """Register an EDGE resource (object or dict)."""
        self.edge_nodes.append(edge_obj)

    def _as_dict(self, obj: Any, node_type_hint: Optional[str] = None) -> Dict[str, Any]:
        """
        Convert node object to dict; if already dict, return a copy.
        Ensure it carries a 'type' and 'reputation' field if available.
        """
        if isinstance(obj, dict):
            d = dict(obj)
        else:
            d = getattr(obj, '__dict__', {}) or {}
            d = dict(d)

        # Ensure type
        if 'type' not in d and node_type_hint:
            d['type'] = node_type_hint.upper()

        # Normalize reputation synonyms into 'reputation'
        rep = None
        for k in ('reputation', 'rep', 'score', 'reliability', 'trust', 'trust_score', 'rating', 'quality'):
            if k in d:
                rep = d.get(k)
                break
        if rep is not None and 'reputation' not in d:
            d['reputation'] = rep
        return d

    def _ensure_rep_scale(self, nodes: List[Dict[str, Any]]):
        """
        Optional normalization: if reputations exceed 1.0 (e.g., in 0..100), scale to 0..1.
        StrategyF can also handle scaling; this is just to keep env_view tidy.
        """
        vals = []
        for n in nodes:
            r = n.get('reputation')
            if isinstance(r, (int, float)):
                vals.append(float(r))
        if not vals:
            return
        mx = max(vals)
        if mx > 1.0:
            for n in nodes:
                r = n.get('reputation')
                if isinstance(r, (int, float)):
                    n['reputation'] = float(r) / mx

    def _build_env_view(self) -> Dict[str, Any]:
        """
        Construct env_view with resource lists under common keys so StrategyF can consume them.
        Keys: 'uavs', 'edges', 'executors'
        """
        env_view: Dict[str, Any] = {}

        # Convert resource objects to dicts with type hints
        uavs = [self._as_dict(u, node_type_hint='UAV') for u in self.uavs]
        edges = [self._as_dict(e, node_type_hint='EDGE') for e in self.edge_nodes]

        # Optional: normalize reputations to 0..1
        self._ensure_rep_scale(uavs)
        self._ensure_rep_scale(edges)

        # Inject resources under common keys
        env_view['uavs'] = uavs
        env_view['edges'] = edges
        env_view['executors'] = uavs + edges  # combined list

        logging.debug(f"[Simulator] env_view keys: {list(env_view.keys())}")
        logging.debug(f"[Simulator] counts(uavs={len(uavs)}, edges={len(edges)}, executors={len(env_view['executors'])})")
        return env_view

    # ===== Task management =====
    def _inject_task_constraints(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Ensure min_reputation exists on the task using config options:
          - config['workload']['min_reputation'] (float, optional)
          - config['workload']['min_reputation_range'] ([lo, hi], optional)
        Inject under multiple synonyms for broader strategy compatibility.
        """
        wl = self.config.get('workload', {}) if isinstance(self.config.get('workload'), dict) else {}
        min_rep = 0.0

        if isinstance(wl.get('min_reputation'), (int, float)):
            min_rep = float(wl.get('min_reputation'))
        elif isinstance(wl.get('min_reputation_range'), (list, tuple)) and len(wl['min_reputation_range']) == 2:
            lo, hi = wl['min_reputation_range']
            try:
                min_rep = random.uniform(float(lo), float(hi))
            except Exception:
                min_rep = 0.0

        # Inject under different keys
        task['min_reputation'] = min_rep
        task['minRep'] = min_rep
        task['min_rep'] = min_rep
        task['minTrust'] = min_rep
        task['reputation_min'] = min_rep
        task['rep_min'] = min_rep
        task['min_trust'] = min_rep
        task['trust_min'] = min_rep
        return task

    def _generate_tasks_for_tick(self, tick: int) -> List[Dict[str, Any]]:
        """
        Generate tasks per tick. Configurable via:
          - config['workload']['tasks_per_tick'] (int, default=3)
          - config['workload']['size_kb_range'] ([lo, hi], default=[200, 1500])
          - config['workload']['cycles_per_kb'] (int, default=800)
          - config['workload']['deadline_slack_range'] ([lo, hi], default=[5, 15])
        """
        wl = self.config.get('workload', {}) if isinstance(self.config.get('workload'), dict) else {}

        tasks_per_tick = int(wl.get('tasks_per_tick', 3))
        size_lo, size_hi = wl.get('size_kb_range', [200, 1500])
        cycles_per_kb = int(wl.get('cycles_per_kb', 800))
        slack_lo, slack_hi = wl.get('deadline_slack_range', [5, 15])

        tasks: List[Dict[str, Any]] = []
        for i in range(tasks_per_tick):
            size_kb = random.randint(int(size_lo), int(size_hi))
            cycles_required = int(size_kb * cycles_per_kb)
            deadline_tick = tick + random.randint(int(slack_lo), int(slack_hi))

            t = {
                'id': f'{tick}-{i}',
                'size_kb': size_kb,
                'cycles_required': cycles_required,
                'arrival_tick': tick,
                'deadline_tick': deadline_tick,
            }
            # Inject min_reputation and synonyms
            t = self._inject_task_constraints(t)

            logging.debug(f"[Simulator] Task kwargs mapped: {t}")
            tasks.append(t)

        return tasks

    def _apply_decisions(self, decisions: Dict[str, Any]):
        """
        Placeholder: implement how decisions are applied in your simulator.
        For diagnostics, we just log a summary per tick.
        """
        accepted = sum(1 for d in decisions.values() if d.get('executor') != 'local')
        fallback = sum(1 for d in decisions.values() if d.get('executor') == 'local')
        logging.info(f"[Simulator] decisions: accepted={accepted}, fallback={fallback}")

    # ===== Tick/run loop =====
    def run_tick(self):
        """
        Run a single tick: build env_view, generate tasks, call strategy, apply decisions.
        """
        env_view = self._build_env_view()
        tasks = self._generate_tasks_for_tick(self.tick)

        # Call strategy
        decisions = self.strategy.step(tasks, env_view)

        # Optionally, emit StrategyF diagnostics summary (task queue length is outside scope here)
        logging.info(f"[StrategyF] Tick={self.tick} | tasks={len(tasks)}")

        # Apply decisions
        self._apply_decisions(decisions)

        # Advance tick
        self.tick += 1

    def run(self, ticks: int):
        """
        Run for the specified number of ticks.
        """
        for _ in range(int(ticks)):
            self.run_tick()


# ===== Example usage (no external YAML needed) =====
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    # Configure StrategyF inline via Python dict (optional)
    strategy_config = {
        # Optional: guide StrategyF to nested resource paths if you have them
        # 'resource_keys': {
        #     'uav': [
        #         ["state", "resources", "uav_list"],
        #     ],
        #     'edge': [
        #         ["state", "resources", "edge_list"],
        #     ],
        # }
    }
    strategy = StrategyF(config=strategy_config)

    # Simulator config inline
    sim_config = {
        'workload': {
            'tasks_per_tick': 3,
            'size_kb_range': [200, 1500],
            'cycles_per_kb': 800,
            'deadline_slack_range': [5, 15],
            'min_reputation_range': [0.4, 0.8],  # or fixed 'min_reputation': 0.6
        }
    }

    sim = Simulator(strategy=strategy, config=sim_config)

    # Register some resources (dicts or objects); make sure each has reputation.
    # UAV examples:
    sim.add_uav({'id': 'uav-1', 'type': 'UAV', 'reputation': 0.7, 'cpu_free': 1500, 'mem_free': 1024, 'bw_free': 20})
    sim.add_uav({'id': 'uav-2', 'type': 'UAV', 'reputation': 0.5, 'cpu_free': 900, 'mem_free': 512, 'bw_free': 10})

    # EDGE examples:
    sim.add_edge({'id': 'edge-1', 'type': 'EDGE', 'reputation': 0.8, 'cpu_free': 4000, 'mem_free': 8192, 'bw_free': 200})
    sim.add_edge({'id': 'edge-2', 'type': 'EDGE', 'reputation': 0.6, 'cpu_free': 2500, 'mem_free': 4096, 'bw_free': 100})

    # Run a few ticks
    sim.run(ticks=5)
