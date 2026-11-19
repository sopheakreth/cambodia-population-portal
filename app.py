"""Entry point — run with:  streamlit run app.py

Defines the sidebar menu. Menu titles come from locales/km.json like every
other label, so the page names can be translated in the same place.
"""
import streamlit as st

from src.i18n import KHMER_FONT, t

st.set_page_config(page_title=t("Where do Cambodians live?"), page_icon="🗺️", layout="wide")
# Khmer font for text only: Streamlit's icons are a font too, so they must keep theirs
st.markdown(
    f"""<style>
    .stApp, .stApp *:not([data-testid="stIconMaterial"]):not([class*="material" i]) {{ font-family: {KHMER_FONT}; }}
    [data-testid="stIconMaterial"], [class*="material-symbols" i] {{
        font-family: "Material Symbols Rounded", "Material Symbols Outlined" !important; }}
    </style>""",
    unsafe_allow_html=True)

nav = st.navigation([
    st.Page("overview.py", title=t("Overview"), icon="🗺️", default=True, url_path="Overview"),
    st.Page("pages/1_Map_explorer.py", title=t("Map explorer"), url_path="Map_explorer"),
    st.Page("pages/2_Time_and_forecast.py", title=t("Time and forecast"), url_path="Time_and_forecast"),
    st.Page("pages/3_Urban_commune_model.py", title=t("Urban commune model"), url_path="Urban_commune_model"),
    # Upload data is switched off. To bring it back, uncomment this line:
    # st.Page("pages/4_Upload_data.py", title=t("Upload data"), url_path="Upload_data"),
    st.Page("pages/5_Data_quality.py", title=t("Data quality"), url_path="Data_quality"),
    st.Page("pages/6_Findings.py", title=t("Findings"), url_path="Findings"),
])
nav.run()
