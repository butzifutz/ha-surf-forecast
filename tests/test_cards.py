"""Tests for the generated dashboard YAML (custom_components/surf_forecast/cards.py)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

_PATH = Path(__file__).parents[1] / "custom_components" / "surf_forecast" / "cards.py"
_spec = importlib.util.spec_from_file_location("cards_logic", _PATH)
cards = importlib.util.module_from_spec(_spec)
sys.modules["cards_logic"] = cards
_spec.loader.exec_module(cards)

CTX = cards.CardContext(
    title='Peter\'s "Spot"',
    wind_direction="sensor.spot_windrichtung",
    wave_direction="sensor.spot_wellenrichtung",
    wind_speed="sensor.spot_windgeschwindigkeit",
    wave_height="sensor.spot_wellenhohe",
    forecast="sensor.spot_7_tage_forecast",
    next_session="sensor.spot_nachste_session",
    compass_image="/api/surf_forecast/compass/abc.svg",
    windy_url="https://www.windy.com/54.180/7.880?waves,54.180,7.880,10",
    surf_rating="sensor.spot_surf_rating",
    actual={"rating": "sensor.spot_surf_rating", "wave": "sensor.spot_wellenhohe"},
    leads={
        "rating": {1: "sensor.spot_rating_prognose_1", 3: "sensor.spot_rating_prognose_3"},
        "wave": {1: "sensor.spot_welle_prognose_1"},
    },
    ahead={
        "rating": {1: "sensor.spot_rating_in_1", 6: "sensor.spot_rating_in_6"},
        "wind": {3: "sensor.spot_wind_in_3"},
    },
)


def test_compass_card():
    card = yaml.safe_load(cards.compass_card(CTX))
    assert card["type"] == "custom:compass-card"
    assert card["header"]["title"]["value"] == CTX.title
    wind, swell = card["indicator_sensors"]
    assert wind["sensor"] == CTX.wind_direction
    assert wind["indicator"]["dynamic_style"]["attribute"] == "in_corridor"
    assert swell["sensor"] == CTX.wave_direction
    # no period: it made the value text too long
    assert [v["sensor"] for v in card["value_sensors"]] == [CTX.wind_speed, CTX.wave_height]
    assert card["compass"]["circle"]["background_image"] == CTX.compass_image
    assert card["tap_action"] == {"action": "url", "url": CTX.windy_url}


def test_wave_chart_card():
    card = yaml.safe_load(cards.wave_chart_card(CTX))
    assert card["type"] == "custom:apexcharts-card"
    assert [s["name"] for s in card["series"]] == ["Welle (m)", "Wind", "Periode (s)", "Surfbar"]
    assert all(s["entity"] == CTX.forecast for s in card["series"])
    assert "h.wave" in card["series"][0]["data_generator"]
    assert "h.wind" in card["series"][1]["data_generator"]
    assert card["series"][3]["opacity"] == 0.3


def test_week_table_card():
    card = yaml.safe_load(cards.week_table_card(CTX))
    assert card["type"] == "markdown"
    assert f"set f = '{CTX.forecast}'" in card["content"]
    assert CTX.next_session in card["content"]
    assert "{{ wd[dt.weekday()] }}" in card["content"]
    assert "d.wave_compass" in card["content"]


def test_notification_contains_all_cards():
    text = cards.notification_markdown(CTX)
    assert text.count("```yaml") == 7
    for body in cards.all_cards(CTX).values():
        assert body in text


def test_rating_chart_card():
    card = yaml.safe_load(cards.rating_chart_card(CTX))
    assert card["type"] == "custom:apexcharts-card"
    (series,) = card["series"]
    assert series["entity"] == CTX.forecast
    assert "h.rating" in series["data_generator"]
    assert card["yaxis"][0]["max"] == 5


def test_forecast_check_cards():
    card = yaml.safe_load(cards.forecast_check_card(CTX))
    assert card["type"] == "history-graph"
    assert [e["entity"] for e in card["entities"]] == [
        CTX.surf_rating,
        "sensor.spot_rating_prognose_1",
        "sensor.spot_rating_prognose_3",
    ]
    assert card["entities"][2]["name"] == "Prognose von vor 3 Tagen"
    wave = yaml.safe_load(cards.forecast_check_card(CTX, "wave"))
    assert [e["entity"] for e in wave["entities"]] == [
        "sensor.spot_wellenhohe",
        "sensor.spot_welle_prognose_1",
    ]
    assert "Wellenhöhe" in wave["title"]


def test_preview_card():
    card = yaml.safe_load(cards.preview_card(CTX))
    assert card["type"] == "glance"
    assert [(e["entity"], e["name"]) for e in card["entities"]] == [
        ("sensor.spot_rating_in_1", "Rating in 1 Tag"),
        ("sensor.spot_rating_in_6", "Rating in 6 Tagen"),
        ("sensor.spot_wind_in_3", "Wind in 3 Tagen"),
    ]
