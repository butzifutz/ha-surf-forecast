"""Button that shows the ready-to-paste dashboard cards."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import SurfConfigEntry, SurfCoordinator
from .dashboard import show_cards_notification
from .entity import SurfEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: SurfConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities([DashboardCardsButton(entry.runtime_data)])


class DashboardCardsButton(SurfEntity, ButtonEntity):
    _attr_icon = "mdi:view-dashboard-edit"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: SurfCoordinator) -> None:
        super().__init__(coordinator, "dashboard_cards")

    async def async_press(self) -> None:
        show_cards_notification(self.hass, self.coordinator.config_entry)
