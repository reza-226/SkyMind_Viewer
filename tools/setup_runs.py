#!/usr/bin/env python3
"""Create the run registry layout, dev/prod directories, and sample files."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REGISTRY_CONTRACTS = ROOT / "registry" / "contracts"
REGISTRY_SCHEMA = REGISTRY_CONTRACTS / "schema"
REGISTRY_RUNS = ROOT / "registry" / "runs"

RUNS_DEV = ROOT / "runs_dev"
RUNS_PROD = ROOT / "runs_prod"

SAMPLE_RUN = RUNS_DEV / "run_2025-09-18_scenario-fogAerial"
SAMPLE_METADATA = SAMPLE_RUN / "run_metadata.json"
SAMPLE_TASKS = SAMPLE_RUN / "tasks.csv"

MANIFEST = REGISTRY_CONTRACTS / "manifest.md"
RUN_INDEX = REGISTRY_RUNS / "index.md"
SCHEMA_FILE = REGISTRY_SCHEMA / "run_metadata.schema.json"

MANIFEST_CONTENT = """\
# Registry Manifest

- version: 0.1.0
- schema: `contracts/schema/run_metadata.schema.json`
- runs:
  - dev: `runs_dev/`
  - prod: `runs_prod/`
"""

RUN_INDEX_CONTENT = """\
# Run Index

| Run ID | Stage | Location |
|--------|-------|----------|
| run_2025-09-18_scenario-fogAerial | dev | runs_dev/run_2025-09-18_scenario-fogAerial |
"""

SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "RunMetadata",
    "type": "object",
    "required": [
        "run_id",
        "scenario",
        "strategy",
        "timestamp",
        "metrics",
        "artifacts",
        "sources",
    ],
    "properties": {
        "run_id": {"type": "string"},
        "scenario": {
            "type": "object",
            "required": ["name", "environment", "uav_fleet"],
            "properties": {
                "name": {"type": "string"},
                "environment": {"type": "string"},
                "uav_fleet": {
                    "type": "object",
                    "required": ["count", "models"],
                    "properties": {
                        "count": {"type": "integer", "minimum": 1},
                        "models": {
                            "type": "array",
                            "items": {"type": "string"},
                            "minItems": 1,
                        },
                    },
                },
            },
        },
        "strategy": {
            "type": "object",
            "required": ["name", "type", "components"],
            "properties": {
                "name": {"type": "string"},
                "type": {"type": "string"},
                "components": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 1,
                },
            },
        },
        "timestamp": {"type": "string"},
        "metrics": {
            "type": "object",
            "required": ["latency_ms", "energy_j", "sla_success_rate"],
            "properties": {
                "latency_ms": {"type": "number"},
                "energy_j": {"type": "number"},
                "sla_success_rate": {"type": "number", "minimum": 0, "maximum": 1},
            },
        },
        "artifacts": {
            "type": "object",
            "required": ["tasks_csv", "logs"],
            "properties": {
                "tasks_csv": {"type": "string"},
                "logs": {
                    "type": "array",
                    "items": {"type": "string"},
                },
            },
        },
        "sources": {
            "type": "object",
            "required": ["papers", "datasets"],
            "properties": {
                "papers": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["id", "title", "year", "focus"],
                        "properties": {
                            "id": {"type": "string"},
                            "title": {"type": "string"},
                            "year": {"type": "integer"},
                            "focus": {"type": "string"},
                        },
                    },
                },
                "datasets": {
                    "type": "array",
                    "items": {"type": "string"},
                },
            },
        },
        "notes": {"type": "string"},
    },
}

SAMPLE_METADATA_CONTENT = {
    "run_id": "run_2025-09-18_scenario-fogAerial",
    "scenario": {
        "name": "fogAerial",
        "environment": "Urban canyon with intermittent NB-IoT backhaul",
        "uav_fleet": {
            "count": 6,
            "models": [
                "EdgeUAV-X7 (30 TOPS, 35 Wh)",
                "EdgeUAV-X7 (30 TOPS, 35 Wh)",
                "RelayUAV-R4 (5G mesh backbone)",
                "RelayUAV-R4 (5G mesh backbone)",
                "ScoutUAV-S2 (LiDAR + mmWave)",
                "ChargeUAV-C1 (Solar hybrid)",
            ],
        },
    },
    "strategy": {
        "name": "StrategyF v2 - DRL Meta Ensemble",
        "type": "Hybrid (DRL + Meta + Graph + Game)",
        "components": [
            "DRL: Multi-agent PPO with partial observation (Paper 39)",
            "Meta-RL: MAML adaptation for environment shifts (Paper 21)",
            "GNN: Graph convolution task encoder (Paper 17)",
            "Game: Stackelberg pricing guard (Paper 51)",
            "Optimizer: GA fairness controller (Paper 24,57)",
            "Resilience: Secrecy-aware link penalization (Paper 52)",
        ],
    },
    "timestamp": "2025-09-18T10:42:17Z",
    "metrics": {
        "latency_ms": 145.7,
        "energy_j": 872.5,
        "sla_success_rate": 0.94,
    },
    "artifacts": {
        "tasks_csv": "tasks.csv",
        "logs": [
            "logs/strategyf_core.log",
            "logs/environment_metrics.log",
            "logs/validation_report.txt",
        ],
    },
    "sources": {
        "papers": [
            {
                "id": "P17",
                "title": "GCN augmented DRL for dependent tasks",
                "year": 2025,
                "focus": "Graph-based policy",
            },
            {
                "id": "P21",
                "title": "Meta-Actor Critic for UAV-MEC",
                "year": 2024,
                "focus": "Meta-learning adaptation",
            },
            {
                "id": "P24",
                "title": "GA fairness-aware latency minimization",
                "year": 2025,
                "focus": "Fairness & GA baseline",
            },
            {
                "id": "P39",
                "title": "Partial observation learning with regret minimization",
                "year": 2024,
                "focus": "POMDP resilience",
            },
            {
                "id": "P51",
                "title": "Game-theoretic pricing in UAV edge",
                "year": 2024,
                "focus": "Economic guardrails",
            },
            {
                "id": "P57",
                "title": "Hybrid fog GA for IoD",
                "year": 2025,
                "focus": "Hybrid fog orchestration",
            },
        ],
        "datasets": [
            "Synthetic workload: Disaster response 12h window",
            "City digital twin: Tehran District 7 (2025)",
        ],
    },
    "notes": "Seed=872613. Controllers re-aligned every 75 epochs. Reward blending: alpha_latency=0.45, alpha_energy=0.35, alpha_sla=0.2.",
}

SAMPLE_TASKS_CONTENT = """\
task_id,application,priority,arrival_tick,deadline_tick,estimated_cycles,estimated_energy_j,assigned_uav,placement_step
24-0,thermal_imaging,high,24,36,1.2e9,38.4,uav-2,meta-round-3
24-1,survivor_detection,critical,24,30,2.4e9,44.8,uav-1,meta-round-3
24-2,route_planning,medium,24,48,0.6e9,12.2,uav-5,meta-round-4
25-0,vision_mapping,high,25,40,1.1e9,34.7,uav-2,meta-round-3
25-1,air_quality,medium,25,55,0.4e9,10.5,uav-6,baseline-round-1
25-2,edge_analytics,low,25,60,0.9e9,18.3,uav-3,baseline-round-1
"""

def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)

def write_file(path: Path, content: str) -> None:
    if path.exists():
        return
    path.write_text(content, encoding="utf-8")

def write_json(path: Path, content: dict) -> None:
    if path.exists():
        return
    path.write_text(json.dumps(content, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

def main() -> None:
    ensure_dir(REGISTRY_CONTRACTS)
    ensure_dir(REGISTRY_SCHEMA)
    ensure_dir(REGISTRY_RUNS)
    ensure_dir(RUNS_DEV)
    ensure_dir(RUNS_PROD)
    ensure_dir(SAMPLE_RUN / "logs")

    write_file(MANIFEST, MANIFEST_CONTENT)
    write_file(RUN_INDEX, RUN_INDEX_CONTENT)
    write_json(SCHEMA_FILE, SCHEMA)
    write_json(SAMPLE_METADATA, SAMPLE_METADATA_CONTENT)
    write_file(SAMPLE_TASKS, SAMPLE_TASKS_CONTENT)

    # create stub log files if absent
    for rel in SAMPLE_METADATA_CONTENT["artifacts"]["logs"]:
        write_file(SAMPLE_RUN / rel, "")

    print("Registry layout ready.")
    print(f"- {RUNS_DEV.relative_to(ROOT)}")
    print(f"- {RUNS_PROD.relative_to(ROOT)}")
    print(f"- {REGISTRY_CONTRACTS.relative_to(ROOT)}")
    print(f"- Sample run: {SAMPLE_RUN.relative_to(ROOT)}")

if __name__ == "__main__":
    main()
