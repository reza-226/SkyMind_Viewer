# sim/strategies/strategy_f.py
# StrategyF — legacy-compatible decision generator with executor/status guarantees
# - Guarantees executor/status for all decisions via legacy fallback
# - Also mirrors executor into 'node' for runners that expect 'node'
# - Preserves informative logging and handles empty candidate sets

from typing import Any, Dict, Iterable, List, Optional
import logging

logger = logging.getLogger(__name__)


class StrategyF:
    """
    StrategyF decides how to execute pending tasks at each tick.

    Legacy guarantees:
      - Returns a dict mapping task_id -> decision dict
      - Each decision contains:
          status: "accepted"
          executor: <non-empty> (defaults to local-derived ID)
          node: same as executor (for compatibility with older runners)
          reason: one of {"auto-select", "legacy-fallback"}
      - If step() produces empty or executors are missing, tick() falls back to local execution for all pending tasks.

    Config keys (optional):
      - default_executor: str -> overrides local executor detection
      - reputation_scale_max: float -> for normalization logs (default: 1.0)
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        self.config = config or {}
        self._accepted_total = 0
        logger.info("[StrategyF] Initialized with config keys=%s", list(self.config.keys()))

    # ------------------------------
    # Public API
    # ------------------------------

    def step(self, world: Any) -> Dict[str, Dict[str, Any]]:
        """
        Produce raw decisions for tasks in the current world state.
        Tries selecting a remote executor if available; otherwise logs feasibility issues and leaves to fallback.
        """
        tasks = self._get_pending_tasks(world)
        decisions: Dict[str, Dict[str, Any]] = {}

        for t in tasks:
            # Emit reputation/SLO-style debug info (optional normalization for logs)
            self._log_task_reputation_info(t, world)

            # Candidate executors/nodes for this task
            candidates = self._get_candidate_nodes(world, t)
            self._log_candidates_summary(world, candidates)

            # Try selecting an executor
            executor = self._select_executor_from_candidates(candidates)
            if executor is not None:
                decisions[str(self._get_task_id(t))] = {
                    "status": "accepted",
                    "executor": executor,
                    "node": executor,            # mirror for compatibility
                    "reason": "auto-select",
                }
            else:
                # No feasible executor in this step; fallback will handle
                logger.info("[StrategyF] No feasible executor for task=%s (reputation/SLO/resources)", self._task_label(t))

        accepted_now = sum(1 for d in decisions.values() if d.get("status") == "accepted")
        self._accepted_total += accepted_now
        logger.info("[StrategyF] step result: acc=%d, skipped=%d", self._accepted_total, 0)

        return decisions

    def tick(self, world: Any) -> Dict[str, Dict[str, Any]]:
        """
        Wrap step() with legacy adapter:
          - If step returns empty OR any decision lacks executor, fill all pending tasks with local executor.
          - Always ensure 'status' is present and equals 'accepted'.
          - Mirror 'executor' into 'node' for runners that rely on 'node'.
        """
        decisions = self.step(world)

        needs_fallback = (not decisions) or any(not self._has_executor(d) for d in decisions.values())
        if needs_fallback:
            tasks = self._get_pending_tasks(world)
            local_exec = self._get_local_executor_id(world)

            # Informative log similar to your 11.txt when no UAV/EDGE found
            if self._count_entities(world) == (0, 0):
                logger.warning("[StrategyF] No UAV/EDGE found; enabling per-task local fallback.")

            decisions = {
                str(self._get_task_id(t)): {
                    "status": "accepted",
                    "executor": local_exec,
                    "node": local_exec,          # mirror
                    "reason": "legacy-fallback",
                }
                for t in tasks
            }

        decisions = self._ensure_status_and_executor(decisions, world)
        return decisions

    # ------------------------------
    # Helpers
    # ------------------------------

    def _ensure_status_and_executor(self, decisions: Dict[str, Dict[str, Any]], world: Any) -> Dict[str, Dict[str, Any]]:
        """
        Ensure each decision has status='accepted' and a valid executor, mirror into 'node', and set reason if needed.
        """
        local_exec = self._get_local_executor_id(world)

        for tid, d in list(decisions.items()):
            if not isinstance(d, dict):
                d = {"status": "accepted", "executor": local_exec, "node": local_exec, "reason": "legacy-fallback"}
            else:
                # status
                d.setdefault("status", "accepted")
                # executor
                if not self._has_executor(d):
                    d["executor"] = local_exec
                    d.setdefault("reason", "legacy-fallback")
                # node (compat)
                if not self._has_node(d):
                    d["node"] = d.get("executor", local_exec)
                # default reason when auto-selected
                d.setdefault("reason", "auto-select" if d.get("executor") != local_exec else "legacy-fallback")
            decisions[tid] = d

        return decisions

    def _get_pending_tasks(self, world: Any) -> List[Any]:
        """
        Obtain pending tasks using common world interfaces.
        """
        tasks: Iterable[Any] = []
        if hasattr(world, "get_pending_tasks") and callable(world.get_pending_tasks):
            try:
                tasks = world.get_pending_tasks() or []
            except Exception:
                tasks = []
        elif hasattr(world, "get_tasks") and callable(world.get_tasks):
            try:
                tasks = world.get_tasks() or []
            except Exception:
                tasks = []
        else:
            for attr in ("pending_tasks", "tasks"):
                if hasattr(world, attr):
                    maybe = getattr(world, attr)
                    if isinstance(maybe, Iterable):
                        tasks = maybe
                        break

        try:
            return list(tasks)
        except Exception:
            return [t for t in tasks]

    def _get_candidate_nodes(self, world: Any, task: Any) -> List[Any]:
        """
        Try common world APIs to get candidate executors/nodes for the given task.
        """
        candidates: List[Any] = []

        for name in ("get_candidate_nodes", "get_available_executors", "get_available_nodes"):
            if hasattr(world, name) and callable(getattr(world, name)):
                fn = getattr(world, name)
                try:
                    got = fn(task)
                except TypeError:
                    got = fn()
                except Exception:
                    got = []
                try:
                    candidates = list(got)
                except Exception:
                    candidates = [n for n in got]
                if candidates:
                    return candidates

        for attr in ("executors", "nodes", "cluster", "neighbors"):
            if hasattr(world, attr):
                try:
                    coll = list(getattr(world, attr))
                except Exception:
                    coll = []
                if coll:
                    return coll

        return candidates  # empty

    def _select_executor_from_candidates(self, candidates: List[Any]) -> Optional[str]:
        """
        Pick a simple viable executor from candidates. For now, choose the first and normalize its ID.
        """
        if not candidates:
            return None
        chosen = candidates[0]
        return self._normalize_executor_id(chosen)

    def _get_local_executor_id(self, world: Any) -> str:
        """
        Derive a local executor identifier from the world or config.
        """
        if isinstance(self.config.get("default_executor"), str) and self.config["default_executor"].strip():
            return self.config["default_executor"].strip()

        for attr in ("local_executor_id", "local_id", "uav_id", "node_id", "agent_id", "device_id"):
            if hasattr(world, attr):
                val = getattr(world, attr)
                if val:
                    return str(val)

        if hasattr(world, "local"):
            val = getattr(world, "local")
            if val is not None:
                for k in ("id", "node_id", "executor_id", "name"):
                    if hasattr(val, k):
                        nid = getattr(val, k)
                        if nid is not None:
                            return str(nid)

        return "local"

    def _log_task_reputation_info(self, task: Any, world: Any) -> None:
        """
        Emit reputation normalization debug line.
        """
        min_rep_raw = self._get_required_reputation(task, world)
        scale_max = float(self.config.get("reputation_scale_max", 1.0))
        try:
            min_rep_norm = min_rep_raw / scale_max if scale_max > 0 else min_rep_raw
        except Exception:
            min_rep_norm = min_rep_raw

        logger.debug(
            "[StrategyF] Task=%s | min_rep_raw=%.3f | scale_max=%.1f | min_rep_norm=%.3f",
            self._task_label(task),
            min_rep_raw,
            scale_max,
            min_rep_norm,
        )

    def _get_required_reputation(self, task: Any, world: Any) -> float:
        for attr in ("min_reputation", "min_rep", "required_rep", "reputation_threshold"):
            if hasattr(task, attr):
                val = getattr(task, attr)
                if isinstance(val, (int, float)):
                    return float(val)
        if hasattr(world, "default_min_rep"):
            val = getattr(world, "default_min_rep")
            try:
                return float(val)
            except Exception:
                pass
        return 0.5

    def _log_candidates_summary(self, world: Any, candidates: List[Any]) -> None:
        """
        Log a short summary of candidate reputations and entity counts to mirror prior style.
        """
        reps = self._sample_node_reputations(candidates, world)
        if reps:
            logger.debug("| node_reps_sample=%s", reps)
        else:
            logger.debug("| node_reps_sample=[]")

        uavs, edges = self._count_entities(world)
        logger.debug("| counts(uavs=%d, edges=%d)", uavs, edges)
        if uavs == 0 and edges == 0 and not candidates:
            logger.warning("[StrategyF] No UAV/EDGE found; enabling per-task local fallback.")

    def _sample_node_reputations(self, nodes: List[Any], world: Any, k: int = 0) -> List[float]:
        reps: List[float] = []
        for n in nodes:
            rep = None
            for attr in ("reputation", "rep", "trust", "score"):
                if hasattr(n, attr):
                    rep = getattr(n, attr)
                    break
            if rep is None and hasattr(world, "get_reputation") and callable(world.get_reputation):
                try:
                    rep = world.get_reputation(n)
                except Exception:
                    rep = None
            if isinstance(rep, (int, float)):
                reps.append(float(rep))
        if k and len(reps) > k:
            return reps[:k]
        return reps

    def _count_entities(self, world: Any) -> (int, int):
        """
        Count UAVs and edge nodes if available for logging.
        """
        uavs = 0
        edges = 0
        for attr in ("uavs", "UAVs", "drones"):
            if hasattr(world, attr):
                try:
                    uavs = len(list(getattr(world, attr)))
                    break
                except Exception:
                    pass
        for attr in ("edges", "edge_nodes", "servers", "executors", "nodes"):
            if hasattr(world, attr):
                try:
                    edges = len(list(getattr(world, attr)))
                    break
                except Exception:
                    pass
        return uavs, edges

    @staticmethod
    def _normalize_executor_id(executor_obj: Any) -> str:
        if isinstance(executor_obj, (str, int)):
            return str(executor_obj)
        for attr in ("id", "node_id", "executor_id", "name"):
            if hasattr(executor_obj, attr):
                val = getattr(executor_obj, attr)
                if val is not None:
                    return str(val)
        return str(executor_obj)

    @staticmethod
    def _has_executor(decision: Dict[str, Any]) -> bool:
        exec_val = decision.get("executor")
        return isinstance(exec_val, str) and len(exec_val.strip()) > 0

    @staticmethod
    def _has_node(decision: Dict[str, Any]) -> bool:
        node_val = decision.get("node")
        return isinstance(node_val, str) and len(node_val.strip()) > 0

    @staticmethod
    def _get_task_id(task: Any) -> Any:
        for attr in ("id", "task_id", "uuid", "name"):
            if hasattr(task, attr):
                return getattr(task, attr)
        return str(task)

    @staticmethod
    def _task_label(task: Any) -> str:
        for attr in ("label", "name", "id", "task_id"):
            if hasattr(task, attr):
                val = getattr(task, attr)
                if val is not None:
                    return str(val)
        return str(task)
