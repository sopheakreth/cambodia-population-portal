import pandas as pd
import streamlit as st

from src import appdata, config
from src.i18n import columns, t
from src.validate import SCHEMAS, read_upload, store_upload, validate

appdata.sidebar_sources()
st.title(t("Upload data"))

schema = st.selectbox(t("File type"), list(SCHEMAS), format_func=lambda k: f"{k} — {t(SCHEMAS[k]['description'])}")
cols = ", ".join(f"`{c}` ({t})" for c, t in SCHEMAS[schema]["columns"].items())
st.caption(t("Required columns: {cols}", cols=cols))
if "units" in SCHEMAS[schema]:
    st.caption(t("Allowed units:") + " " + ", ".join(sorted(SCHEMAS[schema]["units"])))

up = st.file_uploader(t("CSV or Excel file"), type=["csv", "xlsx", "xls"])
if up is not None:
    try:
        raw = read_upload(up, up.name)
    except Exception as e:  # noqa: BLE001
        st.error(t("Couldn't read that file: {e}", e=e))
        st.stop()
    accepted, rejected, errors = validate(raw, schema)
    for e in errors:
        st.error(e)
    if len(accepted):
        dest = store_upload(accepted, up.name, schema, len(rejected))
        st.success(t("{n} rows accepted and stored as {name}", n=len(accepted), name=dest.name))
    if len(rejected):
        st.warning(t("{n} rows rejected — reasons below", n=len(rejected)))
        st.dataframe(rejected, hide_index=True, width="stretch")
        st.download_button(t("Download rejected rows"), rejected.to_csv(index=False),
                           file_name=f"rejected_{up.name}.csv", mime="text/csv")

st.subheader(t("Upload history"))
if config.UPLOAD_LOG.exists():
    st.dataframe(columns(pd.read_csv(config.UPLOAD_LOG)), hide_index=True, width="stretch")
else:
    st.caption(t("No uploads yet."))
