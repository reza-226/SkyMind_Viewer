# sim/core/environment.py
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Any
from sim.config import Config, DefaultConfig
from sim.utils import set_seed

@dataclass
class Environment:
    cfg: Config = field(default_factory=DefaultConfig)
    tick: int = 0
    devices: Dict[str, Any] = field(default_factory=dict)
    uavs: Dict[str, Any] = field(default_factory=dict)
    fogs: Dict[str, Any] = field(default_factory=dict)
    edges: Dict[str, Any] = field(default_factory=dict)
    cloud: Any = None

    def __post_init__(self):
        # honor seed precedence (env var > cfg.seed > default)
        seed_to_use = set_seed(self.cfg.seed)
        _ = seed_to_use  # silence linters
        self._spawn_world()

    def _spawn_world(self):
        # Minimal stubs based on cfg.world counts
        w = self.cfg.world
        for i in range(w.n_devices):
            self.devices[f"ue-{i}"] = {"id": f"ue-{i}"}
        for i in range(w.n_uavs):
            self.uavs[f"uav-{i}"] = {"id": f"uav-{i}", "cpu_free": 2000, "mem_free": 2048, "bw_free": 50, "reputation": 0.7}
        for i in range(w.n_edges):
            self.edges[f"edge-{i}"] = {"id": f"edge-{i}", "cpu_free": 4000, "mem_free": 4096, "bw_free": 100, "reputation": 0.6}
        # fogs/cloud can remain empty in this minimal version
