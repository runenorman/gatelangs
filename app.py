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

# --- INITIALISERING ---
if 'center' not in st.session_state:
    st.session_state.center = [59.915, 10.74]
    st.session_state.zoom = 12

if 'klar' not in st.session_state:
    with st.status("🚀 Initierer Oslo...", expanded=True) as status:
        geo_data, logg_data, feil = last_og_prosesser_data()
        if feil: st.error(feil); st.stop()
        unike_i_kart = {super_rens(f['properties']['name']) for f in
