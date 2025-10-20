# src/skymind_viewer/layers/links.py

import pygame as pg
from typing import List, Tuple

from skymind_viewer.event_types import AnyEvent

class LinksLayer:
    """
    Tracks active logical links and visualizes offloading paths (src->dst).
    Camera transform (world_to_screen) is used for precise placement.
    """
    def __init__(self, color=(100, 200, 255), dash=False):
        self.color = color
        self.dash = dash
        self.active: List[Tuple[str, str]] = []

    def handle_event(self, evt: AnyEvent, state):
        typ = evt.get("type")
        if typ == "offload_decision":
            a = evt["src"]; b = evt["dst"]
            self._add_link(a, b)
        elif typ == "link_up":
            a = evt["a"]; b = evt["b"]
            self._add_link(a, b)
        elif typ == "link_down":
            a = evt["a"]; b = evt["b"]
            self._remove_link(a, b)

    def _add_link(self, a: str, b: str):
        pair = (a, b)
        if pair not in self.active:
            self.active.append(pair)

    def _remove_link(self, a: str, b: str):
        try:
            self.active.remove((a, b))
        except ValueError:
            try:
                self.active.remove((b, a))
            except ValueError:
                pass

    def draw(self, surface: pg.Surface, state):
        for a, b in self.active:
            pa = state.positions.get(a)
            pb = state.positions.get(b)
            if not pa or not pb:
                continue
            xa, ya = state.camera.world_to_screen(pa)
            xb, yb = state.camera.world_to_screen(pb)
            if self.dash:
                self._draw_dashed_line(surface, self.color, (xa, ya), (xb, yb), dash_length=8)
            else:
                pg.draw.line(surface, self.color, (xa, ya), (xb, yb), 2)

    @staticmethod
    def _draw_dashed_line(surface, color, start_pos, end_pos, dash_length=10, width=2):
        from math import hypot
        x1, y1 = start_pos
        x2, y2 = end_pos
        length = hypot(x2 - x1, y2 - y1)
        if length == 0:
            return
        dx = (x2 - x1) / length
        dy = (y2 - y1) / length
        i = 0
        while i < length:
            start = (x1 + dx * i, y1 + dy * i)
            end = (x1 + dx * min(i + dash_length, length), y1 + dy * min(i + dash_length, length))
            pg.draw.line(surface, color, start, end, width)
            i += dash_length * 2
