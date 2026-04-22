import streamlit as st
import pandas as pd
import folium
from streamlit_folium import folium_static
import json
import re
import unicodedata

st.set_page_config(page_title="Gatelangs Oslo 3.0", layout="wide")

def super_rens(s):
    """Normaliserer navn for sammenligning (lik den i Colab)."""
    if not s or pd.isna(s): return ""
    s = unicodedata.normalize('NFC', str(s)).lower()
    s = re.sub(r'\(.*\)', '', s) # Fjern parenteser
    return "".join(c for c in s if c.isalnum())

# --- DATA-LASTING ---
@st.cache_data
def last_data():
    # OBS: Sjekk at dette filnavnet er NØYAKTIG likt det som ligger på GitHub
    filnavn = "Gater Transport  20260419.ods"
    
    try:
        # 1. Les gåtte gater (Fane 1)
        # Vi leser kolonne B (index 1) fra rad 4 og nedover
        df_logg = pd.read_excel(filnavn, sheet_name=0, engine="odf")
        rader = df_logg.iloc[3:, 1].dropna().astype(str)
        # Lag et sett med rensede navn for lynrask sjekk
        gåtte_nøkler = set(super_rens(g) for g in rader)
    except Exception as e:
        st.error(f"Feil ved lesing av .ods fil: {e}")
        gåtte_nøkler = set()
    
    # 2. Last geometri
    try:
        with open("oslo_geometri.geojson", "r", encoding="utf-8") as f:
            geo_data = json.load(f)
    except Exception as e:
        geo_data = None
        
    return gåtte_nøkler, geo_data

gåtte_nøkler, geo_data = last_data()

# --- SIDEBAR (STATISTIKK) ---
st.sidebar.title("📊 Gatelangs-status")

if geo_data:
    # Finn unike gater i kartfilen
    alle_gater_i_kart = {} # nøkkel: originalt_navn
    for f in geo_data['features']:
        navn = f['properties']['name']
        alle_gater_i_kart[super_rens(navn)] = navn
    
    total_gater = len(alle_gater_i_kart)
    # Finn ut hvilke som er gått
    gåtte_treff = [k for k in alle_gater_i_kart.keys() if k in gåtte_nøkler]
    antall_gått = len(gåtte_treff)
    
    prosent = (antall_gått / total_gater * 100) if total_gater > 0 else 0

    st.sidebar.metric("Gater i fasit", total_gater)
    st.sidebar.metric("Gater gått", antall_gått)
    st.sidebar.progress(prosent / 100)
    st.sidebar.subheader(f"Fullført: {prosent:.1f}%")
    
    st.sidebar.markdown("---")
    søk = st.sidebar.text_input("Finn en gate:")
    if søk:
        s_nøkkel = super_rens(søk)
        if s_nøkkel in gåtte_nøkler:
            st.sidebar.success(f"✅ {søk} er GÅTT!")
        elif s_nøkkel in alle_gater_i_kart:
            st.sidebar.warning(f"❌ {søk} er IKKE GÅTT.")
        else:
            st.sidebar.info("Ikke i lista.")

# --- HOVEDSKJERM ---
st.title("🏃‍♂️ Gatelangs Oslo v3.0")

if geo_data is None:
    st.error("Kunne ikke finne kartfilen 'oslo_geometri.geojson'. Sjekk at den er lastet opp til GitHub.")
else:
    # Lag kartet sentrert på Oslo
    m = folium.Map(location=[59.915, 10.74], zoom_start=13, tiles="cartodbpositron")

    # Tegn gatene
    for feature in geo_data['features']:
        org_navn = feature['properties']['name']
        rens_navn = super_rens(org_navn)
        
        er_gått = rens_navn in gåtte_nøkler
        farge = "green" if er_gått else "red"
        
        folium.GeoJson(
            feature,
            style_function=lambda x, f=farge: {
                "color": f,
                "weight": 3 if f == "green" else 2,
                "opacity": 0.7
            },
            tooltip=org_navn
        ).add_to(m)

    folium_static(m, width=1000, height=700)

st.caption(f"Sist oppdatert: {pd.Timestamp.now().strftime('%d.%m.%Y')}")
