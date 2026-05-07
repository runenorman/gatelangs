# 🛠 Developer Manifest: Gatelangs Oslo

Dette dokumentet fungerer som prosjektets hukommelse og "handover"-spesifikasjon for videreutvikling (v3.2+).

## 🏃‍♂️ Prosjektkontekst
"Gatelangs Oslo" er en hobby-app for en vennegjeng på 10 personer som har som mål å gå alle gater i Oslo. 
- **Filosofi:** Hvis en gate er påbegynt, regnes den som GÅTT.
- **Mål:** Visualisere fremdrift (Rødt = skal gå, Grønt = gått) på et interaktivt kart.

## 📊 Datakilder
Hoveddatakilden er en `.ods`-fil (OpenDocument Spreadsheet) som ligger i rotmappa.

### Fane 1: Loggen ("Gater")
- Inneholder kronologisk logg over turer.
- **Kolonne B (Index 1):** Gatenavn (unike navn, men mange duplikater pga etapper).
- **Kolonne O (Index 14):** Dato for når gaten ble gått.
- **Særhet:** Manglende datoer tolkes som "fallback" (01.01.2019) i appen for å sikre grønn farge.

### Fane 2: Fasiten ("marker her")
- En rutenett-oversikt over alle gater som skal gås.
- Vi bruker kun rader opp til linje 587 (unngår "Historiske gater").
- **Kjent bug:** Noen celler inneholder "10:23:00" pga. Excels autokorrektur av datoer. Disse må rettes manuelt i regnearket.

## 🗺️ Kartdata (GeoJSON)
Filen `oslo_geometri.geojson` er hjertet i appen. Den inneholder koordinater fra OpenStreetMap (OSM).
- **Matching-nøkkel:** Vi bruker en funksjon kalt `super_rens()` (slugify) som fjerner mellomrom, parenteser, spesialtegn og gjør alt til små bokstaver. Dette garanterer match mellom regneark og kart selv ved skrivefeil.
- **OSM-filter:** Vi har filtrert dataene strengt til Oslo Kommune (`admin_level=7` eller `ref:kommune=0301`).

### Skript for å regenerere kartdata
Hvis Fane 2 endres (nye gater legges til), må dette kjøres i Google Colab for å oppdatere `oslo_geometri.geojson`:

```python
# (Inkluder her Versjon 15 av skriptet som fungerte)
import pandas as pd
import requests
import json
import re
import unicodedata

def super_rens(s):
    if not s or pd.isna(s): return ""
    s = unicodedata.normalize('NFC', str(s)).lower()
    s = re.sub(r'\(.*\)', '', s)
    return "".join(c for c in s if c.isalnum())

# Query: area["name"="Oslo"]["admin_level"="7"]->.oslo; way(area.oslo)["highway"]["name"]; out geom;
