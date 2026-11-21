# 🏄 Surf Forecast für Home Assistant

Eine Custom Integration mit Surf-Vorhersage für die nächsten 7 Tage, stündlich und je Spot. Sie
meldet sich, wenn **Welle, Windrichtung, Windstärke und Periode** zu dir passen, damit du keine
Session verpasst.

Gebaut für **windgetriebene Spots wie an der Ostsee**: Dort entsteht die Welle aus dem Wind. Bewertet
wird die Energie der Gesamtwelle (Windsee + Swell). Die Windrichtung prüft ein Korridor, den du aus
Erfahrung setzt, denn örtliche Effekte wie eine Mole kennt kein Modell. Restwelle nach einem
Sturm, die das Modell als „Swell“ führt, gibt einen Bonus.

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

| Option | Standard | Bedeutung |
|---|---|---|
| Mindest-Wellenenergie | 0,6 kW/m | Ab hier surfbar. Wellenenergie = 0,49 × Wellenhöhe² × Periode, 0,6 kW/m ≈ 0,6 m bei 3,5 s |
| Wellenenergie für Top-Rating | 4,5 kW/m | Ab hier volles Basis-Rating (≈ 1,4 m bei 4,7 s) |
| Periode min. | 3 s | Sicherung gegen kurze Kabbelwelle |
| Wind-Korridor von/bis | aus | Richtungen, **aus denen** der Wind kommen darf, damit es an deinem Spot geht (aus Erfahrung) |
| Wind max. | 55 km/h | Darüber nicht surfbar |
| Rating-Abzug ab Windstärke | 45 km/h | Darüber −0,5 |
| Flaute | 8 km/h | Bis zu dieser Windstärke ist die Richtung egal |
| Nachlauf-Bonus ab Swell-Höhe | 0,2 m | Restwelle nach einem Sturm, siehe Rating |
| Wasserstand max. | aus (−1) | Darüber −1, z. B. bei Hochwasser durch Ostwind |
| Mindestdauer | 2 h | So viele Stunden am Stück müssen passen |
| Nur bei Tageslicht | an | Nachtstunden ignorieren |
| Benachrichtigungsdienst | – | z. B. `notify.mobile_app_mein_handy` (optional) |
| Vorlauf | 3 Tage | Sessions so viele Tage im Voraus melden |
| Mindest-Rating | 0 | Nur Sessions mit mindestens diesem Rating melden |

Die Wind-Standardwerte sind in km/h angegeben und werden in deine Einheit umgerechnet. Wechselst du
später die Einheit, rechnet die Integration bereits gesetzte Werte **nicht** um.

**Korridore** laufen im Uhrzeigersinn von → bis und dürfen über Norden gehen. Richtungen sind
meteorologisch: 0° = aus Nord, 90° = aus Ost, 180° = aus Süd, 270° = aus West.

> Beispiel **Hohe Düne (Warnemünde)**: Wind-Korridor **235 → 45** (WSW über W und N bis NO).
> Bei SW und südlicheren Winden geht es dort nicht.

### Rating (0–5)

**0** heißt: nicht surfbar. Für surfbare Stunden gilt:

```
Rating = Basis + Nachlauf-Bonus − Abzüge          (begrenzt auf 1–5)

Basis     1 … 4,5   logarithmisch nach Wellenenergie zwischen Mindest- und Top-Energie.
                    Kleine Tage zählen noch, große laufen oben aus.
Nachlauf  0 … +1    Swell über der Schwelle (0,2 m); volle +1 bei 0,3 m mehr.
                    Nach einem Sturm führt das Modell die abklingende, sortierte
                    Restwelle als Swell. Sie steckt schon in der Gesamtwelle und
                    zählt hier bewusst ein zweites Mal.
Wind      −0,5      über der Abzugs-Windstärke
Wasser    −1        über dem maximalen Wasserstand (falls gesetzt)
```

Kalibriert ist das an Hohe Düne vom 12.–14.11.2026 (Werte in km/h):

| | Welle | Swell | Wind | Rating | vor Ort |
|---|---|---|---|---|---|
| Do 14:30 | 0,78 m @ 3,5 s | 0,10 m | 20 aus SW | 0 (Korridor) | „hatte noch keinen Sinn“ |
| Fr 08:30 | 1,32 m @ 4,5 s | 0,10 m | 36 aus W | 4,2 | Longboard möglich |
| Fr 15:30 | 1,52 m @ 4,8 s | 0,08 m | 40 aus WNW | 4,5 | sehr gut |
| Sa 08:30 | 0,80 m @ 3,8 s | 0,38 m | 22 aus WSW | 2,8 | klein, aber sauber (vermutet) |

Der Sensor *Surf-Rating* zeigt das Rating der aktuellen Stunde. Sessions und Tageswerte verwenden
das beste Rating im jeweiligen Zeitraum.

## Entitäten (pro Spot)

| Entität | Inhalt |
|---|---|
| `sensor.<spot>_wave_height` / `_period` / `_direction` | Aktuelle Stunde (Gesamtwelle) |
| `sensor.<spot>_swell_height` / `_period` / `_direction` | Aktueller Swell (Restwelle, für den Nachlauf-Bonus) |
| `sensor.<spot>_energy` | Wellenenergie der aktuellen Stunde in kW/m |
| `sensor.<spot>_wind_speed` / `_gusts` / `_direction` | Wind (Richtungen haben Attribut `compass`, z. B. „WNW“) |
| | Die Windrichtung hat zusätzlich `in_corridor` (1/0) und `compass_image` (siehe Kompass) |
| `sensor.<spot>_water_temperature` | Wassertemperatur |
| `sensor.<spot>_tide` | Wasserstand inkl. Gezeiten (nicht überall verfügbar) |
| `sensor.<spot>_surf_rating` | Rating der aktuellen Stunde (0 = nicht surfbar, 1–5) |
| `sensor.<spot>_next_session` | Startzeit der nächsten Session in den kommenden 7 Tagen. Attribute: `sessions` (alle), `text`, `end`, … |
| `sensor.<spot>_7_day_forecast` | State: bestes Rating heute. Attribute: `daily` (7 Tage) und `hourly` (168 h) |
| `sensor.<spot>_next_session_rating` | Bestes Rating der nächsten Session (0 = keine in Sicht). Attribute: `start`, `end`, `hours`, `text` |
| `sensor.<spot>_best_session` | Startzeit der Session mit dem höchsten Rating in den nächsten 7 Tagen. Attribute wie oben |
| `sensor.<spot>_<größe>_ahead_1` / `_3` / `_6` | **Vorschau:** Vorhersage für jetzt + 1, 3 bzw. 6 Tage. Attribut `target_time` |
| `sensor.<spot>_<größe>_lead_1` / `_3` / `_6` | **Rückschau:** was vor 1, 3 bzw. 6 Tagen für die aktuelle Stunde vorhergesagt wurde. Attribut `issued` |
| | `<größe>` ist jeweils `rating`, `wave` (Wellenhöhe), `swell` (Swell-Höhe) und `wind` (Windgeschwindigkeit), insgesamt 24 Sensoren |
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

Das erzeugte YAML enthält sieben Karten:

- **Kompass** (braucht die [Compass Card](https://github.com/tomvanswam/compass-card) aus HACS):
  Der grüne Keil ist dein Wind-Korridor. Der Pfeil zeigt, woher der Wind gerade kommt, und ist grün, wenn er im Korridor
  liegt, sonst rot. Der blaue Punkt zeigt die Wellenrichtung. Darunter stehen Windgeschwindigkeit
  und Wellenhöhe. Ein Tipp öffnet den Spot auf Windy.
- **Welle & Wind 7 Tage** (braucht die [ApexCharts Card](https://github.com/RomRider/apexcharts-card)
  aus HACS): Wellenhöhe, Wind und Periode pro Stunde, grüne Balken für die surfbaren Stunden.
- **Surf-Rating 7 Tage** (ApexCharts Card): das Rating jeder Stunde der nächsten 7 Tage.
- **Vorschau** (Standard-Kachelkarte): Rating, Wellenhöhe und Wind in 1, 3 und 6 Tagen.
- **Rating** und **Wellenhöhe: Prognose vs. aktueller Lauf** (Standard-Verlaufskarten): siehe
  *Vorschau und Rückschau*.
- **7-Tage-Tabelle** (Standard-Markdown-Karte, ohne HACS): pro Tag Welle, Periode, Wellenrichtung,
  Wind und Rating sowie die nächste Session.

Das Kompass-Hintergrundbild liegt unter `/api/surf_forecast/compass/<entry_id>.svg`. Die URL steht
auch im Attribut `compass_image` des Windrichtungs-Sensors.

Zeigt die App „Konfigurationsfehler“ bei Custom Cards: in der Companion App unter *Einstellungen →
Companion App → Fehlerbehebung* den Frontend-Cache zurücksetzen.

Für eigene Karten: Jeder Eintrag im Attribut `hourly` des 7-Tage-Forecast-Sensors enthält `time, wave, period, swell,
wind, wind_dir, energy, rating, match`. Jeder Tag in `daily` enthält u. a. `wave_min`, `wave_max`,
`period_max`, `energy_max`, `wave_compass`, `wind_min`, `wind_max`, `wind_compass`, `max_rating` und
`good_hours`. Die Attribute stehen nur im Arbeitsspeicher, nicht in der Datenbank.

### Vorschau und Rückschau

Standardkarten (Verlauf, Statistik, Sensor) zeigen nur Werte bis „jetzt“. Damit sich Vorhersagen
trotzdem mit ihnen darstellen und auswerten lassen, gibt es für **Rating, Wellenhöhe, Swell-Höhe und
Wind** je zwei Sorten Sensoren mit 1, 3 und 6 Tagen Vorlauf:

- **Vorschau** (*Rating in 3 Tagen*, *Wellenhöhe in 1 Tag*, …): zeigt jetzt die Vorhersage für jetzt
  + N Tage. Gut für Kacheln und Automationen („in 3 Tagen Rating ≥ 3“). Im Verlauf steht ein Wert
  beim Abrufzeitpunkt, nicht bei der Zielzeit (die steht im Attribut `target_time`).
- **Rückschau** (*Rating-Prognose von vor 3 Tagen*, *Wellenhöhe-Prognose von vor 1 Tag*, …): zeigt
  jetzt, was vor N Tagen für jetzt vorhergesagt wurde. Diese Sensoren liegen auf derselben Zeitachse
  wie der aktuelle Wert. In einer Verlaufs- oder Statistikkarte kannst du sie ohne Verschieben
  übereinanderlegen; die Abweichung ist der Vorhersagefehler bei N Tagen Vorlauf.

„Aktueller Lauf“ heißt dabei: der Wert des neuesten Modelllaufs für die aktuelle Stunde. Das ist die
beste verfügbare Schätzung, aber keine Messung vor Ort.

Die Rückschau-Sensoren füllen sich erst mit der Zeit: „vor 1 Tag“ nach 24 Stunden, „vor 6 Tagen“
nach 6 Tagen. Gespeichert wird höchstens eine Woche, das sind wenige Kilobyte.

Die Modelle rechnen unterschiedlich oft neu: der Wind für die ersten ~2 Tage (DWD ICON-D2) etwa alle
3 Stunden, die Wellenmodelle meist 2- bis 4-mal am Tag. Die Integration fragt stündlich ab und
verpasst damit keinen neuen Lauf.

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
