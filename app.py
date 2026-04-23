import streamlit as st
import pandas as pd
import folium
from streamlit_folium import folium_static
import json
import re
import unicodedata
from folium.plugins import LocateControl
import time

# --- KONFIGURASJON OG STIL ---
st.set_page_config(page_title="Gatelangs v3.1", layout="wide")

# Forminsk overskriften for å spare plass på mobil
st.markdown("#### 🏃‍♂️ Gatelangs Oslo v3.1")

def super_rens(s):
    """Normaliserer navn for sammenligning."""
    if not s or pd.isna(s): return ""
    s = unicodedata.normalize('NFC', str(s)).lower()
    s = re.sub(r'\(.*\)', '', s)
    return "".join(c for c in s if c.isalnum())

# --- DATA-LASTING MED CACHING OG FEEDBACK ---
@st.cache_data(show_spinner=False)
def last_og_prosesser_data():
    filnavn = "Gater Transport  20260419.ods"
    
    # 1. Last GeoJSON (Kartgrunnlag)
    try:
        with open("oslo_geometri.geojson", "r", encoding="utf-8") as f:
            geo_data = json.load(f)
    except:
        return None, None, None

    # 2. Last Logg (Fane 1)
    try:
        df_logg = pd.read_excel(filnavn, sheet_name=0, engine="odf")
        # Kolonne B (index 1) er navn, Kolonne O (index 14) er dato
        logg_data = {}
        for _, row in df_logg.iloc[3:].iterrows():
            g_navn = str(row.iloc[1]).strip()
            nøkkel = super_rens(g_navn)
            raw_dato = row.iloc[14]
            
            # Prøv å tolke dato
            try:
                dato = pd.to_datetime(raw_dato).date()
            except:
                dato = pd.Timestamp('2019-01-01').date() # Fallback for gamle rader
            
            if nøkkel:
                # Behold eldste dato hvis duplikat
                if nøkkel not in logg_data or dato < logg_data[nøkkel]:
                    logg_data[nøkkel] = dato
    except:
        logg_data = {}

    return geo_data, logg_data

# Vis "Vennlig venting" bare når cachen er tom
if 'data_klar' not in st.session_state:
    with st.status("🚀 Initierer Oslo...", expanded=True) as status:
        st.write("Laster inn kartdata...")
        geo_data, logg_data = last_og_prosesser_data()
        st.write(f"Sjekker {len(geo_data['features'])} gater mot loggen...")
        time.sleep(0.5) # Så man rekker å se meldingen
        status.update(label="✅ Alt klart!", state="complete", expanded=False)
        st.session_state['data_klar'] = True
else:
    geo_data, logg_data = last_og_prosesser_data()

if not geo_data:
    st.error("Kunne ikke laste data. Sjekk at filene ligger på GitHub.")
    st.stop()

# --- LOGIKK FOR SØK OG ZOOM ---
if 'map_center' not in st.session_state:
    st.session_state['map_center'] = [59.915, 10.74]
    st.session_state['map_zoom'] = 13

# --- SIDEBAR ---
st.sidebar.markdown("### 📊 Status")

# 1. TIDS-SLIDER
alle_datoer = sorted(list(logg_data.values()))
min_d = alle_datoer[0] if alle_datoer else pd.Timestamp('2019-01-01').date()
max_d = alle_datoer[-1] if alle_datoer else pd.Timestamp.now().date()

st.sidebar.write("📅 **Tidslinje**")
valgt_dato = st.sidebar.slider(
    "Fremdrift frem til:",
    min_value=min_d,
    max_value=max_d,
    value=max_d,
    format="DD.MM.YY"
)

# Finn gåtte gater per valgt dato
gåtte_nå = {k for k, v in logg_data.items() if v <= valgt_dato}

# 2. STATISTIKK
unike_gater_i_kart = {}
for f in geo_data['features']:
    n = f['properties']['name']
    unike_gater_i_kart[super_rens(n)] = {
        'navn': n,
        'coords': f['geometry']['coordinates'][0][::-1] if f['geometry']['type'] == "LineString" else None
    }

total = len(unike_gater_i_kart)
gått = len(unike_gater_i_kart.keys() & gåtte_nå)
prosent = (gått / total * 100) if total > 0 else 0

st.sidebar.metric("Gater i Oslo", total)
st.sidebar.metric("Gater gått", gått, delta=f"{prosent:.1f}%")
st.sidebar.progress(prosent / 100)

# 3. SØK OG ZOOM
st.sidebar.markdown("---")
søk = st.sidebar.text_input("🔍 Finn og zoom til gate:")
if søk:
    s_rens = super_rens(søk)
    if s_rens in unike_gater_i_kart:
        match = unike_gater_i_kart[s_rens]
        st.session_state['map_center'] = match['coords']
        st.session_state['map_zoom'] = 16
        if s_rens in gåtte_nå:
            st.sidebar.success(f"✅ Gått!")
        else:
            st.sidebar.warning(f"❌ Ikke gått")
    else:
        st.sidebar.info("Fant ikke gata.")

# --- KARTET ---
m = folium.Map(
    location=st.session_state['map_center'], 
    zoom_start=st.session_state['map_zoom'], 
    tiles="cartodbpositron",
    control_scale=True
)

# GPS-knapp
LocateControl(
    locateOptions={'enableHighAccuracy': True},
    keepCurrentZoomLevel=True,
    strings={"title": "Hvor er jeg?", "popup": "Du er her"}
).add_to(m)

# Tegn gatene
for feature in geo_data['features']:
    n = feature['properties']['name']
    er_gått = super_rens(n) in gåtte_nå
    
    folium.GeoJson(
        feature,
        style_function=lambda x, f="green" if er_gått else "red": {
            "color": f,
            "weight": 3 if f == "green" else 2,
            "opacity": 0.7 if f == "green" else 0.5
        },
        tooltip=n
    ).add_to(m)

folium_static(m, width=1000, height=650)

st.caption(f"Viser status frem til {valgt_dato.strftime('%d.%m.%Y')}")
