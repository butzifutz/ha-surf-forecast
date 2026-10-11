"""Constants for the Surf Forecast integration."""

from __future__ import annotations

from datetime import timedelta

DOMAIN = "surf_forecast"

MARINE_URL = "https://marine-api.open-meteo.com/v1/marine"
WEATHER_URL = "https://api.open-meteo.com/v1/forecast"

UPDATE_INTERVAL = timedelta(hours=1)
FORECAST_DAYS = 7

EVENT_SESSION = f"{DOMAIN}_session"

# config entry data
CONF_LOCATION = "location"

# options
CONF_WIND_UNIT = "wind_unit"
CONF_WAVE_MIN = "wave_min"
CONF_WAVE_MAX = "wave_max"
CONF_PERIOD_MIN = "period_min"
CONF_USE_SWELL = "use_swell"
CONF_WIND_MAX = "wind_max"
CONF_GLASSY_MAX = "glassy_max"
CONF_WIND_DIR_FROM = "wind_dir_from"
CONF_WIND_DIR_TO = "wind_dir_to"
CONF_SWELL_DIR_FROM = "swell_dir_from"
CONF_SWELL_DIR_TO = "swell_dir_to"
CONF_MIN_DURATION = "min_duration"
CONF_DAYLIGHT_ONLY = "daylight_only"
CONF_NOTIFY_SERVICE = "notify_service"
CONF_NOTIFY_DAYS = "notify_days"
CONF_NOTIFY_MIN_RATING = "notify_min_rating"

# Open-Meteo "wind_speed_unit" values
WIND_UNITS = {"kn": "kn", "kmh": "km/h", "ms": "m/s"}

DEFAULT_OPTIONS = {
    CONF_WIND_UNIT: "kn",
    CONF_WAVE_MIN: 0.8,
    CONF_WAVE_MAX: 2.5,
    CONF_PERIOD_MIN: 7.0,
    CONF_USE_SWELL: False,
    CONF_WIND_MAX: 15.0,
    CONF_GLASSY_MAX: 5.0,
    # -1 = corridor disabled (any direction)
    CONF_WIND_DIR_FROM: -1,
    CONF_WIND_DIR_TO: -1,
    CONF_SWELL_DIR_FROM: -1,
    CONF_SWELL_DIR_TO: -1,
    CONF_MIN_DURATION: 2,
    CONF_DAYLIGHT_ONLY: True,
    CONF_NOTIFY_SERVICE: "",
    CONF_NOTIFY_DAYS: 3,
    CONF_NOTIFY_MIN_RATING: 0.0,
}
