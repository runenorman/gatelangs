# 🛠 Developer Manifest: Gatelangs Oslo

Dette dokumentet fungerer som prosjektets hukommelse og "handover"-spesifikasjon for videreutvikling (v3.2+).

## 🏃‍♂️ Prosjektkontekst
"Gatelangs Oslo" er en hobby-app for en vennegjeng som går alle gater i Oslo. 
- **Filosofi:** Hvis en gate er påbegynt, regnes den som GÅTT.
- **Mål:** Visualisere fremdrift (Rødt = skal gå, Grønt = gått) på et interaktivt kart.

## 📊 Datakilder
Hoveddatakilden er en `.ods`-fil (OpenDocument Spreadsheet).

### Fane 1: Loggen ("Gater")
- **Kolonne B (Index 1):** Gatenavn (mange duplikater pga etapper).
- **Kolonne O (Index 14):** Dato for når gaten ble gått.
- **Dato-logikk:** Manglende datoer settes til `01.01.2019` i appen for å sikre visning.

### Fane 2: Fasiten ("marker her")
- Rutenett-oversikt over gater som skal gås (frem til linje 587).
- **Kjent bug:** Noen celler inneholder "10:23:00" pga. Excel-feil. Må rettes manuelt i arket.

## 🗺️ Kartdata (GeoJSON)
Filen `oslo_geometri.geojson` inneholder koordinater fra OpenStreetMap (OSM).
- **Matching:** Vi bruker `super_rens()` (fjerner alt unntatt bokstaver/tall) for å koble ark og kart. Dette fikser problemer med ÆØÅ, usynlige mellomrom (`\xa0`) og parenteser.

### Skript for å regenerere kartdata
Hvis gater legges til i Fasit-fanen, kjør dette i Google Colab for å oppdatere `oslo_geometri.geojson`:

```python
# --- FULLSTENDIG KART-GENERATOR (VERSJON 15) ---
!pip install odfpy requests pandas
import pandas as pd
import requests
import json
import re
import unicodedata
from google.colab import files

URL = "https://github.com/runenorman/gatelangs/raw/main/Gater%20Transport%20%2020260419.ods"

def super_rens(s):
    if not s or pd.isna(s): return ""
    s = unicodedata.normalize('NFC', str(s)).lower()
    s = re.sub(r'\(.*\)', '', s)
    return "".join(c for c in s if c.isalnum())

def hent_gatenavn_fra_ods(url):
    df = pd.read_excel(url, sheet_name=1, engine="odf", header=None)
    match_register = {}
    for index, row in df.head(587).iterrows():
        for cell in row:
            v = str(cell).strip()
            if len(v) > 2 and v not in ["nan", "10:23:00", "Historiske", "Gate"]:
                match_register[super_rens(v)] = v 
    return match_register

def hent_geometri_oslo_komplett(match_register):
    url = "https://overpass-api.de/api/interpreter"
    query = '[out:json][timeout:300];area["name"="Oslo"]["admin_level"="7"]->.oslo;way(area.oslo)["highway"]["name"];out geom;'
    headers = {'User-Agent': 'GatelangsOslo/6.0'}
    response = requests.post(url, data={'data': query}, headers=headers, timeout=320)
    osm_data = response.json()
    features = []
    for element in osm_data.get('elements', []):
        name = element.get('tags', {}).get('name')
        nøkkel = super_rens(name)
        if nøkkel in match_register:
            if 'geometry' in element:
                coords = [[p['lon'], p['lat']] for p in element['geometry']]
                features.append({"type": "Feature", "properties": {"name": match_register[nøkkel]},
                                 "geometry": {"type": "LineString", "coordinates": coords}})
    return features

ark_reg = hent_gatenavn_fra_ods(URL)
features = hent_geometri_oslo_komplett(ark_reg)
with open('oslo_geometri.geojson', 'w', encoding='utf-8') as f:
    json.dump({"type": "FeatureCollection", "features": features}, f, ensure_ascii=False)
files.download('oslo_geometri.geojson')
