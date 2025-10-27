# sim/models/nodes.py
from dataclasses import dataclass
from typing import Tuple
from sim.models.task import ExecutionLocation

Position = Tuple[float, float]  # (x, y) meters

@dataclass
class BaseComputeNode:
    id: str
    pos: Position
    cpu_cps: float
    efficiency_cycles_per_wh: float
    reputation: float = 0.8

    def processing_delay_s(self, cycles: float) -> float:
        return cycles / max(1.0, self.cpu_cps)

    def compute_energy_wh(self, cycles: float) -> float:
        return cycles / max(1.0, self.efficiency_cycles_per_wh)

@dataclass
class Device(BaseComputeNode):
    battery_wh: float = 10.0
    kind: ExecutionLocation = ExecutionLocation.LOCAL

@dataclass
class UAV(BaseComputeNode):
    battery_wh: float = 200.0
    velocity_mps: float = 5.0
    heading_deg: float = 0.0
    kind: ExecutionLocation = ExecutionLocation.UAV

@dataclass
class FogNode(BaseComputeNode):
    kind: ExecutionLocation = ExecutionLocation.FOG

@dataclass
class EdgeNode(BaseComputeNode):
    kind: ExecutionLocation = ExecutionLocation.EDGE

@dataclass
class CloudNode(BaseComputeNode):
    kind: ExecutionLocation = ExecutionLocation.CLOUD
