"""Pure surf logic: parse Open-Meteo responses, rate hours, find sessions.

This module deliberately has no Home Assistant imports so it can be unit-tested
on its own.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta, timezone
import math
from typing import Any


@dataclass(slots=True)
class HourPoint:
    """Merged marine + weather values for one forecast hour."""

    time: datetime
    wave_height: float | None = None
    wave_period: float | None = None
    wave_direction: float | None = None
    swell_height: float | None = None
    swell_period: float | None = None
    swell_direction: float | None = None
    wind_wave_height: float | None = None
    wind_speed: float | None = None
    wind_gusts: float | None = None
    wind_direction: float | None = None
    water_temperature: float | None = None
    air_temperature: float | None = None
    sea_level: float | None = None
    is_day: bool = True
    # filled in by evaluate()
    energy: float = 0.0
    match: bool = False
    rating: float = 0.0


@dataclass(slots=True)
class SurfCriteria:
    """User-defined conditions for a surfable hour (made for the Baltic Sea).

    An hour is surfable when the wave energy (total waves incl. wind sea) and
    the period are high enough, the wind isn't too strong and blows from the
    corridor that works at the spot (from experience, e.g. sheltered by a
    mole). Below ``calm_max`` the wind direction doesn't matter.

    The corridor is (from, to) in degrees, clockwise, and may wrap around
    north (e.g. 235 -> 45). ``None`` means "any direction".
    """

    energy_min: float = 0.6  # kW/m: just about surfable (~0.6 m @ 3.5 s)
    energy_top: float = 4.5  # kW/m: as good as it gets (~1.4 m @ 4.7 s)
    period_min: float = 3.0
    wind_max: float = 30.0
    wind_strong: float = 24.0  # rating penalty above this
    wind_corridor: tuple[float, float] | None = None
    calm_max: float = 5.0
    swell_bonus_min: float = 0.2  # m: leftover swell above this adds up to +1
    sea_level_max: float | None = None  # m: rating penalty above (high water)
    daylight_only: bool = True
    min_duration: int = 2


@dataclass(slots=True)
class Session:
    """A contiguous window of surfable hours."""

    start: datetime
    end: datetime  # exclusive: end of the last matching hour
    hours: int
    max_rating: float
    avg_rating: float
    wave_min: float
    wave_max: float
    period_max: float
    wind_max: float

    @property
    def key(self) -> str:
        """Stable identifier, used to avoid notifying twice."""
        return self.start.isoformat()

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["start"] = self.start.isoformat()
        data["end"] = self.end.isoformat()
        return data


@dataclass(slots=True)
class DaySummary:
    day: date
    wave_min: float | None
    wave_max: float | None
    period_max: float | None
    energy_max: float | None
    wave_direction: float | None
    swell_direction: float | None
    wind_min: float | None
    wind_max: float | None
    wind_direction: float | None
    water_temperature: float | None
    max_rating: float
    good_hours: int

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["day"] = self.day.isoformat()
        return data


@dataclass(slots=True)
class SurfData:
    hours: list[HourPoint]
    sessions: list[Session]
    days: list[DaySummary]
    tz: timezone = field(default=timezone.utc)

    def current_hour(self, now: datetime) -> HourPoint | None:
        """Return the forecast hour containing ``now``."""
        current = None
        for hour in self.hours:
            if hour.time <= now:
                current = hour
            else:
                break
        return current

    def upcoming_sessions(self, now: datetime) -> list[Session]:
        return [s for s in self.sessions if s.end > now]


# --------------------------------------------------------------------------- #
# Parsing
# --------------------------------------------------------------------------- #

MARINE_FIELDS = {
    "wave_height": "wave_height",
    "wave_period": "wave_period",
    "wave_direction": "wave_direction",
    "swell_wave_height": "swell_height",
    "swell_wave_period": "swell_period",
    "swell_wave_direction": "swell_direction",
    "wind_wave_height": "wind_wave_height",
    "sea_surface_temperature": "water_temperature",
    "sea_level_height_msl": "sea_level",
}

WEATHER_FIELDS = {
    "wind_speed_10m": "wind_speed",
    "wind_gusts_10m": "wind_gusts",
    "wind_direction_10m": "wind_direction",
    "temperature_2m": "air_temperature",
    "is_day": "is_day",
}


def _merge_hourly(
    target: dict[int, HourPoint], payload: dict[str, Any], fields: dict[str, str]
) -> None:
    hourly = payload.get("hourly") or {}
    times = hourly.get("time") or []
    for idx, ts in enumerate(times):
        point = target.get(ts)
        if point is None:
            point = HourPoint(time=datetime.fromtimestamp(ts, tz=timezone.utc))
            target[ts] = point
        for api_name, attr in fields.items():
            values = hourly.get(api_name)
            if values is None or idx >= len(values) or values[idx] is None:
                continue
            value = values[idx]
            setattr(point, attr, bool(value) if attr == "is_day" else float(value))


def parse_responses(
    marine: dict[str, Any], weather: dict[str, Any]
) -> tuple[list[HourPoint], timezone]:
    """Merge Open-Meteo marine + forecast responses (``timeformat=unixtime``)."""
    points: dict[int, HourPoint] = {}
    _merge_hourly(points, marine, MARINE_FIELDS)
    _merge_hourly(points, weather, WEATHER_FIELDS)
    offset = weather.get("utc_offset_seconds", marine.get("utc_offset_seconds", 0))
    tz = timezone(timedelta(seconds=int(offset or 0)))
    # only keep hours where we actually have wave data
    hours = [p for _, p in sorted(points.items()) if p.wave_height is not None]
    return hours, tz


# --------------------------------------------------------------------------- #
# Evaluation
# --------------------------------------------------------------------------- #


def in_corridor(angle: float | None, corridor: tuple[float, float] | None) -> bool:
    """Whether ``angle`` lies in the clockwise corridor ``(from, to)``."""
    if corridor is None:
        return True
    if angle is None:
        return False
    start, end = (c % 360 for c in corridor)
    angle %= 360
    if start <= end:
        return start <= angle <= end
    return angle >= start or angle <= end


def wave_energy(point: HourPoint) -> float:
    """Wave energy flux in kW/m: 0.49 * H² * T (deep-water approximation)."""
    if point.wave_height is None or point.wave_period is None:
        return 0.0
    return 0.49 * point.wave_height**2 * point.wave_period


def wind_ok(point: HourPoint, criteria: SurfCriteria) -> bool:
    if point.wind_speed is None:
        return True  # no wind data -> don't block
    if point.wind_speed > criteria.wind_max:
        return False
    if point.wind_speed <= criteria.calm_max:
        return True  # (almost) no wind: direction doesn't matter
    return in_corridor(point.wind_direction, criteria.wind_corridor)


def _clip(value: float) -> float:
    return max(0.0, min(1.0, value))


def hour_matches(point: HourPoint, criteria: SurfCriteria) -> bool:
    if criteria.daylight_only and not point.is_day:
        return False
    if wave_energy(point) < criteria.energy_min:
        return False
    if criteria.period_min > 0 and (point.wave_period or 0.0) < criteria.period_min:
        return False
    return wind_ok(point, criteria)


def rate_hour(point: HourPoint, criteria: SurfCriteria) -> float:
    """Rating of a surfable hour: 1 (just about) .. 5 (best). Not surfable = 0.

    base:      1 .. 4.5, logarithmic in wave energy between energy_min and
               energy_top (small clean days still count, big days saturate)
    leftover:  +0 .. +1 for swell above swell_bonus_min (sorted leftover sea
               after a blow; counted on top of the total wave energy)
    wind:      -0.5 above wind_strong
    sea level: -1 above sea_level_max (high water)
    """
    if not hour_matches(point, criteria):
        return 0.0
    energy = wave_energy(point)
    span = math.log(criteria.energy_top / criteria.energy_min)
    base = 1.0 + 3.5 * (_clip(math.log(energy / criteria.energy_min) / span) if span > 0 else 1.0)
    bonus = _clip(((point.swell_height or 0.0) - criteria.swell_bonus_min) / 0.3)
    rating = base + bonus
    if point.wind_speed is not None and point.wind_speed > criteria.wind_strong:
        rating -= 0.5
    if (
        criteria.sea_level_max is not None
        and point.sea_level is not None
        and point.sea_level > criteria.sea_level_max
    ):
        rating -= 1.0
    return round(max(1.0, min(5.0, rating)), 1)


def find_sessions(hours: list[HourPoint], criteria: SurfCriteria) -> list[Session]:
    sessions: list[Session] = []
    run: list[HourPoint] = []

    def flush() -> None:
        if len(run) >= max(criteria.min_duration, 1):
            heights = [p.wave_height or 0.0 for p in run]
            ratings = [p.rating for p in run]
            sessions.append(
                Session(
                    start=run[0].time,
                    end=run[-1].time + timedelta(hours=1),
                    hours=len(run),
                    max_rating=max(ratings),
                    avg_rating=round(sum(ratings) / len(ratings), 1),
                    wave_min=round(min(heights), 2),
                    wave_max=round(max(heights), 2),
                    period_max=round(max((p.wave_period or 0.0) for p in run), 1),
                    wind_max=round(max((p.wind_speed or 0.0) for p in run), 1),
                )
            )
        run.clear()

    for point in hours:
        contiguous = not run or point.time - run[-1].time == timedelta(hours=1)
        if point.match and contiguous:
            run.append(point)
            continue
        flush()
        if point.match:
            run.append(point)
    flush()
    return sessions


def _mean_angle(angles: list[float]) -> float | None:
    if not angles:
        return None
    x = sum(math.cos(math.radians(a)) for a in angles)
    y = sum(math.sin(math.radians(a)) for a in angles)
    if abs(x) < 1e-9 and abs(y) < 1e-9:
        return None
    return round(math.degrees(math.atan2(y, x)) % 360)


def summarize_days(
    hours: list[HourPoint], criteria: SurfCriteria, tz: timezone
) -> list[DaySummary]:
    by_day: dict[date, list[HourPoint]] = {}
    for point in hours:
        by_day.setdefault(point.time.astimezone(tz).date(), []).append(point)

    days = []
    for day, points in sorted(by_day.items()):
        # daytime values are what matters for surfing
        relevant = [p for p in points if p.is_day] or points
        heights = [p.wave_height for p in relevant if p.wave_height is not None]
        periods = [p.wave_period for p in relevant if p.wave_period is not None]
        winds = [p.wind_speed for p in relevant if p.wind_speed is not None]
        temps = [p.water_temperature for p in relevant if p.water_temperature is not None]
        days.append(
            DaySummary(
                day=day,
                wave_min=round(min(heights), 2) if heights else None,
                wave_max=round(max(heights), 2) if heights else None,
                period_max=round(max(periods), 1) if periods else None,
                energy_max=round(max(wave_energy(p) for p in relevant), 2),
                wave_direction=_mean_angle(
                    [p.wave_direction for p in relevant if p.wave_direction is not None]
                ),
                swell_direction=_mean_angle(
                    [p.swell_direction for p in relevant if p.swell_direction is not None]
                ),
                wind_min=round(min(winds), 1) if winds else None,
                wind_max=round(max(winds), 1) if winds else None,
                wind_direction=_mean_angle(
                    [p.wind_direction for p in relevant if p.wind_direction is not None]
                ),
                water_temperature=round(sum(temps) / len(temps), 1) if temps else None,
                max_rating=max((p.rating for p in points), default=0.0),
                good_hours=sum(1 for p in points if p.match),
            )
        )
    return days


def evaluate(hours: list[HourPoint], criteria: SurfCriteria, tz: timezone) -> SurfData:
    for point in hours:
        point.energy = round(wave_energy(point), 2)
        point.match = hour_matches(point, criteria)
        point.rating = rate_hour(point, criteria)
    return SurfData(
        hours=hours,
        sessions=find_sessions(hours, criteria),
        days=summarize_days(hours, criteria, tz),
        tz=tz,
    )


# --------------------------------------------------------------------------- #
# Forecast archive (to compare old forecasts with the actual hour)
# --------------------------------------------------------------------------- #

LEAD_DAYS = (1, 2, 3, 6)


def _hour_key(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0).isoformat()


def record_forecast(
    archive: dict[str, dict[str, float]], hours: list[HourPoint], now: datetime
) -> None:
    """Remember the rating forecast for the hours exactly 1, 2, 3, 6 days ahead.

    Called on every (hourly) update; old entries are dropped. The archive maps
    target hour (UTC ISO) -> {lead days: rating}. The first value recorded for a
    lead is kept.
    """
    by_key = {_hour_key(p.time): p for p in hours}
    current = datetime.fromisoformat(_hour_key(now))
    for lead in LEAD_DAYS:
        key = _hour_key(current + timedelta(days=lead))
        if (point := by_key.get(key)) is not None:
            archive.setdefault(key, {}).setdefault(str(lead), point.rating)
    oldest = current - timedelta(hours=2)
    for key in [k for k in archive if datetime.fromisoformat(k) < oldest]:
        del archive[key]


def predicted_rating(
    archive: dict[str, dict[str, float]], now: datetime, lead: int
) -> float | None:
    """Rating forecast made ``lead`` days ago for the current hour."""
    return archive.get(_hour_key(now), {}).get(str(lead))


COMPASS = ["N", "NNO", "NO", "ONO", "O", "OSO", "SO", "SSO",
           "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]  # fmt: skip


def compass(angle: float | None) -> str | None:
    if angle is None:
        return None
    return COMPASS[int((angle % 360) / 22.5 + 0.5) % 16]


def hour_as_attr(point: HourPoint, tz: timezone) -> dict[str, Any]:
    """Compact representation for state attributes / charts."""
    return {
        "time": point.time.astimezone(tz).isoformat(timespec="minutes"),
        "wave": point.wave_height,
        "period": point.wave_period,
        "swell": point.swell_height,
        "wind": point.wind_speed,
        "wind_dir": point.wind_direction,
        "energy": point.energy,
        "rating": point.rating,
        "match": point.match,
    }
