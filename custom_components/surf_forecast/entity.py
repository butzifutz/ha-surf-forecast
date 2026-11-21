"""Base entity for Surf Forecast."""

from __future__ import annotations

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.event import async_track_state_change_event, async_track_time_change
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SurfCoordinator


class SurfEntity(CoordinatorEntity[SurfCoordinator]):
    _attr_has_entity_name = True
    # set by entities that use the measured wind of the station
    _follows_station = False
    _attr_attribution = "Daten: Open-Meteo.com (CC BY 4.0)"

    def __init__(self, coordinator: SurfCoordinator, key: str) -> None:
        super().__init__(coordinator)
        entry = coordinator.config_entry
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_translation_key = key
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=coordinator.spot_name,
            manufacturer="Open-Meteo",
            model="Marine + Wetter Forecast",
            entry_type=DeviceEntryType.SERVICE,
        )

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        # The forecast is hourly; re-evaluate "current hour" values at every
        # full hour even if no new data was fetched in between.
        self.async_on_remove(
            async_track_time_change(self.hass, self._on_hour, minute=0, second=5)
        )
        if self._follows_station and self.coordinator.wind_station:
            # measured values: update as soon as the station reports
            self.async_on_remove(
                async_track_state_change_event(
                    self.hass, [self.coordinator.wind_station], self._on_hour
                )
            )

    @callback
    def _on_hour(self, _now) -> None:
        self.async_write_ha_state()
