from typing import Dict, Any
import math
import pygame
from .base import Camera, Layer

UAV_COLOR = (0, 196, 255)
UAV_LABEL = (180, 220, 255)

class UAVLayer(Layer):
    def __init__(self, show_labels: bool = True):
        self.show_labels = show_labels
        self.font = None

    def _ensure_font(self):
        if self.font is None:
            self.font = pygame.font.SysFont("consolas", 14)

    def draw(self, surface: pygame.Surface, camera: Camera, state: Dict[str, Any]) -> None:
        self._ensure_font()
        uavs = state.get("uavs", {})
        for uid, u in uavs.items():
            x, y = u.get("x", 0.0), u.get("y", 0.0)
            heading = u.get("heading", 0.0)
            sx, sy = camera.world_to_screen(x, y)
            size = max(6, int(8 * camera.zoom))
            # simple triangle indicating heading
            angle = heading
            p1 = (sx + int(math.cos(angle) * size), sy + int(math.sin(angle) * size))
            p2 = (sx + int(math.cos(angle + 2.5) * size * 0.8), sy + int(math.sin(angle + 2.5) * size * 0.8))
            p3 = (sx + int(math.cos(angle - 2.5) * size * 0.8), sy + int(math.sin(angle - 2.5) * size * 0.8))
            pygame.draw.polygon(surface, UAV_COLOR, [p1, p2, p3])
            if self.show_labels:
                label = self.font.render(f"UAV:{uid}", True, UAV_LABEL)
                surface.blit(label, (sx + 10, sy - 10))
