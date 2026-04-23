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
st.markdown("#### 🏃‍♂️ Gatelangs Oslo v3.1")

def super_rens(s):
    if not s or pd.isna(s): return ""
    s = unicodedata.normalize('NFC', str(s)).lower()
    s = re.sub(r'\(.*\)', '', s)
    return "".join(c for c in s if c.isalnum())

# --- DATA-LASTING ---
@st.cache_data(show_spinner=False)
def last_data():
    try:
        # Finn .ods-fil
        alle_filer = os.listdir(".")
        ods_filer = [f for f in alle_filer if f.endswith(".ods")]
        if not ods_filer: return None, None, "Mangler .ods-fil"
        
        # Les logg
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
        
        # Les GeoJSON
        with open("oslo_geometri.geojson", "r", encoding="utf-8") as f:
            geo_data = json.load(f)
            
        return geo_data, logg_dict, None
    except Exception as e:
        return None, None, str(e)

# --- INITIERING ---
if 'klar' not in st.session_state:
    with st.status("🚀 Initierer Oslo...", expanded=True) as status:
        geo_data, logg_data, feil = last_data()
        if feil: st.error(feil); st.stop()
        status.update(label="✅ Kartet er klart!", state="complete", expanded=False)
        st.session_state['klar'] = True
else:
    geo_data, logg_data, feil = last_data()

# --- SIDEBAR ---
st.sidebar.title("📊 Status")

# Tids-slider
min_d = datetime.date(2019, 1, 1)
max_d = datetime.date.today()
valgt_dato = st.sidebar.slider("Fremdrift til:", min_d, max_d, max_d, format="DD.MM.YY")

# Beregn gåtte gater lynraskt
gåtte_nå = {k for k, v in logg_data.items() if v <= valgt_dato}

# Finn gater i kartet for statistikk
unike_gater_kart = {super_rens(f['properties']['name']) for f in geo_data['features']}
total = len(unike_gater_kart)
gått = len(unike_gater_kart & gåtte_nå)
prosent = (gått/total*100) if total > 0 else 0

st.sidebar.metric("Total fremdrift", f"{prosent:.1f}%", f"{gått} av {total}")
st.sidebar.progress(prosent / 100)

# Søk (uten automatisk zoom for å bevare ytelse på slider)
st.sidebar.markdown("---")
søk = st.sidebar.text_input("🔍 Finn en gate:")
if søk:
    s_rens = super_rens(søk)
    if s_rens in gåtte_nå: st.sidebar.success("✅ Gått!")
    elif s_rens in unike_gater_kart: st.sidebar.warning("❌ Ikke gått")

# --- KARTET (OPTIMALISERT) ---
m = folium.Map(location=[59.915, 10.74], zoom_start=13, tiles="cartodbpositron")

LocateControl(auto_start=False).add_to(m)

# Her er "tricket": Vi lager én samlet funksjon for stil
def style_f(feature):
    er_gått = super_rens(feature['properties']['name']) in gåtte_nå
    return {
        'color': 'green' if er_gått else 'red',
        'weight': 3 if er_gått else 2,
        'opacity': 0.7 if er_gått else 0.4
    }

# Legg til hele GeoJSON-filen som ETT lag
folium.GeoJson(
    geo_data,
    style_function=style_f,
    tooltip=folium.GeoJsonTooltip(fields=['name'], labels=False)
).add_to(m)

folium_static(m, width=1000, height=750)
