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
    swell_direction="sensor.spot_swell_richtung",
    wind_speed="sensor.spot_windgeschwindigkeit",
    swell_height="sensor.spot_swell_hohe",
    forecast="sensor.spot_7_tage_forecast",
    next_session="sensor.spot_nachste_session",
    compass_image="/api/surf_forecast/compass/abc.svg",
    windy_url="https://www.windy.com/54.180/7.880?waves,54.180,7.880,10",
)


def test_compass_card():
    card = yaml.safe_load(cards.compass_card(CTX))
    assert card["type"] == "custom:compass-card"
    assert card["header"]["title"]["value"] == CTX.title
    wind, swell = card["indicator_sensors"]
    assert wind["sensor"] == CTX.wind_direction
    assert wind["indicator"]["dynamic_style"]["attribute"] == "in_corridor"
    assert swell["sensor"] == CTX.swell_direction
    # no period: it made the value text too long
    assert [v["sensor"] for v in card["value_sensors"]] == [CTX.wind_speed, CTX.swell_height]
    assert card["compass"]["circle"]["background_image"] == CTX.compass_image
    assert card["tap_action"] == {"action": "url", "url": CTX.windy_url}


def test_swell_chart_card():
    card = yaml.safe_load(cards.swell_chart_card(CTX))
    assert card["type"] == "custom:apexcharts-card"
    assert [s["name"] for s in card["series"]] == ["Swell (m)", "Periode (s)", "Surfbar"]
    assert all(s["entity"] == CTX.forecast for s in card["series"])
    assert "h.swell_period" in card["series"][1]["data_generator"]
    assert card["series"][2]["opacity"] == 0.3


def test_week_table_card():
    card = yaml.safe_load(cards.week_table_card(CTX))
    assert card["type"] == "markdown"
    assert f"set f = '{CTX.forecast}'" in card["content"]
    assert CTX.next_session in card["content"]
    assert "{{ wd[dt.weekday()] }}" in card["content"]


def test_notification_contains_all_cards():
    text = cards.notification_markdown(CTX)
    assert text.count("```yaml") == 3
    for body in cards.all_cards(CTX).values():
        assert body in text
