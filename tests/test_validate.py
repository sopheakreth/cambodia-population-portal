import pandas as pd

from src.validate import store_upload, validate


def _good():
    return pd.DataFrame({"province": ["Phnom Penh", "Kandal"], "year": [2023, 2023],
                         "measure": ["population", "population"], "value": [2.3e6, 1.2e6],
                         "unit": ["persons", "persons"]})


def test_valid_file_passes():
    acc, rej, err = validate(_good(), "province_indicator")
    assert len(acc) == 2 and rej.empty and not err


def test_missing_column_rejects_everything():
    acc, rej, err = validate(_good().drop(columns="unit"), "province_indicator")
    assert acc.empty and len(rej) == 2 and "unit" in err[0]


def test_bad_rows_get_reasons():
    df = _good()
    df.loc[2] = ["Atlantis", 2023, "population", 5, "persons"]
    df.loc[3] = ["Takeo", 2023, "population", "abc", "persons"]
    df.loc[4] = ["Kep", 2023, "population", -1, "persons"]
    df.loc[5] = ["Kep", 1800, "population", 1, "persons"]
    df.loc[6] = ["Kep", 2023, "population", 1, "furlongs"]
    acc, rej, _ = validate(df, "province_indicator")
    reasons = dict(zip(rej["province"], rej["reason"]))
    assert len(acc) == 2 and len(rej) == 5
    assert reasons["Atlantis"] == "Unknown province name"
    assert "not a number" in rej.loc[rej["row"] == 5, "reason"].iloc[0]
    assert set(rej["row"]) == {4, 5, 6, 7, 8}


def test_column_names_are_normalised():
    df = _good().rename(columns={"province": "Province ", "value": "VALUE"})
    acc, rej, _ = validate(df, "province_indicator")
    assert len(acc) == 2


def test_store_upload_logs(synthetic_data):
    acc, rej, _ = validate(_good(), "province_indicator")
    dest = store_upload(acc, "my file.csv", "province_indicator", len(rej))
    assert dest.exists() and "my_file" in dest.name
    log = pd.read_csv(synthetic_data / "logs" / "upload_log.csv")
    assert log.iloc[-1]["accepted"] == 2
