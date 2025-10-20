# src/skymind_viewer/renderer.py
from __future__ import annotations

import json
import math
import os
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

# --------------------------------------------
# Optional imports from project (with fallbacks)
# --------------------------------------------
# Camera: we try to use project's camera; if not available, use a simple fallback.
try:
    from skymind_viewer.camera import Camera as ProjectCamera  # type: ignore
except Exception:
    ProjectCamera = None  # type: ignore

# ViewerState: we try to use project's state; if not available, use a simple fallback.
try:
    from skymind_viewer.state import ViewerState as ProjectState  # type: ignore
except Exception:
    ProjectState = None  # type: ignore

# Pygame is required for rendering.
import pygame


# --------------------------------------------
# Fallback SimpleCamera (if project camera not importable)
# --------------------------------------------
class SimpleCamera:
    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        # world-space center
        self.cx = 0.0
        self.cy = 0.0
        # zoom scale: pixels per world unit
        self.scale = 1.0

    def world_to_screen(self, x: float, y: float) -> Tuple[int, int]:
        sx = (x - self.cx) * self.scale + self.width * 0.5
        sy = (y - self.cy) * self.scale + self.height * 0.5
        return int(round(sx)), int(round(sy))

    def screen_to_world(self, sx: float, sy: float) -> Tuple[float, float]:
        wx = (sx - self.width * 0.5) / self.scale + self.cx
        wy = (sy - self.height * 0.5) / self.scale + self.cy
        return wx, wy

    def pan(self, dx_pixels: float, dy_pixels: float) -> None:
        # pan by pixels: convert to world delta
        if self.scale <= 0:
            return
        self.cx -= dx_pixels / self.scale
        self.cy -= dy_pixels / self.scale

    def zoom_at(self, factor: float, pivot_px: Tuple[int, int]) -> None:
        # Zoom keeping the pivot point fixed in world-space
        if factor <= 0.0:
            return
        px, py = pivot_px
        wx_before, wy_before = self.screen_to_world(px, py)
        self.scale *= factor
        # Adjust center so that pivot remains at same world position
        wx_after, wy_after = self.screen_to_world(px, py)
        self.cx += (wx_before - wx_after)
        self.cy += (wy_before - wy_after)


# --------------------------------------------
# Fallback ViewerState and Entity (if project state not importable)
# --------------------------------------------
@dataclass
class Entity:
    id: str
    kind: str = "node"
    label: Optional[str] = None
    x: float = 0.0
    y: float = 0.0
    meta: Dict[str, Any] = field(default_factory=dict)


class SimpleViewerState:
    def __init__(self):
        self.entities: Dict[str, Entity] = {}
        self.queue_counts: Dict[str, int] = {}
        self.links_active: set[Tuple[str, str]] = set()
        self.sim_time: float = 0.0

    def update_entity(self, eid: str, kind: str, label: Optional[str], x: float, y: float) -> None:
        ent = self.entities.get(eid)
        if ent is None:
            ent = Entity(id=eid, kind=kind or "node", label=label, x=x, y=y)
            self.entities[eid] = ent
        else:
            ent.kind = kind or ent.kind
            if label is not None:
                ent.label = label
            ent.x = x
            ent.y = y

    def set_queue_count(self, node: str, count: int) -> None:
        self.queue_counts[node] = int(count)
        ent = self.entities.get(node)
        if ent:
            ent.meta["queue_count"] = int(count)

    def set_link_state(self, a: str, b: str, up: bool) -> None:
        key = tuple(sorted((a, b)))
        if up:
            self.links_active.add(key)
        else:
            self.links_active.discard(key)

    def pulse_link(self, a: str, b: str) -> None:
        # Optional: can be used to create a transient highlight; here we just ensure the link exists
        key = tuple(sorted((a, b)))
        self.links_active.add(key)


# --------------------------------------------
# Utility
# --------------------------------------------
def _coalesce(*vals, default=None):
    for v in vals:
        if v is not None:
            return v
    return default


# --------------------------------------------
# Renderer
# --------------------------------------------
class Renderer:
    def __init__(
        self,
        replay_file: str,
        width: int = 1280,
        height: int = 800,
        bg_color: Tuple[int, int, int] = (15, 15, 20),
        show_queues: bool = False,
        show_links: bool = False,
        dashed_links: bool = False,
        overlay: bool = True,
        headless: bool = False,
    ) -> None:
        self.replay_file = replay_file
        self.width = width
        self.height = height
        self.bg = bg_color
        self.show_queues = show_queues
        self.show_links = show_links
        self.dashed_links = dashed_links
        self.overlay = overlay
        self.headless = headless

        # State
        if ProjectState is not None:
            try:
                self.state = ProjectState()  # type: ignore
            except Exception:
                self.state = SimpleViewerState()
        else:
            self.state = SimpleViewerState()

        # Camera
        if ProjectCamera is not None:
            try:
                self.camera = ProjectCamera(width=self.width, height=self.height)  # type: ignore
            except Exception:
                self.camera = SimpleCamera(self.width, self.height)
        else:
            self.camera = SimpleCamera(self.width, self.height)

        # Replay data
        self.events: List[Dict[str, Any]] = []
        self.event_times: List[Optional[float]] = []  # extracted "t" or "time" if present
        self.idx: int = 0  # next event index to apply
        self.playing: bool = True

        # UI
        self._font: Optional[pygame.font.Font] = None
        self._font_small: Optional[pygame.font.Font] = None
        self._sb_h: int = 24  # seekbar height
        self._seeking: bool = False
        self._drag_panning: bool = False
        self._drag_last: Tuple[int, int] = (0, 0)

        # Timing
        self._clock = pygame.time.Clock()
        self._last_fps: float = 0.0

        # Load
        self._load_replay(self.replay_file)

    # --------------------------
    # Replay loading and indexing
    # --------------------------
    def _load_replay(self, path: str) -> None:
        self.events.clear()
        self.event_times.clear()
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                s = line.strip()
                if not s:
                    continue
                try:
                    evt = json.loads(s)
                    if not isinstance(evt, dict):
                        continue
                    self.events.append(evt)
                    t = _coalesce(evt.get("t"), evt.get("time"), evt.get("ts"), default=None)
                    if t is not None:
                        try:
                            t = float(t)
                        except Exception:
                            t = None
                    self.event_times.append(t)
                except json.JSONDecodeError:
                    # Skip malformed lines
                    continue

    # --------------------------
    # Event reduction
    # --------------------------
    def _reduce_event(self, evt: dict) -> None:
        """
        Reduce a single event into ViewerState mutations.
        Compatible with v0.2 schema:
          - Position/entity events: entity_create/entity_move/position/node_pos
          - Queue/task events: task_assigned/queue_update
          - Link events: link_up/link_down/offload_decision
        Safely ignores unknown or malformed events.
        """
        etype = evt.get("type") or evt.get("event") or evt.get("kind")  # fallback detection
        if not etype:
            return

        # 1) Entity/position events
        if etype in {"entity_create", "entity_move", "position", "node_pos"}:
            eid = _coalesce(evt.get("id"), evt.get("entity_id"), evt.get("node"), evt.get("uav"), evt.get("src"))
            x = evt.get("x")
            y = evt.get("y")
            if eid is None or x is None or y is None:
                return
            kind = _coalesce(evt.get("kind"), evt.get("entity_kind"), default="node")
            label = evt.get("label")
            try:
                self.state.update_entity(str(eid), str(kind), label, float(x), float(y))
            except Exception:
                # Fallback: if state doesn't have update_entity, try to set attributes directly
                if hasattr(self.state, "entities"):
                    ent = getattr(self.state, "entities").get(str(eid))
                    if ent is None:
                        try:
                            ent = Entity(id=str(eid), kind=str(kind), label=label, x=float(x), y=float(y))  # type: ignore
                        except Exception:
                            return
                        self.state.entities[str(eid)] = ent  # type: ignore
                    else:
                        ent.kind = str(kind)
                        if label is not None:
                            ent.label = label
                        ent.x = float(x)
                        ent.y = float(y)
            # Update sim time if available
            t = _coalesce(evt.get("t"), evt.get("time"), default=None)
            if t is not None:
                try:
                    self.state.sim_time = float(t)
                except Exception:
                    pass
            return

        # 2) Queue/task events
        if etype in {"task_assigned", "queue_update"}:
            node = _coalesce(evt.get("id"), evt.get("node"), evt.get("entity_id"), evt.get("uav"))
            count = _coalesce(evt.get("count"), evt.get("queue_len"), evt.get("delta"))
            if node is None or count is None:
                return
            try:
                if hasattr(self.state, "set_queue_count"):
                    self.state.set_queue_count(str(node), int(count))  # type: ignore
                else:
                    # Fallback: store both in queue_counts and entity meta
                    if not hasattr(self.state, "queue_counts"):
                        self.state.queue_counts = {}  # type: ignore
                    self.state.queue_counts[str(node)] = int(count)  # type: ignore
                    if hasattr(self.state, "entities"):
                        ent = self.state.entities.get(str(node))  # type: ignore
                        if ent is not None:
                            meta = getattr(ent, "meta", {})
                            meta["queue_count"] = int(count)
                            ent.meta = meta
            except Exception:
                pass
            return

        # 3) Link events
        if etype in {"link_up", "link_down"}:
            a = _coalesce(evt.get("src"), evt.get("from"))
            b = _coalesce(evt.get("dst"), evt.get("to"))
            if not a or not b:
                return
            up = (etype == "link_up")
            try:
                if hasattr(self.state, "set_link_state"):
                    self.state.set_link_state(str(a), str(b), up)  # type: ignore
                else:
                    # Fallback
                    if not hasattr(self.state, "links_active"):
                        self.state.links_active = set()  # type: ignore
                    key = tuple(sorted((str(a), str(b))))
                    if up:
                        self.state.links_active.add(key)  # type: ignore
                    else:
                        self.state.links_active.discard(key)  # type: ignore
            except Exception:
                pass
            # Update sim time if available
            t = _coalesce(evt.get("t"), evt.get("time"), default=None)
            if t is not None:
                try:
                    self.state.sim_time = float(t)
                except Exception:
                    pass
            return

        if etype == "offload_decision":
            src = evt.get("src")
            dst = evt.get("dst")
            if not src or not dst:
                return
            try:
                if hasattr(self.state, "pulse_link"):
                    self.state.pulse_link(str(src), str(dst))  # type: ignore
                else:
                    # Ensure the link is visible at least
                    if not hasattr(self.state, "links_active"):
                        self.state.links_active = set()  # type: ignore
                    key = tuple(sorted((str(src), str(dst))))
                    self.state.links_active.add(key)  # type: ignore
            except Exception:
                pass
            # Update sim time if available
            t = _coalesce(evt.get("t"), evt.get("time"), default=None)
            if t is not None:
                try:
                    self.state.sim_time = float(t)
                except Exception:
                    pass
            return

        # 4) Generic time tick or other info updates
        if etype in {"tick", "time_advance", "sim_time"}:
            t = _coalesce(evt.get("t"), evt.get("time"), default=None)
            if t is not None:
                try:
                    self.state.sim_time = float(t)
                except Exception:
                    pass
            return

        # Unknown types: ignore safely
        return

    # --------------------------
    # Seeking and rebuilding state
    # --------------------------
    def _rebuild_state_to(self, upto_idx: int) -> None:
        # Reset state cleanly and re-apply events up to upto_idx (exclusive)
        if ProjectState is not None:
            try:
                self.state = ProjectState()  # type: ignore
            except Exception:
                self.state = SimpleViewerState()
        else:
            self.state = SimpleViewerState()
        upto_idx = max(0, min(upto_idx, len(self.events)))
        for i in range(upto_idx):
            self._reduce_event(self.events[i])

    # --------------------------
    # Drawing
    # --------------------------
    def _draw_dashed_line(self, surf, color, a, b, dash_len: int = 8, gap_len: int = 6, width: int = 1):
        ax, ay = a
        bx, by = b
        dx = bx - ax
        dy = by - ay
        dist = math.hypot(dx, dy)
        if dist == 0:
            return
        ux = dx / dist
        uy = dy / dist
        pos = 0.0
        while pos < dist:
            seg = min(dash_len, dist - pos)
            x1 = ax + ux * pos
            y1 = ay + uy * pos
            x2 = ax + ux * (pos + seg)
            y2 = ay + uy * (pos + seg)
            pygame.draw.line(surf, color, (x1, y1), (x2, y2), width)
            pos += dash_len + gap_len

    def _draw_links(self, screen) -> None:
        links = getattr(self.state, "links_active", set())
        if not links:
            return
        col = (90, 180, 255)
        for (a, b) in list(links):
            ea = getattr(self.state, "entities", {}).get(a)
            eb = getattr(self.state, "entities", {}).get(b)
            if not ea or not eb:
                continue
            p1 = self.camera.world_to_screen(ea.x, ea.y)
            p2 = self.camera.world_to_screen(eb.x, eb.y)
            if self.dashed_links:
                self._draw_dashed_line(screen, col, p1, p2, dash_len=10, gap_len=6, width=2)
            else:
                pygame.draw.line(screen, col, p1, p2, 2)

    def _draw_entities(self, screen) -> None:
        # Simple default palette by kind
        palette = {
            "uav": (120, 220, 255),
            "ue": (120, 255, 140),
            "user": (120, 255, 140),
            "bs": (255, 180, 90),
            "server": (255, 180, 90),
            "node": (220, 220, 220),
        }
        for ent in getattr(self.state, "entities", {}).values():
            col = palette.get(ent.kind, (220, 220, 220))
            sx, sy = self.camera.world_to_screen(ent.x, ent.y)
            r = int(max(2, 6 * (0.8 + 0.2 * (1.0 if ent.kind in ("uav", "bs") else 0.8))))
            pygame.draw.circle(screen, col, (sx, sy), r)
            # Label
            if ent.label:
                self._draw_text(screen, ent.label, (sx + 8, sy - 8), (200, 200, 220))

            # Queue counter
            if self.show_queues:
                q = ent.meta.get("queue_count") if hasattr(ent, "meta") else None
                if q is None and hasattr(self.state, "queue_counts"):
                    q = self.state.queue_counts.get(ent.id)
                if q is not None:
                    self._draw_text(screen, f"Q:{q}", (sx + 8, sy + 6), (180, 210, 255), small=True)

    def _draw_seekbar(self, screen) -> None:
        if len(self.events) <= 1:
            return
        h = self._sb_h
        y0 = self.height - h
        # Background strip
        pygame.draw.rect(screen, (32, 36, 44), pygame.Rect(0, y0, self.width, h))
        # Progress
        ratio = 0.0 if len(self.events) == 0 else min(1.0, max(0.0, self.idx / max(1, len(self.events) - 1)))
        x = int(ratio * self.width)
        pygame.draw.rect(screen, (70, 140, 220), pygame.Rect(0, y0, x, h))
        # Handle
        pygame.draw.rect(screen, (200, 220, 240), pygame.Rect(x - 2, y0, 4, h))
        # Time scale (if we have times)
        if any(t is not None for t in self.event_times):
            t0 = None
            tn = None
            for t in self.event_times:
                if t is not None:
                    t0 = t if t0 is None else min(t0, t)
                    tn = t if tn is None else max(tn, t)
            if t0 is not None and tn is not None and tn > t0:
                # draw min/max labels
                self._draw_text(screen, f"{t0:.2f}s", (6, y0 + 4), (180, 180, 200), small=True)
                s = f"{tn:.2f}s"
                w = self._text_size(s, small=True)[0]
                self._draw_text(screen, s, (self.width - w - 6, y0 + 4), (180, 180, 200), small=True)

    def _draw_overlay(self, screen) -> None:
        if not self.overlay:
            return
        # HUD: play state, sim time, zoom, center, fps
        play = "PLAY" if self.playing else "PAUSE"
        simt = getattr(self.state, "sim_time", 0.0)
        zoom = getattr(self.camera, "scale", 1.0)
        text = f"{play} | Events: {self.idx}/{len(self.events)} | Sim t={simt:.2f}s | Zoom={zoom:.2f} | FPS={self._last_fps:.1f}"
        self._draw_text(screen, text, (8, 6), (210, 220, 230))

        # Controls hint (small)
        hint = "Space:Play/Pause  PgUp/PgDn:±10  Home/End:⟲/⟲  Z/X:Zoom  Arrows:Pan  MouseWheel:Zoom  Seekbar:Click/Drag"
        self._draw_text(screen, hint, (8, 26), (170, 180, 190), small=True)

    # --------------------------
    # Text helpers
    # --------------------------
    def _ensure_fonts(self) -> None:
        if self._font is None or self._font_small is None:
            # Safe init after pygame.init
            try:
                self._font = pygame.font.SysFont("consolas", 16)
                self._font_small = pygame.font.SysFont("consolas", 12)
            except Exception:
                self._font = pygame.font.Font(None, 16)
                self._font_small = pygame.font.Font(None, 12)

    def _text_size(self, s: str, small: bool = False) -> Tuple[int, int]:
        self._ensure_fonts()
        f = self._font_small if small else self._font
        if f is None:
            return (len(s) * 8, 16 if not small else 12)
        tm = f.render(s, True, (255, 255, 255))
        return tm.get_size()

    def _draw_text(self, screen, s: str, pos: Tuple[int, int], color=(255, 255, 255), small: bool = False) -> None:
        self._ensure_fonts()
        f = self._font_small if small else self._font
        if f is None:
            return
        surf = f.render(s, True, color)
        screen.blit(surf, pos)

    # --------------------------
    # Event loop
    # --------------------------
    def run(self, fps: int = 30) -> None:
        pygame.init()

        flags = 0 if not self.headless else pygame.HIDDEN
        screen = pygame.display.set_mode((self.width, self.height), flags)
        pygame.display.set_caption("SkyMind Viewer v0.2")

        running = True
        while running:
            # Event handling
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False

                elif event.type == pygame.MOUSEBUTTONDOWN:
                    mx, my = event.pos
                    if event.button == 1:
                        # Seekbar?
                        if my >= self.height - self._sb_h:
                            self._seeking = True
                            self._seek_to_mouse(mx)
                        else:
                            # left-drag to pan
                            self._drag_panning = True
                            self._drag_last = (mx, my)
                    elif event.button == 3:
                        # right-drag to pan as well
                        self._drag_panning = True
                        self._drag_last = (mx, my)
                    elif event.button == 4:  # wheel up: zoom in
                        self.camera.zoom_at(1.1, (mx, my))
                    elif event.button == 5:  # wheel down: zoom out
                        self.camera.zoom_at(1.0 / 1.1, (mx, my))

                elif event.type == pygame.MOUSEBUTTONUP:
                    if event.button in (1, 3):
                        self._drag_panning = False
                        self._seeking = False

                elif event.type == pygame.MOUSEMOTION:
                    mx, my = event.pos
                    if self._drag_panning and my < self.height - self._sb_h:
                        lx, ly = self._drag_last
                        dx = mx - lx
                        dy = my - ly
                        self.camera.pan(dx, dy)
                        self._drag_last = (mx, my)
                    if self._seeking and my >= self.height - self._sb_h:
                        self._seek_to_mouse(mx)

                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_SPACE:
                        self.playing = not self.playing
                    elif event.key == pygame.K_HOME:
                        self.idx = 0
                        self._rebuild_state_to(self.idx)
                    elif event.key == pygame.K_END:
                        self.idx = len(self.events)
                        self._rebuild_state_to(self.idx)
                    elif event.key == pygame.K_PAGEUP:
                        self.idx = max(0, self.idx - 10)
                        self._rebuild_state_to(self.idx)
                    elif event.key == pygame.K_PAGEDOWN:
                        self.idx = min(len(self.events), self.idx + 10)
                        self._rebuild_state_to(self.idx)
                    elif event.key == pygame.K_z:
                        mx, my = pygame.mouse.get_pos()
                        self.camera.zoom_at(1.1, (mx, my))
                    elif event.key == pygame.K_x:
                        mx, my = pygame.mouse.get_pos()
                        self.camera.zoom_at(1.0 / 1.1, (mx, my))
                    elif event.key == pygame.K_UP:
                        self.camera.pan(0, 50)
                    elif event.key == pygame.K_DOWN:
                        self.camera.pan(0, -50)
                    elif event.key == pygame.K_LEFT:
                        self.camera.pan(50, 0)
                    elif event.key == pygame.K_RIGHT:
                        self.camera.pan(-50, 0)

            # Playback step
            if self.playing and not self._seeking:
                if self.idx < len(self.events):
                    self._reduce_event(self.events[self.idx])
                    self.idx += 1

            # Render
            screen.fill(self.bg)

            # Draw links before entities for nice layering
            if self.show_links:
                self._draw_links(screen)
            self._draw_entities(screen)

            # HUD and seekbar
            if self.overlay:
                self._draw_overlay(screen)
            self._draw_seekbar(screen)

            pygame.display.flip()
            self._last_fps = self._clock.get_fps()
            self._clock.tick(fps)

        pygame.quit()

    def _seek_to_mouse(self, mx: int) -> None:
        # Map x to event index
        ratio = min(1.0, max(0.0, mx / max(1, self.width)))
        new_idx = int(round(ratio * (len(self.events) - 1)))
        new_idx = max(0, min(len(self.events), new_idx))
        if new_idx != self.idx:
            self.idx = new_idx
            self._rebuild_state_to(self.idx)


# --------------------------------------------
# Convenience main (manual testing)
# --------------------------------------------
if __name__ == "__main__":
    # Minimal manual test (requires a JSONL file path as first arg)
    path = sys.argv[1] if len(sys.argv) > 1 else ""
    if not path or not os.path.exists(path):
        print("Usage: python -m skymind_viewer.renderer <path/to/replay.jsonl>")
        sys.exit(1)
    r = Renderer(
        replay_file=path,
        width=1280,
        height=800,
        bg_color=(15, 15, 20),
        show_queues=True,
        show_links=True,
        dashed_links=False,
        overlay=True,
        headless=False,
    )
    r.run(fps=30)
