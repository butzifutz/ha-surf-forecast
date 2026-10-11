"""Generate ready-to-paste dashboard card YAML for a spot.

Pure string building without Home Assistant imports; the entity IDs are looked
up by the caller (they depend on the system language and on renames).
"""

from __future__ import annotations

import json
from dataclasses import dataclass


def _q(text: str) -> str:
    """Quote a string for YAML (JSON strings are valid YAML)."""
    return json.dumps(text, ensure_ascii=False)


@dataclass(frozen=True, slots=True)
class CardContext:
    title: str
    wind_direction: str
    swell_direction: str
    wind_speed: str
    swell_height: str
    forecast: str
    next_session: str
    compass_image: str
    windy_url: str


def compass_card(ctx: CardContext) -> str:
    return f"""\
type: custom:compass-card
header:
  title:
    value: {_q(ctx.title)}
  icon:
    value: mdi:surfing
indicator_sensors:
  - sensor: {ctx.wind_direction}
    indicator:
      image: arrow_inward
      color: "#e53935"
      dynamic_style:
        sensor: {ctx.wind_direction}
        attribute: in_corridor
        bands:
          - from_value: 1
            color: "#43a047"
  - sensor: {ctx.swell_direction}
    indicator:
      image: circle
      color: "#1e88e5"
    state_abbreviation:
      show: false
    state_value:
      show: false
value_sensors:
  - sensor: {ctx.wind_speed}
  - sensor: {ctx.swell_height}
    decimals: 1
compass:
  circle:
    background_image: {ctx.compass_image}
    background_opacity: 1
  north:
    show: true
tap_action:
  action: url
  url: {ctx.windy_url}
"""


def swell_chart_card(ctx: CardContext) -> str:
    def series(name: str, axis: str, kind: str, color: str, expr: str, extra: str = "") -> str:
        return f"""\
  - entity: {ctx.forecast}
    name: {name}
    yaxis_id: {axis}
    type: {kind}
    color: "{color}"
{extra}    data_generator: |
      return entity.attributes.hourly.map(h => [new Date(h.time).getTime(), {expr}]);
"""

    return (
        f"""\
type: custom:apexcharts-card
header:
  show: true
  title: {_q(f"{ctx.title} – Swell 7 Tage")}
graph_span: 7d
span:
  start: hour
now:
  show: true
yaxis:
  - id: height
    min: 0
    decimals: 1
  - id: period
    opposite: true
    min: 0
    decimals: 0
series:
"""
        + series("Swell (m)", "height", "area", "#1e88e5", "h.swell")
        + series("Periode (s)", "period", "line", "#fb8c00", "h.swell_period")
        + series(
            "Surfbar", "height", "column", "#43a047", "h.match ? h.swell : 0", "    opacity: 0.3\n"
        )
    )


def week_table_card(ctx: CardContext) -> str:
    return f"""\
type: markdown
title: {_q(f"{ctx.title} – 7 Tage")}
content: |
  {{% set f = '{ctx.forecast}' -%}}
  {{% set u = state_attr(f, 'wind_unit') -%}}
  {{% set wd = ['Mo','Di','Mi','Do','Fr','Sa','So'] -%}}
  | Tag | Welle | Periode | Swell | Wind | Rating | 🏄 |
  |:--|:--|:--|:--|:--|:--|:--|
  {{% for d in state_attr(f, 'daily') or [] -%}}
  {{% set dt = as_datetime(d.day) -%}}
  | {{{{ wd[dt.weekday()] }}}} {{{{ dt.strftime('%d.%m.') }}}} | {{{{ d.wave_min }}}}–{{{{ d.wave_max }}}} m | {{{{ d.period_max }}}} s | {{{{ d.swell_compass }}}} | {{{{ d.wind_min | round(0) }}}}–{{{{ d.wind_max | round(0) }}}} {{{{ u }}}} {{{{ d.wind_compass }}}} | {{{{ '⭐' * (d.max_rating | round(0) | int) }}}} ({{{{ d.max_rating }}}}) | {{{{ d.good_hours ~ ' h' if d.good_hours else '–' }}}} |
  {{% endfor %}}

  **Nächste Session:** {{{{ state_attr('{ctx.next_session}', 'text') or 'keine in Sicht 😴' }}}}
"""


def all_cards(ctx: CardContext) -> dict[str, str]:
    return {
        "compass": compass_card(ctx),
        "swell_chart": swell_chart_card(ctx),
        "week_table": week_table_card(ctx),
    }


def notification_markdown(ctx: CardContext) -> str:
    cards = all_cards(ctx)
    return (
        "Fertige Dashboard-Karten für diesen Spot. Dashboard → ✏️ Bearbeiten → "
        "*Karte hinzufügen* → *Manuell* und den jeweiligen Block einfügen.\n\n"
        "**Kompass** (braucht *Compass Card* aus HACS)\n"
        f"```yaml\n{cards['compass']}```\n\n"
        "**Swell-Verlauf 7 Tage** (braucht *ApexCharts Card* aus HACS)\n"
        f"```yaml\n{cards['swell_chart']}```\n\n"
        "**7-Tage-Tabelle** (Standard-Markdown-Karte)\n"
        f"```yaml\n{cards['week_table']}```\n\n"
        "Erneut anzeigen: Button *Dashboard-Karten* am Spot-Gerät."
    )
