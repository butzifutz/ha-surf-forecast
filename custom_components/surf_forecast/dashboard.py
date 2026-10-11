"""Dashboard card YAML: notification after setup, button and action."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components import persistent_notification
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er
from homeassistant.util import slugify

from .cards import CardContext, all_cards, notification_markdown
from .const import DOMAIN
from .coordinator import SurfConfigEntry
from .views import compass_url

SERVICE_DASHBOARD_CARDS = "dashboard_cards"
ATTR_CONFIG_ENTRY_ID = "config_entry_id"

SERVICE_SCHEMA = vol.Schema({vol.Optional(ATTR_CONFIG_ENTRY_ID): cv.string})


def card_context(hass: HomeAssistant, entry: SurfConfigEntry) -> CardContext:
    registry = er.async_get(hass)

    def entity_id(platform: str, key: str) -> str:
        found = registry.async_get_entity_id(platform, DOMAIN, f"{entry.entry_id}_{key}")
        # fall back to the English default if the registry entry is missing
        return found or f"{platform}.{slugify(entry.title)}_{key}"

    coordinator = entry.runtime_data
    return CardContext(
        title=coordinator.spot_name,
        wind_direction=entity_id("sensor", "wind_direction"),
        swell_direction=entity_id("sensor", "swell_direction"),
        wind_speed=entity_id("sensor", "wind_speed"),
        swell_height=entity_id("sensor", "swell_height"),
        forecast=entity_id("sensor", "forecast"),
        next_session=entity_id("sensor", "next_session"),
        compass_image=compass_url(entry.entry_id),
        windy_url=coordinator.windy_url,
    )


def show_cards_notification(hass: HomeAssistant, entry: SurfConfigEntry) -> None:
    persistent_notification.async_create(
        hass,
        notification_markdown(card_context(hass, entry)),
        title=f"🏄 Dashboard-Karten: {entry.runtime_data.spot_name}",
        notification_id=f"{DOMAIN}_cards_{entry.entry_id}",
    )


def async_register_services(hass: HomeAssistant) -> None:
    async def handle(call: ServiceCall) -> ServiceResponse:
        entries: list[SurfConfigEntry] = [
            e
            for e in hass.config_entries.async_entries(DOMAIN)
            if e.state is ConfigEntryState.LOADED
        ]
        wanted = call.data.get(ATTR_CONFIG_ENTRY_ID)
        if wanted:
            entries = [e for e in entries if e.entry_id == wanted]
            if not entries:
                raise ServiceValidationError(
                    translation_domain=DOMAIN, translation_key="unknown_entry"
                )
        result: dict[str, Any] = {}
        for entry in entries:
            if not call.return_response:
                show_cards_notification(hass, entry)
            result[entry.entry_id] = {
                "spot": entry.runtime_data.spot_name,
                **all_cards(card_context(hass, entry)),
            }
        return {"spots": result} if call.return_response else None

    hass.services.async_register(
        DOMAIN,
        SERVICE_DASHBOARD_CARDS,
        handle,
        schema=SERVICE_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
