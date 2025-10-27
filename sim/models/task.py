# sim/models/task.py
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional, Dict, Any  # ← افزودن Any

class ExecutionLocation(Enum):
    LOCAL = "local_device"
    UAV = "uav_onboard"
    FOG = "fog_node"
    EDGE = "edge_node"
    CLOUD = "cloud_dc"

class TaskStatus(Enum):
    CREATED = auto()
    ASSIGNED = auto()
    RUNNING = auto()
    COMPLETED = auto()
    DROPPED = auto()

@dataclass
class DelayComponents:
    queue_s: float = 0.0
    uplink_s: float = 0.0
    processing_s: float = 0.0
    downlink_s: float = 0.0

    @property
    def total(self) -> float:
        return self.queue_s + self.uplink_s + self.processing_s + self.downlink_s

@dataclass
class EnergyComponents:
    ue_wh: float = 0.0
    uav_wh: float = 0.0
    fog_wh: float = 0.0
    edge_wh: float = 0.0
    cloud_wh: float = 0.0
    move_wh: float = 0.0
    idle_wh: float = 0.0

    @property
    def total(self) -> float:
        return self.ue_wh + self.uav_wh + self.fog_wh + self.edge_wh + self.cloud_wh + self.move_wh + self.idle_wh

@dataclass
class Task:
    id: str
    source_id: str
    arrival_tick: int
    deadline_tick: Optional[int]
    size_kb: float
    cycles_required: float
    min_reputation: float
    latency_slo_s: float
    status: TaskStatus = TaskStatus.CREATED

    # Decision outcome
    assigned_tick: Optional[int] = None
    executor: Optional[ExecutionLocation] = None
    executor_id: Optional[str] = None

    # Metrics
    delays: DelayComponents = field(default_factory=DelayComponents)
    energy: EnergyComponents = field(default_factory=EnergyComponents)
    success: Optional[bool] = None

@dataclass
class AssignmentDecision:
    """
    ساختار استاندارد برای تصمیم تخصیص وظیفه. فیلدها عمداً قابل‌انعطاف هستند
    تا استراتژی‌های مختلف بتوانند داده‌های مورد نیاز خود را درج کنند.
    """
    task: Optional[Task] = None
    task_id: Optional[str] = None
    executor: Optional[Any] = None
    executor_id: Optional[str] = None
    location: Optional[ExecutionLocation] = None
    estimated_latency_s: Optional[float] = None
    expect_latency_s: Optional[float] = None
    expected_bw_mbps: Optional[float] = None
    bw_mbps: Optional[float] = None
    reason: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def effective_latency(self) -> Optional[float]:
        """برگشت اولین مقدار تأخیر در دسترس."""
        return (
            self.estimated_latency_s
            or self.expect_latency_s
        )

    def effective_bw(self) -> Optional[float]:
        """برگشت اولین مقدار پهنای‌باند در دسترس."""
        return self.expected_bw_mbps or self.bw_mbps
