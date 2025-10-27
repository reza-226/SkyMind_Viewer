# sim/config.py
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional

DEFAULT_SEED = 42

@dataclass
class BandwidthParams:
    ue_to_uav_mbps: float = 20.0
    ue_to_bs_mbps: float = 50.0
    uav_to_edge_mbps: float = 100.0

@dataclass
class TimingParams:
    tick_seconds: float = 1.0
    area_size_m: float = 1000.0
    default_seed: int = DEFAULT_SEED

@dataclass
class WorldParams:
    n_devices: int = 5
    n_uavs: int = 1
    n_fogs: int = 0
    n_edges: int = 1
    n_clouds: int = 0

@dataclass
class Config:
    seed: Optional[int] = None
    strategy_name: str = "A"
    bw: BandwidthParams = field(default_factory=BandwidthParams)
    timing: TimingParams = field(default_factory=TimingParams)
    world: WorldParams = field(default_factory=WorldParams)

def DefaultConfig() -> Config:
    return Config()
