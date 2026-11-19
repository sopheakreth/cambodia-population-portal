import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

from src import appdata, model
from src.i18n import style_plotly, t

appdata.sidebar_sources()
st.title(t("Which communes are urban (sangkat)?"))

gaz = appdata.communes()
mef = appdata.communes_mef()
GAZ, MEF = "Gazetteer", "MEF 2025"
choices = [GAZ] + ([MEF] if not mef.empty else [])
source = st.radio(t("Commune data"), choices, format_func=t, horizontal=True,
                  help=t("MEF 2025 uses the current list of communes and villages. Its khum/sangkat labels are carried over from the Gazetteer."))
com = gaz if source == GAZ else mef
if source == MEF:
    n_lab = int(com["is_sangkat"].notna().sum())
    st.caption(t("MEF 2025: {n} communes, {k} with a khum/sangkat label ({r} recoded). The other {m} are left out of training.",
                 n=len(com), k=n_lab, r=int((com["label_source"] == "recoded").sum()), m=len(com) - n_lab))
if com.empty or com["is_sangkat"].isna().all():
    appdata.missing_data_notice("Commune table with khum/sangkat type (Gazetteer)")
    st.stop()

base_com = com                      # labelled source table, before any 2011 columns are added
use_db = st.toggle(t("Add 2011 commune database features"), value=False,
                   help=t("Electricity coverage, households, land and rice area per commune in 2011. Communes created after 2011 have no row and are filled with the median."))
if use_db:
    com = appdata.with_commune_db(com)
    st.caption(t("{n} of {m} communes have 2011 data.", n=int(com["electricity_pct"].notna().sum()), m=len(com)))

c1, c2, c3 = st.columns(3)
cost_fn = c1.number_input(t("Cost of missing an urban commune"), 1.0, 20.0, 3.0, 0.5)
cost_fp = c2.number_input(t("Cost of a false alarm"), 0.5, 20.0, 1.0, 0.5)
use_dt = c3.toggle(t("Use district type (leaky)"), value=False,
                   help=t("Khan/Krong districts hold mostly sangkat — see the leakage note in src/model.py"))


@st.cache_resource(show_spinner=t("Training with 5-fold CV…"))
def _run(cfn, cfp, dt, src, db):
    return model.run(com, use_district_type=dt, cost_fn=cfn, cost_fp=cfp, use_db=db)


res = _run(cost_fn, cost_fp, use_dt, source, use_db)

m = st.columns(5)
m[0].metric(t("Base rate"), f"{res['base_rate']:.1%}", help=t("of {n} communes are sangkat", n=res['n']))
m[1].metric(t("Cost-based threshold"), f"{res['threshold']:.2f}")
m[2].metric(t("Test precision"), f"{res['test']['precision']:.2f}")
m[3].metric(t("Test recall"), f"{res['test']['recall']:.2f}")
m[4].metric(t("Test PR-AUC"), f"{res['test_pr_auc']:.2f}", help=t("Compare with the base rate, not with 0.5"))

left, right = st.columns(2)
with left:
    st.subheader(t("Try another threshold"))
    thr = st.slider(t("Threshold"), 0.05, 0.95, float(res["threshold"]), 0.01)
    mt = model.metrics_at(res["y_test"], res["proba_test"], thr)
    cm = pd.DataFrame([[mt["tn"], mt["fp"]], [mt["fn"], mt["tp"]]],
                      index=[t("Actual khum"), t("Actual sangkat")], columns=[t("Predicted khum"), t("Predicted sangkat")])
    st.dataframe(cm, width="stretch")
    st.caption(t("Precision {p:.2f} · Recall {r:.2f} · F1 {f:.2f}", p=mt['precision'], r=mt['recall'], f=mt['f1']))
with right:
    st.subheader(t("Total cost by threshold (CV, training rows)"))
    fig = px.line(res["cost_curve"], x="threshold", y="cost", labels={"threshold": t("Threshold"), "cost": t("Total cost")})
    fig.add_vline(x=res["threshold"], line_dash="dash", line_color="#E24B4A")
    fig.update_layout(height=320, margin=dict(l=0, r=0, t=10, b=0))
    st.plotly_chart(style_plotly(fig), width="stretch")

# ---------------------------------------------------------------- the 2011 commune-database features
FEATURE_NAMES = {   # English keys, translated through locales/km.json
    "electricity_pct": "Electricity coverage, % of households (2011)",
    "households_2011": "Households (2011)",
    "land_ha": "Land area, ha (2011)",
    "rice_ha": "Rice field area, ha (2011)",
    "log_households_2011": "Households (2011, log)",
    "log_land_ha": "Land area (2011, log)",
    "log_rice_ha": "Rice field area (2011, log)",
    "villages": "Villages",
    "communes_in_district": "Communes in the district",
}
st.subheader(t("2011 commune features"))
explore = appdata.with_commune_db(base_com)
if "electricity_pct" not in explore:
    st.caption(t("The 2011 commune database is not available."))
else:
    f_left, f_right = st.columns(2)
    with f_left:
        have = explore.dropna(subset=["is_sangkat", "electricity_pct"])
        med = have.groupby(have["is_sangkat"].astype(int))[list(FEATURE_NAMES)[:4]].median().T
        med.index = [t(FEATURE_NAMES[i]) for i in med.index]
        med.columns = [t("Khum") if c == 0 else t("Sangkat") for c in med.columns]
        st.markdown(f"**{t('Median per commune')}**")
        st.dataframe(med.style.format("{:,.0f}"), width="stretch")
        st.caption(t("{n} of {m} communes have a 2011 row. The clearest difference is electricity: sangkat communes have far higher coverage and much less land and rice area, while household counts are similar.",
                     n=len(have), m=len(explore)))
    with f_right:
        if use_db:
            pipe = res["pipeline"]
            names = [n.split("__", 1)[1] for n in pipe.named_steps["prep"].get_feature_names_out() if n.startswith("num__")]
            coef = pd.Series(pipe.named_steps["clf"].coef_[0][:len(names)], index=names)
            cdf = pd.DataFrame({"feature": [t(FEATURE_NAMES.get(n, n)) for n in coef.index], "weight": coef.values})
            fig = px.bar(cdf.sort_values("weight"), x="weight", y="feature", orientation="h",
                         labels={"weight": t("Weight in the model (standardised)"), "feature": ""})
            fig.update_layout(height=300, margin=dict(l=0, r=0, t=10, b=0))
            st.markdown(f"**{t('What the model relies on')}**")
            st.plotly_chart(style_plotly(fig), width="stretch")
        else:
            st.info(t("Turn on “Add 2011 commune database features” above to train with these columns."))
    if use_db:
        other = _run(cost_fn, cost_fp, use_dt, source, False)
        cmp_ = pd.DataFrame({
            t("Without 2011 features"): [other["test_pr_auc"], other["cv_pr_auc"], other["test"]["precision"], other["test"]["recall"]],
            t("With 2011 features"): [res["test_pr_auc"], res["cv_pr_auc"], res["test"]["precision"], res["test"]["recall"]]},
            index=[t("Test PR-AUC"), t("CV PR-AUC"), t("Test precision"), t("Test recall")])
        st.markdown(f"**{t('Effect of the 2011 features')}**")
        st.dataframe(cmp_.style.format("{:.2f}"), width="stretch")
        st.caption(t("The 2011 data describes communes as they were then, while the labels are current. Compare PR-AUC, because the two runs pick different thresholds."))

st.info(t("Accuracy is not reported on purpose: predicting 'khum' for every commune would score {v:.0%} while finding no urban commune at all.", v=1 - res['base_rate']))
