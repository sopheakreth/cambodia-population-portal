"""First-time data setup: download every source into data/raw and data/boundaries.

Run from the repository root:

    python scripts/download_data.py            # everything
    python scripts/download_data.py --only wb census

Then build the processed tables:

    python scripts/build_processed.py
"""
from __future__ import annotations

import argparse
import csv
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src import config, fetch  # noqa: E402

STEPS = ["census", "wb", "boundaries", "gazetteer", "commune_db", "mef", "wpp"]


def update_manifest(file: str, source_url: str, licence: str) -> None:
    """Record a downloaded file in data/raw/MANIFEST.csv (one row per file)."""
    rows = []
    if config.MANIFEST.exists():
        with open(config.MANIFEST, newline="", encoding="utf-8") as f:
            rows = [r for r in csv.DictReader(f) if r["file"] != file]
    rows.append({"file": file, "source_url": source_url, "licence": licence,
                 "retrieved_on": date.today().isoformat(), "retrieved_by": "download_data.py"})
    with open(config.MANIFEST, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["file", "source_url", "licence", "retrieved_on", "retrieved_by"])
        w.writeheader()
        w.writerows(rows)


def main(only: list[str]) -> None:
    results = {}

    if "census" in only:
        print("[S1] Census 2019 by province (ODC) ...")
        try:
            df = fetch.fetch_census_odc()
            results["census"] = f"ok, {len(df)} rows"
            update_manifest("census2019_province.csv", config.ODC_CENSUS_DUMP, "CC BY-SA 4.0")
        except Exception as e:  # noqa: BLE001
            results["census"] = f"FAILED: {e}"

    if "wb" in only:
        print("[S7] World Bank indicators (API) ...")
        for name, code in config.WB_INDICATORS.items():
            try:
                df = fetch.fetch_worldbank(code)
                results[f"wb_{name}"] = f"ok, {len(df)} rows"
                update_manifest(f"wb_{code}.csv", f"{config.WB_BASE}/.../{code}", "CC BY 4.0")
            except Exception as e:  # noqa: BLE001
                results[f"wb_{name}"] = f"FAILED: {e}"

    if "boundaries" in only:
        print("[S2] Province / commune boundaries ...")
        saved = fetch.fetch_boundaries()
        ok = config.PROVINCE_GEOJSON.exists()
        results["boundaries"] = f"saved {saved}" if ok else "FAILED: no province.geojson"
        if ok:
            update_manifest("boundaries/province.geojson",
                            config.SOURCES[1]["url"], "CC BY 4.0")

    if "gazetteer" in only:
        print("[S3] Cambodia Gazetteer (ODC) ...")
        files = fetch.fetch_gazetteer()
        results["gazetteer"] = f"{len(files)} file(s)" if files else "FAILED (see manual steps)"
        for f in files:
            update_manifest(f.name, config.SOURCES[2]["url"], "No licence given")

    if "commune_db" in only:
        print("[S5] Commune database 2011 (ODC) ...")
        files = fetch.fetch_commune_db()
        results["commune_db"] = f"{len(files)} file(s)" if files else "FAILED (optional)"
        for f in files:
            update_manifest(f.name, config.SOURCES[4]["url"], "CC BY 4.0")

    if "mef" in only:
        print("[S4] MEF administrative lists 2025 (open API) ...")
        try:
            out = fetch.fetch_mef()
            results["mef"] = ", ".join(f"{k}: {v} rows" for k, v in out.items())
            for k in out:
                update_manifest(f"mef_{k}_2025.csv", config.MEF_API.format(dataset=config.MEF_DATASETS[k][0]), "Check portal")
        except Exception as e:  # noqa: BLE001
            results["mef"] = f"FAILED: {e}"

    if "wpp" in only:
        print("[S6] UN World Population Prospects 2024 (large download, please wait) ...")
        out = fetch.fetch_wpp()
        results["wpp"] = ", ".join(f"{k}: {len(v)} rows" for k, v in out.items()) or "FAILED"
        for k in out:
            update_manifest(f"wpp2024_khm_{k}.csv", config.WPP_FILES[k], "CC BY 3.0 IGO")

    print("\n================ SUMMARY ================")
    for k, v in results.items():
        print(f"  {k:15s} {v}")
    print(f"\nFetch log: {config.FETCH_LOG}")
    print("""
MANUAL STEPS (cannot be automated):
  1. Census 2008 and 1998 province totals come from NIS PDFs (already extracted to
     data/raw/census2008_province.csv and census1998_province.csv).
  2. If anything above FAILED, open the dataset page in your browser
     (links in docs/DATA_SOURCES.md), download the file, and save it
     under the file name shown in docs/DATA_SOURCES.md.
Next: python scripts/build_processed.py
""")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--only", nargs="*", default=STEPS, choices=STEPS)
    main(p.parse_args().only)
