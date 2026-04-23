import streamlit as st
import pandas as pd
import folium
from streamlit_folium import folium_static
import json
import re
import unicodedata
from folium.plugins import LocateControl
import datetime

# --- KONFIGURASJON ---
st.set_page_config(page_title="Gatelangs Oslo v3.1", layout="wide")

# Liten overskrift for å spare plass på mobil
st.markdown("#### 🏃‍♂️ Gatelangs Oslo v3.1")

def super_rens(s):
    """Normaliserer navn for sammenligning."""
    if not s or pd.isna(s): return ""
    s = unicodedata.normalize('NFC', str(s)).lower()
    s = re.sub(r'\(.*\)', '', s)
    return "".join(c for c in s if c.isalnum())

# --- DATA-LASTING ---
@st.cache_data(show_spinner=False)
def last_og_prosesser_data():
    filnavn = "Gater Transport 20260419.ods"
    default_dato = datetime.date(2019, 1, 1) # Din foreslåtte "fallback" dato
    
    try:
        # 1. Last GeoJSON
        with open("oslo_geometri.geojson", "r", encoding="utf-8") as f:
            geo_data = json.load(f)

        # 2. Last Logg (Fane 1)
        df_logg = pd.read_excel(filnavn, sheet_name=0, engine="odf")
        
        logg_dict = {}
        # Vi går gjennom kolonne B (navn) og kolonne O (dato)
        for _, row in df_logg.iloc[3:].iterrows():
            g_navn = str(row.iloc[1]).strip()
            nøkkel = super_rens(g_navn)
            raw_dato = row.iloc[14]
            
            # DATOLOGIKK (Din foreslåtte forbedring)
            try:
                pd_dato = pd.to_datetime(raw_dato)
                if pd.isna(pd_dato):
                    dato = default_dato
                else:
                    dato = pd_dato.date()
            except:
                dato = default_dato
            
            if nøkkel:
                # Behold eldste dato hvis gata er logget flere ganger
                if nøkkel not in logg_dict or dato < logg_dict[nøkkel]:
                    logg_dict[nøkkel] = dato
                    
        return geo_data, logg_dict
    except Exception as e:
        return None, str(e)

# --- INITIERING MED VENNLIG VENTING ---
if 'init_ferdig' not in st.session_state:
    with st.status("🚀 Initierer Oslo...", expanded=True) as status:
        st.write("Laster gater fra fasit...")
        geo_data, logg_data = last_og_prosesser_data()
        if geo_data:
            st.write(f"Matcher {len(geo_data['features'])} gater mot loggen...")
        status.update(label="✅ Alt klart!", state="complete", expanded=False)
        st.session_state['init_ferdig'] = True
else:
    geo_data, logg_data = last_og_prosesser_data()

if not geo_data:
    st.error("Kunne ikke laste data. Sjekk filnavnet på GitHub.")
    st.stop()

# --- SIDEBAR (STATISTIKK OG FILTER) ---
st.sidebar.title("📊 Gatelangs-status")

# 1. TIDS-SLIDER
alle_datoer = sorted([d for d in logg_data.values()])
min_d = datetime.date(2019, 1, 1)
max_d = datetime.date.today()

st.sidebar.write("📅 **Tidsreise**")
valgt_dato = st.sidebar.slider("Se fremdrift frem til:", min_d, max_d, max_d, format="DD.MM.YY")

# Finn gåtte gater basert på slideren
gåtte_nøkler_nå = {k for k, v in logg_data.items() if v <= valgt_dato}

# 2. STATISTIKK OG BYDELER
gater_i_kart = {}
for f in geo_data['features']:
    n = f['properties']['name']
    n_rens = super_rens(n)
    if n_rens not in gater_i_kart:
        gater_i_kart[n_rens] = {
            'navn': n, 
            'coords': f['geometry']['coordinates'][0][::-1] if f['geometry']['type'] == "LineString" else None
        }

total = len(gater_i_kart)
gått = len(gater_i_kart.keys() & gåtte_nøkler_nå)
prosent = (gått / total * 100) if total > 0 else 0

st.sidebar.metric("Total fremdrift", f"{prosent:.1f}%", f"{gått} av {total} gater")
st.sidebar.progress(prosent / 100)

# 3. SØK OG ZOOM
st.sidebar.markdown("---")
søk = st.sidebar.text_input("🔍 Finn og zoom til gate:")
# Default senter hvis ingen søk
map_center = [59.915, 10.74]
map_zoom = 12

if søk:
    s_rens = super_rens(søk)
    if s_rens in gater_i_kart:
        if gater_i_kart[s_rens]['coords']:
            map_center = gater_i_kart[s_rens]['coords']
            map_zoom = 16
            st.sidebar.success(f"Zoomer til {gater_i_kart[s_rens]['navn']}")
    else:
        st.sidebar.warning("Fant ikke gata i Oslo-listen.")

# --- KARTET ---
m = folium.Map(location=map_center, zoom_start=map_zoom, tiles="cartodbpositron")

# NYTT: Blå prikk (GPS)
LocateControl(
    locateOptions={'enableHighAccuracy': True},
    keepCurrentZoomLevel=True,
    strings={"title": "Hvor er jeg?", "popup": "Du er her"}
).add_to(m)

# Tegn gatene fra GeoJSON
for feature in geo_data['features']:
    n = feature['properties']['name']
    er_gått = super_rens(n) in gåtte_nøkler_nå
    farge = "green" if er_gått else "red"
    
    folium.GeoJson(
        feature,
        style_function=lambda x, f=farge: {
            "color": f,
            "weight": 3 if f == "green" else 2,
            "opacity": 0.7 if f == "green" else 0.4
        },
        tooltip=n
    ).add_to(m)

folium_static(m, width=1000, height=700)

st.caption(f"Viser gåtte gater frem til {valgt_dato.strftime('%d.%m.%Y')}. Manglende datoer i regneark er satt til 2019.")
