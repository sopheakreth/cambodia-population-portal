"""Overview page (loaded by app.py)."""
import pandas as pd
import streamlit as st

from src import appdata, charts
from src.i18n import columns, t

prov = appdata.province_table()
gj = appdata.province_geojson()
nat = appdata.national()

# ---------------------------------------------------------------- sidebar filters
with st.sidebar:
    st.header(t("Filters"))
    years = appdata.census_years()
    year = st.select_slider(t("Census year"), options=years, value=years[-1], disabled=len(years) == 1,
                            help=t("1998 and 2008 show density and population share only. Other measures need the 2019 census."))
    measure = st.selectbox(t("Measure"), list(charts.LABELS) if year == 2019 else charts.HIST_MEASURES,
                           format_func=charts.label)
    ALL = "All provinces"
    prov_names = [ALL] + (prov["province"].dropna().tolist() if not prov.empty else [])
    picked = st.selectbox(t("Province"), prov_names, format_func=t, key="province_pick")
appdata.sidebar_sources()

st.title(t("Where do Cambodians live?"))
st.caption(t("Population density, urbanisation and projected growth across Cambodian provinces, 1950–2100"))

if prov.empty:
    appdata.missing_data_notice("Census 2019 data")
    st.stop()

# ---------------------------------------------------------------- headline metrics (Week 4, 12)
mprov = appdata.province_for_year(year)          # everything below follows the selected census year
# 1998/2008 give Tbong Khmum a copy of Kampong Cham's row (for the map): leave it out of totals
base = mprov[~((mprov["pro_code"] == 25) & mprov["merged"])] if "merged" in mprov else mprov
pop = base["population"].sum()
dens = pop / base["area_km2"].sum()
urban = nat.dropna(subset=["urban_pct"]) if "urban_pct" in nat else pd.DataFrame()
urban = urban[urban["year"] <= year]            # latest World Bank value up to the selected year
proj2050 = nat.loc[nat["year"] == 2050, "population"] if "year" in nat else pd.Series(dtype=float)

c1, c2, c3, c4 = st.columns(4)
c1.metric(t("Population, {year} census", year=year), f"{pop / 1e6:.1f} M")
c2.metric(t("National density"), t("{v:.0f} per km²", v=dens))
if not urban.empty:
    last, prev = urban.iloc[-1], urban[urban["year"] == urban["year"].max() - 5]
    delta = t("{v:+.1f} pts in 5 yrs", v=last['urban_pct'] - prev['urban_pct'].iloc[0]) if len(prev) else None
    c3.metric(t("Urban share, {year}", year=int(last['year'])), f"{last['urban_pct']:.1f} %", delta,
              help=t("World Bank estimate for the census year, or the latest year before it. The series rises steeply between 2008 and 2019, which may partly reflect a change in how urban areas are defined."))
else:
    c3.metric(t("Urban share"), "—", help=t("Run the World Bank download"))
c4.metric(t("UN projection, 2050"), f"{proj2050.iloc[0] / 1e6:.1f} M" if len(proj2050) else "—",
          help=t("The UN's central projection. It does not depend on the census year selected."))

# ---------------------------------------------------------------- linked map + charts
left, right = st.columns([1, 1])
selected_code = None
if picked != "All provinces":
    selected_code = int(prov.loc[prov["province"] == picked, "pro_code"].iloc[0])

with left:
    top = mprov.loc[mprov[measure].idxmax()]
    ratio = top[measure] / mprov[measure].median()
    title = t("{prov} is highest: {ratio:.1f}× the median province", prov=t(top['province']), ratio=ratio)
    if gj is None:
        appdata.missing_data_notice("Province boundaries (data/boundaries/province.geojson)")
    else:
        fig = charts.choropleth(mprov, gj, measure, f"{title} · {year}", highlight=selected_code)
        event = st.plotly_chart(fig, on_select="rerun", selection_mode="points",
                                key="overview_map", width="stretch")
        pts = getattr(getattr(event, "selection", None), "points", None) or []
        if pts:
            loc = pts[0].get("location") or (pts[0].get("customdata") or [None])[0]
            if loc is not None:
                selected_code = int(loc)
        st.caption(t("Click a province (or use the sidebar) to see its details. Class breaks are fixed and shown in the legend."))
        if year != 2019:
            st.caption(t("In {year}, Tbong Khmum was part of Kampong Cham, so both areas show the combined value.", year=year))
            a19 = prov.set_index("pro_code")["area_km2"]
            chg = mprov[(mprov["pro_code"] != 25) & ((mprov["area_km2"] - mprov["pro_code"].map(a19)).abs() / mprov["pro_code"].map(a19) > 0.1)]
            if len(chg):
                st.caption(t("Density is not comparable with 2019 for provinces whose recorded area changed: {names}. Compare population shares instead.",
                             names=", ".join(t(n) for n in chg["province"])))

with right:
    if nat.empty:
        appdata.missing_data_notice("National population series (UN WPP / World Bank)")
    else:
        peak = nat.loc[nat["population"].idxmax()]
        st.plotly_chart(charts.population_chart(
            nat, title=t("Population peaks around {year} at {pop:.1f} M (UN medium)", year=int(peak['year']), pop=peak['population'] / 1e6),
            mark_year=year),
            width="stretch")

# ---------------------------------------------------------------- province detail (linked view)
if selected_code is not None:
    row = mprov[mprov["pro_code"] == selected_code].iloc[0]
    area_share = 100 * row["area_km2"] / base["area_km2"].sum()
    merged = bool(row.get("merged", False))
    st.subheader(t("Kampong Cham and Tbong Khmum (combined)") if merged else t(row['province']))
    d1, d2, d3, d4 = st.columns(4)
    d1.metric(t("Population"), f"{row['population']:,.0f}", t("{v:.1f}% of Cambodia", v=row['pop_share_pct']),
              delta_color="off")
    d2.metric(t("Density"), t("{v:,.0f} per km²", v=row['density_calc']),
              t("{v:.1f}× national", v=row['density_calc'] / dens), delta_color="off")
    d3.metric(t("Household size"), f"{row['household_size']:.2f}" if pd.notna(row["household_size"]) else "—")
    d4.metric(t("Area"), t("{v:,.0f} km²", v=row['area_km2']), t("{v:.1f}% of land", v=area_share),
              delta_color="off")

tab1, tab2, tab3 = st.tabs([t("Density vs household size (H2)"), t("Urban share vs ASEAN"), t("Province table")])
with tab1:
    fig, r = charts.scatter_density_household(base)
    st.plotly_chart(fig, width="stretch")
with tab2:
    a = appdata.asean()
    if a.empty:
        appdata.missing_data_notice("World Bank ASEAN data")
    else:
        st.plotly_chart(charts.urban_share_chart(a), width="stretch")
with tab3:
    cols = ["pro_code", "province", "population", "households", "area_km2", "density_calc",
            "household_size", "pop_share_pct", "density_calc_outlier"]
    st.dataframe(columns(base[[c for c in cols if c in base]], ("province",)), hide_index=True, width="stretch")
