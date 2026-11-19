"""Smoke test: every Streamlit page runs without an exception on synthetic data."""
from pathlib import Path

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from src import pipeline

ROOT = Path(__file__).resolve().parents[1]
PAGES = ["app.py", "overview.py"] + sorted(str(p.relative_to(ROOT)) for p in (ROOT / "pages").glob("*.py"))


@pytest.mark.parametrize("page", PAGES)
def test_page_runs(synthetic_data, page):
    st.cache_data.clear()
    st.cache_resource.clear()
    pipeline.build_processed()
    at = AppTest.from_file(str(ROOT / page), default_timeout=120).run()
    assert not at.exception, f"{page}: {at.exception}"


def test_pages_show_notice_without_data(tmp_path, monkeypatch):
    from src import config
    for name in ("RAW_DIR", "PROCESSED_DIR", "BOUNDARY_DIR", "LOG_DIR"):
        monkeypatch.setattr(config, name, tmp_path)
    monkeypatch.setattr(config, "CENSUS_FILE", tmp_path / "none.csv")
    monkeypatch.setattr(config, "PROVINCE_GEOJSON", tmp_path / "none.geojson")
    monkeypatch.setattr(config, "WPP_MEDIUM_FILE", tmp_path / "none2.csv")
    monkeypatch.setattr(config, "FETCH_LOG", tmp_path / "log.csv")
    st.cache_data.clear()
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60).run()
    assert not at.exception
    assert any("download_data.py" in w.value for w in at.warning)


def test_every_label_has_khmer():
    """All t("...") texts in the code must exist in locales/km.json with a value."""
    import sys
    sys.path.insert(0, str(ROOT / "scripts"))
    import check_translations
    table = __import__("json").loads(check_translations.LOCALE.read_text(encoding="utf-8"))
    missing = sorted(k for k in check_translations.used_keys() if not table.get(k))
    assert not missing, f"Add to locales/km.json: {missing}"
