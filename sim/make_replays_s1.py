#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
make_replays_s1.py
Stage S1 simulator: run multiple strategies (random, min_delay, edw, ecori)
and write a single combined CSV with a 'strategy' column for HUD filtering.

Default output: data/replays/s1/s1_all_strategies.csv
"""

import math
import csv
import random
import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Tuple, Optional

# =========================
# Data models and utilities
# =========================

@dataclass
class Node:
    node_id: int
    x: float
    y: float
    cpu_cycles_per_s: float  # cycles/sec (remote edge compute rate)
    bw_hz: float             # uplink bandwidth (Hz) from UAV to node
    reputation: float        # [0, 1]
    name: str                # human-readable label

@dataclass
class UAVState:
    x: float
    y: float
    yaw_deg: float
    heading_deg: float
    speed_mps: float

def ensure_parent_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

# =========================
# Path and environment model
# =========================

def uav_path(steps: int,
             radius_m: float = 500.0,
             center: Tuple[float, float] = (0.0, 0.0),
             angular_speed_rad_per_step: float = 2 * math.pi / 600,
             speed_mps: float = 15.0) -> List[UAVState]:
    """
    Generate a smooth circular path for the UAV. Returns yaw and heading in degrees.
    HUD uses Yaw and Heading columns; here we set them equal to the tangent angle.
    """
    cx, cy = center
    path = []
    for t in range(steps):
        theta = t * angular_speed_rad_per_step
        x = cx + radius_m * math.cos(theta)
        y = cy + radius_m * math.sin(theta)
        # Tangent angle to the circle is theta + 90 degrees
        heading_rad = theta + math.pi / 2.0
        heading_deg = (heading_rad * 180.0 / math.pi) % 360.0
        yaw_deg = heading_deg
        path.append(UAVState(x=x, y=y, yaw_deg=yaw_deg, heading_deg=heading_deg, speed_mps=speed_mps))
    return path

def build_nodes(n_nodes: int,
                area_bbox: Tuple[float, float, float, float] = (-800, 800, -800, 800),
                seed: int = 42) -> List[Node]:
    """
    Create synthetic edge nodes scattered in area with heterogeneous CPU, BW, reputation.
    """
    rng = random.Random(seed)
    xmin, xmax, ymin, ymax = area_bbox
    nodes: List[Node] = []
    for i in range(n_nodes):
        x = rng.uniform(xmin, xmax)
        y = rng.uniform(ymin, ymax)
        # CPU cycles per second: 0.5e9 to 3e9 cycles/s
        cpu = rng.uniform(0.5e9, 3.0e9)
        # Bandwidth: 5 MHz to 20 MHz
        bw_hz = rng.uniform(5e6, 20e6)
        # Reputation: skewed towards good but with diversity
        reputation = min(1.0, max(0.0, rng.gauss(0.75, 0.15)))
        nodes.append(Node(node_id=i, x=x, y=y, cpu_cycles_per_s=cpu, bw_hz=bw_hz,
                          reputation=reputation, name=f"edge_{i}"))
    return nodes

# =========================
# Link budget and costs
# =========================

def distance(uav: UAVState, node: Node) -> float:
    dx = uav.x - node.x
    dy = uav.y - node.y
    return math.hypot(dx, dy)

def shannon_rate_mbps(snr_linear: float, bw_hz: float) -> float:
    # R = B * log2(1+SNR), convert to Mbps
    return (bw_hz * math.log2(1.0 + snr_linear)) / 1e6

def environment_factors(uav: UAVState,
                        node: Node,
                        tx_power_w: float = 1.0,
                        noise_psd_w_per_hz: float = 3.98e-21,  # ~ -174 dBm/Hz
                        pathloss_alpha: float = 2.7,
                        d0_m: float = 1.0) -> Dict[str, float]:
    """
    Compute approximate SNR and achievable rate between UAV and a node.
    We use a simple distance-based path loss model for SNR.
    """
    d = max(1.0, distance(uav, node))
    # SNR ≈ (Pt / (N0 * B)) * (d0/d)^alpha
    snr = (tx_power_w / (noise_psd_w_per_hz * node.bw_hz)) * ((d0_m / d) ** pathloss_alpha)
    rate_mbps = shannon_rate_mbps(max(1e-6, snr), node.bw_hz)
    return {"distance_m": d, "snr": snr, "rate_mbps": rate_mbps}

def expected_costs(uav: UAVState,
                   node: Optional[Node],
                   task_mb: float,
                   cycles_per_mb: float,
                   uav_cpu_cycles_per_s: float = 0.8e9,
                   cpu_j_per_cycle: float = 1e-9,
                   tx_power_w: float = 1.0,
                   propulsion_j_per_step: float = 5.0) -> Dict[str, float]:
    """
    Compute delay (ms) and energy (J) for either local (node=None) or offloading to node.
    Energy is UAV-side: transmission + local compute + propulsion.
    """
    total_cycles = task_mb * cycles_per_mb
    record: Dict[str, float] = {}
    if node is None:
        # Local processing on UAV
        proc_time_s = total_cycles / uav_cpu_cycles_per_s
        delay_ms = proc_time_s * 1000.0
        energy_compute_j = total_cycles * cpu_j_per_cycle
        energy_tx_j = 0.0
        record["target_type"] = "local"
        record["rate_mbps"] = 0.0
        record["distance_m"] = 0.0
    else:
        # Offload to edge node: uplink tx + remote processing + negligible ack
        env = environment_factors(uav, node)
        rate_mbps = max(0.1, env["rate_mbps"])  # avoid zero
        tx_time_s = (task_mb * 8.0) / rate_mbps  # MB -> Mb, then divide by Mbps
        remote_proc_s = total_cycles / node.cpu_cycles_per_s
        delay_ms = (tx_time_s + remote_proc_s) * 1000.0
        energy_tx_j = tx_power_w * tx_time_s
        energy_compute_j = 0.0  # remote energy not counted for UAV
        record["target_type"] = "edge"
        record["rate_mbps"] = rate_mbps
        record["distance_m"] = env["distance_m"]
    energy_total_j = energy_tx_j + energy_compute_j + propulsion_j_per_step
    record["delay_ms"] = delay_ms
    record["energy_j"] = energy_total_j
    record["energy_tx_j"] = energy_tx_j
    record["energy_compute_j"] = energy_compute_j
    record["propulsion_j"] = propulsion_j_per_step
    return record

# =========================
# Strategy decision rules
# =========================

def choose_target(strategy: str,
                  uav: UAVState,
                  nodes: List[Node],
                  task_mb: float,
                  cycles_per_mb: float,
                  reputation_threshold: float = 0.6) -> Tuple[Optional[Node], Dict[str, float]]:
    """
    Return selected node (or None for local) and its costs dictionary.
    Supported strategies:
      - random: any option (local or any edge) uniformly
      - min_delay: minimize delay_ms
      - edw: energy-delay weighted (normalized min of 0.6*delay + 0.4*energy)
      - ecori: prioritize nodes with reputation>=threshold, choose min_delay among them; fallback to local
    """
    # Compute all options (local + each node)
    options: List[Tuple[Optional[Node], Dict[str, float]]] = []
    local_costs = expected_costs(uav, None, task_mb, cycles_per_mb)
    options.append((None, local_costs))
    for n in nodes:
        c = expected_costs(uav, n, task_mb, cycles_per_mb)
        # Attach reputation for decision convenience
        c["reputation"] = n.reputation
        options.append((n, c))

    if strategy == "random":
        return random.choice(options)

    if strategy == "min_delay":
        return min(options, key=lambda it: it[1]["delay_ms"])

    if strategy == "edw":
        delays = [it[1]["delay_ms"] for it in options]
        energies = [it[1]["energy_j"] for it in options]
        dmin, dmax = min(delays), max(delays)
        emin, emax = min(energies), max(energies)
        def norm(v, vmin, vmax):
            return 0.0 if math.isclose(vmin, vmax) else (v - vmin) / (vmax - vmin)
        weights = []
        for it in options:
            d_norm = norm(it[1]["delay_ms"], dmin, dmax)
            e_norm = norm(it[1]["energy_j"], emin, emax)
            score = 0.6 * d_norm + 0.4 * e_norm
            it[1]["edw_score"] = score
            weights.append(score)
        return min(options, key=lambda it: it[1]["edw_score"])

    if strategy == "ecori":
        # Filter by reputation, then pick min delay
        eligible = [(n, c) for (n, c) in options if (n is None) or (c.get("reputation", 0.0) >= reputation_threshold)]
        # Ensure local option always present
        # Choose min delay among eligible
        return min(eligible, key=lambda it: it[1]["delay_ms"])

    raise ValueError(f"Unknown strategy: {strategy}")

# =========================
# Simulation driver
# =========================

def simulate_strategy(strategy: str,
                      nodes: List[Node],
                      uav_traj: List[UAVState],
                      steps: int,
                      rng: random.Random,
                      task_mb_range: Tuple[float, float] = (4.0, 24.0),
                      cycles_per_mb_range: Tuple[float, float] = (30e6, 80e6)) -> List[Dict[str, object]]:
    """
    Simulate per-step task assignments for a single strategy over a fixed trajectory.
    Returns a list of rows ready for CSV.
    """
    rows: List[Dict[str, object]] = []
    for step_idx in range(steps):
        uav = uav_traj[step_idx]
        # One task per step (S1), randomly sized
        task_mb = rng.uniform(*task_mb_range)
        cycles_per_mb = rng.uniform(*cycles_per_mb_range)
        target_node, costs = choose_target(strategy, uav, nodes, task_mb, cycles_per_mb)

        row = {
            "step": step_idx,
            "time_s": step_idx,  # 1s per step
            "uav_x": round(uav.x, 3),
            "uav_y": round(uav.y, 3),
            "Yaw": round(uav.yaw_deg, 3),
            "Heading": round(uav.heading_deg, 3),
            "strategy": strategy,
            "task_mb": round(task_mb, 3),
            "cycles_per_mb": round(cycles_per_mb, 1),
            "target_type": costs["target_type"],
            "node_id": (None if target_node is None else target_node.node_id),
            "node_name": (None if target_node is None else target_node.name),
            "distance_m": round(costs.get("distance_m", 0.0), 3),
            "rate_mbps": round(costs.get("rate_mbps", 0.0), 3),
            "delay_ms": round(costs["delay_ms"], 3),
            "energy_j": round(costs["energy_j"], 6),
            "energy_tx_j": round(costs["energy_tx_j"], 6),
            "energy_compute_j": round(costs["energy_compute_j"], 6),
            "propulsion_j": round(costs["propulsion_j"], 6),
        }
        # For EDW strategy include score
        if "edw_score" in costs:
            row["edw_score"] = round(costs["edw_score"], 6)
        # For ECORI include reputation if offloaded
        if target_node is not None:
            row["reputation"] = round(target_node.reputation, 4)
            row["node_cpu_cycles_per_s"] = round(target_node.cpu_cycles_per_s, 1)
            row["node_bw_hz"] = round(target_node.bw_hz, 1)
        rows.append(row)
    return rows

def write_combined_csv(out_path: Path, rows: List[Dict[str, object]]) -> None:
    ensure_parent_dir(out_path)
    # Union of keys
    fieldnames: List[str] = [
        "step", "time_s", "uav_x", "uav_y", "Yaw", "Heading",
        "strategy", "task_mb", "cycles_per_mb",
        "target_type", "node_id", "node_name",
        "distance_m", "rate_mbps",
        "delay_ms", "energy_j", "energy_tx_j", "energy_compute_j", "propulsion_j",
        "edw_score", "reputation", "node_cpu_cycles_per_s", "node_bw_hz"
    ]
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for r in rows:
            writer.writerow(r)

def run_sim(out_path: Path,
            steps: int,
            seed: int,
            n_nodes: int,
            radius_m: float) -> None:
    rng = random.Random(seed)
    nodes = build_nodes(n_nodes=n_nodes, seed=seed)
    uav_traj = uav_path(steps=steps, radius_m=radius_m, angular_speed_rad_per_step=2 * math.pi / steps)
    strategies = ["random", "min_delay", "edw", "ecori"]
    all_rows: List[Dict[str, object]] = []
    # Use the same environment and RNG stream per strategy but branch the RNG to keep comparability
    for s in strategies:
        # Derive a sub-seed per strategy to keep task sequence consistent but separable
        sub_rng = random.Random(hash((seed, s)) & 0xffffffff)
        rows = simulate_strategy(s, nodes, uav_traj, steps, sub_rng)
        all_rows.extend(rows)
    write_combined_csv(out_path, all_rows)
    print(f"Wrote {len(all_rows)} rows to {out_path}")

# =========================
# CLI
# =========================

def parse_args():
    p = argparse.ArgumentParser(description="S1 combined strategies simulator to CSV")
    p.add_argument("--out-file", type=str, default="data/replays/s1/s1_all_strategies.csv",
                   help="Output CSV path (default: data/replays/s1/s1_all_strategies.csv)")
    p.add_argument("--steps", type=int, default=600, help="Number of steps (default: 600)")
    p.add_argument("--seed", type=int, default=42, help="Random seed (default: 42)")
    p.add_argument("--nodes", type=int, default=8, help="Number of edge nodes (default: 8)")
    p.add_argument("--radius", type=float, default=500.0, help="UAV path radius in meters (default: 500)")
    return p.parse_args()

def main():
    args = parse_args()
    out_path = Path(args.out_file)
    run_sim(out_path=out_path, steps=args.steps, seed=args.seed, n_nodes=args.nodes, radius_m=args.radius)

if __name__ == "__main__":
    main()
