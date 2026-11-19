"""Cached data loaders and the shared sidebar for the Streamlit pages."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from src import config, fetch, pipeline
from src.i18n import t


@st.cache_data(show_spinner=False)
def province_table() -> pd.DataFrame:
    p = config.PROCESSED_DIR / "province.csv"
    if p.exists():
        return pd.read_csv(p)
    if config.CENSUS_FILE.exists():
        return pipeline.load_census()
    return pd.DataFrame()


@st.cache_data(show_spinner=False)
def census_years() -> list[int]:
    """Census years available, from the files in data/raw (2019 plus any older file)."""
    years = [2019]
    if config.CENSUS_2008_FILE.exists():
        years = [2008] + years
        if config.CENSUS_1998_FILE.exists():
            years = [1998] + years
    return years


@st.cache_data(show_spinner=False)
def province_for_year(year: int) -> pd.DataFrame:
    """Province table for one census year (2019 = the full table)."""
    prov = province_table()
    if year == 2019 or prov.empty:
        return prov
    h = pipeline.load_census_history(prov)
    return h[h["year"] == year].reset_index(drop=True)


@st.cache_data(show_spinner=False)
def census_history() -> pd.DataFrame:
    """Province population for every census year available (1998, 2008, 2019)."""
    prov = province_table()
    return pipeline.load_census_history(prov) if not prov.empty else pd.DataFrame()


@st.cache_data(show_spinner=False)
def province_geojson() -> dict | None:
    if not config.PROVINCE_GEOJSON.exists():
        return None
    gj, _ = pipeline.load_province_geojson()
    return gj


@st.cache_data(show_spinner=False)
def national() -> pd.DataFrame:
    p = config.PROCESSED_DIR / "national.csv"
    return pd.read_csv(p) if p.exists() else pipeline.national_series()


@st.cache_data(show_spinner=False)
def communes() -> pd.DataFrame:
    p = config.PROCESSED_DIR / "commune.csv"
    return pd.read_csv(p, dtype={"commune_code": str, "district_code": str}) if p.exists() else pd.DataFrame()


@st.cache_data(show_spinner=False)
def communes_mef() -> pd.DataFrame:
    """Commune table on the MEF 2025 structure (labels carried over from the Gazetteer)."""
    com = communes()
    return pipeline.load_communes_mef(com) if not com.empty else pd.DataFrame()


@st.cache_data(show_spinner=False)
def with_commune_db(com: pd.DataFrame) -> pd.DataFrame:
    """A commune table plus the 2011 commune-database features (matched on commune_code)."""
    return pipeline.attach_commune_db(com)


@st.cache_data(show_spinner=False)
def asean() -> pd.DataFrame:
    p = config.PROCESSED_DIR / "asean_wb.csv"
    return pd.read_csv(p) if p.exists() else pd.DataFrame()


def missing_data_notice(what: str) -> None:
    st.warning(
        t("{what} not found. On your computer, from the repository folder, run:", what=t(what))
        + "\n\n```\npython scripts/download_data.py\npython scripts/build_processed.py\n```"
    )


def sidebar_sources() -> None:
    """'Automatic sources' box + refresh button, shown on every page."""
    with st.sidebar:
        st.divider()
        st.caption(t("Automatic sources"))
        log = fetch.read_fetch_log()
        if log.empty:
            st.caption(t("No pulls yet."))
        else:
            last = log.sort_values("timestamp").groupby("source").tail(1)
            for _, r in last[last["source"].str.match(r"(odc_census|worldbank)")].iterrows():
                icon = "✅" if r["status"] == "ok" else "⚠️"
                rows = "" if pd.isna(r["rows"]) else " · " + t("{n} rows", n=int(r["rows"]))
                st.caption(f"{icon} {r['source']} · {str(r['timestamp'])[:10]}{rows}")
        if st.button(t("Refresh now"), icon=":material/refresh:", width="stretch"):
            with st.spinner(t("Pulling census and World Bank data…")):
                status = fetch.fetch_automatic()
                pipeline.build_processed()
            st.cache_data.clear()
            bad = {k: v for k, v in status.items() if v != "ok"}
            if bad:
                st.warning(t("Some pulls failed: {bad}", bad=bad))
            else:
                st.rerun()
