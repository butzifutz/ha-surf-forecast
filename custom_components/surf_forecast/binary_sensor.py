"""Binary sensors for Surf Forecast."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import SurfConfigEntry, SurfCoordinator
from .entity import SurfEntity

# removed in 0.4.0: duplicated "next session"
_REMOVED = ("session_upcoming",)


async def async_setup_entry(
    hass: HomeAssistant, entry: SurfConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    registry = er.async_get(hass)
    for key in _REMOVED:
        if entity_id := registry.async_get_entity_id(
            "binary_sensor", DOMAIN, f"{entry.entry_id}_{key}"
        ):
            registry.async_remove(entity_id)
    async_add_entities([SurfableNowSensor(entry.runtime_data)])


class SurfableNowSensor(SurfEntity, BinarySensorEntity):
    """On while the current hour matches the configured conditions."""

    _attr_icon = "mdi:surfing"

    def __init__(self, coordinator: SurfCoordinator) -> None:
        super().__init__(coordinator, "surfable_now")

    @property
    def is_on(self) -> bool:
        hour = self.coordinator.data.current_hour(dt_util.utcnow())
        return bool(hour and hour.match)
