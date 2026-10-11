"""Binary sensors for Surf Forecast."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import CONF_NOTIFY_DAYS
from .coordinator import SurfConfigEntry, SurfCoordinator
from .entity import SurfEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: SurfConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    async_add_entities([SurfableNowSensor(coordinator), SessionUpcomingSensor(coordinator)])


class SurfableNowSensor(SurfEntity, BinarySensorEntity):
    """On while the current hour matches the configured conditions."""

    _attr_icon = "mdi:surfing"

    def __init__(self, coordinator: SurfCoordinator) -> None:
        super().__init__(coordinator, "surfable_now")

    @property
    def is_on(self) -> bool:
        hour = self.coordinator.data.current_hour(dt_util.utcnow())
        return bool(hour and hour.match)


class SessionUpcomingSensor(SurfEntity, BinarySensorEntity):
    """On when a matching session starts within the notification horizon."""

    _attr_icon = "mdi:calendar-alert"

    def __init__(self, coordinator: SurfCoordinator) -> None:
        super().__init__(coordinator, "session_upcoming")

    def _sessions(self):
        now = dt_util.utcnow()
        horizon = now + timedelta(days=int(self.coordinator.options[CONF_NOTIFY_DAYS]))
        return [s for s in self.coordinator.data.upcoming_sessions(now) if s.start <= horizon]

    @property
    def is_on(self) -> bool:
        return bool(self._sessions())

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        tz = self.coordinator.data.tz
        return {
            "count": len(sessions := self._sessions()),
            "sessions": [self.coordinator.describe_session(s, tz) for s in sessions],
        }
