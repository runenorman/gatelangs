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
def last_og_prosesser_data():
    default_dato = datetime.date(2019, 1, 1)
    
    try:
        # 1. Finn .ods-fila automatisk (uansett navn)
        alle_filer = os.listdir(".")
        ods_filer = [f for f in alle_filer if f.endswith(".ods")]
        
        if not ods_filer:
            return None, None, "Fant ingen .ods-fil i mappen på GitHub."
        
        filnavn = ods_filer[0] # Tar den første den finner
        
        # 2. Last Logg (Fane 1)
        df_logg = pd.read_excel(filnavn, sheet_name=0, engine="odf")
        logg_dict = {}
        for _, row in df_logg.iloc[3:].iterrows():
            g_navn = str(row.iloc[1]).strip()
            nøkkel = super_rens(g_navn)
            raw_dato = row.iloc[14]
            
            try:
                pd_dato = pd.to_datetime(raw_dato)
                dato = pd_dato.date() if not pd.isna(pd_dato) else default_dato
            except:
                dato = default_dato
            
            if nøkkel:
                if nøkkel not in logg_dict or dato < logg_dict[nøkkel]:
                    logg_dict[nøkkel] = dato

        # 3. Last GeoJSON
        if "oslo_geometri.geojson" not in alle_filer:
            return None, None, "Fant ikke 'oslo_geometri.geojson' på GitHub."
            
        with open("oslo_geometri.geojson", "r", encoding="utf-8") as f:
            geo_data = json.load(f)
                    
        return geo_data, logg_dict, None
    except Exception as e:
        return None, None, f"Teknisk feil: {str(e)}"

# --- INITIERING ---
if 'init_ferdig' not in st.session_state:
    with st.status("🚀 Initierer Oslo...", expanded=True) as status:
        geo_data, logg_data, feilmelding = last_og_prosesser_data()
        if feilmelding:
            st.error(feilmelding)
            st.stop()
        status.update(label="✅ Alt klart!", state="complete", expanded=False)
        st.session_state['init_ferdig'] = True
else:
    geo_data, logg_data, feilmelding = last_og_prosesser_data()

# --- SIDEBAR ---
st.sidebar.title("📊 Gatelangs-status")

# TIDS-SLIDER
min_d = datetime.date(2019, 1, 1)
max_d = datetime.date.today()
st.sidebar.write("📅 **Tidsreise**")
valgt_dato = st.sidebar.slider("Se fremdrift frem til:", min_d, max_d, max_d, format="DD.MM.YY")

gåtte_nøkler_nå = {k for k, v in logg_data.items() if v <= valgt_dato}

# STATISTIKK
gater_i_kart = {}
for f in geo_data['features']:
    n = f['properties']['name']
    n_rens = super_rens(n)
    if n_rens not in gater_i_kart:
        # Prøver å finne midtpunktet for zoom
        coords = f['geometry']['coordinates']
        if f['geometry']['type'] == "LineString":
            p = coords[len(coords)//2] # Midterste punkt
            gater_i_kart[n_rens] = {'navn': n, 'coords': [p[1], p[0]]}
        else: # MultiLineString
            p = coords[0][len(coords[0])//2]
            gater_i_kart[n_rens] = {'navn': n, 'coords': [p[1], p[0]]}

total = len(gater_i_kart)
gått = len(gater_i_kart.keys() & gåtte_nøkler_nå)
prosent = (gått / total * 100) if total > 0 else 0

st.sidebar.metric("Total fremdrift", f"{prosent:.1f}%", f"{gått} av {total} gater")
st.sidebar.progress(prosent / 100)

# SØK
st.sidebar.markdown("---")
søk = st.sidebar.text_input("🔍 Finn og zoom til gate:")
map_center = [59.915, 10.74]
map_zoom = 12

if søk:
    s_rens = super_rens(søk)
    if s_rens in gater_i_kart:
        map_center = gater_i_kart[s_rens]['coords']
        map_zoom = 16
        st.sidebar.success(f"Zoomer til {gater_i_kart[s_rens]['navn']}")
    else:
        st.sidebar.warning("Ikke funnet i kartet.")

# --- KART ---
m = folium.Map(location=map_center, zoom_start=map_zoom, tiles="cartodbpositron")

LocateControl(auto_start=False, strings={"title": "Hvor er jeg?"}).add_to(m)

for feature in geo_data['features']:
    n = feature['properties']['name']
    er_gått = super_rens(n) in gåtte_nøkler_nå
    farge = "green" if er_gått else "red"
    
    folium.GeoJson(
        feature,
        style_function=lambda x, f=farge: {
            "color": f, "weight": 3 if f == "green" else 2, "opacity": 0.7
        },
        tooltip=n
    ).add_to(m)

folium_static(m, width=1100, height=700)
