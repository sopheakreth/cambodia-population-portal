import json
from pathlib import Path

import pandas as pd
import pytest
import requests

from src import config, fetch

SAMPLE = json.loads((Path(__file__).parent / "fixtures" / "worldbank_sample.json").read_text())


def test_parse_worldbank_json():
    df = fetch.parse_worldbank_json([SAMPLE])
    assert list(df.columns) == ["iso3", "country", "indicator", "year", "value"]
    assert len(df) == 4 and df["year"].dtype.kind == "i"
    assert df["value"].isna().sum() == 1          # null values are kept, not dropped


def test_log_pull_writes_header_once(synthetic_data):
    fetch.log_pull("a", "http://x", 3, "ok")
    fetch.log_pull("b", "http://y", None, "error", "boom")
    log = fetch.read_fetch_log()
    assert list(log["source"]) == ["a", "b"] and log.iloc[1]["status"] == "error"


class _Resp:
    def __init__(self, js):
        self._js = js

    def json(self):
        return self._js

    def raise_for_status(self):
        pass


def test_fetch_worldbank_saves_and_logs(synthetic_data, monkeypatch):
    monkeypatch.setattr(fetch, "http_get", lambda *a, **k: _Resp(SAMPLE))
    df = fetch.fetch_worldbank("SP.URB.TOTL.IN.ZS", ["KHM"])
    assert (config.RAW_DIR / "wb_SP.URB.TOTL.IN.ZS.csv").exists()
    assert fetch.read_fetch_log().iloc[-1]["rows"] == len(df)


def test_network_error_is_logged(synthetic_data, monkeypatch):
    def boom(*a, **k):
        raise requests.ConnectionError("offline")
    monkeypatch.setattr(fetch, "http_get", boom)
    with pytest.raises(requests.ConnectionError):
        fetch.fetch_worldbank("SP.POP.TOTL", ["KHM"])
    last = fetch.read_fetch_log().iloc[-1]
    assert last["status"] == "error" and "offline" in last["error"]


def test_geojson_level_guess(synthetic_data):
    gj = {"type": "FeatureCollection", "features": [{}] * 25}
    assert fetch._save_by_level(gj, "t") == "province"
    assert pd.notna(config.PROVINCE_GEOJSON.stat().st_size)
