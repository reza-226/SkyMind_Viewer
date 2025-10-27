# sim/utils/geo.py
import math
from typing import Tuple

Pos = Tuple[float, float]

def distance_m(a: Pos, b: Pos) -> float:
    """Euclidean distance in meters between two 2D points."""
    dx = a[0] - b[0]
    dy = a[1] - b[1]
    return math.hypot(dx, dy)

def reflect_heading_if_out(x: float, y: float, heading_deg: float, area_size_m: float) -> float:
    """Utility for boundary reflection: returns new heading degrees if out of bounds."""
    bounced = False
    if x < 0 or x > area_size_m:
        heading_deg = (180.0 - heading_deg) % 360.0
        bounced = True
    if y < 0 or y > area_size_m:
        heading_deg = (-heading_deg) % 360.0
        bounced = True
    return heading_deg

__all__ = ["Pos", "distance_m", "reflect_heading_if_out"]
