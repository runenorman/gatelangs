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
        alle_filer = os.listdir(".")
        ods_filer = [f for f in alle_filer if f.endswith(".ods")]
        if not ods_filer: return None, None, None, "Mangler .ods-fil"
        
        # 1. Les Logg (Fane 1)
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
        
        # 2. Les Fasit (Fane 2) - KUN område B4:F585
        # Kolonne B:F er index 1:6. Rad 4:585 er index 3:585.
        df_fasit_raw = pd.read_excel(ods_filer[0], sheet_name=1, engine="odf", header=None)
        grid = df_fasit_raw.iloc[3:585, 1:6]
        
        fasit_nøkler = {} # {rens_navn: original_navn}
        for val in grid.values.flatten():
            v_str = str(val).strip()
            if len(v_str) > 2 and v_str.lower() != "nan":
                nøkkel = super_rens(v_str)
                if nøkkel and not nøkkel.isdigit():
                    fasit_nøkler[nøkkel] = v_str

        # 3. Les GeoJSON
        with open("oslo_geometri.geojson", "r", encoding="utf-8") as f:
            geo_data = json.load(f)
            
        return geo_data, logg_dict, fasit_nøkler, None
    except Exception as e:
        return None, None, None, str(e)

# --- INITIALISERING ---
if 'center' not in st.session_state:
    st.session_state.center = [59.915, 10.74]
    st.session_state.zoom = 12

if 'klar' not in st.session_state:
    with st.status("🚀 Initierer Oslo...", expanded=True) as status:
        geo_data, logg_data, fasit_nøkler, feil = last_og_prosesser_data()
        if feil: st.error(feil); st.stop()
        status.update(label=f"✅ {len(fasit_nøkler)} gater fra fasit klare!", state="complete", expanded=False)
        st.session_state['klar'] = True
else:
    geo_data, logg_data, fasit_nøkler, feil = last_og_prosesser_data()

# --- SIDEBAR ---
st.sidebar.title("📊 Status")
valgt_dato = st.sidebar.slider("Fremdrift til:", datetime.date(2019,1,1), datetime.date.today(), datetime.date.today(), format="DD.MM.YY")
gaatte_naa = {k for k, v in logg_data.items() if v <= valgt_dato}

# Finn koordinater for de gatene som er i rutenettet
gater_i_kart_info = {}
features_å_vise = []

for f in geo_data['features']:
    n_org = f['properties']['name']
    n_rens = super_rens(n_org)
    
    # KUN vis gater som er innenfor rutenettet B4:F585
    if n_rens in fasit_nøkler:
        features_å_vise.append(f)
        if n_rens not in gater_i_kart_info:
            g_type = f['geometry']['type']
            coords = f['geometry']['coordinates']
            try:
                if g_type == "Point": p = coords
                elif g_type == "LineString": p = coords[0]
                else: p = coords[0][0]
                gater_i_kart_info[n_rens] = {'navn': fasit_nøkler[n_rens], 'coords': [p[1], p[0]]}
            except: continue

total_gater = len(fasit_nøkler)
antall_gaatt = len(fasit_nøkler.keys() & gaatte_naa)
prosent = (antall_gaatt / total_gater * 100) if total_gater > 0 else 0

st.sidebar.metric("Gater i rutenett", total_gater)
st.sidebar.metric("Gater gått", antall_gaatt, delta=f"{prosent:.1f}%")
st.sidebar.progress(prosent / 100)

# Autocomplete Søk
st.sidebar.markdown("---")
alfabetisk_liste = sorted(list(fasit_nøkler.values()))
valgt_gate = st.sidebar.selectbox("🔍 Finn og zoom til gate:", options=alfabetisk_liste, index=None, placeholder="Skriv gatenavn...")

if valgt_gate:
    r_valgt = super_rens(valgt_gate)
    if r_valgt in gater_i_kart_info:
        st.session_state.center = gater_i_kart_info[r_valgt]['coords']
        st.session_state.zoom = 16
        status_txt = "✅ GÅTT" if r_valgt in gaatte_naa else "❌ IKKE GÅTT"
        st.sidebar.info(f"{valgt_gate}: {status_txt}")
    else:
        st.sidebar.warning(f"{valgt_gate}: Ingen kartdata funnet.")

# --- KARTET ---
m = folium.Map(location=st.session_state.center, zoom_start=st.session_state.zoom, tiles="cartodbpositron")
LocateControl(auto_start=False, strings={"title": "Hvor er jeg?"}).add_to(m)

def farge_logikk(feature):
    is_done = super_rens(feature['properties']['name']) in gaatte_naa
    return {'color': 'green' if is_done else 'red', 'weight': 3 if is_done else 2, 'opacity': 0.7}

folium.GeoJson(
    {"type": "FeatureCollection", "features": features_å_vise},
    style_function=farge_logikk,
    tooltip=folium.GeoJsonTooltip(fields=['name'], labels=False),
    marker=folium.CircleMarker(radius=4, fill=True)
).add_to(m)

folium_static(m, width=1000, height=750)
st.caption(f"Viser rutenettet B4:F585 per {valgt_dato.strftime('%d.%m.%Y')}.")
