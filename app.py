import streamlit as st
import pandas as pd
import folium
from streamlit_folium import folium_static
import json
import re
import unicodedata
from folium.plugins import LocateControl
import datetime
import os

# --- KONFIGURASJON ---
st.set_page_config(page_title="Gatelangs Oslo v3.1", layout="wide")

# CSS for å rydde opp i marginer og sikre at zoom-knapper er synlige
st.markdown("""
    <style>
    .stMain { padding-top: 0.5rem; }
    [data-testid="stSidebar"] { padding-top: 0.5rem; }
    /* Forsøk på å tvinge zoom-kontroller til toppen */
    .leaflet-top { top: 10px !important; z-index: 999 !important; }
    </style>
    """, unsafe_allow_html=True)

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
    try:
        # 1. Finn og les .ods-fil automatisk
        alle_filer = os.listdir(".")
        ods_filer = [f for f in alle_filer if f.endswith(".ods")]
        if not ods_filer: return None, None, "Mangler .ods-fil i mappen."
        
        df_logg = pd.read_excel(ods_filer[0], sheet_name=0, engine="odf")
        logg_dict = {}
        # Kolonne B (1) er navn, Kolonne O (14) er dato
        for _, row in df_logg.iloc[3:].iterrows():
            n = super_rens(row.iloc[1])
            try:
                d = pd.to_datetime(row.iloc[14]).date()
                if pd.isna(d): d = datetime.date(2019,1,1)
            except: d = datetime.date(2019,1,1)
            if n:
                if n not in logg_dict or d < logg_dict[n]: logg_dict[n] = d
        
        # 2. Les GeoJSON
        if "oslo_geometri.geojson" not in alle_filer:
            return None, None, "Mangler 'oslo_geometri.geojson'."
            
        with open("oslo_geometri.geojson", "r", encoding="utf-8") as f:
            geo_data = json.load(f)
            
        return geo_data, logg_dict, None
    except Exception as e:
        return None, None, f"Feil ved lasting: {str(e)}"

# --- INITIALISERING ---
if 'center' not in st.session_state:
    st.session_state.center = [59.915, 10.74]
    st.session_state.zoom = 12

if 'klar' not in st.session_state:
    with st.status("🚀 Initierer Oslo...", expanded=True) as status:
        geo_data, logg_data, feil = last_og_prosesser_data()
        if feil: st.error(feil); st.stop()
        
        unike_i_kart = {super_rens(f['properties']['name']) for f in geo_data['features']}
        status.update(label=f"✅ {len(unike_i_kart)} gater klare!", state="complete", expanded=False)
        st.session_state['klar'] = True
else:
    geo_data, logg_data, feil = last_og_prosesser_data()

# --- SIDEBAR ---
st.sidebar.title("📊 Status")

# 1. Tids-slider
min_d = datetime.date(2019, 1, 1)
max_d = datetime.date.today()
valgt_dato = st.sidebar.slider("Fremdrift til:", min_d, max_d, max_d, format="DD.MM.YY")

gaatte_naa = {k for k, v in logg_data.items() if v <= valgt_dato}

# 2. Statistikk og Register for Autocomplete
gater_i_kart_info = {} 
unike_navn_i_kart = set()

for f in geo_data['features']:
    n = f['properties']['name']
    r = super_rens(n)
    unike_navn_i_kart.add(r)
    
    if r not in gater_i_kart_info:
        coords = f['geometry']['coordinates']
        p = coords[0] if isinstance(coords[0][0], (int, float)) else coords[0][0]
        gater_i_kart_info[r] = {'navn': n, 'coords': [p[1], p[0]]}

total_gater = len(unike_navn_i_kart)
antall_gaatt = len(unike_navn_i_kart & gaatte_naa)
prosent = (antall_gaatt / total_gater * 100) if total_gater > 0 else 0

# Metrics (Uten bakgrunnsfarge for maksimal lesbarhet)
st.sidebar.metric("Gater i fasit", total_gater)
st.sidebar.metric("Gater gått", antall_gaatt, delta=f"{prosent:.1f}%")
st.sidebar.progress(prosent / 100)

# 3. Autocomplete Søk
st.sidebar.markdown("---")
alfabetisk_liste = sorted([info['navn'] for info in gater_i_kart_info.values()])

valgt_gate = st.sidebar.selectbox(
    "🔍 Finn og zoom til gate:",
    options=alfabetisk_liste,
    index=None,
    placeholder="Skriv gatenavn..."
)

if valgt_gate:
    r_valgt = super_rens(valgt_gate)
    if r_valgt in gater_i_kart_info:
        st.session_state.center = gater_i_kart_info[r_valgt]['coords']
        st.session_state.zoom = 16
        status_tekst = "✅ GÅTT" if r_valgt in gaatte_naa else "❌ IKKE GÅTT"
        st.sidebar.info(f"{valgt_gate}: {status_tekst}")

# --- KARTET ---
m = folium.Map(
    location=st.session_state.center, 
    zoom_start=st.session_state.zoom, 
    tiles="cartodbpositron"
)

LocateControl(auto_start=False, strings={"title": "Hvor er jeg?"}).add_to(m)

def farge_logikk(feature):
    name_rens = super_rens(feature['properties']['name'])
    is_done = name_rens in gaatte_naa
    return {
        'color': 'green' if is_done else 'red',
        'weight': 3 if is_done else 2,
        'opacity': 0.7 if is_done else 0.4
    }

folium.GeoJson(
    geo_data,
    style_function=farge_logikk,
    tooltip=folium.GeoJsonTooltip(fields=['name'], labels=False)
).add_to(m)

folium_static(m, width=1000, height=750)

st.caption(f"Status per {valgt_dato.strftime('%d.%m.%Y')}.")
