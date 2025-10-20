# src/skymind_viewer/event_types.py

from typing import Literal, TypedDict, Optional, List, Dict, Any

# نسخه v0.2.1: توسعه رویدادها برای صف وظایف و مسیرهای ارتباطی

EventType = Literal[
    "entity_created",    # ایجاد موجودیت: UAV/Fog/Cloud/UE
    "uav_pose",          # موقعیت/حالت UAV یا هر موجودیت متحرک
    "task_submit",       # ارسال وظیفه از UE/UAV
    "task_assigned",     # تخصیص وظیفه به مقصد پردازش (local/fog/cloud/peer)
    "task_completed",    # تکمیل وظیفه
    "offload_decision",  # تصمیم آف‌لود با مشخصات src/dst
    "link_up",           # برقراری لینک منطقی/رادیویی بین دو نود
    "link_down",         # قطع لینک
    "sim_tick",          # پیشروی زمان شبیه‌سازی (اختیاری)
]

class BaseEvent(TypedDict, total=False):
    type: EventType
    t: float                   # زمان شبیه‌سازی (ثانیه)
    idx: int                   # ایندکس رویداد در فایل (در زمان بارگذاری اضافه می‌شود)
    meta: Dict[str, Any]       # اطلاعات جانبی

class EntityCreated(BaseEvent):
    type: Literal["entity_created"]
    id: str
    kind: Literal["UAV", "Fog", "Cloud", "UE"]
    label: Optional[str]
    x: float
    y: float

class PoseEvent(BaseEvent):
    type: Literal["uav_pose"]
    id: str
    x: float
    y: float
    yaw: Optional[float]

class TaskSubmit(BaseEvent):
    type: Literal["task_submit"]
    task_id: str
    src: str                 # شناسه موجودیت ارسال‌کننده (UE/UAV)
    size: Optional[float]    # بایت
    cpu: Optional[float]     # سیکل CPU مورد نیاز
    deadline: Optional[float]
    hint: Optional[Literal["local", "fog", "cloud", "peer"]]

class TaskAssigned(BaseEvent):
    type: Literal["task_assigned"]
    task_id: str
    src: str
    dst: str                 # مقصد پردازش
    mode: Literal["local", "fog", "cloud", "peer"]

class TaskCompleted(BaseEvent):
    type: Literal["task_completed"]
    task_id: str
    src: str
    dst: str
    latency: Optional[float]
    energy: Optional[float]
    success: Optional[bool]

class OffloadDecision(BaseEvent):
    type: Literal["offload_decision"]
    task_id: str
    src: str
    dst: str                 # شناسه مقصد (Fog/Cloud/UAV/UE)
    reason: Optional[str]
    link: Optional[str]      # شناسه لینک یا نوع کانال

class LinkUp(BaseEvent):
    type: Literal["link_up"]
    a: str
    b: str
    kind: Optional[Literal["RF", "Backhaul", "LoRa", "mmWave"]]

class LinkDown(BaseEvent):
    type: Literal["link_down"]
    a: str
    b: str

class SimTick(BaseEvent):
    type: Literal["sim_tick"]
    dt: float

AnyEvent = BaseEvent  # برای تایپ ساده‌تر در کد
