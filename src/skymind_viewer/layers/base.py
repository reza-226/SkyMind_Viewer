from typing import Protocol, Tuple, Dict, Any
import pygame

class Camera:
    def __init__(self, width: int, height: int, zoom: float = 1.0):
        self.offset_x = 0.0
        self.offset_y = 0.0
        self.zoom = zoom
        self.width = width
        self.height = height

    def world_to_screen(self, x: float, y: float) -> Tuple[int, int]:
        sx = int((x + self.offset_x) * self.zoom + self.width // 2)
        sy = int((y + self.offset_y) * self.zoom + self.height // 2)
        return sx, sy

class Layer(Protocol):
    def draw(self, surface: pygame.Surface, camera: Camera, state: Dict[str, Any]) -> None:
        ...
