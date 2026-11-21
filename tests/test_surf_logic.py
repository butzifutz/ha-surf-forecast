"""Tests for the HA-independent surf logic (custom_components/surf_forecast/surf.py)."""

from __future__ import annotations

import importlib.util
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

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
    # wind from the corridor (100°) for hours 6..11, from outside (280°) otherwise
    marine, weather = _responses(
        24, wind_direction_10m=lambda i: 100.0 if 6 <= i < 12 else 280.0
    )
    hours, tz = surf.parse_responses(marine, weather)
    criteria = surf.SurfCriteria(wind_corridor=(45, 135), calm_max=3, min_duration=2)
    data = surf.evaluate(hours, criteria, tz)
    assert len(data.sessions) == 1
    session = data.sessions[0]
    assert session.hours == 6
    assert session.start == hours[6].time
    assert session.end == hours[11].time + timedelta(hours=1)


def test_calm_wind_ignores_direction_and_too_much_wind_blocks():
    marine, weather = _responses(
        6,
        wind_direction_10m=lambda i: 280.0,
        wind_speed_10m=lambda i: [2, 2, 2, 20, 20, 40][i],
    )
    hours, tz = surf.parse_responses(marine, weather)
    criteria = surf.SurfCriteria(wind_corridor=(45, 135), calm_max=5, wind_max=30)
    data = surf.evaluate(hours, criteria, tz)
    # calm -> ok, 20 from outside the corridor -> no, 40 -> too strong
    assert [h.match for h in hours] == [True, True, True, False, False, False]
    assert len(data.sessions) == 1


def test_energy_threshold_period_daylight_and_min_duration():
    marine, weather = _responses(
        8,
        wave_height=lambda i: [0.3, 1.2, 1.2, 1.2, 1.2, 1.2, 1.2, 1.2][i],
        wave_period=lambda i: [9, 9, 9, 2.5, 9, 9, 9, 9][i],
        is_day=lambda i: 0 if i == 7 else 1,
    )
    hours, tz = surf.parse_responses(marine, weather)
    data = surf.evaluate(hours, surf.SurfCriteria(min_duration=2), tz)
    # 0.3 m @ 9 s = 0.4 kW/m < 0.6; 2.5 s < period_min 3; hour 7 is dark
    assert [h.match for h in hours] == [False, True, True, False, True, True, True, False]
    assert [s.hours for s in data.sessions] == [2, 3]
    assert hours[1].energy == round(0.49 * 1.2**2 * 9, 2)


def test_daily_summary_groups_by_local_day():
    marine, weather = _responses(48)
    hours, tz = surf.parse_responses(marine, weather)
    data = surf.evaluate(hours, surf.SurfCriteria(), tz)
    # 48 UTC hours at UTC+2 span three local days (22 + 24 + 2 hours)
    assert [d.day.isoformat() for d in data.days] == ["2026-10-11", "2026-10-12", "2026-10-13"]
    assert data.days[1].good_hours == 24
    assert data.days[1].wave_max == 1.2
    assert data.days[1].wind_direction == 100


def _hour(wave, period, swell=0.0, wind=20.0, direction=280.0, sea_level=None):
    t = datetime(2026, 11, 13, 12, tzinfo=timezone.utc)
    return surf.HourPoint(
        time=t, wave_height=wave, wave_period=period, swell_height=swell,
        wind_speed=wind, wind_direction=direction, sea_level=sea_level,
    )  # fmt: skip


# Hohe Düne (km/h), corridor WSW..NE, as calibrated on 12-14 Nov 2026
HOHE_DUENE = surf.SurfCriteria(
    wind_corridor=(235, 45), wind_max=55, wind_strong=45, calm_max=8, daylight_only=False
)


@pytest.mark.parametrize(
    ("hour", "expected"),
    [
        (_hour(0.78, 3.5, 0.10, 20, 224), 0.0),  # Thu: SW is outside the corridor
        (_hour(1.32, 4.5, 0.10, 36, 287), 4.2),  # Fri morning: longboard
        (_hour(1.52, 4.8, 0.08, 40, 287), 4.5),  # Fri afternoon: very good
        (_hour(0.80, 3.8, 0.38, 22, 242), 2.8),  # Sat morning: small, clean leftover
        (_hour(0.68, 3.5, 0.24, 20, 238), 1.6),  # Sat afternoon: just about
        (_hour(0.32, 2.4, 0.14, 17, 153), 0.0),  # Sun: flat
    ],
)
def test_rating_matches_hohe_duene_observations(hour, expected):
    assert surf.rate_hour(hour, HOHE_DUENE) == expected


def test_rating_components():
    c = surf.SurfCriteria(wind_max=40, wind_strong=30, sea_level_max=0.5)
    base = surf.rate_hour(_hour(1.0, 4.0), c)
    assert 1.0 < base < 4.5
    assert surf.rate_hour(_hour(1.0, 4.0, swell=0.5), c) == round(base + 1.0, 1)
    assert surf.rate_hour(_hour(1.0, 4.0, swell=0.35), c) == round(base + 0.5, 1)
    assert surf.rate_hour(_hour(1.0, 4.0, wind=29), c) == base
    assert surf.rate_hour(_hour(1.0, 4.0, wind=31), c) == round(base - 0.5, 1)
    assert surf.rate_hour(_hour(1.0, 4.0, sea_level=0.6), c) == round(base - 1.0, 1)
    assert surf.rate_hour(_hour(3.0, 8.0, swell=1.0), c) == 5.0  # capped
    assert surf.rate_hour(_hour(0.3, 3.0), c) == 0.0  # not surfable


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


def test_forecast_archive_records_lead_times_and_returns_them_later():
    marine, weather = _responses(24 * 7)
    hours, tz = surf.parse_responses(marine, weather)
    surf.evaluate(hours, surf.SurfCriteria(daylight_only=False), tz)
    archive: dict = {}
    now = hours[0].time + timedelta(minutes=17)
    surf.record_forecast(archive, hours, now)
    # leads 1, 3, 6 days -> 3 target hours, each with all tracked quantities
    assert sorted(archive) == sorted(
        (hours[0].time + timedelta(days=d)).isoformat() for d in surf.LEAD_DAYS
    )
    target = hours[0].time + timedelta(days=3)
    point = hours[72]
    assert archive[target.isoformat()] == {
        "3": {"rating": point.rating, "wave": 1.2, "swell": 1.0, "wind": 8.0}
    }

    # a later run must not overwrite what was forecast earlier
    first = point.rating
    assert first > 0
    point.rating = 0.0
    surf.record_forecast(archive, hours, now)
    assert archive[target.isoformat()]["3"]["rating"] == first

    # three days later the current hour has the 3-day-old forecast
    later = target + timedelta(minutes=30)
    assert surf.predicted(archive, later, 3) == first
    assert surf.predicted(archive, later, 3, "wave") == 1.2
    assert surf.predicted(archive, later, 1) is None

    # old entries are pruned
    surf.record_forecast(archive, hours, target + timedelta(days=1))
    assert target.isoformat() not in archive


def test_archive_from_0_5_1_is_upgraded():
    old = {"2026-11-20T10:00:00+00:00": {"1": 3.5, "2": 2.0, "3": 0.0}}
    assert surf.upgrade_archive(old) == {
        "2026-11-20T10:00:00+00:00": {"1": {"rating": 3.5}, "3": {"rating": 0.0}}
    }


def test_forecast_for_finds_the_hour():
    marine, weather = _responses(48)
    hours, _ = surf.parse_responses(marine, weather)
    assert surf.forecast_for(hours, hours[30].time + timedelta(minutes=45)) is hours[30]
    assert surf.forecast_for(hours, hours[-1].time + timedelta(hours=2)) is None


def test_hourly_attributes_are_compact():
    point = surf.HourPoint(time=datetime(2026, 1, 1, tzinfo=timezone.utc), wave_height=1.0)
    attrs = surf.hour_as_attr(point, timezone(timedelta(hours=1)))
    assert attrs["time"] == "2026-01-01T01:00+01:00"
    assert set(attrs) == {"time", "wave", "period", "swell", "wind", "wind_dir", "energy", "rating", "match"}
