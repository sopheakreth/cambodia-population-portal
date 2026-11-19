"""Findings: five one-sentence findings, each with a number, the chart that shows it and a caveat.

The sentences are computed from the data, so they stay true after a refresh.
Every visible word goes through t(), so the wording lives in locales/km.json.
"""
import streamlit as st

from src import appdata, charts, model
from src.i18n import t

appdata.sidebar_sources()
st.title(t("Findings"))
st.caption(t("Each finding is one sentence with a number, the chart behind it, and what could make it misleading."))

prov = appdata.province_table()
nat = appdata.national()
gj = appdata.province_geojson()
hist = appdata.census_history()
if prov.empty:
    appdata.missing_data_notice("Census table")
    st.stop()


def caveat(text: str, **fmt) -> None:
    st.caption(f"**{t('Caveat')}:** {t(text, **fmt)}")


# ---------------------------------------------------------------- Finding 1 (H1): concentration in the capital
pp = prov[prov["province"] == "Phnom Penh"].iloc[0]
st.subheader(t("1. Concentration in the capital"))
share = {}
if not hist.empty:
    share = hist[hist["pro_code"] == 12].set_index("year")["pop_share_pct"].to_dict()
st.markdown(t("Phnom Penh holds **{pop:.1f}%** of Cambodia's population on **{area:.2f}%** of its land, at **{dens:,.0f}** people per km².",
              pop=pp["pop_share_pct"], area=pp["area_share_pct"], dens=pp["density_calc"]))
if len(share) >= 2:
    first, last = min(share), max(share)
    others = hist[hist["pro_code"].isin([8, 21]) & ~hist["merged"]].groupby("year")["pop_share_pct"].sum()
    st.markdown(t("Its share rose from **{a:.1f}%** in {ya} to **{b:.1f}%** in {yb}, while Kandal and Takeo together fell from **{c:.1f}%** to **{d:.1f}%**: the growth is in the capital itself, not in the provinces around it.",
                  a=share[first], ya=first, b=share[last], yb=last, c=others[first], d=others[last]))
c1, c2 = st.columns(2)
with c1:
    if gj is not None:
        st.plotly_chart(charts.choropleth(prov, gj, "density_calc", t("People per km², 2019 census")),
                        width="stretch", key="f1")
with c2:
    if len(share) >= 2:
        st.plotly_chart(charts.share_trend_chart(hist, t("Phnom Penh's share grows; Kandal's and Takeo's shrink")),
                        width="stretch", key="f1b")
caveat("Use population shares, not density, to compare years: Phnom Penh's recorded area differs between the 2008 and 2019 reports, so its density appears to fall although its population grew. The 2019 map splits Tbong Khmum from Kampong Cham.")

# ---------------------------------------------------------------- Finding 2 (H2): density and household size
fig, r = charts.scatter_density_household(prov)
st.subheader(t("2. Density and household size"))
verdict = t("supports") if r < -0.3 else t("does not support")
st.markdown(t("Across {n} provinces the rank correlation between density and household size is **r = {r:.2f}**, which {verdict} H2.",
              n=len(prov), r=r, verdict=verdict))
st.plotly_chart(fig, width="stretch", key="f2")
caveat("This compares provinces, not families, and 25 points are few. A correlation says nothing about cause, and Phnom Penh sits far from the other provinces on the density axis.")

# ---------------------------------------------------------------- Finding 3: projection
if not nat.empty and "kind" in nat:
    st.subheader(t("3. What comes next"))
    peak = nat.loc[nat["population"].idxmax()]
    row50 = nat.loc[nat["year"] == 2050]
    p2050 = row50["population"]
    st.markdown(t("The UN medium projection reaches **{p2050:.1f} M** in 2050 and peaks at **{peak:.1f} M** around **{year}**.",
                  p2050=p2050.iloc[0] / 1e6, peak=peak["population"] / 1e6, year=int(peak["year"]))
                if len(p2050) else t("Load UN WPP data to complete this finding."))
    st.plotly_chart(charts.population_chart(nat), width="stretch", key="f3")
    if len(p2050) and {"pop_low", "pop_high"} <= set(nat.columns) and row50[["pop_low", "pop_high"]].notna().all(axis=None):
        caveat("This is the UN's central scenario, not a forecast made here. Its own low and high variants span {lo:.1f} to {hi:.1f} M in 2050.",
               lo=row50["pop_low"].iloc[0] / 1e6, hi=row50["pop_high"].iloc[0] / 1e6)
    else:
        caveat("This is the UN's central scenario, not a forecast made here.")

# ---------------------------------------------------------------- Finding 4 (H1): urban share trend
if "urban_pct" in nat and nat["urban_pct"].notna().any():
    u = nat.dropna(subset=["urban_pct"]).set_index("year")["urban_pct"]
    y0, y1 = (1998 if 1998 in u.index else int(u.index.min())), int(u.index.max())
    st.subheader(t("4. Urban share"))
    st.markdown(t("The urban share of Cambodia's population rose from **{a:.0f}%** in {ya} to **{b:.0f}%** in {yb}.",
                  a=u[y0], ya=y0, b=u[y1], yb=y1))
    st.plotly_chart(charts.urban_trend_chart(nat, t("Urban share: {a:.0f}% in {ya}, {b:.0f}% in {yb}", a=u[y0], ya=y0, b=u[y1], yb=y1)),
                    width="stretch", key="f4")
    if 2008 in u.index and 2019 in u.index:
        caveat("Almost all of the rise comes between the 2008 ({a:.0f}%) and 2019 ({b:.0f}%) censuses, far faster than before. Part of it may be a change in how urban areas are defined, which this page does not verify, so do not read it as a steady yearly trend.",
               a=u[2008], b=u[2019])

# ---------------------------------------------------------------- Finding 5: urban commune model
com = appdata.communes()
if not com.empty and com["is_sangkat"].notna().any():
    @st.cache_resource(show_spinner=t("Training with 5-fold CV…"))
    def _urban_model():
        return model.run(appdata.with_commune_db(appdata.communes()), use_db=True)

    res = _urban_model()
    st.subheader(t("5. Spotting urban communes"))
    st.markdown(t("Using only village counts, province and 2011 electricity, household, land and rice data, the model finds **{rec:.0%}** of sangkat communes in the test set, and **{prec:.0%}** of the communes it flags really are sangkat; PR-AUC is **{ap:.2f}** against a base rate of {base:.0%}.",
                  rec=res["test"]["recall"], prec=res["test"]["precision"], ap=res["test_pr_auc"], base=res["base_rate"]))
    st.plotly_chart(charts.pr_curve_chart(res["y_test"], res["proba_test"], res["base_rate"],
                                          t("The model is well above guessing at almost every recall level")),
                    width="stretch", key="f5")
    caveat("The test set holds about {n} communes, so these figures are noisy. The khum/sangkat labels come from the Gazetteer, and the 2011 data describes communes as they were then; communes created later have no 2011 row.",
           n=int(len(res["y_test"])))
