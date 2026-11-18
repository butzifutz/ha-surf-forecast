"""Sensors for Surf Forecast."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import DEGREE, UnitOfLength, UnitOfSpeed, UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import DOMAIN, FORECAST_DAYS
from .coordinator import SurfConfigEntry, SurfCoordinator
from .entity import SurfEntity
from .surf import (
    LEAD_DAYS,
    HourPoint,
    Session,
    SurfCriteria,
    compass,
    hour_as_attr,
    in_corridor,
    predicted_rating,
)
from .views import compass_url

SPEED_UNITS = {"kn": UnitOfSpeed.KNOTS, "km/h": UnitOfSpeed.KILOMETERS_PER_HOUR,
               "m/s": UnitOfSpeed.METERS_PER_SECOND}  # fmt: skip


@dataclass(frozen=True, kw_only=True)
class HourSensorDescription(SensorEntityDescription):
    value_fn: Callable[[HourPoint], float | None]
    compass_fn: Callable[[HourPoint], float | None] | None = None
    corridor_fn: Callable[[SurfCriteria], tuple[float, float] | None] | None = None


HOUR_SENSORS: tuple[HourSensorDescription, ...] = (
    HourSensorDescription(
        key="wave_height",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.METERS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        icon="mdi:waves",
        value_fn=lambda h: h.wave_height,
    ),
    HourSensorDescription(
        key="wave_period",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        icon="mdi:timer-outline",
        value_fn=lambda h: h.wave_period,
    ),
    HourSensorDescription(
        key="wave_direction",
        native_unit_of_measurement=DEGREE,
        icon="mdi:compass-outline",
        value_fn=lambda h: h.wave_direction,
        compass_fn=lambda h: h.wave_direction,
    ),
    HourSensorDescription(
        key="swell_height",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.METERS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        icon="mdi:waves-arrow-up",
        value_fn=lambda h: h.swell_height,
    ),
    HourSensorDescription(
        key="swell_period",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        icon="mdi:timer-outline",
        value_fn=lambda h: h.swell_period,
    ),
    HourSensorDescription(
        key="swell_direction",
        native_unit_of_measurement=DEGREE,
        icon="mdi:compass-outline",
        value_fn=lambda h: h.swell_direction,
        compass_fn=lambda h: h.swell_direction,
    ),
    HourSensorDescription(
        key="wind_speed",
        device_class=SensorDeviceClass.WIND_SPEED,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda h: h.wind_speed,
    ),
    HourSensorDescription(
        key="wind_gusts",
        device_class=SensorDeviceClass.WIND_SPEED,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda h: h.wind_gusts,
    ),
    HourSensorDescription(
        key="wind_direction",
        native_unit_of_measurement=DEGREE,
        icon="mdi:weather-windy",
        value_fn=lambda h: h.wind_direction,
        compass_fn=lambda h: h.wind_direction,
        corridor_fn=lambda c: c.wind_corridor,
    ),
    HourSensorDescription(
        key="water_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        icon="mdi:coolant-temperature",
        value_fn=lambda h: h.water_temperature,
    ),
    HourSensorDescription(
        key="tide",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.METERS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        icon="mdi:wave",
        value_fn=lambda h: h.sea_level,
    ),
    HourSensorDescription(
        key="energy",
        native_unit_of_measurement="kW/m",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        icon="mdi:lightning-bolt-outline",
        value_fn=lambda h: h.energy,
    ),
    HourSensorDescription(
        key="rating",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:surfing",
        value_fn=lambda h: h.rating,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: SurfConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    entities: list[SensorEntity] = [
        CurrentHourSensor(coordinator, desc) for desc in HOUR_SENSORS
    ]
    entities += [NextSessionSensor(coordinator), ForecastSensor(coordinator)]
    entities += [NextSessionRatingSensor(coordinator), BestSessionSensor(coordinator)]
    entities += [LeadRatingSensor(coordinator, lead) for lead in LEAD_DAYS]

    # removed in 0.5.1: best rating per day (replaced by the lead sensors)
    registry = er.async_get(hass)
    for offset in range(FORECAST_DAYS):
        if entity_id := registry.async_get_entity_id(
            "sensor", DOMAIN, f"{entry.entry_id}_rating_day_{offset}"
        ):
            registry.async_remove(entity_id)
    async_add_entities(entities)


class CurrentHourSensor(SurfEntity, SensorEntity):
    """Value of the current forecast hour."""

    entity_description: HourSensorDescription

    def __init__(self, coordinator: SurfCoordinator, description: HourSensorDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description
        if description.device_class == SensorDeviceClass.WIND_SPEED:
            self._attr_native_unit_of_measurement = SPEED_UNITS[coordinator.wind_unit]

    @property
    def _hour(self) -> HourPoint | None:
        return self.coordinator.data.current_hour(dt_util.utcnow())

    @property
    def available(self) -> bool:
        return super().available and self._hour is not None and self.native_value is not None

    @property
    def native_value(self) -> float | None:
        hour = self._hour
        return None if hour is None else self.entity_description.value_fn(hour)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        hour = self._hour
        desc = self.entity_description
        if hour is None or desc.compass_fn is None:
            return None
        angle = desc.compass_fn(hour)
        attrs: dict[str, Any] = {"compass": compass(angle)}
        if desc.corridor_fn is not None:
            # 1/0 instead of bool so compass-card's dynamic_style can use it
            corridor = desc.corridor_fn(self.coordinator.criteria)
            attrs["in_corridor"] = int(in_corridor(angle, corridor))
            attrs["compass_image"] = compass_url(self.coordinator.config_entry.entry_id)
        return attrs


class NextSessionSensor(SurfEntity, SensorEntity):
    """Start of the next session that matches the configured conditions."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:calendar-star"
    _unrecorded_attributes = frozenset({"sessions"})

    def __init__(self, coordinator: SurfCoordinator) -> None:
        super().__init__(coordinator, "next_session")

    @property
    def native_value(self) -> datetime | None:
        sessions = self.coordinator.data.upcoming_sessions(dt_util.utcnow())
        return sessions[0].start if sessions else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self.coordinator.data
        sessions = data.upcoming_sessions(dt_util.utcnow())
        attrs: dict[str, Any] = {
            "windy_url": self.coordinator.windy_url,
            "sessions": [
                {**s.as_dict(), "text": self.coordinator.describe_session(s, data.tz)}
                for s in sessions
            ]
        }
        if sessions:
            first = sessions[0]
            attrs.update(
                end=first.end.isoformat(),
                hours=first.hours,
                max_rating=first.max_rating,
                text=self.coordinator.describe_session(first, data.tz),
            )
        return attrs


class ForecastSensor(SurfEntity, SensorEntity):
    """7-day forecast. State = best rating of today, attributes hold the data."""

    _attr_icon = "mdi:calendar-week"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _unrecorded_attributes = frozenset({"daily", "hourly"})

    def __init__(self, coordinator: SurfCoordinator) -> None:
        super().__init__(coordinator, "forecast")

    @property
    def native_value(self) -> float | None:
        data = self.coordinator.data
        today = dt_util.utcnow().astimezone(data.tz).date()
        day = next((d for d in data.days if d.day == today), None)
        return day.max_rating if day else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self.coordinator.data
        return {
            "wind_unit": self.coordinator.wind_unit,
            "windy_url": self.coordinator.windy_url,
            "daily": [
                {
                    **d.as_dict(),
                    "wave_compass": compass(d.wave_direction),
                    "swell_compass": compass(d.swell_direction),
                    "wind_compass": compass(d.wind_direction),
                }
                for d in data.days
            ],
            "hourly": [hour_as_attr(h, data.tz) for h in data.hours],
        }



def _session_attrs(coordinator: SurfCoordinator, session: Session | None) -> dict[str, Any]:
    if session is None:
        return {}
    return {
        "start": session.start.isoformat(),
        "end": session.end.isoformat(),
        "hours": session.hours,
        "max_rating": session.max_rating,
        "text": coordinator.describe_session(session, coordinator.data.tz),
    }


class NextSessionRatingSensor(SurfEntity, SensorEntity):
    """Best rating within the next session (0 = no session in sight)."""

    _attr_icon = "mdi:star-circle-outline"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: SurfCoordinator) -> None:
        super().__init__(coordinator, "next_session_rating")

    def _session(self) -> Session | None:
        sessions = self.coordinator.data.upcoming_sessions(dt_util.utcnow())
        return sessions[0] if sessions else None

    @property
    def native_value(self) -> float:
        session = self._session()
        return session.max_rating if session else 0.0

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return _session_attrs(self.coordinator, self._session())


class BestSessionSensor(SurfEntity, SensorEntity):
    """Start of the session with the highest rating in the next 7 days."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:trophy-outline"

    def __init__(self, coordinator: SurfCoordinator) -> None:
        super().__init__(coordinator, "best_session")

    def _session(self) -> Session | None:
        sessions = self.coordinator.data.upcoming_sessions(dt_util.utcnow())
        # highest rating; on a tie the earlier one
        return max(sessions, key=lambda s: s.max_rating, default=None)

    @property
    def native_value(self) -> datetime | None:
        session = self._session()
        return session.start if session else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return _session_attrs(self.coordinator, self._session())


class LeadRatingSensor(SurfEntity, SensorEntity):
    """Rating forecast made ``lead`` days ago for the current hour.

    Same time axis as the surf rating sensor, so the history shows directly
    how far off forecasts with 1, 2, 3, 6 days lead time were.
    """

    _attr_icon = "mdi:crystal-ball"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: SurfCoordinator, lead: int) -> None:
        super().__init__(coordinator, f"rating_lead_{lead}")
        self._lead = lead

    @property
    def native_value(self) -> float | None:
        return predicted_rating(self.coordinator.forecast_archive, dt_util.utcnow(), self._lead)
