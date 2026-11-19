import re

import pandas as pd
import plotly.express as px
import streamlit as st

from src import appdata, config, fetch, pipeline
from src.i18n import columns, style_plotly, t

appdata.sidebar_sources()
st.title(t("Data quality"))

# ---------------------------------------------------------------- sources + licences
st.subheader(t("Sources"))
manifest = pd.read_csv(config.MANIFEST) if config.MANIFEST.exists() else pd.DataFrame(columns=["file", "retrieved_on"])
src = pd.DataFrame(config.SOURCES).sort_values("id").reset_index(drop=True)
def _retrieved(f: str) -> str:
    """Date(s) the source was pulled. Matches on the start of the file name, because the
    download script saves multi-part files as gazetteer_0.xlsx, commune_db_2011_0.csv, ..."""
    key = re.split(r"[*.]", f.split("/")[-1])[0]
    base = manifest["file"].str.split("/").str[-1]
    return ", ".join(manifest.loc[base.str.startswith(key), "retrieved_on"].unique()) or t("not downloaded")


src["retrieved_on"] = src["file"].map(_retrieved)
st.dataframe(columns(src[["id", "name", "licence", "fetch", "retrieved_on", "url"]]), hide_index=True, width="stretch",
             column_config={t("url"): st.column_config.LinkColumn(t("Link"))})
st.caption(t("The Gazetteer carries no licence: only derived counts are shown, the raw file is not republished."))

# ---------------------------------------------------------------- census totals add up?
st.subheader(t("Census totals check"))
chk = pipeline.census_total_check(appdata.census_history())
if chk.empty:
    st.caption(t("No census data to check."))
else:
    shown = chk.assign(ok=chk["ok"].map(lambda v: "✅" if v else "⚠️"))
    st.dataframe(columns(shown), hide_index=True, width="stretch",
                 column_config={t("provinces_sum"): st.column_config.NumberColumn(format="%d"),
                                t("official_total"): st.column_config.NumberColumn(format="%d")})
    if chk["ok"].all():
        st.caption(t("The province rows of every census add up exactly to the national total printed in the NIS report."))
    else:
        st.warning(t("At least one census does not add up to its official national total. Check the province rows."))

# ---------------------------------------------------------------- missingness (Week 2)
st.subheader(t("Missing values"))
tables = {"province": appdata.province_table(), "national": appdata.national(),
          "commune": appdata.communes(), "asean_wb": appdata.asean()}
reports = [pipeline.missingness_report(df, name) for name, df in tables.items() if not df.empty]
if reports:
    rep = pd.concat(reports)
    fig = px.bar(rep[rep["missing_pct"] > 0], x="missing_pct", y="column", color="source",
                 orientation="h", labels={"missing_pct": t("% missing"), "column": "", "source": t("source")})
    fig.update_layout(height=max(250, 18 * (rep["missing_pct"] > 0).sum()), margin=dict(l=0, r=0, t=10, b=0))
    st.plotly_chart(style_plotly(fig), width="stretch")
    with st.expander(t("Full table")):
        st.dataframe(columns(rep), hide_index=True, width="stretch")
    st.caption(t("Why gaps exist: e.g. WPP has no urban share; World Bank starts in 1960; growth rates are empty for the first year by construction."))

# ---------------------------------------------------------------- outliers (Week 3)
st.subheader(t("Flagged outliers"))
prov = tables["province"]
if not prov.empty:
    flags = prov[prov.filter(like="_outlier").any(axis=1)]
    st.dataframe(columns(flags[["province", "density_calc", "density_calc_score", "density_calc_outlier",
                        "household_size", "household_size_score", "household_size_outlier"]], ("province",)),
                 hide_index=True, width="stretch")
    st.caption(t("Outliers are flagged and explained, never deleted. Phnom Penh's density is real: it is the capital."))

# ---------------------------------------------------------------- commune code check (MEF 2025 vs Gazetteer)
st.subheader(t("Commune code check"))
summary, only_mef, only_app = pipeline.commune_code_check(appdata.communes())
if not summary:
    st.caption(t("Save the MEF Commune List 2025 as data/raw/mef_commune_2025.csv to compare it with the Gazetteer."))
else:
    k1, k2, k3, k4 = st.columns(4)
    k1.metric(t("Communes in MEF 2025"), f"{summary['mef_rows']:,}")
    k2.metric(t("Communes in Gazetteer"), f"{summary['app_rows']:,}")
    k3.metric(t("Same code in both"), f"{summary['matched']:,}")
    k4.metric(t("Different code"), f"{summary['only_mef']} / {summary['only_app']}",
              help=t("Only in MEF / only in Gazetteer"))
    if summary["mef_districts"]:
        st.caption(t("Districts: {m} in MEF 2025, {a} in the Gazetteer; {d} differ.", m=summary["mef_districts"],
                     a=summary["app_districts"], d=summary["districts_only_mef"] + summary["districts_only_app"]))
    if summary.get("villages_differ") is not None:
        st.caption(t("Village counts: {n} of the {m} communes with the same code have a different number of villages in MEF 2025 than in the Gazetteer.",
                     n=summary["villages_differ"], m=summary["matched"]))
    c1, c2 = st.columns(2)
    with c1:
        st.markdown(f"**{t('Only in MEF 2025')}**")
        st.dataframe(columns(only_mef), hide_index=True, width="stretch")
    with c2:
        st.markdown(f"**{t('Only in Gazetteer')}**")
        st.dataframe(columns(only_app), hide_index=True, width="stretch")
    st.caption(t("Match on the 6-digit code, not on names: {n} MEF names are repeated. A suggested old code means the same name appears under another code, which usually means the commune was recoded. Rows named Kokir (250315–250321) look like a source error.", n=summary["repeated_names"]))

# ---------------------------------------------------------------- fetch log
st.subheader(t("Automatic pulls"))
log = fetch.read_fetch_log().sort_values("timestamp", ascending=False)
if log.empty:
    st.caption(t("No pulls yet."))
else:
    latest = log.groupby("source", as_index=False).first()[["source", "timestamp", "rows", "status", "error"]]
    st.dataframe(columns(latest.sort_values("source")), hide_index=True, width="stretch")
    if (latest["status"] != "ok").any():
        st.warning(t("{n} source(s) failed on their latest pull.", n=int((latest["status"] != "ok").sum())))
    with st.expander(t("Full log")):
        st.dataframe(columns(log), hide_index=True, width="stretch")
