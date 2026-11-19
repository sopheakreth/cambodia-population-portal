"""Cleaning, joining and feature engineering. Shared by the app and the notebook.

Every function documents which course week it serves. Raw files are never
modified; outputs go to data/processed/.
"""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd

from src import config

# =============================================================== Week 5 + 9: province codes and name matching
# Official NIS/NCDD province codes (1–25). Aliases cover spellings seen across
# the census, boundary files, World Bank and Gazetteer.
PROVINCES = pd.DataFrame([
    (1, "Banteay Meanchey", ["banteay mean chey", "banteay meanchey", "bntaey mean chey"]),
    (2, "Battambang", ["bat dambang", "batdambang", "battambang"]),
    (3, "Kampong Cham", ["kampong cham", "kompong cham"]),
    (4, "Kampong Chhnang", ["kampong chhnang", "kompong chhnang"]),
    (5, "Kampong Speu", ["kampong speu", "kampong spoe", "kompong speu"]),
    (6, "Kampong Thom", ["kampong thom", "kampong thum", "kompong thom"]),
    (7, "Kampot", ["kampot", "kampaot"]),
    (8, "Kandal", ["kandal", "kandaal"]),
    (9, "Koh Kong", ["koh kong", "kaoh kong"]),
    (10, "Kratie", ["kratie", "kracheh", "kratié"]),
    (11, "Mondul Kiri", ["mondul kiri", "mondulkiri", "mondol kiri", "mondolkiri"]),
    (12, "Phnom Penh", ["phnom penh", "phnum penh"]),
    (13, "Preah Vihear", ["preah vihear", "preah vihéar"]),
    (14, "Prey Veng", ["prey veng", "prey veaeng"]),
    (15, "Pursat", ["pursat", "pousat", "pouthisat"]),
    (16, "Ratanak Kiri", ["ratanak kiri", "ratanakiri", "rotanak kiri", "rotanakiri", "ratanakkiri"]),
    (17, "Siem Reap", ["siem reap", "siemreap", "siem reab"]),
    (18, "Preah Sihanouk", ["preah sihanouk", "sihanoukville", "preah seihanu", "kampong som"]),
    (19, "Stung Treng", ["stung treng", "stueng traeng", "steung treng", "stungtreng"]),
    (20, "Svay Rieng", ["svay rieng", "svay rieng"]),
    (21, "Takeo", ["takeo", "takev"]),
    (22, "Oddar Meanchey", ["oddar meanchey", "otdar mean chey", "oddor meanchey", "otdar meanchey"]),
    (23, "Kep", ["kep", "kaeb"]),
    (24, "Pailin", ["pailin", "pailin"]),
    (25, "Tbong Khmum", ["tbong khmum", "tboung khmum", "tbaung khmum"]),
], columns=["pro_code", "province", "aliases"])

_PREFIXES = r"^(krong|khaet|khett|province of|capital|municipality|province|city)\s+"
_SUFFIXES = r"\s+(province|municipality|capital|city)$"


def normalise_name(name: str) -> str:
    """Lower-case, strip accents, prefixes ('Krong', 'Province') and punctuation."""
    if not isinstance(name, str):
        return ""
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    s = s.lower().strip()
    s = re.sub(r"[-_/.,()]", " ", s)
    s = re.sub(r"\s+", " ", s)
    s = re.sub(_PREFIXES, "", s)
    s = re.sub(_SUFFIXES, "", s)
    return s.strip()


_ALIAS_TO_CODE = {}
for _code, _name, _aliases in PROVINCES.itertuples(index=False):
    for a in [_name, *_aliases]:
        _ALIAS_TO_CODE[normalise_name(a)] = _code
        _ALIAS_TO_CODE[normalise_name(a).replace(" ", "")] = _code


def match_province(name: str) -> int | None:
    """Return the official province code for any known spelling, else None."""
    n = normalise_name(name)
    return _ALIAS_TO_CODE.get(n) or _ALIAS_TO_CODE.get(n.replace(" ", ""))


def province_match_table(names: pd.Series) -> pd.DataFrame:
    """Week 9 deliverable: the name-matching table (input name -> code -> official name)."""
    t = pd.DataFrame({"input_name": names.dropna().unique()})
    t["pro_code"] = t["input_name"].map(match_province)
    t = t.merge(PROVINCES[["pro_code", "province"]], on="pro_code", how="left")
    t["matched"] = t["pro_code"].notna()
    return t


# =============================================================== Week 2: missing values
def missingness_report(df: pd.DataFrame, name: str = "") -> pd.DataFrame:
    """Share of missing values per column."""
    rep = pd.DataFrame({
        "source": name,
        "column": df.columns,
        "missing": df.isna().sum().values,
        "missing_pct": (df.isna().mean() * 100).round(2).values,
        "dtype": df.dtypes.astype(str).values,
    })
    return rep


# =============================================================== Week 3: outliers (flag, never delete)
def flag_outliers(df: pd.DataFrame, col: str, method: str = "iqr", k: float = 1.5,
                  z: float = 3.5, log: bool = False) -> pd.DataFrame:
    """Add `<col>_outlier` (bool) and `<col>_score`. Rows are never dropped.

    iqr      : outside [Q1 - k*IQR, Q3 + k*IQR]
    robust_z : |0.6745 * (x - median) / MAD| > z
    log=True : apply the test to log10(x) (useful for skewed density)
    """
    out = df.copy()
    x = out[col].astype(float)
    if log:
        x = np.log10(x.where(x > 0))
    if method == "iqr":
        q1, q3 = x.quantile([0.25, 0.75])
        iqr = q3 - q1
        lo, hi = q1 - k * iqr, q3 + k * iqr
        out[f"{col}_score"] = ((x - x.median()) / iqr).round(2) if iqr else 0.0
        out[f"{col}_outlier"] = (x < lo) | (x > hi)
    elif method == "robust_z":
        med = x.median()
        mad = (x - med).abs().median()
        score = 0.6745 * (x - med) / mad if mad else x * 0
        out[f"{col}_score"] = score.round(2)
        out[f"{col}_outlier"] = score.abs() > z
    else:
        raise ValueError("method must be 'iqr' or 'robust_z'")
    return out


# =============================================================== Week 1 + 4 + 6: census province table
CENSUS_RENAME = {
    "pro_code": "pro_code", "province_k": "province_kh", "provinces": "province_en",
    "province": "province_en", "households": "households", "males": "males",
    "females": "females", "total": "population", "house_size": "household_size",
    "area_km2": "area_km2", "pop_km2": "density",
}


def load_census(path: Path | None = None) -> pd.DataFrame:
    """Census 2019 by province, cleaned, with rates (Week 4) and features (Week 6)."""
    raw = pd.read_csv(path or config.CENSUS_FILE)
    df = raw.rename(columns={c: CENSUS_RENAME.get(c.strip().lower(), c.strip().lower())
                             for c in raw.columns})
    df = df.drop(columns=[c for c in ("_id", "reference") if c in df.columns])
    for c in ("population", "households", "males", "females", "area_km2",
              "density", "household_size"):
        if c in df.columns:
            df[c] = pd.to_numeric(df[c].astype(str).str.replace(",", ""), errors="coerce")

    # Week 9: always trust the name match over a possibly different code scheme
    if "province_en" in df.columns:
        matched = df["province_en"].map(match_province)
        df["pro_code"] = matched.fillna(pd.to_numeric(df.get("pro_code"), errors="coerce"))
    df["pro_code"] = df["pro_code"].astype("Int64")
    df = df.merge(PROVINCES[["pro_code", "province"]], on="pro_code", how="left")

    # Week 4: rates, never raw counts on the map
    df["density_calc"] = df["population"] / df["area_km2"]
    df["pop_share_pct"] = 100 * df["population"] / df["population"].sum()
    df["area_share_pct"] = 100 * df["area_km2"] / df["area_km2"].sum()
    df["households_per_km2"] = df["households"] / df["area_km2"]
    df["sex_ratio"] = 100 * df["males"] / df["females"]
    if "household_size" not in df.columns or df["household_size"].isna().all():
        df["household_size"] = df["population"] / df["households"]
    # Week 6: log density (claim: density is multiplicative, so compare on log scale)
    df["log10_density"] = np.log10(df["density_calc"])
    # Week 3
    df = flag_outliers(df, "density_calc", method="iqr", log=False)
    df = flag_outliers(df, "household_size", method="robust_z")
    return df.sort_values("pro_code").reset_index(drop=True)


def load_census_history(prov2019: pd.DataFrame) -> pd.DataFrame:
    """Province population for 1998, 2008 and 2019 on one frame (long table).

    1998 and 2008 predate Tbong Khmum (code 25), which was part of Kampong Cham
    (code 3). For those years both polygons receive the Kampong Cham value and
    `merged` is True, so the page can say so. Areas are the 2008 report's (new
    frame) for both older years; 1998 uses the 2008-frame totals for Koh Kong
    and Preah Sihanouk so the two years are comparable.
    """
    out = []
    f08 = pd.read_csv(config.CENSUS_2008_FILE) if config.CENSUS_2008_FILE.exists() else pd.DataFrame()
    f98 = pd.read_csv(config.CENSUS_1998_FILE) if config.CENSUS_1998_FILE.exists() else pd.DataFrame()
    if not f08.empty:
        area = f08.set_index("pro_code")["area_km2"]
        for year, df, col in ((1998, f98, "total_2008_frame"), (2008, f08, "total")):
            if df.empty:
                continue
            d = df[["pro_code", col]].rename(columns={col: "population"})
            hh = df.set_index("pro_code")["households"] if "households" in df else None
            d["households"] = d["pro_code"].map(hh) if hh is not None else np.nan
            if year == 1998:  # households are old-frame for the two moved provinces
                d.loc[d["pro_code"].isin([9, 18]), "households"] = np.nan
            d["area_km2"] = d["pro_code"].map(area)
            kc = d[d["pro_code"] == 3].assign(pro_code=25)       # Tbong Khmum is inside Kampong Cham
            d = pd.concat([d.assign(merged=d["pro_code"] == 3), kc.assign(merged=True)], ignore_index=True)
            d["year"] = year
            out.append(d)
    cur = prov2019[["pro_code", "population", "households", "area_km2"]].assign(year=2019, merged=False)
    out.append(cur)
    h = pd.concat(out, ignore_index=True)
    h = h.merge(PROVINCES[["pro_code", "province"]], on="pro_code", how="left")
    h["density_calc"] = h["population"] / h["area_km2"]
    h["household_size"] = h["population"] / h["households"]
    total = h[~h["pro_code"].eq(25) | ~h["merged"]].groupby("year")["population"].sum()
    h["pop_share_pct"] = 100 * h["population"] / h["year"].map(total)
    return h.sort_values(["year", "pro_code"]).reset_index(drop=True)


# =============================================================== boundaries
NAME_KEYS = ["HRName", "HRNAME", "NAME_1", "ADM1_EN", "shapeName", "name", "Name",
             "province", "Province", "PROVINCE", "pro_name_e", "NAME_ENG", "Prov_EN", "Pro_EN"]


def _utm_to_lonlat(x: float, y: float, zone: int = 48, north: bool = True) -> tuple[float, float]:
    """Inverse UTM (WGS84) -> (lon, lat) in degrees. Pure Python, no pyproj needed."""
    a, f = 6378137.0, 1 / 298.257223563
    k0, e2 = 0.9996, f * (2 - f)
    ep2 = e2 / (1 - e2)
    m = (y if north else y - 10_000_000.0) / k0
    mu = m / (a * (1 - e2 / 4 - 3 * e2**2 / 64 - 5 * e2**3 / 256))
    e1 = (1 - np.sqrt(1 - e2)) / (1 + np.sqrt(1 - e2))
    phi1 = (mu + (3 * e1 / 2 - 27 * e1**3 / 32) * np.sin(2 * mu)
            + (21 * e1**2 / 16 - 55 * e1**4 / 32) * np.sin(4 * mu)
            + (151 * e1**3 / 96) * np.sin(6 * mu) + (1097 * e1**4 / 512) * np.sin(8 * mu))
    s1, c1, t1 = np.sin(phi1), np.cos(phi1), np.tan(phi1)
    n1 = a / np.sqrt(1 - e2 * s1**2)
    r1 = a * (1 - e2) / (1 - e2 * s1**2) ** 1.5
    c = ep2 * c1**2
    t = t1**2
    d = (x - 500_000.0) / (n1 * k0)
    lat = phi1 - (n1 * t1 / r1) * (d**2 / 2 - (5 + 3 * t + 10 * c - 4 * c**2 - 9 * ep2) * d**4 / 24
                                   + (61 + 90 * t + 298 * c + 45 * t**2 - 252 * ep2 - 3 * c**2) * d**6 / 720)
    lon = (d - (1 + 2 * t + c) * d**3 / 6
           + (5 - 2 * c + 28 * t - 3 * c**2 + 8 * ep2 + 24 * t**2) * d**5 / 120) / c1
    return float(np.degrees(lon) + (zone - 1) * 6 - 180 + 3), float(np.degrees(lat))


def _walk(coords, fn):
    if coords and isinstance(coords[0], (int, float)):
        return list(fn(coords[0], coords[1]))
    return [_walk(c, fn) for c in coords]


def ensure_lonlat(gj: dict) -> dict:
    """Plotly needs lon/lat. If the file is projected (UTM metres), convert it in place."""
    crs = str(gj.get("crs", {}).get("properties", {}).get("name", ""))
    m = re.search(r"EPSG::?(32[67])(\d\d)", crs)
    zone, north = (int(m.group(2)), m.group(1) == "326") if m else (48, True)

    def first_xy(c):
        while c and not isinstance(c[0], (int, float)):
            c = c[0]
        return c
    feats = gj.get("features", [])
    if not feats or max(abs(v) for v in first_xy(feats[0]["geometry"]["coordinates"])[:2]) <= 360:
        return gj  # already degrees
    for f in feats:
        f["geometry"]["coordinates"] = _walk(f["geometry"]["coordinates"],
                                             lambda x, y: _utm_to_lonlat(x, y, zone, north))
    gj.pop("crs", None)
    return gj


def load_province_geojson(path: Path | None = None) -> tuple[dict, pd.DataFrame]:
    """Read province GeoJSON and write `pro_code` into each feature's properties.

    Returns the GeoJSON and a matching table (for the Week 9 report).
    """
    gj = ensure_lonlat(json.loads(Path(path or config.PROVINCE_GEOJSON).read_text(encoding="utf-8")))
    rows = []
    for feat in gj["features"]:
        props = feat.setdefault("properties", {})
        code, used = None, None
        for k in NAME_KEYS + list(props):
            v = props.get(k)
            if isinstance(v, str) and (c := match_province(v)):
                code, used = c, v
                break
        props["pro_code"] = code
        rows.append({"geo_name": used, "pro_code": code})
    return gj, pd.DataFrame(rows)


# =============================================================== World Bank + WPP (national series)
def load_worldbank(code: str, iso3: str | None = "KHM") -> pd.DataFrame:
    f = config.RAW_DIR / f"wb_{code}.csv"
    if not f.exists():
        return pd.DataFrame(columns=["iso3", "country", "indicator", "year", "value"])
    df = pd.read_csv(f)
    return df[df["iso3"] == iso3] if iso3 else df


def load_wpp() -> pd.DataFrame:
    """National population 1950–2100 (thousands -> people) with Low/High variants."""
    if not config.WPP_MEDIUM_FILE.exists():
        return pd.DataFrame()
    med = pd.read_csv(config.WPP_MEDIUM_FILE)
    keep = {"Time": "year", "TPopulation1July": "population_k", "PopDensity": "density",
            "PopGrowthRate": "growth_rate_pct", "TFR": "fertility", "LEx": "life_expectancy",
            "Variant": "variant"}
    med = med[[c for c in keep if c in med.columns]].rename(columns=keep)
    med["population"] = med["population_k"] * 1000
    med["kind"] = np.where(med["year"] <= 2023, "estimate", "projection")
    if config.WPP_VARIANTS_FILE.exists():
        var = pd.read_csv(config.WPP_VARIANTS_FILE)
        if {"Variant", "Time", "TPopulation1July"} <= set(var.columns):
            piv = (var[var["Variant"].isin(["Low", "High"])]
                   .pivot_table(index="Time", columns="Variant", values="TPopulation1July"))
            piv = (piv * 1000).rename(columns={"Low": "pop_low", "High": "pop_high"})
            med = med.merge(piv, left_on="year", right_index=True, how="left")
    return med.sort_values("year").reset_index(drop=True)


def national_series() -> pd.DataFrame:
    """One row per year: population (WPP, else World Bank), urban %, features (Week 6)."""
    wpp = load_wpp()
    if not wpp.empty:
        nat = wpp.copy()
    else:
        wb = load_worldbank(config.WB_INDICATORS["population"])
        nat = wb.rename(columns={"value": "population"})[["year", "population"]]
        nat["kind"] = "estimate"
    urb = load_worldbank(config.WB_INDICATORS["urban_pct"])[["year", "value"]]
    nat = nat.merge(urb.rename(columns={"value": "urban_pct"}), on="year", how="left")
    nat = nat.sort_values("year").reset_index(drop=True)
    # Week 6 features
    nat["pop_change_yoy"] = nat["population"].diff()
    nat["pop_growth_pct"] = nat["population"].pct_change() * 100
    nat["pop_growth_roll5"] = nat["pop_growth_pct"].rolling(5).mean()
    nat["urban_pct_change"] = nat["urban_pct"].diff()
    nat["urban_pct_lag1"] = nat["urban_pct"].shift(1)
    return nat


# =============================================================== Gazetteer -> commune table (Week 10 target)
def _read_any_table(path: Path) -> pd.DataFrame:
    if path.suffix.lower() in (".xlsx", ".xls"):
        sheets = pd.read_excel(path, sheet_name=None, dtype=str)
        return pd.concat(sheets.values(), ignore_index=True)
    return pd.read_csv(path, dtype=str)


def _admin_level(code: str) -> str | None:
    digits = re.sub(r"\D", "", str(code))
    if not digits:
        return None
    digits = digits.zfill(len(digits) + len(digits) % 2)
    return {2: "province", 4: "district", 6: "commune", 8: "village"}.get(len(digits))


def parse_gazetteer(df: pd.DataFrame) -> pd.DataFrame:
    """Turn a raw NCDD gazetteer sheet into one row per commune.

    Heuristics (check them on your file!):
      * the code column is the column whose values look like 2/4/6/8-digit codes
      * a commune is a sangkat if its row mentions 'Sangkat' / 'សង្កាត់', a khum if 'Khum' / 'ឃុំ'
      * district type (Krong / Khan / Srok) is read the same way from the district row
    """
    df = df.dropna(how="all").copy()
    best, best_share = None, 0.0
    for c in df.columns:
        s = df[c].dropna().astype(str).str.replace(r"\.0$", "", regex=True)
        share = s.str.fullmatch(r"\d{1,8}").mean() if len(s) else 0
        if share > best_share:
            best, best_share = c, share
    if best is None or best_share < 0.5:
        raise ValueError("Could not find a numeric code column in the gazetteer.")
    df["code"] = df[best].astype(str).str.replace(r"\.0$", "", regex=True).str.strip()
    df["level"] = df["code"].map(_admin_level)
    text = df.drop(columns=["code", "level"]).fillna("").astype(str).agg(" ".join, axis=1).str.lower()
    df["text"] = text

    def kind(t: str) -> str | None:
        for key, words in {"sangkat": ["sangkat", "សង្កាត់"], "khum": ["khum", "ឃុំ"],
                           "krong": ["krong", "ក្រុង"], "khan": ["khan", "ខណ្ឌ"],
                           "srok": ["srok", "ស្រុក"]}.items():
            if any(w in t for w in words):
                return key
        return None

    df["kind"] = df["text"].map(kind)

    com = df[df["level"] == "commune"].copy()
    com["commune_code"] = com["code"].str.zfill(6)
    com["district_code"] = com["commune_code"].str[:4]
    com["pro_code"] = com["commune_code"].str[:2].astype(int)
    com["is_sangkat"] = com["kind"].map({"sangkat": 1, "khum": 0})
    name_col = next((c for c in df.columns if "latin" in str(c).lower() or "english" in str(c).lower()), None)
    com["name"] = com[name_col] if name_col else com["text"].str[:40]

    vil = df[df["level"] == "village"]
    vcount = vil["code"].str.zfill(8).str[:6].value_counts()
    com["villages"] = com["commune_code"].map(vcount).fillna(0).astype(int)

    dist = df[df["level"] == "district"].copy()
    dist["district_code"] = dist["code"].str.zfill(4)
    dtype = dist.set_index("district_code")["kind"]
    com["district_type"] = com["district_code"].map(dtype).fillna("unknown")
    com["communes_in_district"] = com.groupby("district_code")["commune_code"].transform("count")

    cols = ["commune_code", "district_code", "pro_code", "name", "is_sangkat",
            "villages", "district_type", "communes_in_district"]
    return com[cols].drop_duplicates("commune_code").reset_index(drop=True)


def load_communes() -> pd.DataFrame:
    """Parse the first gazetteer file found in data/raw."""
    files = sorted(config.RAW_DIR.glob("gazetteer*.*"))
    files = [f for f in files if f.suffix.lower() in (".xlsx", ".xls", ".csv")]
    if not files:
        return pd.DataFrame()
    return parse_gazetteer(_read_any_table(files[0]))


def census_total_check(hist: pd.DataFrame) -> pd.DataFrame:
    """Do the province rows of each census add up to the official national total?"""
    if hist.empty:
        return pd.DataFrame()
    base = hist[~((hist["pro_code"] == 25) & hist["merged"])] if "merged" in hist else hist
    tot = base.groupby("year")["population"].sum()
    rows = []
    for year, official in config.CENSUS_NATIONAL_TOTALS.items():
        if year in tot.index:
            rows.append({"year": year, "provinces_sum": int(tot[year]), "official_total": official,
                         "difference": int(tot[year]) - official, "ok": int(tot[year]) == official})
    return pd.DataFrame(rows)


def commune_code_check(com: pd.DataFrame, mef_path: Path | None = None):
    """Compare the commune codes of the app's Gazetteer table with the MEF Commune List 2025.

    Match on the 6-digit code (names repeat: e.g. several "Kokir"). Returns
    (summary, only_in_mef, only_in_app); `only_in_mef` carries a suggested old code
    when the same romanised name sits in the same province among the app-only codes.
    """
    path = mef_path or config.MEF_COMMUNE_FILE
    if not path.exists() or com.empty:
        return {}, pd.DataFrame(), pd.DataFrame()
    mef = pd.read_csv(path, dtype=str)
    mef["pro_code"] = mef["province_code"].astype(int)
    app = com.assign(commune_code=com["commune_code"].astype(str))
    both = set(mef["commune_code"]) & set(app["commune_code"])
    only_mef = mef[~mef["commune_code"].isin(both)].copy()
    only_app = app[~app["commune_code"].isin(both)].copy()
    only_app["name_short"] = only_app["name"].astype(str).str.slice(0, 45)

    def suggest(r):
        cand = only_app[(only_app["pro_code"] == r["pro_code"])
                        & only_app["name"].astype(str).str.lower().str.contains(str(r["commune_en"]).lower(), regex=False)]
        return cand["commune_code"].iloc[0] if len(cand) == 1 else ""
    only_mef["maybe_old_code"] = only_mef.apply(suggest, axis=1)
    only_mef["repeated_name"] = only_mef["commune_en"].duplicated(keep=False) & only_mef["maybe_old_code"].eq("")
    md = pd.read_csv(config.MEF_DISTRICT_FILE, dtype=str)["district_code"] if config.MEF_DISTRICT_FILE.exists() else pd.Series(dtype=str)
    ad = app["district_code"].astype(str)
    vfile = config.MEF_VILLAGE_FILE
    if vfile.exists() and "villages" in app:
        vc = pd.read_csv(vfile, dtype=str)["commune_code"].value_counts()
        mv = app[app["commune_code"].isin(both)]
        villages_differ = int((mv["villages"] != mv["commune_code"].map(vc)).sum())
    else:
        villages_differ = None
    summary = {"villages_differ": villages_differ, "mef_districts": int(md.nunique()), "app_districts": int(ad.nunique()),
               "districts_only_mef": len(set(md) - set(ad)), "districts_only_app": len(set(ad) - set(md)),
               "mef_rows": len(mef), "app_rows": len(app), "matched": len(both),
               "only_mef": len(only_mef), "only_app": len(only_app),
               "repeated_names": int(mef["commune_en"].duplicated(keep=False).sum())}
    return (summary,
            only_mef[["commune_code", "province_code", "commune_en", "commune_kh", "maybe_old_code"]],
            only_app[["commune_code", "pro_code", "name_short"]])


def load_communes_mef(com: pd.DataFrame) -> pd.DataFrame:
    """Commune table built on the MEF 2025 structure (same columns as the Gazetteer table).

    * rows, names, villages per commune and communes per district come from MEF 2025;
    * the khum/sangkat label has to come from the Gazetteer: by code where it matches,
      by the suggested old code where a commune was recoded, otherwise it stays empty
      (and such rows are left out of training);
    * `label_source` says which of the three applied.
    """
    if com.empty or not config.MEF_COMMUNE_FILE.exists():
        return pd.DataFrame()
    mef = pd.read_csv(config.MEF_COMMUNE_FILE, dtype=str)
    gaz = com.assign(commune_code=com["commune_code"].astype(str)).set_index("commune_code")
    out = pd.DataFrame({"commune_code": mef["commune_code"], "district_code": mef["district_code"],
                        "pro_code": mef["province_code"].astype(int), "name": mef["commune_en"]})
    out["is_sangkat"] = out["commune_code"].map(gaz["is_sangkat"])
    out["label_source"] = np.where(out["is_sangkat"].notna(), "gazetteer", "missing")
    _, only_mef, _ = commune_code_check(com)
    if len(only_mef):
        old = only_mef.set_index("commune_code")["maybe_old_code"].replace("", np.nan).dropna()
        fill = out["commune_code"].map(old).map(gaz["is_sangkat"])
        use = out["is_sangkat"].isna() & fill.notna()
        out.loc[use, "is_sangkat"] = fill[use]
        out.loc[use, "label_source"] = "recoded"
    if config.MEF_VILLAGE_FILE.exists():
        vc = pd.read_csv(config.MEF_VILLAGE_FILE, dtype=str)["commune_code"].value_counts()
        out["villages"] = out["commune_code"].map(vc).fillna(0).astype(int)
    else:
        out["villages"] = out["commune_code"].map(gaz["villages"])
    dtype = com.drop_duplicates("district_code").set_index("district_code")["district_type"]
    out["district_type"] = out["district_code"].map(dtype)
    out["communes_in_district"] = out.groupby("district_code")["commune_code"].transform("size")
    return out


COMMUNE_DB_FEATURES = ["log_households_2011", "log_land_ha", "log_rice_ha", "electricity_pct"]


def load_commune_db() -> pd.DataFrame:
    """Rebuild the 2011 commune database into one clean row per commune.

    The file ODC serves is five tables stacked on top of each other (8,105 rows =
    5 x 1,621 communes): every block lists the same communes in the same order but fills a
    different set of columns, the rest are zeros. We line the blocks up by position
    and add them (each column is non-zero in one block only). The join key is
    `NCDD_CodeC`, the 6-digit commune code; `Com_Code` is all zeros and useless.
    """
    files = sorted(config.RAW_DIR.glob("commune_db_2011*.csv"))
    if not files:
        return pd.DataFrame()
    d = pd.read_csv(files[0], dtype=str)
    blocks = 5                                   # five stacked tables
    if len(d) % blocks:
        raise ValueError(f"commune database has {len(d)} rows, expected a multiple of {blocks}")
    n = len(d) // blocks
    names = d["Commune"].iloc[:n].reset_index(drop=True)
    for b in range(1, blocks):   # the blocks must really list the same communes in the same order
        if not (d["Commune"].iloc[b * n:(b + 1) * n].reset_index(drop=True) == names).all():
            raise ValueError("commune database blocks are not in the same order")
    num = d.drop(columns=["Commune", "Acronym_C", "Acronym_D", "Com_Code"]).apply(pd.to_numeric, errors="coerce").fillna(0)
    agg = num.groupby(np.arange(len(d)) % n).sum()
    out = pd.DataFrame({"commune_code": agg["NCDD_CodeC"].round().astype("int64").astype(str).str.zfill(6).values,
                        "name_2011": names.values})
    out["households_2011"] = agg["HH"].values
    out["land_ha"] = agg["LSize_Ha"].values
    out["rice_ha"] = agg["RiField_Ha"].values
    out["electricity_pct"] = agg["Per_HH_El"].values          # % of households with electricity, 2011
    out["log_households_2011"] = np.log1p(out["households_2011"])
    out["log_land_ha"] = np.log1p(out["land_ha"])
    out["log_rice_ha"] = np.log1p(out["rice_ha"])
    return out.drop_duplicates("commune_code")


def attach_commune_db(com: pd.DataFrame) -> pd.DataFrame:
    """Add the 2011 commune-database features to a commune table (matched on commune_code).

    Communes created after 2011 have no row there; they keep empty values and the model
    fills them with the median inside each CV fold.
    """
    db = load_commune_db()
    if db.empty or com.empty:
        return com
    return com.merge(db[["commune_code"] + COMMUNE_DB_FEATURES + ["households_2011", "land_ha", "rice_ha"]],
                     on="commune_code", how="left")


# =============================================================== build everything
def build_processed() -> dict[str, int]:
    """Week 1 + 9: raw -> processed, printing row counts before/after each join."""
    report = {}
    if config.CENSUS_FILE.exists():
        raw_n = len(pd.read_csv(config.CENSUS_FILE))
        prov = load_census()
        print(f"census: raw {raw_n} rows -> processed {len(prov)} rows; "
              f"unmatched names: {prov['province'].isna().sum()}")
        prov.to_csv(config.PROCESSED_DIR / "province.csv", index=False)
        report["province"] = len(prov)
    nat = national_series()
    if not nat.empty:
        nat.to_csv(config.PROCESSED_DIR / "national.csv", index=False)
        report["national"] = len(nat)
        print(f"national series: {len(nat)} years ({nat['year'].min()}–{nat['year'].max()})")
    com = load_communes()
    if not com.empty:
        com.to_csv(config.PROCESSED_DIR / "commune.csv", index=False)
        report["commune"] = len(com)
        print(f"communes: {len(com)} rows; sangkat share "
              f"{com['is_sangkat'].mean():.1%}; type unknown: {com['is_sangkat'].isna().sum()}")
    asean = pd.concat([load_worldbank(c, None) for c in config.WB_INDICATORS.values()],
                      ignore_index=True)
    if not asean.empty:
        asean.to_csv(config.PROCESSED_DIR / "asean_wb.csv", index=False)
        report["asean_wb"] = len(asean)
    return report
