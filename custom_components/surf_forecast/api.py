"""Small async client for the Open-Meteo marine and weather APIs."""

from __future__ import annotations

import asyncio
from typing import Any

import aiohttp

from .const import FORECAST_DAYS, MARINE_URL, WEATHER_URL
from .surf import MARINE_FIELDS, WEATHER_FIELDS

# sea_level_height_msl (tide) is not available everywhere; retry without it.
OPTIONAL_MARINE_FIELDS = {"sea_level_height_msl", "sea_surface_temperature"}


class OpenMeteoError(Exception):
    """Raised when Open-Meteo cannot be reached or returns an error."""


class NoMarineData(OpenMeteoError):
    """Raised when the location has no marine data (e.g. inland)."""


class OpenMeteoClient:
    def __init__(self, session: aiohttp.ClientSession) -> None:
        self._session = session

    async def _get(self, url: str, params: dict[str, Any]) -> dict[str, Any]:
        try:
            async with asyncio.timeout(30):
                resp = await self._session.get(url, params=params)
                data = await resp.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError, ValueError) as err:
            raise OpenMeteoError(f"Request to {url} failed: {err}") from err
        if resp.status != 200 or data.get("error"):
            raise OpenMeteoError(data.get("reason") or f"HTTP {resp.status}")
        return data

    async def fetch(
        self, latitude: float, longitude: float, wind_unit: str
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Return (marine, weather) raw responses."""
        common = {
            "latitude": round(latitude, 4),
            "longitude": round(longitude, 4),
            "timezone": "auto",
            "timeformat": "unixtime",
            "forecast_days": FORECAST_DAYS,
        }
        marine_params = {**common, "hourly": ",".join(MARINE_FIELDS)}
        weather_params = {
            **common,
            "hourly": ",".join(WEATHER_FIELDS),
            "wind_speed_unit": wind_unit,
        }

        marine_task = self._fetch_marine(marine_params)
        weather_task = self._get(WEATHER_URL, weather_params)
        marine, weather = await asyncio.gather(marine_task, weather_task)

        heights = (marine.get("hourly") or {}).get("wave_height") or []
        if not any(h is not None for h in heights):
            raise NoMarineData("No wave data for this location")
        return marine, weather

    async def _fetch_marine(self, params: dict[str, Any]) -> dict[str, Any]:
        try:
            return await self._get(MARINE_URL, params)
        except OpenMeteoError:
            reduced = [f for f in MARINE_FIELDS if f not in OPTIONAL_MARINE_FIELDS]
            return await self._get(MARINE_URL, {**params, "hourly": ",".join(reduced)})
