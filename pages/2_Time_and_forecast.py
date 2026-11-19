import pandas as pd
import plotly.express as px
import streamlit as st

from src import appdata, charts, forecast
from src.i18n import columns, style_plotly, t

appdata.sidebar_sources()
st.title(t("Time and forecast"))

nat = appdata.national()
if nat.empty:
    appdata.missing_data_notice("National series")
    st.stop()

est = nat[nat["kind"] == "estimate"] if "kind" in nat else nat
series = est.set_index("year")["population"]

first, last = int(series.index.min()), int(series.index.max())
s1, s2 = st.columns(2)
train_start = s1.slider(t("Training starts in"), first, last - 14, 2000,
                        help=t("Earlier years are left out. The 1970s and 1990s contain large swings (war, repatriation) that a smooth trend cannot follow."))
t_min, t_max = train_start + 10, last - 3
test_start = s2.slider(t("Test period starts in"), t_min, t_max, max(t_min, min(2015, t_max)),
                       help=t("Models are fitted on earlier years only (split in time)."))
preds, scores = forecast.evaluate(series, test_start, train_start)

st.plotly_chart(charts.population_chart(nat, preds), width="stretch")

c1, c2 = st.columns([1, 1])
with c1:
    st.subheader(t("Does the model beat 'same as last time'?"))
    st.dataframe(columns(scores.rename(index=lambda m: t(m.replace("_", " ")))).style.format({t("MAE"): "{:,.0f}", t("MAPE_%"): "{:.2f}"}), width="stretch")
    winner = scores["MAE"].idxmin()
    st.caption(t("Lowest error on {n} test years: **{winner}**.", n=int(scores['n'].iloc[0]), winner=t(winner.replace('_', ' '))))
with c2:
    st.subheader(t("Growth rate and its trend"))
    g = est[["year", "pop_growth_pct", "pop_growth_roll5"]].dropna()
    fig = px.line(g, x="year", y=["pop_growth_pct", "pop_growth_roll5"],
                  labels={"value": t("% per year"), "year": "", "variable": ""})
    fig.for_each_trace(lambda tr: tr.update(name=t(tr.name)))
    style_plotly(fig)
    fig.update_layout(height=320, margin=dict(l=0, r=0, t=10, b=0))
    st.plotly_chart(fig, width="stretch")
    st.caption(t("Annual data has no season, so only the trend (5-year rolling mean) is separated."))

# ---------------------------------------------------------------- forecast ahead (chosen range)
st.subheader(t("Forecast ahead"))
end_year = st.slider(t("Forecast until"), last + 2, 2050, min(2040, 2050),
                     help=t("The two models are fitted on all years from the training start and extended to this year."))
fc = forecast.forecast_ahead(series, end_year, train_start)
un = nat.set_index("year")
if len(fc):
    un_end = un.loc[end_year, "population"] if end_year in un.index else None
    lo, hi = fc.loc[end_year].min() / 1e6, fc.loc[end_year].max() / 1e6
    title = (t("By {year} the two simple models give {lo:.1f}–{hi:.1f} M; the UN medium projection is {un:.1f} M", year=end_year, lo=lo, hi=hi, un=un_end / 1e6)
             if un_end is not None else t("By {year} the two simple models give {lo:.1f}–{hi:.1f} M", year=end_year, lo=lo, hi=hi))
    st.plotly_chart(charts.forecast_chart(nat, fc, train_start, title), width="stretch", key="forecast_ahead")
    years = sorted({y for y in (2030, 2040, 2050, end_year) if last < y <= end_year})
    tbl = pd.DataFrame({t("naive drift"): fc.loc[years, "naive_drift"], t("holt damped"): fc.loc[years, "holt_damped"]})
    for col, label in (("population", "UN medium projection"), ("pop_low", "UN low"), ("pop_high", "UN high")):
        if col in un:
            tbl[t(label)] = un.reindex(years)[col]
    tbl.index = [str(y) for y in years]
    st.dataframe((tbl / 1e6).style.format("{:.1f}"), width="stretch")
    st.caption(t("Millions of people. Both models only extend the recent trend; they know nothing about births, deaths or migration. There is no probability band because the earlier years include large swings, so one built from past errors would look more exact than it is. Use the UN low–high range as the realistic uncertainty."))

if "urban_pct" in nat and nat["urban_pct"].notna().any():
    st.subheader(t("Urban share and its change on a year earlier"))
    u = nat[["year", "urban_pct", "urban_pct_change"]].dropna()
    st.plotly_chart(px.bar(u, x="year", y="urban_pct_change",
                           labels={"urban_pct_change": t("Change, percentage points"), "year": ""}),
                    width="stretch")
