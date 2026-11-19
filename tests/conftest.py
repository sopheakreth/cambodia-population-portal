"""Shared test fixtures.

`synthetic_data` builds SMALL, CLEARLY FAKE files in a temp folder with the
same layout and column names as the real sources, then points src.config at
them. Tests never touch data/ and never need the network.
"""
import json

import numpy as np
import pandas as pd
import pytest

from src import config, pipeline

FAKE_DENSITY = [130, 85, 180, 95, 125, 50, 120, 370, 11, 30, 6, 3300, 18, 215, 30,
                18, 98, 155, 14, 180, 250, 40, 245, 64, 180]


def _square(i):
    x, y = 102 + (i % 5), 10 + (i // 5)
    return {"type": "Polygon", "coordinates": [[[x, y], [x + 1, y], [x + 1, y + 1], [x, y + 1], [x, y]]]}


@pytest.fixture
def synthetic_data(tmp_path, monkeypatch):
    raw, proc, bnd, up, logs = (tmp_path / d for d in ("raw", "processed", "boundaries", "uploads", "logs"))
    for d in (raw, proc, bnd, up, logs):
        d.mkdir()
    for name, val in {
        "RAW_DIR": raw, "PROCESSED_DIR": proc, "BOUNDARY_DIR": bnd, "UPLOAD_DIR": up, "LOG_DIR": logs,
        "FETCH_LOG": logs / "fetch_log.csv", "UPLOAD_LOG": logs / "upload_log.csv",
        "MANIFEST": raw / "MANIFEST.csv", "CENSUS_FILE": raw / "census2019_province.csv",
        "WPP_MEDIUM_FILE": raw / "wpp2024_khm_medium.csv",
        "WPP_VARIANTS_FILE": raw / "wpp2024_khm_variants.csv",
        "PROVINCE_GEOJSON": bnd / "province.geojson", "COMMUNE_GEOJSON": bnd / "commune.geojson",
    }.items():
        monkeypatch.setattr(config, name, val)

    rng = np.random.default_rng(0)
    p = pipeline.PROVINCES
    area = rng.uniform(300, 15000, 25)
    total = (np.array(FAKE_DENSITY) * area).round()
    hh_size = 4.9 - 0.25 * np.log10(FAKE_DENSITY) + rng.normal(0, 0.05, 25)
    pd.DataFrame({
        "_id": range(1, 26), "pro_code": p["pro_code"], "province_k": "ខេត្ត",
        "provinces": p["province"], "households": (total / hh_size).round(),
        "males": (total * 0.49).round(), "females": (total * 0.51).round(), "total": total,
        "house_size": hh_size.round(2), "area_km2": area.round(1),
        "pop_km2": FAKE_DENSITY, "reference": "SYNTHETIC TEST DATA",
    }).to_csv(config.CENSUS_FILE, index=False)

    feats = [{"type": "Feature", "properties": {"HRName": n}, "geometry": _square(i)}
             for i, n in enumerate(p["province"])]
    config.PROVINCE_GEOJSON.write_text(json.dumps({"type": "FeatureCollection", "features": feats}))

    years = np.arange(1950, 2101)
    pop_k = 4500 + 140 * (years - 1950) - 0.9 * (years - 1950) ** 2 / 2
    pd.DataFrame({"ISO3_code": "KHM", "Time": years, "TPopulation1July": pop_k,
                  "PopDensity": pop_k / 176, "PopGrowthRate": np.gradient(pop_k) / pop_k * 100}
                 ).to_csv(config.WPP_MEDIUM_FILE, index=False)
    var = pd.concat([pd.DataFrame({"ISO3_code": "KHM", "Variant": v, "Time": years[years >= 2024],
                                   "TPopulation1July": pop_k[years >= 2024] * f})
                     for v, f in (("Low", 0.9), ("High", 1.1))])
    var.to_csv(config.WPP_VARIANTS_FILE, index=False)

    rows = []
    for iso, start in (("KHM", 10), ("THA", 20), ("VNM", 15)):
        for y in range(1960, 2025):
            rows.append({"iso3": iso, "country": iso, "indicator": "SP.URB.TOTL.IN.ZS",
                         "year": y, "value": start + 0.2 * (y - 1960)})
    pd.DataFrame(rows).to_csv(raw / "wb_SP.URB.TOTL.IN.ZS.csv", index=False)

    g = []
    for pc in range(1, 26):
        g.append({"Code": f"{pc:02d}", "Name (Latin)": f"Province {pc}", "Type": "Khaet"})
        for d in range(1, 4):
            dcode = f"{pc:02d}{d:02d}"
            dtype = "Krong" if d == 1 else "Srok"
            g.append({"Code": dcode, "Name (Latin)": f"{dtype} {pc}-{d}", "Type": dtype})
            for c in range(1, 8):
                urban = dtype == "Krong" or rng.random() < 0.05
                ccode = f"{dcode}{c:02d}"
                g.append({"Code": ccode, "Name (Latin)": f"{'Sangkat' if urban else 'Khum'} {ccode}",
                          "Type": "Sangkat" if urban else "Khum"})
                for v in range(1, int(rng.integers(3, 15)) if not urban else int(rng.integers(2, 6))):
                    g.append({"Code": f"{ccode}{v:02d}", "Name (Latin)": f"Phum {v}", "Type": "Phum"})
    pd.DataFrame(g).to_excel(raw / "gazetteer_0.xlsx", index=False)
    return tmp_path
