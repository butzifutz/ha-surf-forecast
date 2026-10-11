"""SVG background for the compass card showing the configured corridors.

No Home Assistant imports, so it can be unit-tested on its own.
"""

from __future__ import annotations

import math

SIZE = 126  # compass-card recommends a square image of 126 x 126 px
CENTER = SIZE / 2

WIND_COLOR = "#43a047"  # green: wind may come from here
SWELL_COLOR = "#1e88e5"  # blue: swell may come from here


def _point(angle: float, radius: float) -> tuple[float, float]:
    """Compass angle (0 = north, clockwise) to SVG coordinates."""
    rad = math.radians(angle)
    return CENTER + radius * math.sin(rad), CENTER - radius * math.cos(rad)


def _span(start: float, end: float) -> float:
    """Clockwise angular width from ``start`` to ``end``."""
    return (end - start) % 360 or 360


def sector_path(start: float, end: float, outer: float, inner: float = 0.0) -> str:
    """SVG path for a clockwise sector (inner > 0 gives a ring segment)."""
    span = _span(start, end)
    if span >= 360:
        # full circle: a single arc can't draw it, use two halves
        return sector_path(start, start + 180, outer, inner) + sector_path(
            start + 180, start + 360, outer, inner
        )
    large = 1 if span > 180 else 0
    x1, y1 = _point(start, outer)
    x2, y2 = _point(start + span, outer)
    path = f"M{x1:.2f},{y1:.2f} A{outer},{outer} 0 {large} 1 {x2:.2f},{y2:.2f} "
    if inner > 0:
        x3, y3 = _point(start + span, inner)
        x4, y4 = _point(start, inner)
        path += f"L{x3:.2f},{y3:.2f} A{inner},{inner} 0 {large} 0 {x4:.2f},{y4:.2f} Z"
    else:
        path += f"L{CENTER},{CENTER} Z"
    return path


def compass_svg(
    wind_corridor: tuple[float, float] | None,
    swell_corridor: tuple[float, float] | None,
) -> str:
    """Background image: wind corridor as green wedge, swell corridor as blue ring."""
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{SIZE}" height="{SIZE}" '
        f'viewBox="0 0 {SIZE} {SIZE}">'
    ]
    if wind_corridor is not None:
        parts.append(
            f'<path d="{sector_path(*wind_corridor, outer=CENTER - 6)}" '
            f'fill="{WIND_COLOR}" fill-opacity="0.35"/>'
        )
    if swell_corridor is not None:
        parts.append(
            f'<path d="{sector_path(*swell_corridor, outer=CENTER, inner=CENTER - 6)}" '
            f'fill="{SWELL_COLOR}" fill-opacity="0.8"/>'
        )
    parts.append("</svg>")
    return "".join(parts)
