# Installer verktøyet som trengs for å lese .ods-filer
!pip install odfpy

import pandas as pd
import requests
import json
import time
from datetime import datetime

# --- KONFIGURASJON ---
# Vi henter fila di direkte fra GitHub
URL = "https://github.com/runenorman/gatelangs/raw/main/Gater%20Transport%20%2020260419.ods"

def hent_gatenavn_fra_ods(url):
    print("Henter gatenavn fra GitHub...")
    # Vi bruker fane 2 (index 1)
    df = pd.read_excel(url, sheet_name=1, engine="odf", header=None)
    
    # Vi går gjennom rutenettet og henter alle strenger som ser ut som gatenavn
    gater = []
    # Vi sjekker alle celler frem til linje 587
    for index, row in df.head(587).iterrows():
        for cell in row:
            val = str(cell).strip()
            # Ignorer overskrifter (én bokstav), tomme celler, dato-feil og historiske gater
            if len(val) > 2 and val not in ["nan", "10:23:00", "Historiske"]:
                gater.append(val)
    
    unike_gater = sorted(list(set(gater)))
    print(f"Fant {len(unike_gater)} unike gatenavn i regnearket.")
    return unike_gater

def hent_geometri_fra_osm(gateliste):
    overpass_url = "http://overpass-api.de/api/interpreter"
    geo_json_features = []
    mangler = []
    
    print("Kontakter OpenStreetMap (dette tar et par minutter)...")
    
    query = """
    [out:json][timeout:90];
    area(3600062422)->.oslo;
    way["highway"]["name"](area.oslo);
    out geom;
    """
    
    response = requests.get(overpass_url, params={'data': query})
    if response.status_code != 200:
        print("Feil ved kontakt med OSM. Prøver igjen om litt...")
        return None
        
    osm_data = response.json()
    
    osm_veier = {}
    for element in osm_data.get('elements', []):
        name = element.get('tags', {}).get('name')
        if name:
            if name not in osm_veier:
                osm_veier[name] = []
            osm_veier[name].append(element)

    for gate in gateliste:
        if gate in osm_veier:
            for osm_item in osm_veier[gate]:
                coordinates = [[p['lon'], p['lat']] for p in osm_item['geometry']]
                feature = {
                    "type": "Feature",
                    "properties": {"name": gate},
                    "geometry": {
                        "type": "LineString",
                        "coordinates": coordinates
                    }
                }
                geo_json_features.append(feature)
        else:
            mangler.append(gate)
            
    return {"type": "FeatureCollection", "features": geo_json_features}, mangler

# --- KJØRING ---
try:
    gater = hent_gatenavn_fra_ods(URL)
    geojson, ikke_funnet = hent_geometri_fra_osm(gater)

    # Lagre fila
    with open('oslo_geometri.geojson', 'w', encoding='utf-8') as f:
        json.dump(geojson, f, ensure_ascii=False)

    print("\n--- FERDIG! ---")
    print(f"Suksess: {len(gater) - len(ikke_funnet)} gater funnet i OSM.")
    print(f"Mangler: {len(ikke_funnet)} gater ble ikke funnet.")
    
    if ikke_funnet:
        print("\nTopp 20 gater som mangler (sjekk skrivemåte i regnearket):")
        for m i ikke_funnet[:20]:
            print(f"- {m}")

    # Last ned fila til din PC automatisk
    from google.colab import files
    files.download('oslo_geometri.geojson')
except Exception as e:
    print(f"En feil oppstod: {e}")
