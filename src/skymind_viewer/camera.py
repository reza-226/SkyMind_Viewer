# src/skymind_viewer/camera.py

from typing import Tuple

class Camera:
    """
    Simple 2D camera with pan and zoom.
    - World coordinates (x,y) are transformed to screen coordinates via:
      screen_x = x * scale + offset_x
      screen_y = y * scale + offset_y
    """
    def __init__(self, viewport_size: Tuple[int, int], scale: float = 1.0, min_scale: float = 0.25, max_scale: float = 8.0):
        self.viewport_w, self.viewport_h = viewport_size
        self.scale = scale
        self.offset_x = 0.0
        self.offset_y = 0.0
        self.min_scale = min_scale
        self.max_scale = max_scale

    def world_to_screen(self, pos: Tuple[float, float]) -> Tuple[int, int]:
        x, y = pos
        sx = int(x * self.scale + self.offset_x)
        sy = int(y * self.scale + self.offset_y)
        return sx, sy

    def screen_to_world(self, pos: Tuple[int, int]) -> Tuple[float, float]:
        sx, sy = pos
        x = (sx - self.offset_x) / self.scale
        y = (sy - self.offset_y) / self.scale
        return x, y

    def pan(self, dx: float, dy: float):
        self.offset_x += dx
        self.offset_y += dy

    def set_viewport(self, size: Tuple[int, int]):
        self.viewport_w, self.viewport_h = size

    def zoom_to(self, new_scale: float, pivot_screen: Tuple[int, int] | None = None):
        new_scale = max(self.min_scale, min(self.max_scale, new_scale))
        if pivot_screen is None:
            self.scale = new_scale
            return
        # Keep the pivot world coordinate at the same screen pixel when zooming.
        # Solve for new offsets:
        px, py = pivot_screen
        wx, wy = self.screen_to_world((px, py))
        self.scale = new_scale
        self.offset_x = px - wx * self.scale
        self.offset_y = py - wy * self.scale

    def zoom_by(self, factor: float, pivot_screen: Tuple[int, int] | None = None):
        self.zoom_to(self.scale * factor, pivot_screen=pivot_screen)
