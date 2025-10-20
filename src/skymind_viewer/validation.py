# src/skymind_viewer/validation.py

from typing import Dict, List, Any, Tuple

VALID_ENTITY_KINDS = {"UAV", "Fog", "Cloud", "UE"}
VALID_MODES = {"local", "fog", "cloud", "peer"}
VALID_LINK_KINDS = {"RF", "Backhaul", "LoRa", "mmWave"}

class ValidationResult:
    def __init__(self):
        self.counters: Dict[str, int] = {}
        self.errors: List[str] = []
        self.warnings: List[str] = []

    @property
    def errors_count(self) -> int:
        return len(self.errors)

    @property
    def warnings_count(self) -> int:
        return len(self.warnings)

def _is_num(x) -> bool:
    return isinstance(x, (int, float))

def validate_events(events: List[Dict[str, Any]]) -> ValidationResult:
    """
    Stricter validation aligned with snapshot_schema v0.2:
    - Required fields and types per event
    - Referential integrity for entities and tasks
    - Time monotonicity check
    """
    res = ValidationResult()
    entities: Dict[str, str] = {}  # id -> kind
    tasks_seen: Dict[str, str] = {}  # task_id -> src
    prev_t = None

    def count(typ: str):
        res.counters[typ] = res.counters.get(typ, 0) + 1

    for i, evt in enumerate(events):
        typ = evt.get("type", "unknown")
        count(typ)
        # t & idx presence
        if "t" not in evt:
            res.errors.append(f"[{i}] missing 't'")
        else:
            t = evt["t"]
            if not _is_num(t):
                res.errors.append(f"[{i}] 't' must be numeric")
            else:
                if prev_t is not None and t < prev_t:
                    res.errors.append(f"[{i}] non-monotonic time: {t} < {prev_t}")
                prev_t = t
        if "idx" not in evt:
            res.warnings.append(f"[{i}] missing 'idx' (will be added on load)")

        if typ == "entity_created":
            rid = evt.get("id")
            kind = evt.get("kind")
            x = evt.get("x"); y = evt.get("y")
            if not rid or not isinstance(rid, str):
                res.errors.append(f"[{i}] entity_created requires string 'id'")
            if kind not in VALID_ENTITY_KINDS:
                res.errors.append(f"[{i}] invalid kind '{kind}'")
            if not _is_num(x) or not _is_num(y):
                res.errors.append(f"[{i}] entity_created requires numeric x,y")
            if rid in entities:
                res.errors.append(f"[{i}] duplicate entity id '{rid}'")
            else:
                entities[rid] = kind

        elif typ == "uav_pose":
            rid = evt.get("id")
            x = evt.get("x"); y = evt.get("y")
            if not rid or rid not in entities:
                res.errors.append(f"[{i}] uav_pose id '{rid}' not known")
            if not _is_num(x) or not _is_num(y):
                res.errors.append(f"[{i}] uav_pose requires numeric x,y")

        elif typ == "task_submit":
            tid = evt.get("task_id"); src = evt.get("src")
            if not tid or not isinstance(tid, str):
                res.errors.append(f"[{i}] task_submit requires 'task_id' string")
            elif tid in tasks_seen:
                res.errors.append(f"[{i}] duplicate task_id '{tid}' on submit")
            if not src or src not in entities:
                res.errors.append(f"[{i}] task_submit src '{src}' not known")
            # optional numeric fields
            for k in ("size", "cpu", "deadline"):
                if k in evt and evt[k] is not None and not _is_num(evt[k]):
                    res.errors.append(f"[{i}] task_submit {k} must be numeric")
            # hint
            hint = evt.get("hint")
            if hint is not None and hint not in VALID_MODES:
                res.errors.append(f"[{i}] task_submit hint invalid '{hint}'")
            if tid and src in entities:
                tasks_seen[tid] = src

        elif typ == "task_assigned":
            tid = evt.get("task_id"); src = evt.get("src"); dst = evt.get("dst")
            mode = evt.get("mode")
            if not tid or tid not in tasks_seen:
                res.errors.append(f"[{i}] task_assigned unknown task_id '{tid}'")
            if src not in entities:
                res.errors.append(f"[{i}] task_assigned src '{src}' not known")
            if dst not in entities:
                res.errors.append(f"[{i}] task_assigned dst '{dst}' not known")
            if mode not in VALID_MODES:
                res.errors.append(f"[{i}] task_assigned invalid mode '{mode}'")

        elif typ == "task_completed":
            tid = evt.get("task_id"); src = evt.get("src"); dst = evt.get("dst")
            if tid not in tasks_seen:
                res.errors.append(f"[{i}] task_completed unknown task_id '{tid}'")
            for role, rid in (("src", src), ("dst", dst)):
                if rid not in entities:
                    res.errors.append(f"[{i}] task_completed {role} '{rid}' not known")
            for k in ("latency", "energy"):
                if k in evt and evt[k] is not None and not _is_num(evt[k]):
                    res.errors.append(f"[{i}] task_completed {k} must be numeric")
            if "success" in evt and not isinstance(evt["success"], bool):
                res.errors.append(f"[{i}] task_completed success must be bool")

        elif typ == "offload_decision":
            tid = evt.get("task_id"); src = evt.get("src"); dst = evt.get("dst")
            if tid not in tasks_seen:
                res.errors.append(f"[{i}] offload_decision unknown task_id '{tid}'")
            if src not in entities or dst not in entities:
                res.errors.append(f"[{i}] offload_decision src/dst must exist (src={src}, dst={dst})")
            if "reason" in evt and evt["reason"] is not None and not isinstance(evt["reason"], str):
                res.errors.append(f"[{i}] offload_decision reason must be str")
            # link is opaque id/type; allow any str
            if "link" in evt and evt["link"] is not None and not isinstance(evt["link"], str):
                res.errors.append(f"[{i}] offload_decision link must be str")

        elif typ == "link_up":
            a = evt.get("a"); b = evt.get("b")
            if a not in entities or b not in entities:
                res.errors.append(f"[{i}] link_up requires existing endpoints (a={a}, b={b})")
            kind = evt.get("kind")
            if kind is not None and kind not in VALID_LINK_KINDS:
                res.errors.append(f"[{i}] link_up invalid kind '{kind}'")

        elif typ == "link_down":
            a = evt.get("a"); b = evt.get("b")
            if a not in entities or b not in entities:
                res.errors.append(f"[{i}] link_down requires existing endpoints (a={a}, b={b})")

        elif typ == "sim_tick":
            dt = evt.get("dt")
            if not _is_num(dt):
                res.errors.append(f"[{i}] sim_tick dt must be numeric")

        else:
            res.warnings.append(f"[{i}] unknown event type '{typ}'")

    # rollup counters
    res.counters["__errors__"] = res.errors_count
    res.counters["__warnings__"] = res.warnings_count
    res.counters["__entities__"] = len(entities)
    res.counters["__tasks__"] = len(tasks_seen)
    return res
