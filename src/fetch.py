"""Data retrieval: one function per source. Every pull is logged.

Log format (data/logs/fetch_log.csv):
    timestamp, source, url, rows, status, error

Run everything from the repository root with:
    python -m src.fetch            # automatic sources only (census + World Bank)
    python scripts/download_data.py  # every source, first-time setup
"""
from __future__ import annotations

import csv
import gzip
import io
import json
import shutil
import tempfile
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

from src import config

HEADERS = {"User-Agent": "cambodia-population-portal/1.0 (student project)"}
TIMEOUT = 60


# ---------------------------------------------------------------- logging
def log_pull(source: str, url: str, rows: int | None, status: str, error: str = "") -> None:
    """Append one line to the fetch log (creates the file with a header)."""
    new = not config.FETCH_LOG.exists()
    with open(config.FETCH_LOG, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["timestamp", "source", "url", "rows", "status", "error"])
        w.writerow([datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    source, url, "" if rows is None else rows, status, error[:300]])


def read_fetch_log() -> pd.DataFrame:
    if not config.FETCH_LOG.exists():
        return pd.DataFrame(columns=["timestamp", "source", "url", "rows", "status", "error"])
    return pd.read_csv(config.FETCH_LOG)


# ---------------------------------------------------------------- HTTP helpers
def http_get(url: str, *, params: dict | None = None, stream: bool = False,
             retries: int = 3) -> requests.Response:
    """GET with a few retries and a back-off. Raises on final failure."""
    last = None
    for attempt in range(retries):
        try:
            r = requests.get(url, params=params, headers=HEADERS,
                             timeout=TIMEOUT, stream=stream)
            r.raise_for_status()
            return r
        except requests.RequestException as e:  # noqa: PERF203
            last = e
            time.sleep(2 * (attempt + 1))
    raise last  # type: ignore[misc]


def download_file(url: str, dest: Path) -> Path:
    """Stream a URL to disk."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    with http_get(url, stream=True) as r, open(dest, "wb") as f:
        shutil.copyfileobj(r.raw, f)
    return dest


# ---------------------------------------------------------------- CKAN (Open Development Cambodia)
def ckan_package(package_id: str) -> dict:
    """Return CKAN package metadata, trying each known ODC API base."""
    errors = []
    for base in config.ODC_CKAN_APIS:
        try:
            r = http_get(f"{base}/package_show", params={"id": package_id})
            data = r.json()
            if data.get("success"):
                return data["result"]
        except Exception as e:  # noqa: BLE001
            errors.append(f"{base}: {e}")
    raise RuntimeError(f"CKAN package '{package_id}' not found. " + " | ".join(errors))


def ckan_resources(package_id: str, formats: tuple[str, ...]) -> list[dict]:
    """Resources of a package whose format matches one of `formats` (case-insensitive)."""
    pkg = ckan_package(package_id)
    want = {f.lower() for f in formats}
    out = []
    for res in pkg.get("resources", []):
        fmt = (res.get("format") or "").lower()
        url = res.get("url") or ""
        ext = url.rsplit(".", 1)[-1].lower() if "." in url else ""
        if fmt in want or ext in want:
            out.append(res)
    return out


# ---------------------------------------------------------------- S1 census 2019
def fetch_census_odc() -> pd.DataFrame:
    """Census 2019 final totals by province -> data/raw/census2019_province.csv"""
    url = config.ODC_CENSUS_DUMP
    try:
        r = http_get(url)
        df = pd.read_csv(io.StringIO(r.content.decode("utf-8-sig")))
        df.to_csv(config.CENSUS_FILE, index=False)
        log_pull("odc_census2019", url, len(df), "ok")
        return df
    except Exception as e:  # noqa: BLE001
        log_pull("odc_census2019", url, None, "error", str(e))
        raise


# ---------------------------------------------------------------- S7 World Bank
def parse_worldbank_json(pages: list) -> pd.DataFrame:
    """Turn World Bank API JSON pages into a tidy table (iso3, country, year, value)."""
    rows = []
    for page in pages:
        if not isinstance(page, list) or len(page) < 2 or page[1] is None:
            continue
        for rec in page[1]:
            rows.append({
                "iso3": rec.get("countryiso3code") or rec["country"]["id"],
                "country": rec["country"]["value"],
                "indicator": rec["indicator"]["id"],
                "year": int(rec["date"]),
                "value": rec["value"],
            })
    df = pd.DataFrame(rows, columns=["iso3", "country", "indicator", "year", "value"])
    return df.sort_values(["iso3", "year"]).reset_index(drop=True)


def fetch_worldbank(indicator: str, countries: list[str] | None = None) -> pd.DataFrame:
    """One World Bank indicator for the given countries -> data/raw/wb_<indicator>.csv"""
    countries = countries or config.ASEAN
    url = f"{config.WB_BASE}/country/{';'.join(countries)}/indicator/{indicator}"
    try:
        pages, page, total = [], 1, 1
        while page <= total:
            r = http_get(url, params={"format": "json", "per_page": 1000, "page": page})
            js = r.json()
            if isinstance(js, list) and js and "message" in js[0]:
                raise RuntimeError(js[0]["message"])
            pages.append(js)
            total = int(js[0].get("pages", 1))
            page += 1
        df = parse_worldbank_json(pages)
        df.to_csv(config.RAW_DIR / f"wb_{indicator}.csv", index=False)
        log_pull(f"worldbank_{indicator}", url, len(df), "ok")
        return df
    except Exception as e:  # noqa: BLE001
        log_pull(f"worldbank_{indicator}", url, None, "error", str(e))
        raise


# ---------------------------------------------------------------- S6 UN WPP 2024
def fetch_wpp(iso3: str = "KHM") -> dict[str, pd.DataFrame]:
    """Download the WPP 2024 demographic-indicator files and keep only `iso3`.

    The global files are large (tens of MB), so they are streamed to a temp
    file, filtered in chunks, and only the small Cambodia extract is kept.
    """
    out = {}
    targets = {"medium": config.WPP_MEDIUM_FILE, "variants": config.WPP_VARIANTS_FILE}
    for key, url in config.WPP_FILES.items():
        try:
            with tempfile.TemporaryDirectory() as tmp:
                gz = download_file(url, Path(tmp) / "wpp.csv.gz")
                parts = []
                with gzip.open(gz, "rt", encoding="utf-8", errors="replace") as fh:
                    for chunk in pd.read_csv(fh, chunksize=100_000, low_memory=False):
                        parts.append(chunk[chunk["ISO3_code"] == iso3])
                df = pd.concat(parts, ignore_index=True)
            df.to_csv(targets[key], index=False)
            log_pull(f"wpp2024_{key}", url, len(df), "ok")
            out[key] = df
        except Exception as e:  # noqa: BLE001
            log_pull(f"wpp2024_{key}", url, None, "error", str(e))
            print(f"  ! WPP {key} failed: {e}")
    return out


# ---------------------------------------------------------------- S2 boundaries
def _geojson_from_bytes(content: bytes, url: str) -> list[dict]:
    """Return one or more GeoJSON dicts from raw bytes (plain or zipped)."""
    if url.lower().endswith(".zip") or content[:2] == b"PK":
        found = []
        with zipfile.ZipFile(io.BytesIO(content)) as z:
            for name in z.namelist():
                if name.lower().endswith((".geojson", ".json")):
                    found.append(json.loads(z.read(name)))
        return found
    return [json.loads(content)]


def _save_by_level(gj: dict, tag: str) -> str | None:
    """Guess the admin level from the feature count and save to the right file."""
    n = len(gj.get("features", []))
    if 20 <= n <= 30:
        path, level = config.PROVINCE_GEOJSON, "province"
    elif 1000 <= n <= 2500:
        path, level = config.COMMUNE_GEOJSON, "commune"
    elif 150 <= n <= 250:
        path, level = config.BOUNDARY_DIR / "district.geojson", "district"
    else:
        path, level = config.BOUNDARY_DIR / f"other_{tag}.geojson", f"other({n})"
    path.write_text(json.dumps(gj), encoding="utf-8")
    return level


def fetch_boundaries() -> list[str]:
    """ODC 'Basic map of Cambodia 2014' GeoJSON; geoBoundaries as fallback."""
    saved = []
    try:
        resources = ckan_resources(config.ODC_PACKAGES["boundaries"], ("geojson", "json", "zip"))
        for i, res in enumerate(resources):
            url = res["url"]
            try:
                r = http_get(url)
                for j, gj in enumerate(_geojson_from_bytes(r.content, url)):
                    level = _save_by_level(gj, f"{i}_{j}")
                    saved.append(level)
                    log_pull(f"odc_boundaries_{level}", url, len(gj.get("features", [])), "ok")
            except Exception as e:  # noqa: BLE001
                log_pull("odc_boundaries", url, None, "error", str(e))
    except Exception as e:  # noqa: BLE001
        log_pull("odc_boundaries", config.ODC_PACKAGES["boundaries"], None, "error", str(e))

    # fallback: geoBoundaries (CC BY 4.0)
    for level, path in (("ADM1", config.PROVINCE_GEOJSON), ("ADM3", config.COMMUNE_GEOJSON)):
        if path.exists():
            continue
        api = config.GEOBOUNDARIES_API.format(level=level)
        try:
            meta = http_get(api).json()
            url = meta.get("simplifiedGeometryGeoJSON") or meta["gjDownloadURL"]
            gj = http_get(url).json()
            path.write_text(json.dumps(gj), encoding="utf-8")
            saved.append(f"geoboundaries_{level}")
            log_pull(f"geoboundaries_{level}", url, len(gj.get("features", [])), "ok")
        except Exception as e:  # noqa: BLE001
            log_pull(f"geoboundaries_{level}", api, None, "error", str(e))
    return saved


# ---------------------------------------------------------------- S3 gazetteer, S5 commune database
def fetch_ckan_tables(package_key: str, dest_stem: Path,
                      formats=("xlsx", "xls", "csv")) -> list[Path]:
    """Download every spreadsheet/CSV resource of a CKAN package."""
    pkg_id = config.ODC_PACKAGES[package_key]
    saved = []
    try:
        resources = ckan_resources(pkg_id, formats)
    except Exception as e:  # noqa: BLE001
        log_pull(f"odc_{package_key}", pkg_id, None, "error", str(e))
        return saved
    for i, res in enumerate(resources):
        url = res["url"]
        ext = (res.get("format") or url.rsplit(".", 1)[-1]).lower()
        ext = ext if ext in ("xlsx", "xls", "csv") else "csv"
        dest = dest_stem.parent / f"{dest_stem.name}_{i}.{ext}"
        try:
            download_file(url, dest)
            saved.append(dest)
            log_pull(f"odc_{package_key}", url, None, "ok")
        except Exception as e:  # noqa: BLE001
            log_pull(f"odc_{package_key}", url, None, "error", str(e))
    return saved


def fetch_gazetteer() -> list[Path]:
    return fetch_ckan_tables("gazetteer", config.GAZETTEER_FILE)


def fetch_commune_db() -> list[Path]:
    return fetch_ckan_tables("commune_db", config.COMMUNE_DB_FILE.with_suffix(""), ("csv",))


# ---------------------------------------------------------------- scheduled entry point
def fetch_mef(names: tuple[str, ...] | None = None) -> dict[str, int]:
    """Province, district and commune lists 2025 from the MEF open-data API (no login).

    The API returns at most 200 rows per page, so this walks every page. Codes are
    kept as text so leading zeros survive (e.g. "01", "010201"). `names` limits which
    lists are pulled; the village list (14,576 rows) takes about 3 minutes.
    """
    out = {}
    for name, (dataset, dest) in config.MEF_DATASETS.items():
        if names is not None and name not in names:
            continue
        url = config.MEF_API.format(dataset=dataset)
        try:
            rows, page = [], 1
            while True:
                d = http_get(url, params={"page": page, "page_size": 200}).json()
                rows += d["items"]
                if page >= d["total_pages"]:
                    break
                page += 1
            if len(rows) != d["total_items"]:
                raise ValueError(f"expected {d['total_items']} rows, got {len(rows)}")
            pd.DataFrame(rows, dtype=str).to_csv(dest, index=False)
            log_pull(f"mef_{name}_2025", url, len(rows), "ok")
            out[name] = len(rows)
        except Exception as e:  # noqa: BLE001
            log_pull(f"mef_{name}_2025", url, None, "error", str(e))
            raise
    return out


def fetch_automatic() -> dict[str, str]:
    """The sources the portal refreshes by itself (GitHub Action + refresh button)."""
    status = {}
    try:
        fetch_census_odc()
        status["census"] = "ok"
    except Exception as e:  # noqa: BLE001
        status["census"] = f"error: {e}"
    for name, code in config.WB_INDICATORS.items():
        try:
            fetch_worldbank(code)
            status[name] = "ok"
        except Exception as e:  # noqa: BLE001
            status[name] = f"error: {e}"
    try:
        fetch_mef(("province", "district", "commune"))   # villages: download script only (slow)
        status["mef"] = "ok"
    except Exception as e:  # noqa: BLE001
        status["mef"] = f"error: {e}"
    return status


if __name__ == "__main__":
    for k, v in fetch_automatic().items():
        print(f"{k:15s} {v}")
