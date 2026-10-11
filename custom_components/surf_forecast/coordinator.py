"""Data update coordinator: fetches forecast, evaluates it, sends notifications."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import OpenMeteoClient, OpenMeteoError
from .const import (
    CONF_DAYLIGHT_ONLY,
    CONF_GLASSY_MAX,
    CONF_LOCATION,
    CONF_MIN_DURATION,
    CONF_NOTIFY_DAYS,
    CONF_NOTIFY_MIN_RATING,
    CONF_NOTIFY_SERVICE,
    CONF_PERIOD_MIN,
    CONF_SWELL_DIR_FROM,
    CONF_SWELL_DIR_TO,
    CONF_USE_SWELL,
    CONF_WAVE_MAX,
    CONF_WAVE_MIN,
    CONF_WIND_DIR_FROM,
    CONF_WIND_DIR_TO,
    CONF_WIND_MAX,
    CONF_WIND_UNIT,
    DEFAULT_OPTIONS,
    DOMAIN,
    EVENT_SESSION,
    UPDATE_INTERVAL,
    WIND_UNITS,
)
from .surf import Session, SurfCriteria, SurfData, compass, evaluate, parse_responses

_LOGGER = logging.getLogger(__name__)

STORAGE_VERSION = 1

WEEKDAYS = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]

type SurfConfigEntry = ConfigEntry[SurfCoordinator]


def _corridor(options: dict[str, Any], key_from: str, key_to: str) -> tuple[float, float] | None:
    start, end = options.get(key_from, -1), options.get(key_to, -1)
    if start is None or end is None or start < 0 or end < 0:
        return None
    return float(start), float(end)


def windy_url(latitude: float, longitude: float) -> str:
    """Link to Windy's wave layer and point forecast for the spot."""
    lat, lon = f"{latitude:.3f}", f"{longitude:.3f}"
    return f"https://www.windy.com/{lat}/{lon}?waves,{lat},{lon},10"


def criteria_from_options(options: dict[str, Any]) -> SurfCriteria:
    opts = {**DEFAULT_OPTIONS, **options}
    return SurfCriteria(
        wave_min=float(opts[CONF_WAVE_MIN]),
        wave_max=float(opts[CONF_WAVE_MAX]),
        period_min=float(opts[CONF_PERIOD_MIN]),
        wind_max=float(opts[CONF_WIND_MAX]),
        glassy_max=float(opts[CONF_GLASSY_MAX]),
        wind_corridor=_corridor(opts, CONF_WIND_DIR_FROM, CONF_WIND_DIR_TO),
        swell_corridor=_corridor(opts, CONF_SWELL_DIR_FROM, CONF_SWELL_DIR_TO),
        use_swell=bool(opts[CONF_USE_SWELL]),
        daylight_only=bool(opts[CONF_DAYLIGHT_ONLY]),
        min_duration=int(opts[CONF_MIN_DURATION]),
    )


class SurfCoordinator(DataUpdateCoordinator[SurfData]):
    config_entry: SurfConfigEntry

    def __init__(self, hass: HomeAssistant, entry: SurfConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {entry.title}",
            update_interval=UPDATE_INTERVAL,
        )
        self.options: dict[str, Any] = {**DEFAULT_OPTIONS, **entry.options}
        self.criteria = criteria_from_options(self.options)
        self.wind_unit = WIND_UNITS[self.options[CONF_WIND_UNIT]]
        location = entry.data[CONF_LOCATION]
        self.latitude: float = location[CONF_LATITUDE]
        self.longitude: float = location[CONF_LONGITUDE]
        self.spot_name: str = entry.data.get(CONF_NAME, entry.title)
        self.windy_url = windy_url(self.latitude, self.longitude)
        self._client = OpenMeteoClient(async_get_clientsession(hass))
        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}.notified"
        )
        self._notified: dict[str, str] = {}
        self.cards_shown = False

    async def _async_setup(self) -> None:
        stored = await self._store.async_load()
        self._notified = (stored or {}).get("sessions", {})
        self.cards_shown = bool((stored or {}).get("cards_shown"))

    async def _async_update_data(self) -> SurfData:
        try:
            marine, weather = await self._client.fetch(
                self.latitude, self.longitude, self.options[CONF_WIND_UNIT]
            )
        except OpenMeteoError as err:
            raise UpdateFailed(str(err)) from err

        hours, tz = parse_responses(marine, weather)
        data = evaluate(hours, self.criteria, tz)
        await self._handle_notifications(data)
        return data

    async def async_save_state(self) -> None:
        await self._store.async_save(
            {"sessions": self._notified, "cards_shown": self.cards_shown}
        )

    # ------------------------------------------------------------------ #
    # Notifications
    # ------------------------------------------------------------------ #

    def describe_session(self, session: Session, tz) -> str:
        start = session.start.astimezone(tz)
        end = session.end.astimezone(tz)
        day = f"{WEEKDAYS[start.weekday()]} {start:%d.%m.}"
        waves = (
            f"{session.wave_min:g}"
            if session.wave_min == session.wave_max
            else f"{session.wave_min:g}–{session.wave_max:g}"
        )
        return (
            f"{day} {start:%H:%M}–{end:%H:%M} ({session.hours} h): "
            f"{waves} m @ {session.period_max:g} s, "
            f"Wind max {session.wind_max:g} {self.wind_unit}, "
            f"Rating {session.max_rating:g}/5"
        )

    async def _handle_notifications(self, data: SurfData) -> None:
        now = dt_util.utcnow()
        horizon = now + timedelta(days=int(self.options[CONF_NOTIFY_DAYS]))
        min_rating = float(self.options[CONF_NOTIFY_MIN_RATING])

        # forget sessions that are over
        self._notified = {
            k: v for k, v in self._notified.items() if datetime.fromisoformat(v) > now
        }

        known = [
            (datetime.fromisoformat(k), datetime.fromisoformat(v))
            for k, v in self._notified.items()
        ]
        # A session that overlaps an already announced one (e.g. because the
        # forecast shifted by an hour) is not announced again.
        new_sessions = [
            s
            for s in data.upcoming_sessions(now)
            if s.start <= horizon
            and s.max_rating >= min_rating
            and not any(s.start < end and start < s.end for start, end in known)
        ]
        if not new_sessions:
            await self.async_save_state()
            return

        for session in new_sessions:
            self._notified[session.key] = session.end.isoformat()
            first_hour = next((h for h in data.hours if h.time == session.start), None)
            self.hass.bus.async_fire(
                EVENT_SESSION,
                {
                    "entry_id": self.config_entry.entry_id,
                    "spot": self.spot_name,
                    "windy_url": self.windy_url,
                    "description": self.describe_session(session, data.tz),
                    "wind_unit": self.wind_unit,
                    "wind_direction": compass(first_hour.wind_direction) if first_hour else None,
                    "swell_direction": compass(first_hour.swell_direction) if first_hour else None,
                    **session.as_dict(),
                },
            )

        service = (self.options.get(CONF_NOTIFY_SERVICE) or "").strip()
        if service:
            await self._send_notification(service, new_sessions, data)

        await self.async_save_state()

    async def _send_notification(
        self, service: str, sessions: list[Session], data: SurfData
    ) -> None:
        domain, _, name = service.partition(".")
        if not name:
            domain, name = "notify", domain
        lines = [self.describe_session(s, data.tz) for s in sessions]
        payload: dict[str, Any] = {
            "title": f"🏄 Surf-Alarm {self.spot_name}",
            "message": "\n".join(lines),
        }
        if domain == "notify" and name.startswith("mobile_app_"):
            # Companion app: tapping the notification opens Windy
            # (`url` is used by iOS, `clickAction` by Android).
            payload["data"] = {"url": self.windy_url, "clickAction": self.windy_url}
        else:
            payload["message"] += f"\nWindy: {self.windy_url}"
        try:
            await self.hass.services.async_call(domain, name, payload, blocking=False)
        except Exception:  # noqa: BLE001 - never break updates because of notify
            _LOGGER.exception("Could not send surf notification via %s", service)
