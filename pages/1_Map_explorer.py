import streamlit as st

from src import appdata, charts, pipeline
from src.i18n import columns, t

appdata.sidebar_sources()
st.title(t("Map explorer"))

prov = appdata.province_table()
gj = appdata.province_geojson()
if prov.empty or gj is None:
    appdata.missing_data_notice("Census table or province boundaries")
    st.stop()

years = appdata.census_years()
year = st.radio(t("Census year"), years, index=len(years) - 1, horizontal=True, disabled=len(years) == 1)
measure = st.radio(t("Measure"), list(charts.LABELS) if year == 2019 else charts.HIST_MEASURES,
                   format_func=charts.label, horizontal=True)
mprov = appdata.province_for_year(year)
top = mprov.loc[mprov[measure].idxmax()]
low = mprov.loc[mprov[measure].idxmin()]
st.plotly_chart(
    charts.choropleth(mprov, gj, measure,
                      t("{measure}: highest in {top} ({top_v:,.1f}), lowest in {low} ({low_v:,.1f})",
                        measure=charts.label(measure), top=t(top['province']), top_v=top[measure],
                        low=t(low['province']), low_v=low[measure]) + f" · {year}"),
    width="stretch")
if year != 2019:
    st.caption(t("In {year}, Tbong Khmum was part of Kampong Cham, so both areas show the combined value.", year=year))

st.subheader(t("Class breaks used"))
st.write(", ".join(f"{b:g}" for b in charts.BREAKS[measure][:-1]) + " " + t("and above"))

st.subheader(t("Boundary name matching"))
_, match = pipeline.load_province_geojson()
st.dataframe(columns(match), hide_index=True, width="stretch")
if match["pro_code"].isna().any():
    st.error(t("Some boundary features did not match a province code. Add the spelling to `PROVINCES` aliases in src/pipeline.py."))
