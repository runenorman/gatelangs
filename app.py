import streamlit as st
import pandas as pd

st.set_page_config(page_title="Gatelangs Oslo", layout="wide")

st.title("🏃‍♂️ Gatelangs Oslo - Versjon 3.0")

# Prøv å lese regnearket
try:
    # Finn filnavnet (vi antar den heter det du lastet opp)
    filnavn = "Gater Transport  20260419.ods"
    
    # Les fane 1 (Logg)
    df_logg = pd.read_excel(filnavn, sheet_name=0, engine="odf")
    # Les fane 2 (Fasit)
    df_fasit = pd.read_excel(filnavn, sheet_name=1, engine="odf")

    st.success(f"✅ Kontakt med regnearket! Fant {len(df_logg)} rader i loggen.")
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Antall rader i loggen", len(df_logg))
    with col2:
        st.metric("Gater i fasit (rådata)", "Beregnes snart...")

    st.info("Neste steg: Her kommer kartet så snart vi har generert koordinatene!")

except Exception as e:
    st.error(f"Kunne ikke lese regnearket. Sjekk at filnavnet er nøyaktig 'Gater Transport  20260419.ods'.")
    st.write("Feilmelding:", e)
