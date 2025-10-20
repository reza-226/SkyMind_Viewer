from typing import Dict, Any, List
import pygame
from .base import Camera, Layer

class MetricsOverlay(Layer):
    def __init__(self):
        self.font_small = None

    def _ensure_fonts(self):
        if self.font_small is None:
            self.font_small = pygame.font.SysFont("consolas", 14)

    def draw(self, surface: pygame.Surface, camera: Camera, state: Dict[str, Any]) -> None:
        self._ensure_fonts()
        lines: List[str] = []
        lines.append(f"Events: {state.get('events_processed', 0)}/{state.get('events_total', 0)}")
        sim_t = state.get("sim_time", 0.0)
        lines.append(f"Sim t: {sim_t:.2f}s")
        lines.append(f"Playback: {'PAUSED' if state.get('paused', False) else 'PLAYING'} x{state.get('speed', 1.0):.2f} | {'REALTIME' if state.get('realtime', False) else 'STEPPED'}")
        lines.append(f"Zoom: {camera.zoom:.2f} | Offset: ({camera.offset_x:.1f},{camera.offset_y:.1f})")
        lines.append("Controls: Space=Play/Pause, Left/Right=Step, +/-=Speed, Z/X=Zoom, Arrows=Pan, H=Help")

        y = 8
        for s in lines:
            txt = self.font_small.render(s, True, (220, 220, 220))
            surface.blit(txt, (8, y))
            y += 18
