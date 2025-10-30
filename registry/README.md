# Registry Overview

The `registry/` directory centralizes data contracts, run registries, and archival policies for SkyMind simulations.

## Layout
- `contracts/`: canonical manifests and schemas for simulation outputs.
- `runs/`: indexed records for development and production runs.
- `archive/`: legacy or superseded artifacts. `archive/legacy_runs/` stores historic outputs retained for reference.

## Naming Conventions
- Use ISO dates (`YYYY-MM-DD`) and UTC timestamps for run identifiers.
- Prefix development runs with `dev_`, production with `prod_`.
- Mirror directory structure across environments: `runs_dev/<run_id>/...`, `runs_prod/<run_id>/...`.

## Maintenance
- Update manifests whenever output schema changes.
- Keep run index synchronized with actual artifacts stored under `runs_dev/` or `runs_prod/`.
- Move deprecated artifacts to `archive/legacy_runs/` with a changelog entry in `archive/README.md`.
