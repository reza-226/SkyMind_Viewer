import json
import math
import time
from pathlib import Path

def emit_demo(file_path: str, duration_s: float = 20.0, uav_id: str = "u1"):
    out = Path(file_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    t0 = time.perf_counter()
    with out.open("w", encoding="utf-8") as f:
        # Create entities
        f.write(json.dumps({"ts": 0.0, "type": "entity_created", "entity_id": uav_id, "entity_kind": "uav", "x": 0.0, "y": 0.0, "heading": 0.0}) + "\n")
        f.write(json.dumps({"ts": 0.0, "type": "entity_created", "entity_id": "f1", "entity_kind": "fog_bs", "x": 200.0, "y": 100.0}) + "\n")
        f.write(json.dumps({"ts": 0.0, "type": "entity_created", "entity_id": "cloud0", "entity_kind": "cloud", "x": -250.0, "y": -120.0}) + "\n")

        steps = int(duration_s * 30)
        for i in range(steps):
            t = i / 30.0
            angle = t * 0.8
            x = 180 * math.cos(angle)
            y = 120 * math.sin(angle)
            ev = {"ts": t, "type": "uav_pose", "entity_id": uav_id, "x": x, "y": y, "heading": angle}
            f.write(json.dumps(ev) + "\n")
            if i % 45 == 0:
                # emit a task submit every 1.5s
                f.write(json.dumps({"ts": t, "type": "task_submit", "task_id": f"task{i}", "src_id": uav_id, "dst_id": "f1", "size_bits": 2_000_000}) + "\n")

        # final sim time
        f.write(json.dumps({"ts": duration_s, "type": "sim_time", "t": duration_s}) + "\n")

if __name__ == "__main__":
    emit_demo("runs/demo.replay.jsonl", duration_s=30.0)
