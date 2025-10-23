# scripts/make_hud_demo.py
import os
import csv
from datetime import datetime, timedelta
import random

out_path = os.path.join("data", "replays", "hud_demo.csv")
os.makedirs(os.path.dirname(out_path), exist_ok=True)

fields = [
    "timestamp",
    "uav_id",
    "task_id",
    "strategy",
    "node_type",
    "size_mb",
    "flops_m",
    "latency_ms",
    "energy_J",
    "success",
    "reputation",
]

start = datetime.now()
strategies = ["Random", "LowLatency", "Hybrid", "Reputation"]
node_types = ["local", "D2D", "UAV", "BS", "LEO"]

rows = []
for i in range(200):
    t = start + timedelta(seconds=i * 3)
    uav = f"UAV-{1 + i % 3}"
    task = f"T-{1000 + i}"
    strat = random.choice(strategies)
    node = random.choice(node_types)
    size = round(random.uniform(0.5, 20.0), 2)
    flops = round(random.uniform(50, 800), 1)
    latency = round(random.uniform(10, 900), 1)
    energy = round(random.uniform(0.5, 30.0), 2)
    success = 1 if random.random() > 0.15 else 0
    rep = round(random.uniform(0.2, 0.99), 2)
    rows.append([
        t.isoformat(timespec="seconds"),
        uav,
        task,
        strat,
        node,
        size,
        flops,
        latency,
        energy,
        success,
        rep
    ])

with open(out_path, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(fields)
    writer.writerows(rows)

print(f"Wrote sample CSV: {out_path}  (rows={len(rows)})")
