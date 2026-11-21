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
CONF_ENERGY_MIN = "energy_min"
CONF_ENERGY_TOP = "energy_top"
CONF_PERIOD_MIN = "period_min"
CONF_WIND_MAX = "wind_max"
CONF_WIND_STRONG = "wind_strong"
# key kept from earlier versions: below this wind the direction doesn't matter
CONF_CALM_MAX = "glassy_max"
CONF_WIND_DIR_FROM = "wind_dir_from"
CONF_WIND_DIR_TO = "wind_dir_to"
CONF_SWELL_BONUS_MIN = "swell_bonus_min"
CONF_SEA_LEVEL_MAX = "sea_level_max"
CONF_MIN_DURATION = "min_duration"
CONF_DAYLIGHT_ONLY = "daylight_only"
CONF_NOTIFY_SERVICE = "notify_service"
CONF_NOTIFY_DAYS = "notify_days"
CONF_NOTIFY_MIN_RATING = "notify_min_rating"
# weather entity with measured wind (e.g. a DWD station)
CONF_WIND_STATION = "wind_station"

# Open-Meteo "wind_speed_unit" values
WIND_UNITS = {"kn": "kn", "kmh": "km/h", "ms": "m/s"}
# km/h -> unit
WIND_FACTORS = {"kn": 1 / 1.852, "kmh": 1.0, "ms": 1 / 3.6}

# wind defaults in km/h, converted to the configured unit when not set
WIND_DEFAULTS_KMH = {
    CONF_WIND_MAX: 55.0,
    CONF_WIND_STRONG: 45.0,
    CONF_CALM_MAX: 8.0,
}

DEFAULT_OPTIONS = {
    CONF_WIND_UNIT: "kn",
    CONF_ENERGY_MIN: 0.6,
    CONF_ENERGY_TOP: 4.5,
    CONF_PERIOD_MIN: 3.0,
    # -1 = corridor disabled (any direction)
    CONF_WIND_DIR_FROM: -1,
    CONF_WIND_DIR_TO: -1,
    CONF_SWELL_BONUS_MIN: 0.2,
    # -1 = no high-water penalty
    CONF_SEA_LEVEL_MAX: -1.0,
    CONF_MIN_DURATION: 2,
    CONF_DAYLIGHT_ONLY: True,
    CONF_NOTIFY_SERVICE: "",
    CONF_NOTIFY_DAYS: 3,
    CONF_NOTIFY_MIN_RATING: 0.0,
}


def effective_options(options: dict) -> dict:
    """Options with defaults filled in (wind defaults in the chosen unit)."""
    opts = {**DEFAULT_OPTIONS, **options}
    factor = WIND_FACTORS.get(opts[CONF_WIND_UNIT], 1.0)
    for key, kmh in WIND_DEFAULTS_KMH.items():
        if key not in options:
            opts[key] = round(kmh * factor)
    return opts
