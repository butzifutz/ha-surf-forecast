"""Surf Forecast integration for Home Assistant (data: Open-Meteo)."""

from __future__ import annotations

import logging

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import CONF_PERIOD_MIN, DOMAIN
from .coordinator import SurfConfigEntry, SurfCoordinator
from .dashboard import async_register_services, show_cards_notification
from .views import CompassImageView

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.BUTTON]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

_LOGGER = logging.getLogger(__name__)

# options of versions <= 0.4 that the energy based rating (0.5) replaced
_OBSOLETE_OPTIONS = (
    "wave_min",
    "wave_max",
    "use_swell",
    "wind_min",
    "swell_dir_from",
    "swell_dir_to",
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    hass.http.register_view(CompassImageView(hass))
    async_register_services(hass)
    return True


async def async_migrate_entry(hass: HomeAssistant, entry: SurfConfigEntry) -> bool:
    if entry.version == 1 and entry.minor_version < 2:
        # 0.5: the period is only a guard against short chop now; the wave
        # energy already rates it. Higher old values would hide small days.
        options = {k: v for k, v in entry.options.items() if k not in _OBSOLETE_OPTIONS}
        if CONF_PERIOD_MIN in options:
            options[CONF_PERIOD_MIN] = min(float(options[CONF_PERIOD_MIN]), 3.0)
        hass.config_entries.async_update_entry(entry, options=options, minor_version=2)
        _LOGGER.info("Migrated %s to the energy based rating (0.5)", entry.title)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: SurfConfigEntry) -> bool:
    coordinator = SurfCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Once per spot: offer ready-to-paste dashboard cards with the real entity IDs.
    if not coordinator.cards_shown:
        show_cards_notification(hass, entry)
        coordinator.cards_shown = True
        await coordinator.async_save_state()
    return True


async def async_unload_entry(hass: HomeAssistant, entry: SurfConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_reload(hass: HomeAssistant, entry: SurfConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
