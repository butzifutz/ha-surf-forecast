"""Pure surf logic: parse Open-Meteo responses, rate hours, find sessions.

This module deliberately has no Home Assistant imports so it can be unit-tested
on its own.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta, timezone
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
    match: bool = False
    rating: float = 0.0


@dataclass(slots=True)
class SurfCriteria:
    """User-defined conditions for a surfable hour.

    Corridors are given as (from, to) in degrees, clockwise, and may wrap
    around north (e.g. 300 -> 60). ``None`` means "any direction".
    """

    wave_min: float = 0.8
    wave_max: float = 2.5
    period_min: float = 7.0
    wind_max: float = 15.0
    wind_corridor: tuple[float, float] | None = None
    # below this speed the wind direction doesn't matter (glassy conditions)
    glassy_max: float = 5.0
    swell_corridor: tuple[float, float] | None = None
    use_swell: bool = False
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


def _height(point: HourPoint, criteria: SurfCriteria) -> float | None:
    if criteria.use_swell and point.swell_height is not None:
        return point.swell_height
    return point.wave_height


def _period(point: HourPoint, criteria: SurfCriteria) -> float | None:
    if criteria.use_swell and point.swell_period is not None:
        return point.swell_period
    return point.wave_period


def _direction(point: HourPoint) -> float | None:
    return point.swell_direction if point.swell_direction is not None else point.wave_direction


def wind_ok(point: HourPoint, criteria: SurfCriteria) -> bool:
    if point.wind_speed is None:
        return True  # no wind data -> don't block
    if point.wind_speed > criteria.wind_max:
        return False
    if point.wind_speed <= criteria.glassy_max:
        return True
    return in_corridor(point.wind_direction, criteria.wind_corridor)


def rate_hour(point: HourPoint, criteria: SurfCriteria) -> float:
    """Return a 0..5 rating for one hour (0 = flat/blown out, 5 = epic)."""
    height = _height(point, criteria)
    if height is None or height < criteria.wave_min * 0.5:
        return 0.0

    # waves: 0..2 points, best in the middle of the configured corridor
    if criteria.wave_min <= height <= criteria.wave_max:
        span = max(criteria.wave_max - criteria.wave_min, 0.01)
        centre = criteria.wave_min + span / 2
        wave_score = 2.0 - abs(height - centre) / (span / 2) * 0.5
    elif height < criteria.wave_min:
        wave_score = height / criteria.wave_min
    else:
        wave_score = max(0.0, 1.5 - (height - criteria.wave_max) / max(criteria.wave_max, 0.1))

    # period: 0..1.5 points
    period = _period(point, criteria) or 0.0
    if criteria.period_min > 0:
        period_score = min(1.5, max(0.0, period / criteria.period_min) * 1.0)
        if period >= criteria.period_min * 1.4:
            period_score = 1.5
    else:
        period_score = 1.5

    # wind: 0..1.5 points
    speed = point.wind_speed
    if speed is None:
        wind_score = 0.75
    elif speed <= criteria.glassy_max:
        wind_score = 1.5
    elif in_corridor(point.wind_direction, criteria.wind_corridor) and speed <= criteria.wind_max:
        wind_score = 1.5 - 0.5 * (speed - criteria.glassy_max) / max(
            criteria.wind_max - criteria.glassy_max, 0.1
        )
    elif speed <= criteria.wind_max:
        wind_score = 0.5
    else:
        wind_score = max(0.0, 0.5 - (speed - criteria.wind_max) / max(criteria.wind_max, 0.1))

    return round(max(0.0, min(5.0, wave_score + period_score + wind_score)), 1)


def hour_matches(point: HourPoint, criteria: SurfCriteria) -> bool:
    if criteria.daylight_only and not point.is_day:
        return False
    height = _height(point, criteria)
    if height is None or not criteria.wave_min <= height <= criteria.wave_max:
        return False
    period = _period(point, criteria)
    if criteria.period_min > 0 and (period is None or period < criteria.period_min):
        return False
    if criteria.swell_corridor is not None and not in_corridor(
        _direction(point), criteria.swell_corridor
    ):
        return False
    return wind_ok(point, criteria)


def find_sessions(hours: list[HourPoint], criteria: SurfCriteria) -> list[Session]:
    sessions: list[Session] = []
    run: list[HourPoint] = []

    def flush() -> None:
        if len(run) >= max(criteria.min_duration, 1):
            heights = [_height(p, criteria) or 0.0 for p in run]
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
                    period_max=round(max((_period(p, criteria) or 0.0) for p in run), 1),
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
    import math

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
        heights = [h for p in relevant if (h := _height(p, criteria)) is not None]
        periods = [v for p in relevant if (v := _period(p, criteria)) is not None]
        winds = [p.wind_speed for p in relevant if p.wind_speed is not None]
        temps = [p.water_temperature for p in relevant if p.water_temperature is not None]
        days.append(
            DaySummary(
                day=day,
                wave_min=round(min(heights), 2) if heights else None,
                wave_max=round(max(heights), 2) if heights else None,
                period_max=round(max(periods), 1) if periods else None,
                swell_direction=_mean_angle(
                    [d for p in relevant if (d := _direction(p)) is not None]
                ),
                wind_min=round(min(winds), 1) if winds else None,
                wind_max=round(max(winds), 1) if winds else None,
                wind_direction=_mean_angle(
                    [p.wind_direction for p in relevant if p.wind_direction is not None]
                ),
                water_temperature=round(sum(temps) / len(temps), 1) if temps else None,
                max_rating=max((p.rating for p in relevant), default=0.0),
                good_hours=sum(1 for p in points if p.match),
            )
        )
    return days


def evaluate(hours: list[HourPoint], criteria: SurfCriteria, tz: timezone) -> SurfData:
    for point in hours:
        point.rating = rate_hour(point, criteria)
        point.match = hour_matches(point, criteria)
    return SurfData(
        hours=hours,
        sessions=find_sessions(hours, criteria),
        days=summarize_days(hours, criteria, tz),
        tz=tz,
    )


COMPASS = ["N", "NNO", "NO", "ONO", "O", "OSO", "SO", "SSO",
           "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]  # fmt: skip


def compass(angle: float | None) -> str | None:
    if angle is None:
        return None
    return COMPASS[int((angle % 360) / 22.5 + 0.5) % 16]


def hour_as_attr(point: HourPoint, tz: timezone) -> dict[str, Any]:
    """Compact representation for state attributes / charts."""
    return {
        "time": point.time.astimezone(tz).isoformat(),
        "wave": point.wave_height,
        "period": point.wave_period,
        "swell": point.swell_height,
        "swell_period": point.swell_period,
        "swell_dir": point.swell_direction,
        "wind": point.wind_speed,
        "gusts": point.wind_gusts,
        "wind_dir": point.wind_direction,
        "tide": point.sea_level,
        "rating": point.rating,
        "match": point.match,
    }
