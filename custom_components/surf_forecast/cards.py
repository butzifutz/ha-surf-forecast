"""Generate ready-to-paste dashboard card YAML for a spot.

Pure string building without Home Assistant imports; the entity IDs are looked
up by the caller (they depend on the system language and on renames).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field


def _q(text: str) -> str:
    """Quote a string for YAML (JSON strings are valid YAML)."""
    return json.dumps(text, ensure_ascii=False)


@dataclass(frozen=True, slots=True)
class CardContext:
    title: str
    wind_direction: str
    wave_direction: str
    wind_speed: str
    wave_height: str
    forecast: str
    next_session: str
    compass_image: str
    windy_url: str
    surf_rating: str = ""
    # lead days -> entity id of the "rating forecast from N days ago" sensor
    lead_ratings: dict[int, str] = field(default_factory=dict)


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
  - sensor: {ctx.wave_direction}
    indicator:
      image: circle
      color: "#1e88e5"
    state_abbreviation:
      show: false
    state_value:
      show: false
value_sensors:
  - sensor: {ctx.wind_speed}
  - sensor: {ctx.wave_height}
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


def wave_chart_card(ctx: CardContext) -> str:
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
  title: {_q(f"{ctx.title} – Welle & Wind 7 Tage")}
graph_span: 7d
span:
  start: hour
now:
  show: true
yaxis:
  - id: height
    min: 0
    decimals: 1
  - id: wind
    opposite: true
    min: 0
    decimals: 0
series:
"""
        + series("Welle (m)", "height", "area", "#1e88e5", "h.wave")
        + series("Wind", "wind", "line", "#757575", "h.wind")
        + series("Periode (s)", "wind", "line", "#fb8c00", "h.period")
        + series(
            "Surfbar", "height", "column", "#43a047", "h.match ? h.wave : 0", "    opacity: 0.3\n"
        )
    )


def rating_chart_card(ctx: CardContext) -> str:
    return f"""\
type: custom:apexcharts-card
header:
  show: true
  title: {_q(f"{ctx.title} – Surf-Rating 7 Tage")}
graph_span: 7d
span:
  start: hour
now:
  show: true
yaxis:
  - min: 0
    max: 5
    decimals: 1
series:
  - entity: {ctx.forecast}
    name: Rating
    type: column
    color: "#43a047"
    data_generator: |
      return entity.attributes.hourly.map(h => [new Date(h.time).getTime(), h.rating]);
"""


def forecast_check_card(ctx: CardContext) -> str:
    leads = "".join(
        f"""\
  - entity: {entity_id}
    name: {_q(f"Prognose von vor {lead} Tag{'' if lead == 1 else 'en'}")}
"""
        for lead, entity_id in sorted(ctx.lead_ratings.items())
    )
    return f"""\
type: history-graph
title: {_q(f"{ctx.title} – Prognose vs. aktuelles Rating")}
hours_to_show: 168
entities:
  - entity: {ctx.surf_rating}
    name: Rating (aktueller Lauf)
{leads}"""


def week_table_card(ctx: CardContext) -> str:
    return f"""\
type: markdown
title: {_q(f"{ctx.title} – 7 Tage")}
content: |
  {{% set f = '{ctx.forecast}' -%}}
  {{% set u = state_attr(f, 'wind_unit') -%}}
  {{% set wd = ['Mo','Di','Mi','Do','Fr','Sa','So'] -%}}
  | Tag | Welle | Periode | aus | Wind | Rating | 🏄 |
  |:--|:--|:--|:--|:--|:--|:--|
  {{% for d in state_attr(f, 'daily') or [] -%}}
  {{% set dt = as_datetime(d.day) -%}}
  | {{{{ wd[dt.weekday()] }}}} {{{{ dt.strftime('%d.%m.') }}}} | {{{{ d.wave_min }}}}–{{{{ d.wave_max }}}} m | {{{{ d.period_max }}}} s | {{{{ d.wave_compass }}}} | {{{{ d.wind_min | round(0) }}}}–{{{{ d.wind_max | round(0) }}}} {{{{ u }}}} {{{{ d.wind_compass }}}} | {{{{ ('⭐' * (d.max_rating | round(0) | int)) ~ ' (' ~ d.max_rating ~ ')' if d.max_rating else '–' }}}} | {{{{ d.good_hours ~ ' h' if d.good_hours else '–' }}}} |
  {{% endfor %}}

  **Nächste Session:** {{{{ state_attr('{ctx.next_session}', 'text') or 'keine in Sicht 😴' }}}}
"""


def all_cards(ctx: CardContext) -> dict[str, str]:
    return {
        "compass": compass_card(ctx),
        "wave_chart": wave_chart_card(ctx),
        "rating_chart": rating_chart_card(ctx),
        "forecast_check": forecast_check_card(ctx),
        "week_table": week_table_card(ctx),
    }


def notification_markdown(ctx: CardContext) -> str:
    cards = all_cards(ctx)
    return (
        "Fertige Dashboard-Karten für diesen Spot. Dashboard → ✏️ Bearbeiten → "
        "*Karte hinzufügen* → *Manuell* und den jeweiligen Block einfügen.\n\n"
        "**Kompass** (braucht *Compass Card* aus HACS)\n"
        f"```yaml\n{cards['compass']}```\n\n"
        "**Welle & Wind 7 Tage** (braucht *ApexCharts Card* aus HACS)\n"
        f"```yaml\n{cards['wave_chart']}```\n\n"
        "**Surf-Rating 7 Tage** (braucht *ApexCharts Card* aus HACS)\n"
        f"```yaml\n{cards['rating_chart']}```\n\n"
        "**Prognose vs. aktuelles Rating** (Standard-Verlaufskarte; füllt sich erst "
        "mit der Zeit, z. B. nach 3 Tagen für die 3-Tage-Prognose)\n"
        f"```yaml\n{cards['forecast_check']}```\n\n"
        "**7-Tage-Tabelle** (Standard-Markdown-Karte)\n"
        f"```yaml\n{cards['week_table']}```\n\n"
        "Erneut anzeigen: Button *Dashboard-Karten* am Spot-Gerät."
    )
