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

# CSS-fix: Hindrer at zoom-knapper forsvinner og trimmer topp-plass
st.markdown("""
    <style>
    .stMain { padding-top: 0.5rem; }
    .leaflet-top { top: 10px !important; }
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
def last_data():
    try:
        alle_filer = os.listdir(".")
        ods_filer = [f for f in alle_filer if f.endswith(".ods")]
        if not ods_filer: return None, None, "Mangler .ods-fil"
        
        df_logg = pd.read_excel(ods_filer[0], sheet_name=0, engine="odf")
        logg_dict = {}
        for _, row in df_logg.iloc[3:].iterrows():
            n = super_rens(row.iloc[1])
            try:
                d = pd.to_datetime(row.iloc[14]).date()
                if pd.isna(d): d = datetime.date(2019,1,1)
            except: d = datetime.date(2019,1,1)
            if n:
                if n not in logg_dict or d < logg_dict[n]: logg_dict[n] = d
        
        with open("oslo_geometri.geojson", "r", encoding="utf-8") as f:
            geo_data = json.load(f)
            
        return geo_data, logg_dict, None
    except Exception as e:
        return None, None, str(e)

# --- INITIALISERING AV KART-STATUR ---
# Bruker session_state så kartet "husker" zoom/senter når du søker
if 'center' not in st.session_state:
    st.session_state.center = [59.915, 10.74]
    st.session_state.zoom = 12

if 'klar' not in st.session_state:
    with st.status("🚀 Initierer Oslo...", expanded=True) as status:
        geo_data, logg_data, feil = last_data()
        if feil: st.error(feil); st.stop()
        status.update(label=f"✅ {len(geo_data['features'])} gater klare!", state="complete", expanded=False)
        st.session_state['klar'] = True
else:
    geo_data, logg_data, feil = last_data()

# --- SIDEBAR ---
st.sidebar.title("📊 Status")

min_d = datetime.date(2019, 1, 1)
max_d = datetime.date.today()
valgt_dato = st.sidebar.slider("Fremdrift til:", min_d, max_d, max_d, format="DD.MM.YY")

gåtte_nå = {k for k, v in logg_data.items() if v <= valgt_dato}

# Bygg register for søk og statistikk
gater_i_kart = {}
bydels_stat = {}

for f in geo_data['features']:
    n = f['properties']['name']
    r = super_rens(n)
    b = f['properties'].get('bydel', 'Oslo')
    
    if r not in gater_i_kart:
        # Lagre koordinater for zoom (vi tar det første punktet i linja)
        coords = f['geometry']['coordinates']
        if f['geometry']['type'] == "LineString":
            p = coords[0]
        else: # MultiLineString
            p = coords[0][0]
        gater_i_kart[r] = {'navn': n, 'coords': [p[1], p[0]]}
        
    if b not in bydels_stat: bydels_stat[b] = {'total': 0, 'gått': 0}
    bydels_stat[b]['total'] += 1
    if r in gåtte_nå:
        bydels_stat[b]['gått'] += 1

total = len(gater_i_kart)
gått = len(gater_i_kart.keys() & gåtte_nå)
prosent = (gått/total*100) if total > 0 else 0

st.sidebar.metric("Fremdrift", f"{prosent:.1f}%", f"{gått} / {total} gater")
st.sidebar.progress(prosent / 100)

# SØK-FUNKSJONALITET
st.sidebar.markdown("---")
søk = st.sidebar.text_input("🔍 Finn og zoom til gate:")
if søk:
    s_rens = super_rens(søk)
    if s_rens in gater_i_kart:
        st.session_state.center = gater_i_kart[s_rens]['coords']
        st.session_state.zoom = 16
        status_ikon = "✅ GÅTT" if s_rens in gåtte_nå else "❌ IKKE GÅTT"
        st.sidebar.success(f"{gater_i_kart[s_rens]['navn']}: {status_ikon}")
    else:
        st.sidebar.error(f"Finner ikke '{søk}' i fasiten.")

# BYDELSSTATISTIKK
with st.sidebar.expander("🏘️ Se per bydel"):
    for b, s in sorted(bydels_stat.items()):
        p_bydel = (s['gått']/s['total']*100)
        st.write(f"**{b}**: {p_bydel:.0f}% ({s['gått']}/{s['total']})")

# --- KARTET ---
m = folium.Map(
    location=st.session_state.center, 
    zoom_start=st.session_state.zoom, 
    tiles="cartodbpositron"
)

# GPS-knapp
LocateControl(auto_start=False, strings={"title": "Hvor er jeg?"}).add_to(m)

# Farge-funksjon
def style_f(feature):
    er_gått = super_rens(feature['properties']['name']) in gåtte_nå
    return {
        'color': 'green' if er_gått else 'red',
        'weight': 3 if er_gått else 2,
        'opacity': 0.7 if er_gått else 0.4
    }

# Tegn hele Oslo
folium.GeoJson(
    geo_data,
    style_function=style_f,
    tooltip=folium.GeoJsonTooltip(fields=['name'], labels=False)
).add_to(m)

folium_static(m, width=1000, height=750)
