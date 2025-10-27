# -*- coding: utf-8 -*-
"""
StrategyF: Fault-tolerant, flexible task assignment strategy.

Key features:
- Robust to env_view.executors being list or dict (auto-indexing).
- Flexible resource/reputation extraction from heterogeneous schemas.
- Feasibility checks: resources, reputation, simple SLO (deadline/urgency).
- Scoring with configurable weights (CPU, MEM, BW, REP, URGENCY).
- Load-balance penalty and optional saturation penalty.
- Optional dynamic normalization per assignment to discourage repeated selection of the same node.
- Returns a decisions dict compatible with Simulator._apply_decisions:
    decisions = {task_id: {'executor': <node_id or 'local'>, ...}, ...}
- Legacy adapter: tick(world) wrapper for tests that call Strategy.tick(world).

Drop-in file to replace sim/strategies/strategy_f.py (adjust namespace imports if needed).
"""

from typing import Any, Dict, List, Tuple, Optional
import logging

logger = logging.getLogger(__name__)


class StrategyF:
    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        """
        Initialize StrategyF with optional configuration.
        """
        self.config = config or {}

        # Defaults and configurable knobs
        # Return a dict mapping task_id -> decision dict (required by simulator)
        self.return_mode: str = self.config.get('return_mode', 'dict')  # 'dict' or 'list'
        self.cpu_divisor: float = float(self.config.get('cpu_divisor', 1000.0))
        self.mem_divisor: float = float(self.config.get('mem_divisor', 1024.0))
        self.load_balance_weight: float = float(self.config.get('load_balance_weight', 0.35))
        self.use_saturation_penalty: bool = bool(self.config.get('use_saturation_penalty', True))
        self.saturation_alpha: float = float(self.config.get('saturation_alpha', 0.35))
        self.dynamic_norm_per_assign: bool = bool(self.config.get('dynamic_norm_per_assign', True))
        self.use_urgency: bool = bool(self.config.get('use_urgency', True))

        # Weights for node score composition
        self.score_weights: Dict[str, float] = self.config.get('score_weights', {
            'cpu': 0.30,
            'mem': 0.15,
            'bw': 0.30,
            'rep': 0.20,
            'urgency': 0.05,  # used only if use_urgency=True and task has deadline
        })

        # Norm factors updated at every step (and optionally after each assignment)
        self.norm_max: Dict[str, float] = {'cpu': 1.0, 'mem': 1.0, 'bw': 1.0, 'rep': 1.0}

        # Task counters for logging
        self._accepted_count = 0
        self._skipped_count = 0

        logger.info("[StrategyF] Initialized with config keys=%s", list(self.config.keys()))

    # ---------------------------
    # Core public API
    # ---------------------------
    def step(self, tasks: Any, env_view: Dict[str, Any]) -> Any:
        """
        Main entry point: assign tasks to executors.

        Parameters:
        - tasks: iterable/dict of tasks. Each task should define resource requirements at least.
        - env_view: dict containing executors information, possibly other fields like tick/time.

        Returns:
        - Dict mapping task_id -> decision dict with at least 'executor' key.
          If return_mode == 'list', returns a list of decision dicts.
        """
        tasks_list: List[Dict[str, Any]] = self._normalize_step_args(tasks)
        local_state, meta_state = self._build_local_state(env_view)

        # Optional DEBUG of env_view keys:
        try:
            logger.debug("[StrategyF] env_view keys=%s | types: tick=%s, executors=%s",
                         list(env_view.keys()) if isinstance(env_view, dict) else 'not-dict',
                         type(env_view.get('tick')).__name__ if isinstance(env_view, dict) and 'tick' in env_view else 'none',
                         type(env_view.get('executors')).__name__ if isinstance(env_view, dict) and 'executors' in env_view else 'none')
        except Exception:
            pass

        # Compute normalization factors across available nodes (free capacities)
        self.norm_max = self._compute_norm_factors(local_state)

        tick = env_view.get('tick', None)

        decisions_map: Dict[str, Dict[str, Any]] = {}
        decisions_list: List[Dict[str, Any]] = []
        self._accepted_count = 0
        self._skipped_count = 0

        for idx, t in enumerate(tasks_list):
            # Normalize task requirements
            treq = self._normalize_task_reqs(t)

            # Reputation threshold logging (as observed in earlier traces)
            min_rep_raw = treq.get('min_rep', 0.0)
            scale_max = 1.0  # reputation expected in [0,1]
            min_rep_norm = min(max(min_rep_raw / scale_max, 0.0), 1.0)
            task_key = self._format_task_key(t, idx, tick)

            logger.debug("[StrategyF] Task=%s | min_rep_raw=%.3f | scale_max=1.0 | min_rep_norm=%.3f",
                         task_key, min_rep_raw, min_rep_norm)

            # Build candidate nodes: feasibility by rep/SLO/resources
            candidates: List[Tuple[str, float]] = []

            for node_id, res in local_state.items():
                meta = meta_state.get(node_id, {})
                node_rep = self._extract_reputation(meta)

                # Reputation feasibility
                if node_rep < min_rep_norm:
                    continue

                # Simple SLO check for deadline if exists
                if not self._slo_feasible(treq, meta, env_view):
                    continue

                # Resource feasibility
                if not self._resources_feasible(treq, res):
                    continue

                # Score candidate node
                score = self._score_task_to_node(treq, res, meta, env_view)
                candidates.append((node_id, score))

            if not candidates:
                # Keep a signature similar to previously seen log lines
                logger.info("[StrategyF] No feasible executor for task=%s (reputation/SLO/resources)", task_key)
                self._skipped_count += 1

                # Emit a 'local' decision (so simulator can count/handle it)
                decision = {
                    'task_id': t.get('id', task_key),
                    'executor': 'local',
                    'node_id': 'local',
                    'score': 0.0,
                    'requirements': treq,
                    'status': 'skipped',
                    'reason': 'no_feasible_executor',
                    'tick': tick,
                }
                decisions_map[decision['task_id']] = decision
                decisions_list.append(decision)
                continue

            # Pick the best candidate by score
            candidates.sort(key=lambda x: x[1], reverse=True)
            chosen_node, chosen_score = candidates[0]

            # Apply assignment: update local_state capacities
            self._apply_assignment(treq, local_state[chosen_node])

            # Optionally update norm factors to penalize immediate saturation of the chosen node
            if self.dynamic_norm_per_assign:
                self.norm_max = self._compute_norm_factors(local_state)

            # Record decision
            decision = {
                'task_id': t.get('id', task_key),
                'executor': chosen_node,   # REQUIRED by simulator
                'node_id': chosen_node,
                'score': chosen_score,
                'requirements': treq,
                'status': 'accepted',
                'tick': tick,
            }
            decisions_map[decision['task_id']] = decision
            decisions_list.append(decision)
            self._accepted_count += 1

        # Summary log
        logger.info("[StrategyF] step result: acc=%d, skipped=%d", self._accepted_count, self._skipped_count)

        # Return decisions in the format simulator expects
        if self.return_mode == 'list':
            return decisions_list
        else:
            # IMPORTANT: return a pure decisions map, no extra keys
            return decisions_map

    def tick(self, world: Any) -> Dict[str, Dict[str, Any]]:
        """
        Legacy adapter for tests that call Strategy.tick(world).
        Attempts to extract tasks and executors from `world` and delegates to `step`.
        """
        # Extract tasks from common attributes
        tasks_src = None
        for attr in ("tasks", "queue", "pending_tasks"):
            if hasattr(world, attr):
                tasks_src = getattr(world, attr)
                break
        if tasks_src is None:
            tasks_src = []

        # Normalize task objects to dicts with at least an 'id'
        def to_task_dict(t) -> Dict[str, Any]:
            if isinstance(t, dict):
                return dict(t)
            d: Dict[str, Any] = {}
            # id
            for k in ("id", "task_id", "name"):
                if hasattr(t, k):
                    d["id"] = getattr(t, k)
                    break
            # optional fields (kept for completeness; not strictly needed by StrategyF)
            for (out_k, candidates) in [
                ("size_kb", ("size_kb", "size", "input_size_kb")),
                ("cycles_required", ("cycles_required", "cycles", "cpu_cycles")),
                ("arrival_tick", ("arrival_tick", "arrival", "arrived_at")),
                ("deadline_tick", ("deadline_tick", "deadline", "due")),
                ("mem_required_kb", ("mem_required_kb", "mem_kb", "memory_kb")),
                ("min_rep", ("min_rep", "min_reputation")),
            ]:
                for ck in candidates:
                    if hasattr(t, ck):
                        d[out_k] = getattr(t, ck)
                        break
            return d

        tasks_list: List[Dict[str, Any]] = []
        if isinstance(tasks_src, dict):
            for t in tasks_src.values():
                tasks_list.append(to_task_dict(t))
        else:
            for t in list(tasks_src):
                tasks_list.append(to_task_dict(t))

        # Build env_view with tick and executors
        tick = getattr(world, "tick", getattr(world, "current_tick", 0))
        executors: List[Dict[str, Any]] = []

        # Try common executor pools
        if hasattr(world, "executors"):
            ex = getattr(world, "executors")
            if isinstance(ex, dict):
                executors = list(ex.values())
            elif isinstance(ex, list):
                executors = ex
        else:
            for pool in ("uavs", "edges", "fogs"):
                if hasattr(world, pool):
                    val = getattr(world, pool)
                    if isinstance(val, dict):
                        executors.extend(list(val.values()))
                    elif isinstance(val, list):
                        executors.extend(val)
            if hasattr(world, "cloud") and getattr(world, "cloud"):
                executors.append(getattr(world, "cloud"))

        # Minimal local fallback if no executors are found
        if not executors:
            executors = [{"id": "local", "cpu_free": 1e9, "mem_free": 1e9, "bw_free": 1e9, "reputation": 1.0}]

        env_view = {"tick": tick, "executors": executors}
        return self.step(tasks_list, env_view)

    # ---------------------------
    # Helpers: Input normalization
    # ---------------------------
    def _normalize_step_args(self, tasks: Any) -> List[Dict[str, Any]]:
        """
        Normalize tasks input to a list of dicts.
        Accepts list, tuple, dict with 'tasks', or single dict.
        """
        if tasks is None:
            return []

        if isinstance(tasks, list):
            return [t if isinstance(t, dict) else {'raw': t} for t in tasks]
        if isinstance(tasks, tuple):
            return [t if isinstance(t, dict) else {'raw': t} for t in list(tasks)]
        if isinstance(tasks, dict):
            # If dict includes tasks key
            if 'tasks' in tasks and isinstance(tasks['tasks'], list):
                return [t if isinstance(t, dict) else {'raw': t} for t in tasks['tasks']]
            # Single task dict
            return [tasks]
        # Fallback
        return [{'raw': tasks}]

        # Produce a human-readable key for logging, similar to "tick-index"
    def _format_task_key(self, task: Dict[str, Any], idx: int, tick: Any) -> str:
        """
        e.g., "23-2" when tick=23 and idx=2. If not available, fallback to task.id or idx.
        """
        if task.get('id'):
            return str(task['id'])
        if tick is not None:
            return f"{tick}-{idx}"
        return f"{idx}"

    # ---------------------------
    # Helpers: Env/executors ingestion
    # ---------------------------
    def _index_executors(self, execs_raw) -> Dict[str, Dict[str, Any]]:
        """
        Index executors block (dict or list) into dict keyed by id/node_id/name.

        If input is list, create a dict with keys from ('id','node_id','name','uid','nid') fallback to "node-<i>".
        If input is dict, return as-is.
        """
        if execs_raw is None:
            return {}

        if isinstance(execs_raw, dict):
            return execs_raw

        indexed: Dict[str, Dict[str, Any]] = {}
        if isinstance(execs_raw, list):
            for i, meta in enumerate(execs_raw):
                if not isinstance(meta, dict):
                    # skip unknown items
                    continue
                nid = str(meta.get('id') or
                          meta.get('node_id') or
                          meta.get('name') or
                          meta.get('uid') or
                          meta.get('nid') or
                          f"node-{i}")
                indexed[nid] = meta
            return indexed

        # Unknown structure
        return {}

    def _build_local_state(self, env_view: Dict[str, Any]) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Dict[str, Any]]]:
        """
        Build local_state from env_view. Be tolerant to schema variations.
        Returns:
            local_state: node_id -> resources dict (cpu_total, cpu_free, mem_total, mem_free, bw_total, bw_free)
            meta_state: node_id -> original/meta fields dict (for rep/type/etc.)
        """
        execs_raw = None
        # Prefer common keys
        for key in ('executors', 'nodes', 'agents', 'edges', 'uavs'):
            v = env_view.get(key)
            if isinstance(v, (dict, list)):
                # If edges/uavs are present, combine them
                if key in ('edges', 'uavs'):
                    combined: List[Dict[str, Any]] = []
                    edges = env_view.get('edges')
                    uavs = env_view.get('uavs')
                    if isinstance(edges, list):
                        combined.extend(edges)
                    if isinstance(uavs, list):
                        combined.extend(uavs)
                    execs_raw = combined if combined else v
                else:
                    execs_raw = v
                break

        # Try nested or alternate structures
        if execs_raw is None and isinstance(env_view, dict):
            for k, v in env_view.items():
                if isinstance(v, (dict, list)):
                    execs_raw = v
                    break

        # If env_view itself is list/dict of executors
        if execs_raw is None and isinstance(env_view, (dict, list)):
            execs_raw = env_view

        execs = self._index_executors(execs_raw)

        local_state: Dict[str, Dict[str, Any]] = {}
        meta_state: Dict[str, Dict[str, Any]] = {}
        counts = {'uav': 0, 'edge': 0, 'other': 0}

        for node_id, meta in execs.items():
            ntype = self._infer_node_type(node_id, meta)
            res = self._extract_resource_block(meta)

            local_state[node_id] = res
            meta_state[node_id] = dict(meta)

            if ntype == 'uav':
                counts['uav'] += 1
            elif ntype == 'edge':
                counts['edge'] += 1
            else:
                counts['other'] += 1

        # Debug sample of node reputations
        sample_reps = []
        for node_id, meta in meta_state.items():
            try:
                sample_reps.append(self._extract_reputation(meta))
            except Exception:
                pass

        logger.debug("[StrategyF] node_reps_sample=%s | counts(uav=%d, edge=%d, other=%d) | execs_type=%s len=%d",
                     sample_reps, counts['uav'], counts['edge'], counts['other'],
                     type(execs_raw).__name__ if execs_raw is not None else 'None',
                     (len(execs) if isinstance(execs, dict) else 0))

        if counts['uav'] == 0 and counts['edge'] == 0 and counts['other'] == 0 and len(execs) == 0:
            logger.warning("[StrategyF] No executors found in env_view; got type=%s. Check env_view schema.",
                           type(env_view).__name__)

        self.norm_max = self._compute_norm_factors(local_state)
        return local_state, meta_state

    def _infer_node_type(self, node_id: str, meta: Dict[str, Any]) -> str:
        """
        Try to infer node type (uav/edge/other) by name/id or meta.type.
        """
        t = (str(meta.get('type', '')).lower() if 'type' in meta else '').strip()
        hint = (node_id.lower() if node_id else '')
        if t in ('uav', 'drone'):
            return 'uav'
        if t in ('edge', 'fog', 'mec', 'server'):
            return 'edge'
        if 'uav' in hint or 'drone' in hint:
            return 'uav'
        if 'edge' in hint or 'fog' in hint or 'mec' in hint or 'server' in hint:
            return 'edge'
        return 'other'

    # ---------------------------
    # Helpers: Resources & Reputation
    # ---------------------------
    def _extract_resource_block(self, meta: Dict[str, Any]) -> Dict[str, float]:
        """
        Extract resource capacities and free amounts from a node meta map.
        Tries a variety of common schemas. Unknown fields default conservatively.

        Returned keys:
            cpu_total, cpu_free
            mem_total, mem_free
            bw_total,  bw_free
        All as floats.
        """
        res = {}
        # Common nested map
        resources = meta.get('resources') or meta.get('res') or {}

        # Try total/free pairs
        cpu_total = self._pick_first_float([
            resources.get('cpu_total'),
            resources.get('cpu_cap'),
            meta.get('cpu_total'),
            meta.get('cpu_cap'),
            meta.get('cpu'),
        ], default=0.0)
        cpu_free = self._pick_first_float([
            resources.get('cpu_free'),
            resources.get('cpu_available'),
            meta.get('cpu_free'),
            meta.get('cpu_available'),
        ], default=cpu_total)

        mem_total = self._pick_first_float([
            resources.get('mem_total'),
            resources.get('memory_total'),
            resources.get('mem_cap'),
            meta.get('mem_total'),
            meta.get('memory_total'),
            meta.get('mem_cap'),
            meta.get('mem'),
        ], default=0.0)
        mem_free = self._pick_first_float([
            resources.get('mem_free'),
            resources.get('memory_free'),
            resources.get('mem_available'),
            meta.get('mem_free'),
            meta.get('memory_free'),
            meta.get('mem_available'),
        ], default=mem_total)

        bw_total = self._pick_first_float([
            resources.get('bw_total'),
            resources.get('bandwidth_total'),
            resources.get('bw_cap'),
            meta.get('bw_total'),
            meta.get('bandwidth_total'),
            meta.get('bw_cap'),
            meta.get('bw'),
        ], default=0.0)
        bw_free = self._pick_first_float([
            resources.get('bw_free'),
            resources.get('bandwidth_free'),
            resources.get('bw_available'),
            meta.get('bw_free'),
            meta.get('bandwidth_free'),
            meta.get('bw_available'),
        ], default=bw_total)

        return {
            'cpu_total': float(cpu_total),
            'cpu_free': float(cpu_free),
            'mem_total': float(mem_total),
            'mem_free': float(mem_free),
            'bw_total': float(bw_total),
            'bw_free': float(bw_free),
        }

    def _extract_reputation(self, meta: Dict[str, Any]) -> float:
        """
        Extract node reputation in [0,1].
        Attempts various likely fields; defaults to 0.5 if not found.
        """
        rep = self._pick_first_float([
            meta.get('reputation'),
            meta.get('rep'),
            meta.get('trust'),
            meta.get('score'),
            meta.get('quality'),
        ], default=0.5)
        rep = 0.0 if rep is None else float(rep)
        if rep < 0.0:
            rep = 0.0
        if rep > 1.0:
            rep = 1.0
        return rep

    def _pick_first_float(self, candidates: List[Any], default: float) -> float:
        for c in candidates:
            if c is None:
                continue
            try:
                return float(c)
            except Exception:
                continue
        return float(default)

    def _resources_feasible(self, treq: Dict[str, float], res: Dict[str, float]) -> bool:
        """
        Check if node resources can satisfy task requirements (simple additive model).
        """
        return (treq['cpu'] <= res['cpu_free'] and
                treq['mem'] <= res['mem_free'] and
                treq['bw'] <= res['bw_free'])

    def _slo_feasible(self, treq: Dict[str, float], meta: Dict[str, Any], env_view: Dict[str, Any]) -> bool:
        """
        Simple feasibility gate for deadlines.
        If deadline exists, accept by default (no path/queue modeled here).
        Realistic checks require queue/service-time estimates; we keep it permissive.
        """
        deadline = treq.get('deadline')
        if deadline is None:
            return True
        return True

    def _apply_assignment(self, treq: Dict[str, float], res: Dict[str, float]) -> None:
        """
        Subtract allocated resources from node state (greedy immediate assignment).
        """
        res['cpu_free'] = max(0.0, res['cpu_free'] - treq['cpu'])
        res['mem_free'] = max(0.0, res['mem_free'] - treq['mem'])
        res['bw_free'] = max(0.0, res['bw_free'] - treq['bw'])

    # ---------------------------
    # Helpers: Task normalization
    # ---------------------------
    def _normalize_task_reqs(self, task: Dict[str, Any]) -> Dict[str, float]:
        """
        Normalize task requirements to a unified dict:
            cpu, mem, bw: floats (raw units from env, no divisors applied)
            min_rep: float in [0,1]
            deadline: optional float (ticks or seconds)
        Tries multiple field names and nested maps.
        """
        req = task.get('req') or task.get('requirements') or {}
        cpu = self._pick_first_float([
            req.get('cpu'), task.get('cpu'), task.get('cpu_req'), req.get('cpu_req')
        ], default=0.0)
        mem = self._pick_first_float([
            req.get('mem'), task.get('mem'), task.get('mem_req'), req.get('mem_req'), task.get('memory'), req.get('memory')
        ], default=0.0)
        bw = self._pick_first_float([
            req.get('bw'), task.get('bw'), task.get('bw_req'), req.get('bw_req'),
            req.get('bandwidth'), task.get('bandwidth')
        ], default=0.0)

        # Reputation threshold
        min_rep = self._pick_first_float([
            task.get('min_rep'), req.get('min_rep'),
            task.get('min_reputation'), req.get('min_reputation'),
            task.get('reputation_min'), req.get('reputation_min'),
            task.get('rep_min'), req.get('rep_min'),
            task.get('minTrust'), req.get('minTrust'),
            task.get('min_trust'), req.get('min_trust'),
            task.get('trust_min'), req.get('trust_min'),
        ], default=0.0)
        if min_rep < 0.0:
            min_rep = 0.0
        if min_rep > 1.0:
            min_rep = 1.0

        # Deadline (if present) — accept many aliases
        deadline = self._pick_first_float([
            task.get('deadline'), req.get('deadline'),
            task.get('deadline_tick'), req.get('deadline_tick'),
            task.get('ddl'), req.get('ddl'),
            task.get('latency_slo'), req.get('latency_slo'),
        ], default=float('nan'))
        deadline = deadline if deadline == deadline else None  # NaN check

        return {
            'cpu': float(cpu),
            'mem': float(mem),
            'bw': float(bw),
            'min_rep': float(min_rep),
            'deadline': deadline,
        }

    # ---------------------------
    # Scoring and normalization
    # ---------------------------
    def _compute_norm_factors(self, local_state: Dict[str, Dict[str, Any]]) -> Dict[str, float]:
        """
        Compute normalization maxima across nodes for free cpu/mem/bw.
        """
        max_cpu = 1e-9
        max_mem = 1e-9
        max_bw = 1e-9

        for node_id, res in local_state.items():
            max_cpu = max(max_cpu, float(res.get('cpu_free', 0.0)))
            max_mem = max(max_mem, float(res.get('mem_free', 0.0)))
            max_bw = max(max_bw, float(res.get('bw_free', 0.0)))

        return {'cpu': max_cpu, 'mem': max_mem, 'bw': max_bw, 'rep': 1.0}

    def _node_saturation_ratio(self, res: Dict[str, float]) -> float:
        """
        Estimate saturation ratio (used/(used+free)) across cpu/mem/bw and average it.
        """
        ratios: List[float] = []
        for key_total, key_free in (('cpu_total', 'cpu_free'),
                                    ('mem_total', 'mem_free'),
                                    ('bw_total', 'bw_free')):
            total = float(res.get(key_total, 0.0))
            free = float(res.get(key_free, 0.0))
            used = max(0.0, total - free)
            if total > 0.0:
                ratios.append(used / total)
        if not ratios:
            return 0.0
        return sum(ratios) / len(ratios)

    def _urgency_component(self, treq: Dict[str, float], env_view: Dict[str, Any]) -> float:
        """
        Compute urgency score in [0,1] if deadline is present.
        Simplified model: more urgent tasks get higher component.
        If tick is present, we consider a simple time-left notion, else return 0.
        """
        if not self.use_urgency:
            return 0.0
        deadline = treq.get('deadline')
        if deadline is None:
            return 0.0
        tick = env_view.get('tick')
        if tick is None:
            # Without global time reference, assign moderate urgency
            return 0.5
        try:
            if deadline <= tick:
                return 1.0
            remaining = max(1.0, float(deadline - tick))
            urg = 1.0 / (1.0 + remaining / 10.0)
            return max(0.0, min(1.0, urg))
        except Exception:
            return 0.5

    def _score_task_to_node(self, treq: Dict[str, float], res: Dict[str, float],
                            meta: Dict[str, Any], env_view: Dict[str, Any]) -> float:
        """
        Compute the node score for a given task assignment using normalized free resources,
        reputation, urgency, and penalties for load/saturation.
        """
        # Normalized available resources
        cpu_norm = 0.0
        mem_norm = 0.0
        bw_norm = 0.0

        if self.norm_max['cpu'] > 0.0:
            cpu_norm = float(res.get('cpu_free', 0.0)) / self.norm_max['cpu']
        if self.norm_max['mem'] > 0.0:
            mem_norm = float(res.get('mem_free', 0.0)) / self.norm_max['mem']
        if self.norm_max['bw'] > 0.0:
            bw_norm = float(res.get('bw_free', 0.0)) / self.norm_max['bw']

        # Clamp
        cpu_norm = max(0.0, min(1.0, cpu_norm))
        mem_norm = max(0.0, min(1.0, mem_norm))
        bw_norm = max(0.0, min(1.0, bw_norm))

        rep = self._extract_reputation(meta)
        rep = max(0.0, min(1.0, rep))

        urgency = self._urgency_component(treq, env_view)
        urgency = max(0.0, min(1.0, urgency))

        # Base weighted score
        sw = self.score_weights
        base_score = (sw.get('cpu', 0.0) * cpu_norm +
                      sw.get('mem', 0.0) * mem_norm +
                      sw.get('bw', 0.0) * bw_norm +
                      sw.get('rep', 0.0) * rep +
                      sw.get('urgency', 0.0) * urgency)

        # Load-balance penalty (discourage picking highly utilized nodes)
        sat = self._node_saturation_ratio(res)  # 0..1
        load_penalty = self.load_balance_weight * sat

        score = base_score - load_penalty

        # Optional saturation penalty for heavy usage
        if self.use_saturation_penalty:
            score -= self.saturation_alpha * max(0.0, sat - 0.5)  # penalize only beyond 50% usage

        return float(score)

    # ---------------------------
    # End of class
    # ---------------------------

# Direct run sanity test
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    s = StrategyF({
        'return_mode': 'dict',
        'load_balance_weight': 0.55,
        'use_saturation_penalty': True,
        'saturation_alpha': 0.35,
        'dynamic_norm_per_assign': True,
        'use_urgency': True,
        'score_weights': {'cpu': 0.25, 'mem': 0.15, 'bw': 0.30, 'rep': 0.25, 'urgency': 0.05},
    })

    env = {
        'tick': 0,
        'executors': [
            {'id': 'edge-1', 'type': 'edge', 'reputation': 0.95,
             'resources': {'cpu_total': 100, 'cpu_free': 80, 'mem_total': 8192, 'mem_free': 6000, 'bw_total': 500, 'bw_free': 400}},
            {'id': 'edge-2', 'type': 'edge', 'reputation': 0.80,
             'resources': {'cpu_total': 50, 'cpu_free': 35, 'mem_total': 4096, 'mem_free': 3500, 'bw_total': 300, 'bw_free': 250}},
            {'id': 'uav-1', 'type': 'uav', 'reputation': 0.60,
             'resources': {'cpu_total': 30, 'cpu_free': 20, 'mem_total': 2048, 'mem_free': 1500, 'bw_total': 100, 'bw_free': 80}},
        ]
    }
    tasks = [
        {'id': '0-0', 'requirements': {'cpu': 10, 'mem': 512, 'bw': 50}, 'min_rep': 0.5, 'deadline': 3},
        {'id': '0-1', 'req': {'cpu': 60, 'mem': 2000, 'bw': 100}, 'min_rep': 0.7, 'deadline': 2},
        {'id': '0-2', 'cpu': 5, 'mem': 1024, 'bw': 120, 'min_rep': 0.6},
    ]
    decisions = s.step(tasks, env)
    print(decisions)
