#!/usr/bin/env python3
import json, random, argparse

def emit(f, t, etype, payload):
    f.write(json.dumps({"t": t, "type": etype, **payload}) + "\n")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--duration", type=int, default=30)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--uavs", type=int, default=2)
    ap.add_argument("--output", type=str, default="data/replays/hud_demo_v0.2.2.jsonl")
    args = ap.parse_args()
    random.seed(args.seed)

    dt = 0.5
    uavs = [f"uav-{i+1}" for i in range(args.uavs)]
    state = {
        u: {
            "battery": 100.0,
            "cpu": 0.35 + 0.1*random.random(),
            "queue": random.randint(0, 3),
            "link_up": True,
            "cache": 0.6 + 0.1*random.random(),
            "pos": [random.uniform(0, 30), random.uniform(0, 30), 100.0]
        } for u in uavs
    }

    with open(args.output, "w", encoding="utf-8") as f:
        emit(f, 0.0, "session_start", {"session_id": "hud_demo_v0.2.2"})
        t = 0.0
        while t <= args.duration:
            for u in uavs:
                s = state[u]
                # motion
                s["pos"][0] += 4.0 + random.uniform(-0.5, 0.5)
                s["pos"][1] += 2.0 + random.uniform(-0.5, 0.5)
                s["pos"][2] = 100.0 + random.choice([-5, 0, 5])
                # energy and compute
                s["battery"] -= 0.5 + 0.2*random.random()
                s["cpu"] = max(0.05, min(0.98, s["cpu"] + random.uniform(-0.1, 0.1)))
                s["queue"] = max(0, s["queue"] + random.choice([-1, 0, 1]))
                s["cache"] = max(0.0, min(1.0, s["cache"] + random.uniform(-0.05, 0.05)))

                # link flap
                if random.random() < 0.06:
                    s["link_up"] = not s["link_up"]
                    emit(f, t, "link_event", {"uav_id": u, "link": {"up": s["link_up"], "rssi": (-58 if s["link_up"] else None)}})

                # offload decision
                if random.random() < 0.1:
                    target = random.choice(["edge-1","edge-2","sat-LEO-3"])
                    emit(f, t, "offload_decision", {
                        "uav_id": u,
                        "task_id": f"task-{u}-{int(t*10)}",
                        "decision": {"target": target, "reason": "latency/energy tradeoff", "est_latency_ms": int(80+random.random()*120)}
                    })
                    s["queue"] = max(0, s["queue"]-1)

                # HUD telemetry_tick per Schema v0.2.1
                emit(f, t, "telemetry_tick", {
                    "uav_id": u,
                    "pos": {"x": round(s["pos"][0],2), "y": round(s["pos"][1],2), "z": s["pos"][2]},
                    "energy": {"battery_pct": round(s["battery"],1), "consumption_w": round(45+10*random.random(),1)},
                    "compute": {"cpu_util": round(s["cpu"],2), "queue_len": s["queue"]},
                    "link": {"up": s["link_up"], "throughput_mbps": (round(12+8*random.random(),2) if s["link_up"] else 0.0)},
                    "cache": {"hit_ratio": round(s["cache"],2), "size_mb": 64}
                })
            t = round(t + dt, 2)

        emit(f, t, "session_end", {"session_id": "hud_demo_v0.2.2"})

if __name__ == "__main__":
    main()
