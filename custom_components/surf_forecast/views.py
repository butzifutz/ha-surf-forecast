"""HTTP view serving the compass background image per spot."""

from __future__ import annotations

from aiohttp import web

from homeassistant.components.http import HomeAssistantView
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.util import slugify

from .compass import compass_svg
from .const import DOMAIN

COMPASS_URL = f"/api/{DOMAIN}/compass/{{key}}.svg"


def compass_url(key: str) -> str:
    return COMPASS_URL.format(key=key)


class CompassImageView(HomeAssistantView):
    """Serve the SVG with the configured wind/swell corridors.

    The image is loaded by the browser via <img>, which can't send the auth
    header, so the view is public. It only contains the corridor geometry.
    """

    url = COMPASS_URL
    name = f"api:{DOMAIN}:compass"
    requires_auth = False

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def get(self, request: web.Request, key: str) -> web.Response:
        for entry in self.hass.config_entries.async_entries(DOMAIN):
            if entry.state is ConfigEntryState.LOADED and key in (
                entry.entry_id,
                slugify(entry.title),
            ):
                criteria = entry.runtime_data.criteria
                svg = compass_svg(criteria.wind_corridor, criteria.swell_corridor)
                return web.Response(
                    text=svg,
                    content_type="image/svg+xml",
                    headers={"Cache-Control": "no-cache"},
                )
        return web.Response(status=404)
