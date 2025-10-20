# src/skymind_viewer/layers/overlay.py

import pygame as pg

class MetricsOverlay:
    """
    Optional overlay layer if you prefer the overlay as a layer.
    Currently the Renderer draws the overlay itself; this layer is provided
    for modularity and future extension.
    """
    def __init__(self, font: pg.font.Font = None):
        self.font = font or pg.font.SysFont("consolas", 14)

    def handle_event(self, evt, state):
        pass

    def draw(self, surface: pg.Surface, state):
        # Example: draw a tiny crosshair at viewport center in world coords
        cx, cy = surface.get_width() // 2, surface.get_height() // 2
        pg.draw.line(surface, (80, 80, 80), (cx - 8, cy), (cx + 8, cy), 1)
        pg.draw.line(surface, (80, 80, 80), (cx, cy - 8), (cx, cy + 8), 1)
