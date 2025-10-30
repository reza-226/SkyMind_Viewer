# StrategyF Simulation Manifest
Version: manifest-2025-10-30  
Owner: Simulation Platform Team (Reza, GPT-5)  
Applies to: StrategyF multi-UAV simulations (Streamlit dashboard ingestion)

## 1. Purpose
Define the required inputs, generated artifacts, and validation rules for a single StrategyF simulation run. Streamlit dashboards rely on this contract to render results consistently in both RTL and LTR layouts.

## 2. Inputs
| key                | type     | required | description                              |
|--------------------|----------|----------|------------------------------------------|
| `scenario_file`    | YAML     | yes      | Scenario configuration (e.g., `scenarios/demo.yml`). |
| `seed`             | integer  | yes      | RNG seed applied across simulator components. |
| `strategy_variant` | string   | yes      | Strategy implementation identifier (e.g., `StrategyF`). |
| `run_mode`         | enum     | yes      | One of `dev`, `prod`. Controls retention policy. |
| `env_config`       | JSON/YAML| optional | Overrides for environment (wind, obstacles). |

## 3. Output Artifacts
| artifact_id | relative_path_template                     | format   | retention | description |
|-------------|---------------------------------------------|----------|-----------|-------------|
| `run_log`   | `runs_<env>/<run_id>/sim.log`               | text     | 30 days (dev), 365 days (prod) | Simulator runtime log. |
| `metrics`   | `runs_<env>/<run_id>/metrics.json`          | JSON     | 180 / 730 days | Aggregated KPIs (delay, energy, success_ratio). |
| `trajectory`| `runs_<env>/<run_id>/trajectory.parquet`    | Parquet  | 180 / 730 days | Time-series UAV state machine outputs. |
| `events`    | `runs_<env>/<run_id>/events.jsonl`          | JSONL    | 90 / 365 days | Stream of scheduling/communication events. |
| `visual`    | `runs_<env>/<run_id>/dashboard_snapshot.png`| PNG      | optional  | Optional captured dashboard view for archival. |

`<env>` = `dev` or `prod`. `<run_id>` = `StrategyF-YYYYMMDDThhmmssZ-seedNNN`.

## 4. Field Dictionary (metrics.json)
- `total_tasks`: int, count of generated tasks.
- `completed_tasks`: int, tasks satisfied before deadline.
- `mean_delay_ms`: float, average latency per task.
- `energy_consumption_j`: float, cumulative propulsion and compute energy.
- `communication_cost_j`: float, radio transmission energy.
- `sla_violation_rate`: float, fraction of tasks violating SLA.
- `notes`: string, optional, operator comments.

## 5. Validation Rules
1. `completed_tasks <= total_tasks`.
2. `sla_violation_rate = 1 - completed_tasks/total_tasks` (within ±0.01 tolerance).
3. Trajectory dataset must contain columns: `tick`, `uav_id`, `x`, `y`, `z`, `battery_j`.
4. Events stream must be sorted by `tick` ascending.
5. Log file must include StrategyF tick summary lines (`INFO:root:[StrategyF] Tick=`).

## 6. Dashboard Consumption
- Streamlit Results page expects metrics JSON and trajectory parquet. Absence should raise a warning card.
- `events.jsonl` powers Task Analytics drill-down.
- Manifest version must be embedded inside metrics JSON under `_manifest_version`.

## 7. Change Management
- Increment `Version` using semantic suffix (e.g., `manifest-2025-11-15a`) when schema changes.
- Document breaking changes in `registry/contracts/CHANGELOG.md`.
- Coordinate with dashboard team to update ingestion pipeline.

