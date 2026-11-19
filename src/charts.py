"""Plotly chart builders (Week 12). Every chart title states its finding."""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from sklearn.metrics import precision_recall_curve

from src.i18n import style_plotly, t

BLUES = ["#E6F1FB", "#B5D4F4", "#85B7EB", "#378ADD", "#185FA5", "#0C447C"]

# Fixed, stated class breaks per measure (shown in the legend)
BREAKS = {
    "density_calc": [0, 25, 75, 150, 300, np.inf],
    "household_size": [0, 4.0, 4.2, 4.4, 4.6, np.inf],
    "pop_share_pct": [0, 2, 4, 6, 10, np.inf],
    "households_per_km2": [0, 5, 15, 35, 70, np.inf],
    "sex_ratio": [0, 92, 94, 96, 98, np.inf],
}
HIST_MEASURES = ["density_calc", "pop_share_pct"]  # measures available for 1998 and 2008
LABELS = {  # English keys; show them with label(measure)
    "density_calc": "People per km²",
    "household_size": "People per household",
    "pop_share_pct": "Share of national population (%)",
    "households_per_km2": "Households per km²",
    "sex_ratio": "Males per 100 females",
}


def label(measure: str) -> str:
    return t(LABELS.get(measure, measure))


def classify(values: pd.Series, breaks: list[float]) -> pd.Series:
    """Bin values into labelled classes like '25–75'."""
    labels = []
    for lo, hi in zip(breaks[:-1], breaks[1:]):
        labels.append(f"≥ {lo:g}" if np.isinf(hi) else f"{lo:g}–{hi:g}")
    return pd.cut(values, bins=breaks, labels=labels, right=False)


def choropleth(df: pd.DataFrame, geojson: dict, measure: str, title: str,
               highlight: int | None = None) -> go.Figure:
    breaks = BREAKS.get(measure) or list(df[measure].quantile([0, .2, .4, .6, .8]).values) + [np.inf]
    d = df.copy()
    d["province"] = d["province"].map(t)
    d["class"] = classify(d[measure], breaks).astype(str)
    order = [c for c in classify(pd.Series(dtype=float), breaks).cat.categories]
    cmap = {c: BLUES[i + 1] if i + 1 < len(BLUES) else BLUES[-1] for i, c in enumerate(order)}
    fig = px.choropleth(
        d, geojson=geojson, locations="pro_code", featureidkey="properties.pro_code",
        color="class", category_orders={"class": order}, color_discrete_map=cmap,
        hover_name="province", custom_data=["pro_code"],
        hover_data={measure: ":.1f", "class": False, "pro_code": False},
        labels={"class": label(measure)},
    )
    fig.update_geos(fitbounds="locations", visible=False)
    fig.update_traces(marker_line_color="white", marker_line_width=0.6)
    if highlight is not None:
        sel = d[d["pro_code"] == highlight]
        fig.add_trace(go.Choropleth(
            geojson=geojson, locations=sel["pro_code"], featureidkey="properties.pro_code",
            z=[1] * len(sel), colorscale=[[0, "rgba(0,0,0,0)"], [1, "rgba(0,0,0,0)"]],
            showscale=False, marker_line_color="#E24B4A", marker_line_width=2.5,
            hoverinfo="skip"))
    fig.update_layout(title=title, margin=dict(l=0, r=0, t=40, b=0), height=430,
                      legend=dict(title=label(measure), orientation="h", y=-0.05))
    return style_plotly(fig)


def population_chart(nat: pd.DataFrame, forecast: pd.DataFrame | None = None,
                     title: str | None = None, mark_year: int | None = None) -> go.Figure:
    title = title or t("Population, 1950–2100")
    fig = go.Figure()
    est = nat[nat.get("kind", "estimate") == "estimate"] if "kind" in nat else nat
    proj = nat[nat["kind"] == "projection"] if "kind" in nat else nat.iloc[0:0]
    if {"pop_low", "pop_high"} <= set(nat.columns) and not proj.empty:
        fig.add_trace(go.Scatter(x=list(proj["year"]) + list(proj["year"][::-1]),
                                 y=list(proj["pop_high"] / 1e6) + list(proj["pop_low"][::-1] / 1e6),
                                 fill="toself", fillcolor="rgba(127,119,221,0.2)",
                                 line=dict(width=0), name=t("UN low–high variant")))
    fig.add_trace(go.Scatter(x=est["year"], y=est["population"] / 1e6, name=t("Recorded (UN estimate)"),
                             line=dict(color="#185FA5", width=2.5)))
    if not proj.empty:
        fig.add_trace(go.Scatter(x=proj["year"], y=proj["population"] / 1e6, name=t("UN medium projection"),
                                 line=dict(color="#534AB7", width=2, dash="dash")))
    if forecast is not None:
        for col, color, dash in (("naive_drift", "#888780", "dot"), ("holt_damped", "#D85A30", "solid")):
            if col in forecast:
                fig.add_trace(go.Scatter(x=forecast.index, y=forecast[col] / 1e6,
                                         name=t(col.replace("_", " ")), line=dict(color=color, dash=dash)))
    fig.update_layout(title=title, yaxis_title=t("Million people"), xaxis_title=None,
                      height=400, margin=dict(l=0, r=0, t=40, b=0), legend=dict(orientation="h", y=-0.15))
    fig.update_yaxes(rangemode="tozero")
    if mark_year is not None:   # the census year picked on the page
        fig.add_vline(x=mark_year, line_dash="dot", line_color="#888780",
                      annotation_text=t("Census {year}", year=mark_year), annotation_position="top left")
    return style_plotly(fig)


def scatter_density_household(df: pd.DataFrame) -> tuple[go.Figure, float]:
    """H2 test: household size vs log density. Returns figure and Spearman r."""
    d = df.dropna(subset=["density_calc", "household_size"]).copy()
    d["province"] = d["province"].map(t)
    r = d["density_calc"].corr(d["household_size"], method="spearman")
    fig = px.scatter(d, x="density_calc", y="household_size", text="province", log_x=True,
                     trendline="ols", trendline_options=dict(log_x=True),
                     labels={"density_calc": t("People per km² (log scale)"),
                             "household_size": t("People per household")})
    fig.update_traces(textposition="top center", textfont_size=10, marker=dict(size=9, color="#378ADD"))
    title = (t("Denser provinces have smaller households (Spearman r = {r:.2f})", r=r) if r < 0
             else t("Denser provinces have larger households (Spearman r = {r:.2f})", r=r))
    fig.update_layout(title=title,
                      height=420, margin=dict(l=0, r=0, t=40, b=0))
    return style_plotly(fig), float(r)


def urban_share_chart(asean: pd.DataFrame, code: str = "SP.URB.TOTL.IN.ZS") -> go.Figure:
    d = asean[asean["indicator"] == code].dropna(subset=["value"])
    d = d.assign(country=d["country"].map(t))
    fig = px.line(d, x="year", y="value", color="country",
                  labels={"value": t("Urban population (% of total)"), "year": "", "country": t("country")})
    home = t("Cambodia")
    fig.for_each_trace(lambda tr: tr.update(line_width=4 if tr.name == home else 1.2,
                                            opacity=1 if tr.name == home else 0.5))
    # TODO: once you have looked at the data, replace this title with the finding
    fig.update_layout(title=t("Urban share: Cambodia (thick line) against ASEAN neighbours"),
                      height=400, margin=dict(l=0, r=0, t=40, b=0))
    return style_plotly(fig)


def share_trend_chart(hist: pd.DataFrame, title: str, codes: tuple[int, ...] = (12, 8, 21)) -> go.Figure:
    """Population share of selected provinces at each census year (default: Phnom Penh, Kandal, Takeo)."""
    d = hist[hist["pro_code"].isin(codes)]
    if "merged" in d:
        d = d[~((d["pro_code"] == 25) & d["merged"])]
    d = d.assign(province=d["province"].map(t))
    fig = px.line(d, x="year", y="pop_share_pct", color="province", markers=True,
                  labels={"pop_share_pct": t("Share of national population (%)"), "year": "", "province": ""})
    fig.update_xaxes(tickvals=sorted(d["year"].unique()))
    fig.update_yaxes(rangemode="tozero")
    fig.update_layout(title=title, height=340, margin=dict(l=0, r=0, t=40, b=0), legend=dict(orientation="h", y=-0.2))
    return style_plotly(fig)


def urban_trend_chart(nat: pd.DataFrame, title: str, break_years: tuple[int, int] = (2008, 2019)) -> go.Figure:
    """Cambodia's urban share over time, with the span between the 2008 and 2019 censuses shaded."""
    d = nat.dropna(subset=["urban_pct"])
    fig = px.line(d, x="year", y="urban_pct", labels={"urban_pct": t("Urban population (% of total)"), "year": ""})
    fig.update_traces(line=dict(color="#185FA5", width=2.5))
    fig.add_vrect(x0=break_years[0], x1=break_years[1], fillcolor="#888780", opacity=0.15, line_width=0,
                  annotation_text=t("Steep rise between the 2008 and 2019 censuses"), annotation_position="top left")
    fig.update_yaxes(rangemode="tozero")
    fig.update_layout(title=title, height=340, margin=dict(l=0, r=0, t=40, b=0))
    return style_plotly(fig)


def pr_curve_chart(y_true, proba, base_rate: float, title: str) -> go.Figure:
    """Precision-recall curve on the test set, with the base rate (a model that guesses) as reference."""
    p, r, _ = precision_recall_curve(y_true, proba)
    fig = go.Figure(go.Scatter(x=r, y=p, mode="lines", line=dict(color="#185FA5", width=2.5), name=t("Model")))
    fig.add_hline(y=base_rate, line_dash="dash", line_color="#888780",
                  annotation_text=t("Base rate: {v:.0%} of communes are sangkat", v=base_rate), annotation_position="bottom right")
    fig.update_layout(title=title, xaxis_title=t("Recall (share of sangkat found)"),
                      yaxis_title=t("Precision (share of flagged that are sangkat)"),
                      height=340, margin=dict(l=0, r=0, t=40, b=0))
    fig.update_yaxes(range=[0, 1.02])
    return style_plotly(fig)


def forecast_chart(nat: pd.DataFrame, fc: pd.DataFrame, train_start: int, title: str) -> go.Figure:
    """Forward forecast of the two simple models against the UN medium projection and its low-high range."""
    est = nat[nat["kind"] == "estimate"] if "kind" in nat else nat
    est = est[est["year"] >= train_start]
    un = nat[nat["year"].between(est["year"].max(), fc.index.max())] if len(fc) else nat.iloc[0:0]
    fig = go.Figure()
    if {"pop_low", "pop_high"} <= set(un.columns) and un["pop_low"].notna().any():
        fig.add_trace(go.Scatter(x=list(un["year"]) + list(un["year"][::-1]),
                                 y=list(un["pop_high"] / 1e6) + list(un["pop_low"][::-1] / 1e6),
                                 fill="toself", fillcolor="rgba(127,119,221,0.2)", line=dict(width=0),
                                 name=t("UN low–high variant")))
    fig.add_trace(go.Scatter(x=est["year"], y=est["population"] / 1e6, name=t("Recorded (UN estimate)"),
                             line=dict(color="#185FA5", width=2.5)))
    if len(un):
        fig.add_trace(go.Scatter(x=un["year"], y=un["population"] / 1e6, name=t("UN medium projection"),
                                 line=dict(color="#534AB7", width=2, dash="dash")))
    for col, color, dash in (("naive_drift", "#888780", "dot"), ("holt_damped", "#D85A30", "solid")):
        if col in fc:
            fig.add_trace(go.Scatter(x=fc.index, y=fc[col] / 1e6, name=t(col.replace("_", " ")),
                                     line=dict(color=color, dash=dash, width=2)))
    fig.update_layout(title=title, yaxis_title=t("Million people"), xaxis_title=None, height=400,
                      margin=dict(l=0, r=0, t=40, b=0), legend=dict(orientation="h", y=-0.15))
    fig.update_yaxes(rangemode="tozero")
    return style_plotly(fig)
