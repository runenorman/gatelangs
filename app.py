import streamlit as st
import pandas as pd
import folium
from streamlit_folium import folium_static
import json

st.set_page_config(page_title="Gatelangs Oslo 3.0", layout="wide")

# --- DATA-LASTING ---
@st.cache_data
def last_data():
    filnavn = "Gater Transport  20260419.ods"
    # Les gåtte gater (Fane 1)
    df_logg = pd.read_excel(filnavn, sheet_name=0, engine="odf")
    # Rens kolonne B for gåtte gater
    gåtte_gater = set(df_logg.iloc[3:, 1].dropna().astype(str).str.strip())
    
    # Last geometri (denne fila lager jeg til deg nå)
    try:
        with open("oslo_geometri.geojson", "r", encoding="utf-8") as f:
            geo_data = json.load(f)
    except:
        geo_data = None
        
    return gåtte_gater, geo_data

gåtte_gater, geo_data = last_data()

# --- SIDEBAR (STATISTIKK) ---
st.sidebar.title("📊 Statistikk")
total_gater = len(geo_data['features']) if geo_data else 0
antall_gått = 0

if geo_data:
    # Sjekk hvilke gater i GeoJSON som finnes i loggen
    for feature in geo_data['features']:
        if feature['properties']['name'] in gåtte_gater:
            antall_gått += 1

prosent = (antall_gått / total_gater * 100) if total_gater > 0 else 0

st.sidebar.metric("Gater totalt", total_gater)
st.sidebar.metric("Gater gått", antall_gått)
st.sidebar.progress(prosent / 100)
st.sidebar.write(f"Du har gått **{prosent:.1f}%** av Oslo!")

# --- HOVEDSKJERM ---
st.title("🏃‍♂️ Gatelangs Oslo")

if not geo_data:
    st.warning("Venter på kartdata... Last opp 'oslo_geometri.geojson' til GitHub.")
else:
    # Lag kartet
    m = folium.Map(location=[59.91, 10.75], zoom_start=12, tiles="cartodbpositron")

    # Tegn gatene
    for feature in geo_data['features']:
        gate_navn = feature['properties']['name']
        er_gått = gate_navn in gåtte_gater
        farge = "green" if er_gått else "red"
        
        folium.GeoJson(
            feature,
            style_function=lambda x, f=farge: {
                "color": f,
                "weight": 3,
                "opacity": 0.7
            },
            tooltip=gate_navn
        ).add_to(m)

    folium_static(m, width=1000, height=600)

st.caption("Data fra OpenStreetMap og gå-gruppas regneark.")
