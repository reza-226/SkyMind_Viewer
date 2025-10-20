# src/skymind_viewer/state.py

from typing import Dict, Tuple, Optional

from .camera import Camera

class ViewerState:
    """
    Central state for viewer.
    - Holds entities map and positions in world coordinates.
    - Maintains sim_time and camera for transforms.
    """
    def __init__(self, viewport_size=(1024, 768)):
        self.sim_time: float = 0.0
        self.entities: Dict[str, Dict[str, object]] = {}  # id -> {kind, label, x, y}
        self.positions: Dict[str, Tuple[float, float]] = {}  # id -> (x, y)
        self.camera = Camera(viewport_size)

    def update_entity(self, id: str, kind: str, label: Optional[str], x: float, y: float):
        self.entities[id] = {"kind": kind, "label": label or "", "x": x, "y": y}
        self.positions[id] = (x, y)

    def update_pose(self, id: str, x: float, y: float):
        if id in self.entities:
            self.entities[id]["x"] = x
            self.entities[id]["y"] = y
        self.positions[id] = (x, y)

    def set_viewport(self, size):
        self.camera.set_viewport(size)
