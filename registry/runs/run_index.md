# Simulation Run Index

| run_id                             | environment | started_at (UTC)     | completed_at (UTC)   | seed | scenario           | status    | artifact_root                              | metrics_path                                   |
|-----------------------------------|-------------|----------------------|----------------------|------|--------------------|-----------|---------------------------------------------|------------------------------------------------|
| StrategyF-20251023T180000Z-seed42 | dev         | 2025-10-23T18:00:00Z | 2025-10-23T18:45:00Z | 42   | scenarios/demo.yml | completed | runs_dev/StrategyF-20251023T180000Z-seed42  | runs_dev/StrategyF-20251023T180000Z-seed42/metrics.json |
| StrategyF-20251024T090500Z-seed77 | prod        | 2025-10-24T09:05:00Z | null                 | 77   | scenarios/demo.yml | running   | runs_prod/StrategyF-20251024T090500Z-seed77 | runs_prod/StrategyF-20251024T090500Z-seed77/metrics.json |

## Usage Notes
- Add a new row immediately after kicking off a run (status `running`).
- Update `completed_at` and `status` when the run finalizes.
- If a run is archived, move the row to `archive/legacy_runs/run_index_legacy.md` and point `artifact_root` to the archived location.
