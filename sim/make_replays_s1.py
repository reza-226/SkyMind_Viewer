#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
make_replays_s1.py
Generate synthetic replays for Scenario S1: ECORI vs baselines.
Produces CSV files per strategy under data/replays/s1/.

Strategies:
- random: assignment is random among nodes
- min_delay: assign to node with lowest expected delay
- edw: energy-delay weighted tradeoff (alpha*delay + beta*energy)
- ecori: reputation-aware offloading (threshold + priority order)

Each CSV row is one timestep aggregate:
- time_ms: simulation time
- x, y, z: UAV position
- speed_mps: UAV speed
- Yaw, Heading: degrees
- strategy: strategy name
- kpi_success_rate: [0..1] per timestep (processed tasks)
- kpi_delay_mean_ms: average delay of tasks this timestep
- kpi_energy_mean_j: average energy of tasks this timestep
"""

import argparse
import os
from dataclasses import dataclass
import math
import random
from typing import List, Dict, Tuple

import numpy as np
import pandas as pd


@dataclass
class Node:
    name: str
    base_delay_ms: float
    base_energy_j: float
    reliability: float  # intrinsic reliability [0..1]
    reputation: float = 0.6  # dynamic reputation [0..1], used by ECORI


def ensure_out_dir(path: str):
    os.makedirs(path, exist_ok=True)


def uav_path(total_steps: int, radius_m: float = 500.0, altitude_m: float = 120.0, max_speed_mps: float = 18.0
             ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Generate a smooth circular-ish path for the UAV.
    Returns arrays: x, y, z, yaw_deg, heading_deg, and speed_mps.
    """
    t = np.linspace(0, 2 * math.pi, total_steps)
    # Circle with slight harmonic perturbation
    x = radius_m * np.cos(t) + 50 * np.cos(3 * t)
    y = radius_m * np.sin(t) + 50 * np.sin(2 * t)
    z = np.full(total_steps, altitude_m)
    # Heading from derivative
    dx = np.gradient(x)
    dy = np.gradient(y)
    heading_rad = np.arctan2(dy, dx)
    heading_deg = (np.degrees(heading_rad) + 360) % 360
    # Yaw follows heading with small noise
    yaw_deg = heading_deg + np.random.normal(0, 3, size=total_steps)
    # Speed based on path arc length per step
    step_dist = np.sqrt(dx**2 + dy**2)
    # Normalize to max speed
    speed_mps = (step_dist / (np.max(step_dist) + 1e-9)) * max_speed_mps
    return x, y, z, yaw_deg, heading_deg, speed_mps


def environment_factors(total_steps: int, seed: int) -> Dict[str, np.ndarray]:
    """
    Time-varying environment multipliers for delay and energy per node type.
    """
    rng = np.random.default_rng(seed)
    # Slightly different patterns for each node
    def smooth_noise(scale=0.15):
        base = rng.normal(0, scale, total_steps)
        return np.convolve(base, np.ones(5)/5, mode='same')

    env = {
        "local_delay_mul": 1.0 + smooth_noise(0.10),
        "local_energy_mul": 1.0 + smooth_noise(0.05),
        "bs_delay_mul": 1.2 + smooth_noise(0.12),
        "bs_energy_mul": 0.9 + smooth_noise(0.06),
        "peer_delay_mul": 1.1 + smooth_noise(0.15),
        "peer_energy_mul": 0.95 + smooth_noise(0.06),
        "sat_delay_mul": 1.6 + smooth_noise(0.20),
        "sat_energy_mul": 0.85 + smooth_noise(0.04),
        "channel_quality": np.clip(0.7 + smooth_noise(0.20), 0.3, 1.0),  # [0..1]
    }
    # Clip negatives
    for k in env:
        env[k] = np.clip(env[k], 0.3, 3.0)
    return env


def expected_costs(nodes: Dict[str, Node], env: Dict[str, np.ndarray], step: int) -> Dict[str, Tuple[float, float]]:
    """
    Compute expected (delay_ms, energy_j) for each node at this step, factoring environment multipliers.
    """
    mul = {
        "local": (env["local_delay_mul"][step], env["local_energy_mul"][step]),
        "bs": (env["bs_delay_mul"][step], env["bs_energy_mul"][step]),
        "peer": (env["peer_delay_mul"][step], env["peer_energy_mul"][step]),
        "sat": (env["sat_delay_mul"][step], env["sat_energy_mul"][step]),
    }
    costs = {}
    for key, node in nodes.items():
        dmul, emul = mul[key]
        # Channel quality affects non-local nodes: worse channel increases delay and energy
        cq = env["channel_quality"][step]
        channel_penalty = 1.0 / max(cq, 0.05) if key in ("bs", "peer", "sat") else 1.0
        delay = node.base_delay_ms * dmul * channel_penalty
        energy = node.base_energy_j * emul * channel_penalty
        costs[key] = (max(delay, 1.0), max(energy, 0.01))
    return costs


def simulate_step_assignments(strategy: str,
                              nodes: Dict[str, Node],
                              costs: Dict[str, Tuple[float, float]],
                              tasks: List[Dict],
                              rng: random.Random) -> Tuple[List[Dict], Dict[str, float]]:
    """
    For a list of tasks (each with size_mb and deadline_ms), decide assignment per task and outcome based on strategy.
    Returns:
      outcomes: list of {assigned_to, delay_ms, energy_j, success}
      updates: dict of reputation deltas (for ECORI)
    """
    outcomes = []
    updates = {"local": 0.0, "bs": 0.0, "peer": 0.0, "sat": 0.0}

    # Scores for EDW
    alpha, beta = 0.6, 0.4

    # ECORI priority: prefer nodes with higher rep that meet deadline
    def ecori_select(task_deadline_ms):
        # threshold grows with deadline tightness
        base_thresh = 0.55
        tight = 1.0 if task_deadline_ms < 150 else (0.9 if task_deadline_ms < 250 else 0.8)
        threshold = base_thresh * tight
        candidates = []
        for key, node in nodes.items():
            delay_ms, energy_j = costs[key]
            # Eligible if reputation high enough and delay meets deadline
            if node.reputation >= threshold and delay_ms <= task_deadline_ms * 1.1:
                # Preference: highest reputation, then lowest EDW score
                edw_score = alpha * delay_ms + beta * energy_j
                candidates.append((key, node.reputation, edw_score))
        if candidates:
            # sort by reputation desc, then EDW asc
            candidates.sort(key=lambda x: (-x[1], x[2]))
            return candidates[0][0]
        # Fallback: lowest EDW
        return min(costs.keys(), key=lambda k: alpha * costs[k][0] + beta * costs[k][1])

    for task in tasks:
        deadline_ms = task["deadline_ms"]
        # Choose node per strategy
        if strategy == "random":
            assigned = rng.choice(list(nodes.keys()))
        elif strategy == "min_delay":
            assigned = min(costs.keys(), key=lambda k: costs[k][0])
        elif strategy == "edw":
            assigned = min(costs.keys(), key=lambda k: alpha * costs[k][0] + beta * costs[k][1])
        elif strategy == "ecori":
            assigned = ecori_select(deadline_ms)
        else:
            assigned = rng.choice(list(nodes.keys()))

        delay_ms, energy_j = costs[assigned]
        # Success probability: mix of reliability, deadline pressure, and mild randomness
        node = nodes[assigned]
        deadline_factor = np.clip(deadline_ms / max(delay_ms, 1.0), 0.2, 1.2)  # >1 helps success
        base_success = 0.4 * node.reliability + 0.4 * min(node.reputation, 1.0) + 0.2 * min(deadline_factor, 1.0)
        success_prob = np.clip(base_success, 0.05, 0.98)
        success = rng.random() < success_prob

        outcomes.append({
            "assigned_to": assigned,
            "delay_ms": delay_ms,
            "energy_j": energy_j,
            "success": 1 if success else 0
        })

        # Reputation updates only for ECORI
        if strategy == "ecori":
            if success:
                updates[assigned] += +0.02
            else:
                updates[assigned] += -0.05

    return outcomes, updates


def simulate_strategy(strategy: str,
                      steps: int,
                      seed: int,
                      out_path: str,
                      tasks_per_step: int = 6):
    rng = random.Random(seed + hash(strategy) % 100000)
    ensure_out_dir(os.path.dirname(out_path))

    # Define nodes
    nodes = {
        "local": Node("local", base_delay_ms=120, base_energy_j=1.8, reliability=0.90, reputation=0.70),
        "bs":    Node("bs",    base_delay_ms=180, base_energy_j=1.2, reliability=0.88, reputation=0.65),
        "peer":  Node("peer",  base_delay_ms=220, base_energy_j=1.0, reliability=0.80, reputation=0.60),
        "sat":   Node("sat",   base_delay_ms=350, base_energy_j=0.8, reliability=0.75, reputation=0.55),
    }

    env = environment_factors(steps, seed=seed)
    x, y, z, yaw_deg, heading_deg, speed_mps = uav_path(steps)

    rows = []
    time_ms = 0
    dt_ms = 200  # 5 Hz samples

    for step in range(steps):
        # Build tasks for this step
        tasks = []
        for _ in range(tasks_per_step):
            size_mb = rng.uniform(2.0, 12.0)
            deadline_ms = rng.choice([120, 180, 240, 300])
            tasks.append({"size_mb": size_mb, "deadline_ms": deadline_ms})

        costs = expected_costs(nodes, env, step)
        outcomes, rep_updates = simulate_step_assignments(strategy, nodes, costs, tasks, rng)

        # Apply reputation updates (ECORI only)
        if strategy == "ecori":
            for k, delta in rep_updates.items():
                nodes[k].reputation = float(np.clip(nodes[k].reputation + delta, 0.0, 1.0))

        # Aggregate KPIs for this timestep
        success_rate = np.mean([o["success"] for o in outcomes]) if outcomes else 0.0
        delay_mean = float(np.mean([o["delay_ms"] for o in outcomes])) if outcomes else 0.0
        energy_mean = float(np.mean([o["energy_j"] for o in outcomes])) if outcomes else 0.0

        rows.append({
            "time_ms": time_ms,
            "x": float(x[step]),
            "y": float(y[step]),
            "z": float(z[step]),
            "speed_mps": float(speed_mps[step]),
            # Columns for HUD charts
            "Yaw": float(yaw_deg[step]),
            "Heading": float(heading_deg[step]),
            # Strategy and KPIs
            "strategy": strategy,
            "kpi_success_rate": float(success_rate),
            "kpi_delay_mean_ms": float(delay_mean),
            "kpi_energy_mean_j": float(energy_mean),
            # Optional: snapshot of expected costs this step
            "cost_local_delay_ms": float(costs["local"][0]),
            "cost_local_energy_j": float(costs["local"][1]),
            "cost_bs_delay_ms": float(costs["bs"][0]),
            "cost_bs_energy_j": float(costs["bs"][1]),
            "cost_peer_delay_ms": float(costs["peer"][0]),
            "cost_peer_energy_j": float(costs["peer"][1]),
            "cost_sat_delay_ms": float(costs["sat"][0]),
            "cost_sat_energy_j": float(costs["sat"][1]),
            # Reputation snapshot (useful for ECORI plots)
            "rep_local": float(nodes["local"].reputation),
            "rep_bs": float(nodes["bs"].reputation),
            "rep_peer": float(nodes["peer"].reputation),
            "rep_sat": float(nodes["sat"].reputation),
        })

        time_ms += dt_ms

    df = pd.DataFrame(rows)

    # Save CSV
    df.to_csv(out_path, index=False)
    print(f"[OK] Wrote {len(df)} rows to {out_path}")


def parse_args():
    parser = argparse.ArgumentParser(description="Generate S1 replays (ECORI vs baselines).")
    parser.add_argument("--out-dir", default="data/replays/s1", help="Output directory for CSV replays")
    parser.add_argument("--strategies", nargs="+",
                        default=["random", "min_delay", "edw", "ecori"],
                        choices=["random", "min_delay", "edw", "ecori"],
                        help="Which strategies to simulate")
    parser.add_argument("--steps", type=int, default=600, help="Number of timesteps (rows) per replay")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--tasks-per-step", type=int, default=6, help="Number of tasks processed per timestep")
    return parser.parse_args()


def main():
    args = parse_args()
    ensure_out_dir(args.out_dir)
    for strat in args.strategies:
        out_path = os.path.join(args.out_dir, f"s1_{strat}.csv")
        simulate_strategy(strategy=strat,
                          steps=args.steps,
                          seed=args.seed,
                          out_path=out_path,
                          tasks_per_step=args.tasks_per_step)


if __name__ == "__main__":
    main()
