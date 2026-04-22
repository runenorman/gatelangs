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
    try:
        # Les gåtte gater (Fane 1)
        df_logg = pd.read_excel(filnavn, sheet_name=0, engine="odf")
        # Rens kolonne B (index 1) for gåtte gater - vi starter fra rad 4 (index 3)
        gåtte_gater = set(df_logg.iloc[3:, 1].dropna().astype(str).str.strip())
    except Exception as e:
        st.error(f"Feil ved lesing av regneark: {e}")
        gåtte_gater = set()
    
    # Last geometri (denne fila lager du i Colab nå)
    try:
        with open("oslo_geometri.geojson", "r", encoding="utf-8") as f:
            geo_data = json.load(f)
    except:
        geo_data = None
        
    return gåtte_gater, geo_data

gåtte_gater, geo_data = last_data()

# --- SIDEBAR (STATISTIKK) ---
st.sidebar.title("📊 Statistikk")

if geo_data:
    # Finn unike gatenavn i GeoJSON-fila
    unike_i_kart = set(f['properties']['name'] for f in geo_data['features'])
    total_gater = len(unike_i_kart)
    
    # Finn ut hvilke av disse som finnes i gåtte_gater
    gåtte_treff = unike_i_kart.intersection(gåtte_gater)
    antall_gått = len(gåtte_treff)
    
    prosent = (antall_gått / total_gater * 100) if total_gater > 0 else 0

    st.sidebar.metric("Gater i Oslo (Fasit)", total_gater)
    st.sidebar.metric("Gater gått", antall_gått)
    st.sidebar.progress(prosent / 100)
    st.sidebar.write(f"Dere har gått **{prosent:.1f}%** av Oslo!")
    
    # Søkefunksjon
    st.sidebar.markdown("---")
    søk = st.sidebar.text_input("Søk etter gate:")
    if søk:
        if søk in gåtte_gater:
            st.sidebar.success(f"✅ {søk} er GÅTT!")
        elif søk in unike_i_kart:
            st.sidebar.warning(f"❌ {søk} er IKKE GÅTT ennå.")
        else:
            st.sidebar.info(f"Fant ikke '{søk}' i fasiten.")

# --- HOVEDSKJERM ---
st.title("🏃‍♂️ Gatelangs Oslo")

if not geo_data:
    st.warning("Venter på kartdata... Vennligst kjør Colab-skriptet og last opp 'oslo_geometri.geojson' til GitHub.")
else:
    # Lag kartet (Sentrer på Oslo)
    m = folium.Map(location=[59.915, 10.74], zoom_start=13, tiles="cartodbpositron")

    # Tegn gatene
    for feature in geo_data['features']:
        gate_navn = feature['properties']['name']
        er_gått = gate_navn in gåtte_gater
        farge = "green" if er_gått else "red"
        
        folium.GeoJson(
            feature,
            style_function=lambda x, f=farge: {
                "color": f,
                "weight": 4 if er_gått else 2,
                "opacity": 0.8
            },
            tooltip=gate_navn
        ).add_to(m)

    folium_static(m, width=1100, height=700)

st.caption("Data fra OpenStreetMap og gå-gruppas regneark.")
