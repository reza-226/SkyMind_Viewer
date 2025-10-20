from typing import Dict, Any
import pygame
from .base import Camera, Layer

class GridLayer(Layer):
    def __init__(self, spacing: int = 50, color=(40, 44, 52)):
        self.spacing = spacing
        self.color = color

    def draw(self, surface: pygame.Surface, camera: Camera, state: Dict[str, Any]) -> None:
        w, h = surface.get_size()
        # derive effective spacing with zoom
        s = int(self.spacing * camera.zoom)
        if s < 8:
            return
        # vertical lines
        for x in range(0, w, s):
            pygame.draw.line(surface, self.color, (x, 0), (x, h), width=1)
        # horizontal lines
        for y in range(0, h, s):
            pygame.draw.line(surface, self.color, (0, y), (w, y), width=1)
