import numpy as np
import pandas as pd
import pytest

from src import forecast, model, pipeline


@pytest.mark.parametrize("name,code", [
    ("Phnom Penh", 12), ("Krong Phnom Penh", 12), ("Siemreap", 17), ("SIEM REAP", 17),
    ("Rotanak Kiri", 16), ("Mondulkiri", 11), ("Sihanoukville", 18), ("Tboung Khmum", 25),
    ("Otdar Mean Chey", 22), ("Kratié", 10), ("Banteay Mean Chey Province", 1), ("Atlantis", None),
])
def test_match_province(name, code):
    assert pipeline.match_province(name) == code


def test_flag_outliers_never_drops_rows():
    df = pd.DataFrame({"x": [1, 2, 3, 4, 5, 1000]})
    out = pipeline.flag_outliers(df, "x")
    assert len(out) == 6 and out["x_outlier"].tolist() == [False] * 5 + [True]


def test_census_pipeline(synthetic_data):
    prov = pipeline.load_census()
    assert len(prov) == 25 and prov["province"].notna().all()
    assert np.allclose(prov["density_calc"], prov["population"] / prov["area_km2"])
    assert prov["pop_share_pct"].sum() == pytest.approx(100)
    assert prov.loc[prov["pro_code"] == 12, "density_calc_outlier"].item()   # Phnom Penh flagged


def test_geojson_gets_codes(synthetic_data):
    gj, match = pipeline.load_province_geojson()
    assert match["pro_code"].notna().all() and len(match) == 25
    assert all("pro_code" in f["properties"] for f in gj["features"])


def test_national_series_and_build(synthetic_data):
    nat = pipeline.national_series()
    assert nat["year"].min() == 1950 and nat["year"].max() == 2100
    assert {"pop_low", "pop_high", "urban_pct", "pop_growth_pct"} <= set(nat.columns)
    report = pipeline.build_processed()
    assert report["province"] == 25 and report["commune"] > 0


def test_gazetteer_parse(synthetic_data):
    com = pipeline.load_communes()
    assert len(com) == 25 * 3 * 7
    assert com["is_sangkat"].isin([0, 1]).all()
    assert (com["villages"] > 0).all()
    assert set(com["district_type"]) <= {"krong", "srok", "khan", "unknown"}


def test_forecast_beats_or_not(synthetic_data):
    nat = pipeline.national_series()
    s = nat[nat["kind"] == "estimate"].set_index("year")["population"]
    preds, scores = forecast.evaluate(s, 2015)
    assert set(scores.index) == {"naive_drift", "holt_damped"}
    assert preds.index.min() == 2015 and scores["MAE"].notna().all()


def test_model_runs(synthetic_data):
    com = pipeline.load_communes()
    res = model.run(com)
    assert 0 < res["base_rate"] < 0.6
    assert 0.05 <= res["threshold"] <= 0.95
    assert 0 <= res["test"]["recall"] <= 1


def test_commune_code_check_matches_on_code(synthetic_data, tmp_path, monkeypatch):
    from src import config
    mef = tmp_path / "mef.csv"
    mef.write_text("province_code,district_code,commune_code,commune_kh,commune_en\n"
                   "01,0101,010101,ក,Alpha\n01,0101,010199,ខ,Newone\n")
    dist = tmp_path / "dist.csv"
    dist.write_text("province_code,district_code,district_kh,district_en\n01,0101,ក,D\n")
    monkeypatch.setattr(config, "MEF_DISTRICT_FILE", dist)
    com = pd.DataFrame({"commune_code": ["010101", "010102"], "district_code": ["0101", "0101"],
                        "pro_code": [1, 1], "name": ["alpha", "beta"]})
    summary, only_mef, only_app = pipeline.commune_code_check(com, mef)
    assert summary["matched"] == 1 and summary["only_mef"] == 1 and summary["only_app"] == 1
    assert summary["districts_only_mef"] == 0 and summary["districts_only_app"] == 0
    assert only_mef["commune_code"].tolist() == ["010199"]


def test_mef_commune_table_carries_labels(synthetic_data, tmp_path, monkeypatch):
    from src import config
    monkeypatch.setattr(config, "MEF_COMMUNE_FILE", tmp_path / "c.csv")
    monkeypatch.setattr(config, "MEF_VILLAGE_FILE", tmp_path / "v.csv")
    monkeypatch.setattr(config, "MEF_DISTRICT_FILE", tmp_path / "d.csv")
    (tmp_path / "c.csv").write_text("province_code,district_code,commune_code,commune_kh,commune_en\n"
                                    "01,0101,010101,ក,Alpha\n01,0101,010199,ខ,Beta\n01,0101,010198,គ,Zed\n")
    (tmp_path / "v.csv").write_text("province_code,district_code,commune_code,village_code,village_kh,village_en\n"
                                    "01,0101,010101,01010101,ក,v1\n01,0101,010101,01010102,ខ,v2\n")
    com = pd.DataFrame({"commune_code": ["010101", "010102"], "district_code": ["0101", "0101"], "pro_code": [1, 1],
                        "name": ["alpha", "beta"], "is_sangkat": [1, 0], "villages": [2, 3],
                        "district_type": ["krong", "krong"], "communes_in_district": [2, 2]})
    out = pipeline.load_communes_mef(com).set_index("commune_code")
    assert out.loc["010101", "is_sangkat"] == 1 and out.loc["010101", "villages"] == 2
    assert out.loc["010199", "is_sangkat"] == 0 and out.loc["010199", "label_source"] == "recoded"   # same name 'beta', same province
    assert pd.isna(out.loc["010198", "is_sangkat"]) and out.loc["010198", "label_source"] == "missing"
    assert (out["communes_in_district"] == 3).all()


def test_commune_db_blocks_are_stacked_by_position(synthetic_data, tmp_path, monkeypatch):
    """The ODC commune database is 5 stacked tables of the same communes; rebuild one row per commune."""
    from src import config
    monkeypatch.setattr(config, "RAW_DIR", tmp_path)
    cols = ["Commune", "LSize_Ha", "Com_Code", "NCDD_CodeC", "HH", "RiField_Ha", "Per_HH_El", "Acronym_C", "Acronym_D"]
    z = lambda **kw: {c: kw.get(c, "0.00000000000") for c in cols}
    rows = []
    for b in range(5):
        for name, code, land, hh in (("A", "010101", "50", "120"), ("B", "010102", "70", "300")):
            kw = {"Commune": name, "Acronym_C": "", "Acronym_D": ""}
            if b == 0: kw["LSize_Ha"] = land
            if b == 3: kw["NCDD_CodeC"] = code + ".00000000000"
            if b == 4: kw["HH"] = hh
            rows.append(z(**kw))
    pd.DataFrame(rows).to_csv(tmp_path / "commune_db_2011_0.csv", index=False)
    out = pipeline.load_commune_db().set_index("commune_code")
    assert out.loc["010101", "households_2011"] == 120 and out.loc["010102", "land_ha"] == 70
    assert len(out) == 2


def test_forecast_ahead_uses_chosen_range():
    s = pd.Series(np.linspace(10e6, 16e6, 40), index=range(1984, 2024))
    fc = forecast.forecast_ahead(s, 2035, train_start=2000)
    assert list(fc.index) == list(range(2024, 2036))
    assert {"naive_drift", "holt_damped"} <= set(fc.columns)
    assert (fc["naive_drift"].diff().dropna() > 0).all()          # trend continues upward
    _, scores = forecast.evaluate(s, 2015, train_start=2000)
    assert scores["n"].iloc[0] == 9                               # test years 2015..2023


def test_census_total_check_flags_mismatch(monkeypatch):
    from src import config
    monkeypatch.setattr(config, "CENSUS_NATIONAL_TOTALS", {2008: 100, 2019: 250})
    hist = pd.DataFrame({"year": [2008, 2008, 2019, 2019], "pro_code": [1, 2, 1, 2],
                         "population": [60, 40, 120, 120], "merged": [False] * 4})
    out = pipeline.census_total_check(hist).set_index("year")
    assert out.loc[2008, "ok"] and not out.loc[2019, "ok"] and out.loc[2019, "difference"] == -10
