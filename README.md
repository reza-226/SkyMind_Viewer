# SkyMind Viewer

A modular, Pygame-based viewer for replaying and live-inspecting simulation snapshots emitted by a SimPy-based core. The design follows a Ports & Adapters (Hexagonal) architecture to keep the simulation core decoupled from the Pygame viewer.

- Core ideas:
  - Clean separation between simulation (producer) and visualization (consumer)
  - JSONL snapshot stream as the contract between modules
  - Replay (offline) and Live (queue/IPC) modes
  - Minimal dependencies for easy setup

See docs/snapshot_schema.md for the evolving snapshot contract.

## Project layout

- src/
  - skymind_viewer/
    - assets/                # images/fonts/etc. (empty placeholder)
    - event_types.py         # message/event structures (to be implemented)
    - renderer.py            # Pygame viewer (to be implemented)
    - replay.py              # JSONL replay logic (to be implemented)
    - live.py                # live mode via IPC/queue (to be implemented)
  - cli/
    - skymind_cli.py         # CLI entry points (to be implemented)
- examples/
  - simpy_side_emit.py       # example producer to emit JSONL (placeholder)
- runs/                      # output folder for replay files (.jsonl)
- docs/
  - snapshot_schema.md       # snapshot/message schema (draft)
- README.md
- requirements.txt

## Prerequisites

- Python 3.10+ recommended
- Windows: Git Bash or PowerShell
- Optional: a virtual environment (.venv)

## Quickstart

1) Create and activate a venv
- Git Bash:
  - python -m venv .venv
  - source .venv/Scripts/activate
- PowerShell:
  - py -3 -m venv .venv
  - .\.venv\Scripts\Activate.ps1

2) Install dependencies
- pip install -r requirements.txt

3) Produce a replay file (JSONL)
- Placeholder example at examples/simpy_side_emit.py (to be implemented)
- Output target: runs/exp001.replay.jsonl

4) Run the viewer (planned CLI)
- python -m src.cli.skymind_cli viewer replay --file runs/exp001.replay.jsonl --fps 30 --realtime

Notes:
- The CLI and modules are currently skeletons; commands above reflect the intended interface.

## Snapshot format (high-level)

- Line-delimited JSON (JSONL), one event per line
- Each event includes:
  - timestamp (float)
  - type (string, e.g., "entity_created", "state_update", "metric")
  - payload (object with fields per event type)
- See docs/snapshot_schema.md for details and examples.

## Controls (planned)

- Space: Play/Pause
- G: Toggle grid
- M: Toggle metrics overlay
- Q / Esc: Quit

## Development

- Keep the simulation core independent of the viewer (no Pygame in core)
- Keep message/event contracts in a shared schema (docs/snapshot_schema.md)
- Prefer small, composable modules in skymind_viewer/
- Python version: 3.10+ (consistent local venv is recommended)

### Useful commands

- Activate venv (Git Bash): source .venv/Scripts/activate
- Install deps: pip install -r requirements.txt
- Linting/formatting: (add your preferred tools later, e.g., black, ruff)

## Roadmap

- [ ] Define event structures (event_types.py) and finalize schema
- [ ] Implement renderer (renderer.py) with camera/grid/overlay toggles
- [ ] Implement replay (replay.py) with pause/speed control
- [ ] Implement live mode (live.py) via queue/IPC
- [ ] Implement CLI commands (skymind_cli.py) for replay/live
- [ ] Provide a working example emitter (examples/simpy_side_emit.py)
- [ ] Add unit tests and CI
- [ ] Package and publish (optional)

## License

TBD (e.g., MIT)
