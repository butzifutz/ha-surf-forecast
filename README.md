# 🏄 Surf Forecast für Home Assistant

Eine Custom Integration mit Surf-Vorhersage für die nächsten 7 Tage, stündlich und je Spot. Sie
meldet sich, wenn **Welle, Periode, Windstärke und Windrichtung (Korridor)** zu dir passen, damit
du keine Session verpasst.

**Datenquelle:** [Open-Meteo](https://open-meteo.com/) (kostenlos, kein API-Key, CC BY 4.0)

- [Marine API](https://open-meteo.com/en/docs/marine-weather-api): Wellenhöhe, -periode und
  -richtung, Swell, Windsee, Wassertemperatur, Wasserstand inkl. Gezeiten
- [Forecast API](https://open-meteo.com/en/docs): Wind, Böen, Windrichtung, Tag/Nacht

Die Daten werden einmal pro Stunde abgerufen. Pro Spot sind das 2 Requests, weit unter dem
kostenlosen Limit.

## Installation

[![Open in HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=butzifutz&repository=ha-surf-forecast&category=integration)

**HACS:** HACS → ⋮ → *Benutzerdefinierte Repositories* → `https://github.com/butzifutz/ha-surf-forecast`,
Typ *Integration*, danach „Surf Forecast“ installieren und HA neu starten.

**Manuell:** Den Ordner `custom_components/surf_forecast` nach `<config>/custom_components/`
kopieren und HA neu starten.

Danach: *Einstellungen → Geräte & Dienste → Integration hinzufügen → Surf Forecast*.

1. **Spot:** Name und Pin auf der Karte. Setz den Pin aufs Wasser direkt vor den Strand und nicht
   auf den Strand selbst (das Marine-Modell hat ein ~5–25 km Raster). Wenn „keine Wellendaten“
   kommt, schieb den Pin etwas weiter raus.
2. **Bedingungen:** Was ist für dich surfbar? Kann später jederzeit über *Konfigurieren*
   geändert werden.

Mehrere Spots? Die Integration einfach mehrmals hinzufügen.

## Bedingungen

Eine Stunde gilt als **surfbar**, wenn **alle** Bedingungen erfüllt sind. Mehrere surfbare Stunden
am Stück (mindestens *Mindestdauer*) ergeben eine **Session**.

| Option | Bedeutung |
|---|---|
| Wellenhöhe min./max. | Korridor für die signifikante Wellenhöhe (m) |
| Periode min. | Mindestperiode (s). Kurze Periode heißt Windsee, lange heißt sauberer Swell |
| Swell statt Gesamt-Wellenhöhe | Nur die Swell-Komponente bewerten (ohne Windsee) |
| Swell-Richtung von/bis | Korridor, aus dem der Swell kommen muss (−1 = egal) |
| Wind max. | Maximale Windgeschwindigkeit (Einheit wählbar: kn, km/h, m/s) |
| Wind-Korridor von/bis | Richtung, **aus der** der Wind kommen darf (−1 = egal) |
| Richtung egal bis | Unterhalb dieser Windstärke ist die Richtung egal (glassy) |
| Mindestdauer | So viele Stunden am Stück müssen passen |
| Nur bei Tageslicht | Nachtstunden ignorieren |
| Benachrichtigungsdienst | z. B. `notify.mobile_app_mein_handy` (optional) |
| Vorlauf | Sessions so viele Tage im Voraus melden |
| Mindest-Rating | Nur Sessions mit mindestens diesem Rating melden |

**Korridore** laufen im Uhrzeigersinn von → bis und dürfen über Norden gehen (z. B. 300 → 60).
Richtungen sind meteorologisch: 0° = aus Nord, 90° = aus Ost, 180° = aus Süd, 270° = aus West.

> Beispiel **Offshore**: Ein Strand, der nach Westen aufs Meer schaut (z. B. Sylt, Westküste
> Frankreich), hat Offshore-Wind aus Osten. Ein Wind-Korridor **45 → 135** heißt Wind aus NO bis SO.

Wenn du die Windeinheit änderst, werden die Schwellwerte **nicht** umgerechnet. Pass sie einfach
im selben Dialog mit an.

### Rating (0–5)

Jede Stunde bekommt ein Rating aus drei Teilen:

- Welle (0–2): am besten in der Mitte deines Korridors
- Periode (0–1,5): voll ab 1,4 × Mindestperiode
- Wind (0–1,5): glassy oder offshore im Korridor ist gut, onshore oder zu stark schlecht

## Entitäten (pro Spot)

| Entität | Inhalt |
|---|---|
| `sensor.<spot>_wave_height` / `_period` / `_direction` | Aktuelle Stunde (Gesamtwelle) |
| `sensor.<spot>_swell_height` / `_period` / `_direction` | Aktueller Swell |
| `sensor.<spot>_wind_speed` / `_gusts` / `_direction` | Wind (Richtungen haben Attribut `compass`, z. B. „WNW“) |
| | Wind- und Swell-Richtung haben zusätzlich `in_corridor` (1/0) und `compass_image` (siehe Kompass) |
| `sensor.<spot>_water_temperature` | Wassertemperatur |
| `sensor.<spot>_tide` | Wasserstand inkl. Gezeiten (nicht überall verfügbar) |
| `sensor.<spot>_surf_rating` | Rating der aktuellen Stunde (0–5) |
| `sensor.<spot>_next_session` | Startzeit der nächsten passenden Session. Attribute: `sessions`, `text`, `end`, … |
| `sensor.<spot>_7_day_forecast` | State: bestes Rating heute. Attribute: `daily` (7 Tage) und `hourly` (168 h) |
| `binary_sensor.<spot>_surfable_now` | An, wenn die aktuelle Stunde passt |
| `binary_sensor.<spot>_session_upcoming` | An, wenn innerhalb des Vorlaufs eine Session ansteht |

Die Entity-IDs richten sich nach der Systemsprache. Auf Deutsch heißen sie z. B.
`sensor.hausstrand_wellenhohe` oder `sensor.hausstrand_7_tage_forecast`. Die Beispiele unten
verwenden die englischen IDs, du musst sie also ggf. anpassen. Die großen Attribute `daily`,
`hourly` und `sessions` werden nicht in der Datenbank gespeichert.

## Benachrichtigungen

Es gibt zwei Wege, die du auch kombinieren kannst. Jede Session wird nur **einmal** gemeldet, auch
nach einem Neustart. Verschiebt sich eine Session im Forecast um ein paar Stunden, wird sie
ebenfalls nicht erneut gemeldet.

1. **Direkt:** Im Optionsdialog einen Dienst wie `notify.mobile_app_mein_handy` eintragen. Fertig.
   Bei der Companion App öffnet ein Tipp auf die Nachricht den Spot auf **Windy**. Bei anderen
   Diensten (Telegram, E-Mail, …) steht der Windy-Link im Text.
2. **Blueprint:** [`blueprints/automation/surf_forecast/surf_session_notify.yaml`](blueprints/automation/surf_forecast/surf_session_notify.yaml)
   importieren (*Einstellungen → Automationen → Blueprints → Blueprint importieren*, Raw-URL der
   Datei). Damit bekommst du Mindest-Rating, Mindestdauer und Ruhezeiten (Meldungen während der
   Ruhezeit werden verworfen und nicht nachgeholt).

Für eigene Automationen feuert die Integration pro neuer Session das Event
**`surf_forecast_session`** mit diesen Daten:

```yaml
spot: Hausstrand
description: "Sa 17.10. 08:00–13:00 (5 h): 1.1–1.4 m @ 9.5 s, Wind max 11 kn, Rating 4.3/5"
start: "2026-10-17T06:00:00+00:00"
end: "2026-10-17T11:00:00+00:00"
hours: 5
max_rating: 4.3
avg_rating: 3.9
wave_min: 1.1
wave_max: 1.4
period_max: 9.5
wind_max: 11
wind_unit: kn
wind_direction: OSO
swell_direction: WNW
windy_url: https://www.windy.com/54.180/7.880?waves,54.180,7.880,10
entry_id: ...
```

Beispiel: morgendliche Zusammenfassung um 7 Uhr, wenn heute oder morgen etwas geht:

```yaml
triggers:
  - trigger: time
    at: "07:00:00"
conditions:
  - condition: state
    entity_id: binary_sensor.hausstrand_session_upcoming
    state: "on"
actions:
  - action: notify.mobile_app_mein_handy
    data:
      title: "🏄 Surf-Check"
      message: "{{ state_attr('binary_sensor.hausstrand_session_upcoming', 'sessions') | join('\n') }}"
```

## Dashboard

### Kompass: Wind, Swell und dein Korridor (mit [Compass Card](https://github.com/tomvanswam/compass-card) aus HACS)

Die Integration liefert pro Spot ein Hintergrundbild für den Kompass:

- **grüner Keil:** dein Wind-Korridor (aus dieser Richtung darf der Wind kommen)
- **blauer Ring:** dein Swell-Korridor

Die Pfeile zeigen, woher Wind und Swell gerade kommen. Liegt der Pfeil im grünen Keil, passt die
Windrichtung, und der Pfeil wird zusätzlich grün statt rot.

Bild-URL: `/api/surf_forecast/compass/<spot>.svg`, wobei `<spot>` der Name des Spots in
Kleinbuchstaben mit `_` statt Leerzeichen ist (z. B. `hausstrand`, `st_peter_ording`). Die exakte
URL steht auch im Attribut `compass_image` des Windrichtungs-Sensors.

```yaml
type: custom:compass-card
header:
  title:
    value: Hausstrand
  icon:
    value: mdi:surfing
indicator_sensors:
  # Wind: Pfeil zeigt zur Mitte, sitzt also dort, woher der Wind kommt
  - sensor: sensor.hausstrand_wind_direction
    indicator:
      image: arrow_inward
      color: "#e53935"
      dynamic_style:
        sensor: sensor.hausstrand_wind_direction
        attribute: in_corridor
        bands:
          - from_value: 1
            color: "#43a047"
  # Swell: blauer Punkt außen am Ring
  - sensor: sensor.hausstrand_swell_direction
    indicator:
      image: circle
      color: "#1e88e5"
    state_abbreviation:
      show: false
    state_value:
      show: false
value_sensors:
  - sensor: sensor.hausstrand_wind_speed
  - sensor: sensor.hausstrand_swell_height
    decimals: 1
  - sensor: sensor.hausstrand_swell_period
compass:
  circle:
    background_image: /api/surf_forecast/compass/hausstrand.svg
    background_opacity: 1
  north:
    show: true
tap_action:
  action: url
  url: https://www.windy.com/54.180/7.880?waves,54.180,7.880,10
```

Ein Tipp auf den Kompass öffnet den Spot auf Windy. Die URL für deinen Spot steht im Attribut
`windy_url` des Sensors „Nächste Session“.

### 7-Tage-Übersicht (Markdown-Karte, ohne Zusatzkarten)

```yaml
type: markdown
title: 🏄 Hausstrand – 7 Tage
content: |
  {% set f = 'sensor.hausstrand_7_day_forecast' -%}
  {% set u = state_attr(f, 'wind_unit') -%}
  {% set wd = ['Mo','Di','Mi','Do','Fr','Sa','So'] -%}
  | Tag | Welle | Periode | Swell | Wind | Rating | 🏄 |
  |:--|:--|:--|:--|:--|:--|:--|
  {% for d in state_attr(f, 'daily') or [] -%}
  {% set dt = as_datetime(d.day) -%}
  | {{ wd[dt.weekday()] }} {{ dt.strftime('%d.%m.') }} | {{ d.wave_min }}–{{ d.wave_max }} m | {{ d.period_max }} s | {{ d.swell_compass }} | {{ d.wind_min | round(0) }}–{{ d.wind_max | round(0) }} {{ u }} {{ d.wind_compass }} | {{ '⭐' * (d.max_rating | round(0) | int) }} ({{ d.max_rating }}) | {{ d.good_hours ~ ' h' if d.good_hours else '–' }} |
  {% endfor %}

  **Nächste Session:** {{ state_attr('sensor.hausstrand_next_session', 'text') or 'keine in Sicht 😴' }}
```

### Stündlicher Chart (mit [ApexCharts Card](https://github.com/RomRider/apexcharts-card) aus HACS)

```yaml
type: custom:apexcharts-card
header:
  show: true
  title: Welle & Wind – 7 Tage
graph_span: 7d
span:
  start: hour
yaxis:
  - id: wave
    min: 0
    decimals: 1
  - id: wind
    opposite: true
    min: 0
    decimals: 0
series:
  - entity: sensor.hausstrand_7_day_forecast
    name: Welle (m)
    yaxis_id: wave
    type: area
    color: "#1e88e5"
    data_generator: |
      return entity.attributes.hourly.map(h => [new Date(h.time).getTime(), h.wave]);
  - entity: sensor.hausstrand_7_day_forecast
    name: Swell (m)
    yaxis_id: wave
    type: line
    color: "#26c6da"
    data_generator: |
      return entity.attributes.hourly.map(h => [new Date(h.time).getTime(), h.swell]);
  - entity: sensor.hausstrand_7_day_forecast
    name: Wind
    yaxis_id: wind
    type: line
    color: "#9e9e9e"
    data_generator: |
      return entity.attributes.hourly.map(h => [new Date(h.time).getTime(), h.wind]);
  - entity: sensor.hausstrand_7_day_forecast
    name: Surfbar
    yaxis_id: wave
    type: column
    color: "#43a047"
    opacity: 0.3
    data_generator: |
      return entity.attributes.hourly.map(h => [new Date(h.time).getTime(), h.match ? h.wave : 0]);
```

Jeder Eintrag in `hourly` enthält `time, wave, period, swell, swell_period, swell_dir, wind,
gusts, wind_dir, tide, rating, match`.

## Grenzen

- Open-Meteo rechnet mit globalen bzw. regionalen Wellenmodellen (u. a. DWD, ECMWF, MeteoFrance).
  Lokale Effekte wie Sandbänke, Abschattung durch Inseln oder Riffe kennt das Modell nicht. Die
  Bedingungen solltest du deshalb an deinen Spot anpassen und mit der Zeit nachjustieren.
- Die Gezeiten-Daten aus dem Modell sind grob. Für Spots, bei denen die Tide entscheidend ist,
  ist eine lokale Gezeitentafel genauer.

## Lizenz

[MIT](LICENSE). Die Wetter- und Wellendaten stammen von [Open-Meteo.com](https://open-meteo.com/)
und stehen unter [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Die Namensnennung
ist in jeder Entität als `attribution` hinterlegt. Windy wird nur verlinkt; die Integration ruft
keine Daten von Windy ab.

## Entwicklung

Die Surf-Logik (`custom_components/surf_forecast/surf.py`) hat keine Abhängigkeit zu Home
Assistant und wird mit `pytest` getestet:

```bash
pip install pytest
pytest -q
```
