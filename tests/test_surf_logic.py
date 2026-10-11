"""Tests for the HA-independent surf logic (custom_components/surf_forecast/surf.py)."""

from __future__ import annotations

import importlib.util
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

_PATH = Path(__file__).parents[1] / "custom_components" / "surf_forecast" / "surf.py"
_spec = importlib.util.spec_from_file_location("surf_logic", _PATH)
surf = importlib.util.module_from_spec(_spec)
sys.modules["surf_logic"] = surf
_spec.loader.exec_module(surf)

T0 = int(datetime(2026, 10, 11, 0, tzinfo=timezone.utc).timestamp())


def _responses(hours: int, **overrides):
    """Build fake Open-Meteo responses; overrides map field -> callable(i)."""
    times = [T0 + i * 3600 for i in range(hours)]

    def series(name, default):
        fn = overrides.get(name, lambda i: default)
        return [fn(i) for i in range(hours)]

    marine = {
        "utc_offset_seconds": 7200,
        "hourly": {
            "time": times,
            "wave_height": series("wave_height", 1.2),
            "wave_period": series("wave_period", 9.0),
            "wave_direction": series("wave_direction", 280.0),
            "swell_wave_height": series("swell_wave_height", 1.0),
            "swell_wave_period": series("swell_wave_period", 10.0),
            "swell_wave_direction": series("swell_wave_direction", 285.0),
            "sea_surface_temperature": series("sea_surface_temperature", 15.0),
        },
    }
    weather = {
        "utc_offset_seconds": 7200,
        "hourly": {
            "time": times,
            "wind_speed_10m": series("wind_speed_10m", 8.0),
            "wind_direction_10m": series("wind_direction_10m", 100.0),
            "wind_gusts_10m": series("wind_gusts_10m", 12.0),
            "is_day": series("is_day", 1),
        },
    }
    return marine, weather


def test_in_corridor_wraps_around_north():
    assert surf.in_corridor(10, (300, 60))
    assert surf.in_corridor(330, (300, 60))
    assert not surf.in_corridor(180, (300, 60))
    assert surf.in_corridor(150, (90, 200))
    assert not surf.in_corridor(250, (90, 200))
    assert surf.in_corridor(None, None)
    assert not surf.in_corridor(None, (0, 90))


def test_parse_merges_and_uses_local_offset():
    marine, weather = _responses(3)
    hours, tz = surf.parse_responses(marine, weather)
    assert len(hours) == 3
    assert hours[0].time == datetime(2026, 10, 11, 0, tzinfo=timezone.utc)
    assert hours[0].wind_speed == 8.0 and hours[0].swell_height == 1.0
    assert tz.utcoffset(None) == timedelta(hours=2)


def test_parse_drops_hours_without_waves_and_tolerates_missing_fields():
    marine, weather = _responses(4, wave_height=lambda i: None if i == 3 else 1.0)
    del marine["hourly"]["sea_surface_temperature"]
    hours, _ = surf.parse_responses(marine, weather)
    assert len(hours) == 3
    assert hours[0].water_temperature is None


def test_session_detection_with_wind_corridor():
    # offshore (100°) for hours 6..11, onshore (280°) otherwise
    marine, weather = _responses(
        24, wind_direction_10m=lambda i: 100.0 if 6 <= i < 12 else 280.0
    )
    hours, tz = surf.parse_responses(marine, weather)
    criteria = surf.SurfCriteria(wind_corridor=(45, 135), glassy_max=3, min_duration=2)
    data = surf.evaluate(hours, criteria, tz)
    assert len(data.sessions) == 1
    session = data.sessions[0]
    assert session.hours == 6
    assert session.start == hours[6].time
    assert session.end == hours[11].time + timedelta(hours=1)


def test_glassy_wind_ignores_direction_and_too_much_wind_blocks():
    marine, weather = _responses(
        6,
        wind_direction_10m=lambda i: 280.0,
        wind_speed_10m=lambda i: [2, 2, 2, 20, 20, 20][i],
    )
    hours, tz = surf.parse_responses(marine, weather)
    criteria = surf.SurfCriteria(wind_corridor=(45, 135), glassy_max=5, wind_max=15)
    data = surf.evaluate(hours, criteria, tz)
    assert [h.match for h in hours] == [True, True, True, False, False, False]
    assert len(data.sessions) == 1


def test_wave_corridor_period_daylight_and_min_duration():
    marine, weather = _responses(
        8,
        wave_height=lambda i: [0.3, 1.2, 1.2, 3.5, 1.2, 1.2, 1.2, 1.2][i],
        wave_period=lambda i: [9, 9, 9, 9, 9, 5, 9, 9][i],
        is_day=lambda i: 0 if i == 7 else 1,
    )
    hours, tz = surf.parse_responses(marine, weather)
    data = surf.evaluate(hours, surf.SurfCriteria(min_duration=2), tz)
    assert [h.match for h in hours] == [False, True, True, False, True, False, True, False]
    # runs: [1,2] -> session, [4] too short, [6] too short
    assert [s.hours for s in data.sessions] == [2]


def test_swell_mode_and_swell_corridor():
    marine, weather = _responses(4, swell_wave_direction=lambda i: 285.0 if i < 2 else 20.0)
    hours, tz = surf.parse_responses(marine, weather)
    criteria = surf.SurfCriteria(use_swell=True, swell_corridor=(250, 320), min_duration=1)
    data = surf.evaluate(hours, criteria, tz)
    assert [h.match for h in hours] == [True, True, False, False]


def test_daily_summary_groups_by_local_day():
    marine, weather = _responses(48)
    hours, tz = surf.parse_responses(marine, weather)
    data = surf.evaluate(hours, surf.SurfCriteria(), tz)
    # 48 UTC hours at UTC+2 span three local days (22 + 24 + 2 hours)
    assert [d.day.isoformat() for d in data.days] == ["2026-10-11", "2026-10-12", "2026-10-13"]
    assert data.days[1].good_hours == 24
    assert data.days[1].wave_max == 1.2
    assert data.days[1].wind_direction == 100


def test_rating_prefers_good_conditions():
    criteria = surf.SurfCriteria(wind_corridor=(45, 135))
    t = datetime(2026, 1, 1, tzinfo=timezone.utc)
    good = surf.HourPoint(time=t, wave_height=1.6, wave_period=13, wind_speed=3, wind_direction=280)
    blown = surf.HourPoint(time=t, wave_height=1.6, wave_period=13, wind_speed=30, wind_direction=280)
    flat = surf.HourPoint(time=t, wave_height=0.2, wave_period=4, wind_speed=0)
    assert surf.rate_hour(good, criteria) == 5.0
    assert surf.rate_hour(blown, criteria) < 4
    assert surf.rate_hour(flat, criteria) == 0.0


def test_current_hour_and_upcoming_sessions():
    marine, weather = _responses(6)
    hours, tz = surf.parse_responses(marine, weather)
    data = surf.evaluate(hours, surf.SurfCriteria(), tz)
    now = hours[2].time + timedelta(minutes=30)
    assert data.current_hour(now) is hours[2]
    assert len(data.upcoming_sessions(now)) == 1
    assert data.upcoming_sessions(hours[-1].time + timedelta(hours=2)) == []


def test_compass():
    assert surf.compass(0) == "N"
    assert surf.compass(359) == "N"
    assert surf.compass(90) == "O"
    assert surf.compass(225) == "SW"
    assert surf.compass(None) is None
