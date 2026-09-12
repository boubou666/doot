"""Doot's monitor policy on top of :mod:`desktop_overlay`.

The shared package owns operating-system enumeration and geometry. This module
keeps Doot's French status text and its legacy random-placement method names so
the application-facing API remains stable.
"""

from __future__ import annotations

import random

from desktop_overlay import geometry as _geometry
from desktop_overlay.monitors import enumerate_monitors


class Monitor(_geometry.Monitor):
    """A shared monitor rectangle with Doot's legacy placement vocabulary."""

    def __init__(self, x, y, width, height, primary=False, name=""):
        super().__init__(
            x, y, width, height, primary=primary, name=name or "ecran"
        )

    def place(self, width: int, height: int, center: bool, rng):
        return self.random_position(width, height, center=center, rng=rng)

    def entry(self, width: int, height: int, side: str, rng,
              near=(0.0, 0.03), center=False):
        return self.edge_entry(
            width, height, side, rng=rng, near=near, center=center
        )


def _local(monitor: _geometry.Monitor) -> Monitor:
    if isinstance(monitor, Monitor):
        return monitor
    return Monitor(
        monitor.x,
        monitor.y,
        monitor.width,
        monitor.height,
        primary=monitor.primary,
        name=monitor.name,
    )


def monitors(fallback_width: int = 1920,
             fallback_height: int = 1080) -> list[Monitor]:
    """Return every active screen, with one fallback when detection fails."""
    return [
        _local(monitor)
        for monitor in enumerate_monitors(fallback_width, fallback_height)
    ]


def pick(found: list[Monitor], preference=None, rng=None) -> Monitor:
    """Choose a monitor using Doot's random default policy."""
    return _local(
        _geometry.pick_monitor(
            found,
            preference,
            default="random",
            rng=rng or random,
        )
    )


ease_out = _geometry.ease_out
virtual_bounds = _geometry.horizontal_bounds


def pan_for(center_x: float, found: list[Monitor] | None = None) -> float:
    """Map a Doot's resting position to the whole desktop's stereo field."""
    return _geometry.pan_for(
        center_x,
        found if found is not None else monitors(),
    )


def describe(found: list[Monitor]) -> str:
    if len(found) == 1:
        monitor = found[0]
        return f"1 ecran ({monitor.width}x{monitor.height})"
    parts = ", ".join(
        f"{index}:{monitor.name} {monitor.width}x{monitor.height}"
        f"{'*' if monitor.primary else ''}"
        for index, monitor in enumerate(found)
    )
    return f"{len(found)} ecrans [{parts}]"