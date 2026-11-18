"""Config and options flow for Surf Forecast."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import NoMarineData, OpenMeteoClient, OpenMeteoError
from .const import (
    CONF_CALM_MAX,
    CONF_DAYLIGHT_ONLY,
    CONF_ENERGY_MIN,
    CONF_ENERGY_TOP,
    CONF_LOCATION,
    CONF_MIN_DURATION,
    CONF_NOTIFY_DAYS,
    CONF_NOTIFY_MIN_RATING,
    CONF_NOTIFY_SERVICE,
    CONF_PERIOD_MIN,
    CONF_SEA_LEVEL_MAX,
    CONF_SWELL_BONUS_MIN,
    CONF_WIND_DIR_FROM,
    CONF_WIND_DIR_TO,
    CONF_WIND_MAX,
    CONF_WIND_STRONG,
    CONF_WIND_UNIT,
    DOMAIN,
    WIND_UNITS,
    effective_options,
)


def _number(minimum: float, maximum: float, step: float, unit: str | None = None):
    config = selector.NumberSelectorConfig(
        min=minimum, max=maximum, step=step, mode=selector.NumberSelectorMode.BOX
    )
    if unit:
        config["unit_of_measurement"] = unit
    return selector.NumberSelector(config)


# -1 disables a direction corridor
_DIRECTION = _number(-1, 359, 1, "°")


def options_schema(options: dict[str, Any]) -> vol.Schema:
    o = effective_options(options)
    unit = WIND_UNITS[o[CONF_WIND_UNIT]]
    return vol.Schema(
        {
            vol.Required(CONF_WIND_UNIT, default=o[CONF_WIND_UNIT]): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=list(WIND_UNITS),
                    translation_key=CONF_WIND_UNIT,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Required(CONF_ENERGY_MIN, default=o[CONF_ENERGY_MIN]): _number(
                0.05, 20, 0.05, "kW/m"
            ),
            vol.Required(CONF_ENERGY_TOP, default=o[CONF_ENERGY_TOP]): _number(
                0.1, 50, 0.1, "kW/m"
            ),
            vol.Required(CONF_PERIOD_MIN, default=o[CONF_PERIOD_MIN]): _number(0, 25, 0.5, "s"),
            vol.Required(CONF_WIND_DIR_FROM, default=o[CONF_WIND_DIR_FROM]): _DIRECTION,
            vol.Required(CONF_WIND_DIR_TO, default=o[CONF_WIND_DIR_TO]): _DIRECTION,
            vol.Required(CONF_WIND_MAX, default=o[CONF_WIND_MAX]): _number(0, 200, 1, unit),
            vol.Required(CONF_WIND_STRONG, default=o[CONF_WIND_STRONG]): _number(0, 200, 1, unit),
            vol.Required(CONF_CALM_MAX, default=o[CONF_CALM_MAX]): _number(0, 100, 1, unit),
            vol.Required(CONF_SWELL_BONUS_MIN, default=o[CONF_SWELL_BONUS_MIN]): _number(
                0, 5, 0.05, "m"
            ),
            vol.Required(CONF_SEA_LEVEL_MAX, default=o[CONF_SEA_LEVEL_MAX]): _number(
                -1, 5, 0.05, "m"
            ),
            vol.Required(CONF_MIN_DURATION, default=o[CONF_MIN_DURATION]): _number(1, 12, 1, "h"),
            vol.Required(
                CONF_DAYLIGHT_ONLY, default=o[CONF_DAYLIGHT_ONLY]
            ): selector.BooleanSelector(),
            vol.Optional(
                CONF_NOTIFY_SERVICE,
                description={"suggested_value": o[CONF_NOTIFY_SERVICE]},
            ): selector.TextSelector(),
            vol.Required(CONF_NOTIFY_DAYS, default=o[CONF_NOTIFY_DAYS]): _number(1, 7, 1, "d"),
            vol.Required(
                CONF_NOTIFY_MIN_RATING, default=o[CONF_NOTIFY_MIN_RATING]
            ): _number(0, 5, 0.5),
        }
    )


def validate_options(user_input: dict[str, Any]) -> dict[str, str]:
    errors: dict[str, str] = {}
    if user_input[CONF_ENERGY_MIN] >= user_input[CONF_ENERGY_TOP]:
        errors[CONF_ENERGY_TOP] = "energy_range"
    if (user_input[CONF_WIND_DIR_FROM] < 0) != (user_input[CONF_WIND_DIR_TO] < 0):
        errors[CONF_WIND_DIR_TO] = "corridor_incomplete"
    service = (user_input.get(CONF_NOTIFY_SERVICE) or "").strip()
    if service and not service.startswith("notify."):
        errors[CONF_NOTIFY_SERVICE] = "notify_service"
    return errors


def _clean(user_input: dict[str, Any]) -> dict[str, Any]:
    data = dict(user_input)
    data[CONF_NOTIFY_SERVICE] = (data.get(CONF_NOTIFY_SERVICE) or "").strip()
    for key in (CONF_MIN_DURATION, CONF_NOTIFY_DAYS, CONF_WIND_DIR_FROM, CONF_WIND_DIR_TO):
        data[key] = int(data[key])
    return data


class SurfForecastConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1
    MINOR_VERSION = 2

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            location = user_input[CONF_LOCATION]
            lat, lon = location[CONF_LATITUDE], location[CONF_LONGITUDE]
            await self.async_set_unique_id(f"{lat:.3f}_{lon:.3f}")
            self._abort_if_unique_id_configured()
            client = OpenMeteoClient(async_get_clientsession(self.hass))
            try:
                await client.fetch(lat, lon, "kn")
            except NoMarineData:
                errors[CONF_LOCATION] = "no_marine_data"
            except OpenMeteoError:
                errors["base"] = "cannot_connect"
            else:
                self._data = {
                    CONF_NAME: user_input[CONF_NAME],
                    CONF_LOCATION: {CONF_LATITUDE: lat, CONF_LONGITUDE: lon},
                }
                return await self.async_step_conditions()

        default_location = {
            CONF_LATITUDE: self.hass.config.latitude,
            CONF_LONGITUDE: self.hass.config.longitude,
        }
        schema = vol.Schema(
            {
                vol.Required(CONF_NAME): selector.TextSelector(),
                vol.Required(CONF_LOCATION, default=default_location): selector.LocationSelector(
                    selector.LocationSelectorConfig(radius=False)
                ),
            }
        )
        if user_input is not None:
            schema = self.add_suggested_values_to_schema(schema, user_input)
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_conditions(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = validate_options(user_input)
            if not errors:
                return self.async_create_entry(
                    title=self._data[CONF_NAME], data=self._data, options=_clean(user_input)
                )
        return self.async_show_form(
            step_id="conditions",
            data_schema=options_schema(user_input or {}),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry) -> SurfForecastOptionsFlow:
        return SurfForecastOptionsFlow()


class SurfForecastOptionsFlow(OptionsFlow):
    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = validate_options(user_input)
            if not errors:
                return self.async_create_entry(data=_clean(user_input))
        return self.async_show_form(
            step_id="init",
            data_schema=options_schema(user_input or dict(self.config_entry.options)),
            errors=errors,
        )
