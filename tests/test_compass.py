"""Tests for the compass background SVG (custom_components/surf_forecast/compass.py)."""

from __future__ import annotations

import importlib.util
import re
import xml.etree.ElementTree as ET
from pathlib import Path

_PATH = Path(__file__).parents[1] / "custom_components" / "surf_forecast" / "compass.py"
_spec = importlib.util.spec_from_file_location("compass_logic", _PATH)
compass = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(compass)

NUM = r"(-?\d+(?:\.\d+)?)"


def _arc(path: str) -> tuple[float, float, int, float, float]:
    """(start x, start y, large-arc flag, end x, end y) of the first arc."""
    m = re.match(rf"M{NUM},{NUM} A[\d.]+,[\d.]+ 0 (\d) 1 {NUM},{NUM}", path)
    assert m, path
    x1, y1, large, x2, y2 = m.groups()
    return float(x1), float(y1), int(large), float(x2), float(y2)


def test_point_orientation():
    c = compass.CENTER
    assert compass._point(0, 10) == (c, c - 10)  # north is up
    x, y = compass._point(90, 10)  # east is right
    assert round(x - c, 6) == 10 and round(y - c, 6) == 0


def test_wedge_east_quadrant():
    c = compass.CENTER
    x1, y1, large, x2, y2 = _arc(compass.sector_path(0, 90, outer=50))
    assert (round(x1, 2), round(y1, 2)) == (c, c - 50)
    assert (round(x2, 2), round(y2, 2)) == (c + 50, c)
    assert large == 0


def test_wrap_around_north_and_large_arc():
    # 300 -> 60 is 120° wide (wraps over north)
    *_, large, _, _ = _arc(compass.sector_path(300, 60, outer=50))
    assert large == 0
    # 90 -> 0 is 270° wide
    *_, large, _, _ = _arc(compass.sector_path(90, 0, outer=50))
    assert large == 1


def test_svg_is_valid_xml_and_contains_requested_layers():
    svg = compass.compass_svg((45, 135), (250, 320))
    root = ET.fromstring(svg)
    paths = root.findall("{http://www.w3.org/2000/svg}path")
    assert [p.get("fill") for p in paths] == [compass.WIND_COLOR, compass.SWELL_COLOR]
    assert len(ET.fromstring(compass.compass_svg(None, None))) == 0
    # a full-circle corridor still renders
    ET.fromstring(compass.compass_svg((0, 0), None))
