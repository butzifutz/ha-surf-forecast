# 🏄 Surf Forecast für Home Assistant

Eine Custom Integration mit Surf-Vorhersage für die nächsten 7 Tage, stündlich und je Spot. Sie
meldet sich, wenn **Welle, Windrichtung, Windstärke und Periode** zu dir passen, damit du keine
Session verpasst.

Gebaut für **windgetriebene Spots wie an der Ostsee**: Dort gibt es kaum Swell, die Welle entsteht
aus dem Wind. Der Wind muss deshalb aus der richtigen Richtung und mit genug Stärke kommen. Für
Ozean-Spots lässt sich auf Swell umschalten.

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
| Wellenhöhe min./max. | Korridor für die Wellenhöhe am Spot (Gesamtwelle inkl. Windsee, in m) |
| Periode min. | Mindestperiode in s. Ostsee: meist 4–6 s. 0 = egal |
| Wind-Korridor von/bis | Richtung, **aus der** der Wind kommen muss, damit er an deinem Spot Welle macht (−1 = egal) |
| Wind min./max. | Der Wind muss mindestens so stark sein, dass Welle entsteht, und darf höchstens so stark sein, dass es nicht verblasen ist (Einheit wählbar: kn, km/h, m/s) |
| Nachlauf bis | Unterhalb dieser Windstärke zählt nur noch die Welle, egal woher der Wind kommt. Das ist die Clean-up-Session, wenn der Wind nach einem Sturm einschläft und die Welle noch steht |
| Wellenrichtung von/bis | Optional: Richtung, aus der die Wellen kommen müssen (−1 = egal) |
| Swell statt Gesamtwelle | Für Ozean-Spots: Swell-Höhe, -Periode und -Richtung bewerten. Für die Ostsee aus lassen |
| Mindestdauer | So viele Stunden am Stück müssen passen |
| Nur bei Tageslicht | Nachtstunden ignorieren |
| Benachrichtigungsdienst | z. B. `notify.mobile_app_mein_handy` (optional) |
| Vorlauf | Sessions so viele Tage im Voraus melden |
| Mindest-Rating | Nur Sessions mit mindestens diesem Rating melden |

**Korridore** laufen im Uhrzeigersinn von → bis und dürfen über Norden gehen (z. B. 300 → 60).
Richtungen sind meteorologisch: 0° = aus Nord, 90° = aus Ost, 180° = aus Süd, 270° = aus West.

> Beispiel **Ostsee**: Ein Strand, der nach Nordosten aufs offene Wasser schaut, bekommt Welle bei
> Wind aus N bis O. Wind-Korridor **0 → 90**, Wind min. **12 kn**, max. **30 kn**, Nachlauf bis
> **6 kn**. Ablandiger Wind aus SW zählt dann nicht, egal wie stark er ist.

Die **Wellenrichtung** im Modell ist an der Ostsee oft unzuverlässig, weil das Modellraster in
Küstennähe grob ist. Lass den Korridor dafür am besten auf −1 und verlass dich auf die
Windrichtung. Prüf am Spot, ob die Werte passen.

Wenn du die Windeinheit änderst, werden die Schwellwerte **nicht** umgerechnet. Pass sie einfach
im selben Dialog mit an.

### Rating (0–5)

- **0:** Die Stunde ist nicht surfbar.
- **1–5:** Die Stunde ist surfbar. Wie gut, hängt vor allem von der Wellenhöhe ab: Je weiter
  oben in deinem Korridor, desto besser (60 %). Dazu kommen die Periode (25 %; 3 s zählt nichts,
  ab 8 s voll) und ein Abzug für sehr starken Wind (15 %).

Der Sensor *Surf-Rating* zeigt das Rating der aktuellen Stunde. Sessions und Tageswerte
verwenden das beste Rating im jeweiligen Zeitraum.

## Entitäten (pro Spot)

| Entität | Inhalt |
|---|---|
| `sensor.<spot>_wave_height` / `_period` / `_direction` | Aktuelle Stunde (Gesamtwelle) |
| `sensor.<spot>_swell_height` / `_period` / `_direction` | Aktueller Swell (für die Bewertung nur mit „Swell statt Gesamtwelle“) |
| `sensor.<spot>_wind_speed` / `_gusts` / `_direction` | Wind (Richtungen haben Attribut `compass`, z. B. „WNW“) |
| | Wind- und Wellenrichtung haben zusätzlich `in_corridor` (1/0) und `compass_image` (siehe Kompass) |
| `sensor.<spot>_water_temperature` | Wassertemperatur |
| `sensor.<spot>_tide` | Wasserstand inkl. Gezeiten (nicht überall verfügbar) |
| `sensor.<spot>_surf_rating` | Rating der aktuellen Stunde (0 = nicht surfbar, 1–5) |
| `sensor.<spot>_next_session` | Startzeit der nächsten Session in den kommenden 7 Tagen. Attribute: `sessions` (alle), `text`, `end`, … |
| `sensor.<spot>_7_day_forecast` | State: bestes Rating heute. Attribute: `daily` (7 Tage) und `hourly` (168 h) |
| `binary_sensor.<spot>_surfable_now` | An, wenn die aktuelle Stunde passt |
| `button.<spot>_dashboard_cards` | Zeigt fertiges Dashboard-YAML für diesen Spot als Benachrichtigung |

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
wave_direction: NO
swell_direction: WNW
windy_url: https://www.windy.com/54.180/7.880?waves,54.180,7.880,10
entry_id: ...
```

Beispiel: morgendliche Zusammenfassung um 7 Uhr, wenn heute oder morgen eine Session ansteht:

```yaml
triggers:
  - trigger: time
    at: "07:00:00"
conditions:
  - condition: template
    value_template: >-
      {% set n = states('sensor.hausstrand_next_session') | as_datetime %}
      {{ n is not none and n < today_at() + timedelta(days=2) }}
actions:
  - action: notify.mobile_app_mein_handy
    data:
      title: "🏄 Surf-Check"
      message: "{{ state_attr('sensor.hausstrand_next_session', 'text') }}"
```

## Dashboard

### Karten automatisch erzeugen

Du musst die Beispiele unten nicht von Hand anpassen. Beim Anlegen eines Spots erscheint in HA
eine **Benachrichtigung** (🔔 links unten) mit fertigem YAML für Kompass, Welle-&-Wind-Chart und
7-Tage-Tabelle. Darin stehen bereits deine echten Entity-IDs, egal in welcher Sprache dein HA
läuft. Dashboard → ✏️ Bearbeiten → *Karte hinzufügen* → *Manuell* → Block einfügen.

Später kannst du das YAML jederzeit erneut erzeugen:

- **Button** *Dashboard-Karten* am Spot-Gerät
  (*Einstellungen → Geräte & Dienste → Surf Forecast → Spot*)
- **Aktion** `surf_forecast.dashboard_cards` (optional mit `config_entry_id`). Mit
  Antwortvariable liefert sie das YAML als Daten zurück, statt eine Benachrichtigung zu zeigen.

Das erzeugte YAML enthält drei Karten:

- **Kompass** (braucht die [Compass Card](https://github.com/tomvanswam/compass-card) aus HACS):
  Der grüne Keil ist dein Wind-Korridor, der blaue Ring dein Wellenrichtungs-Korridor (falls
  gesetzt). Der Pfeil zeigt, woher der Wind gerade kommt, und ist grün, wenn er im Korridor
  liegt, sonst rot. Der blaue Punkt zeigt die Wellenrichtung. Darunter stehen Windgeschwindigkeit
  und Wellenhöhe. Ein Tipp öffnet den Spot auf Windy.
- **Welle & Wind 7 Tage** (braucht die [ApexCharts Card](https://github.com/RomRider/apexcharts-card)
  aus HACS): Wellenhöhe, Wind und Periode pro Stunde, grüne Balken für die surfbaren Stunden.
- **7-Tage-Tabelle** (Standard-Markdown-Karte, ohne HACS): pro Tag Welle, Periode, Wellenrichtung,
  Wind und Rating sowie die nächste Session.

Das Kompass-Hintergrundbild liegt unter `/api/surf_forecast/compass/<entry_id>.svg`. Die URL steht
auch im Attribut `compass_image` des Windrichtungs-Sensors.

Zeigt die App „Konfigurationsfehler“ bei Custom Cards: in der Companion App unter *Einstellungen →
Companion App → Fehlerbehebung* den Frontend-Cache zurücksetzen.

Für eigene Karten: Jeder Eintrag im Attribut `hourly` des 7-Tage-Forecast-Sensors enthält `time, wave, period,
wave_dir, swell, swell_period, swell_dir, wind, gusts, wind_dir, tide, rating, match`. Jeder Tag in
`daily` enthält u. a. `wave_min`, `wave_max`, `period_max`, `wave_compass`, `wind_min`, `wind_max`,
`wind_compass`, `max_rating` und `good_hours`.

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
