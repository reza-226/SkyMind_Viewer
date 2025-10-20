from typing import Dict, Any
import pygame
from .base import Camera, Layer

FOG_COLOR = (255, 196, 0)
CLOUD_COLOR = (200, 200, 200)
LABEL_COLOR = (220, 220, 220)

class EntitiesLayer(Layer):
    def __init__(self, show_labels: bool = True):
        self.show_labels = show_labels
        self.font = None

    def _ensure_font(self):
        if self.font is None:
            self.font = pygame.font.SysFont("consolas", 14)

    def draw(self, surface: pygame.Surface, camera: Camera, state: Dict[str, Any]) -> None:
        self._ensure_font()
        fbs = state.get("fog_bs", {})
        for eid, e in fbs.items():
            sx, sy = camera.world_to_screen(e["x"], e["y"])
            size = max(6, int(6 * camera.zoom))
            rect = pygame.Rect(0, 0, size * 2, size * 2)
            rect.center = (sx, sy)
            pygame.draw.rect(surface, FOG_COLOR, rect, border_radius=3)
            if self.show_labels:
                surface.blit(self.font.render(f"FBS:{eid}", True, LABEL_COLOR), (sx + 8, sy - 8))
        clouds = state.get("cloud", {})
        for eid, e in clouds.items():
            sx, sy = camera.world_to_screen(e["x"], e["y"])
            radius = max(6, int(10 * camera.zoom))
            pygame.draw.circle(surface, CLOUD_COLOR, (sx, sy), radius, width=2)
            if self.show_labels:
                surface.blit(self.font.render(f"Cloud:{eid}", True, LABEL_COLOR), (sx + 8, sy - 8))
