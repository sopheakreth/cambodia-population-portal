# Data sources

Run `python scripts/download_data.py` from the repository root. It downloads every
source it can and prints a summary. If a step fails, use the manual fallback below
and save the file under the **exact name** shown.

Every automatic pull is logged in `data/logs/fetch_log.csv`.
Every downloaded file is listed in `data/raw/MANIFEST.csv` (file, URL, licence, date).

| ID | Dataset | Script step | Saved as | Manual fallback |
|---|---|---|---|---|
| S1 | Census 2019 final totals by province | `census` | `data/raw/census2019_province.csv` | Open the [dataset page](https://data.opendevelopmentcambodia.net/en/dataset/population-census-2019-final-population-totals) → CSV resource → Download. Or the [direct dump](https://data.opendevelopmentcambodia.net/datastore/dump/6095b312-5e7d-4723-8cab-9631a38a2f21) |
| S2 | Province + commune boundaries 2014 | `boundaries` | `data/boundaries/province.geojson`, `commune.geojson` | [Dataset page](https://data.opendevelopmentcambodia.net/dataset/administrative-boundaries-of-cambodia-2014) → GeoJSON resources. Script falls back to [geoBoundaries](https://www.geoboundaries.org) (CC BY 4.0) if ODC fails |
| S3 | Cambodia Gazetteer | `gazetteer` | `data/raw/gazetteer_0.xlsx` (or `.csv`) | [Dataset page](https://data.opendevelopmentmekong.net/dataset/cambodia-gazetteer) → newest XLSX |
| S4 | Cambodia Commune List 2025 (MEF data portal) | automatic (MEF open API) | `data/raw/mef_commune_2025.csv`, `mef_district_2025.csv`, `mef_province_2025.csv`, `mef_village_2025.csv` (villages: download script only, about 3 minutes) | [data.mef.gov.kh](https://data.mef.gov.kh/datasets/pd_66a8603900604c000123e146) |
| S5 | Commune database 2011 (optional) | `commune_db` | `data/raw/commune_db_2011_0.csv` | [Dataset page](https://data.opendevelopmentcambodia.net/dataset/commune-database-of-cambodia-commune-level-2011) → CSV |
| S6 | UN WPP 2024 demographic indicators | `wpp` | `data/raw/wpp2024_khm_medium.csv`, `wpp2024_khm_variants.csv` | [WPP downloads](https://population.un.org/wpp/downloads/) → CSV format → *Demographic Indicators* (Medium and Other variants). Filter to `ISO3_code == "KHM"` |
| S7 | World Bank: urban %, population, density, urban growth (10 ASEAN members) | `wb` | `data/raw/wb_<CODE>.csv` | [API](https://api.worldbank.org/v2/country/KHM/indicator/SP.URB.TOTL.IN.ZS?format=json&per_page=1000) |

## Grain and keys (Week 9)

| Table | Grain | Key | Joins to |
|---|---|---|---|
| census (S1) | province | `pro_code` (1–25) | boundaries, gazetteer |
| boundaries (S2) | province / commune polygon | name → `pro_code` via `PROVINCES` alias table | census |
| gazetteer (S3) | province / district / commune / village | 2/4/6/8-digit NCDD code | census (first 2 digits) |
| WPP (S6) | country-year | `year` | World Bank |
| World Bank (S7) | country-year | `iso3`, `year` | WPP |

## Things to check after downloading

1. `census2019_province.csv` has 25 rows and columns `pro_code, provinces, total, households, area_km2, pop_km2, house_size`.
2. Open the **Map explorer** page and check the *Boundary name matching* table: every row should have a `pro_code`. If not, add the spelling to `PROVINCES` in `src/pipeline.py`.
3. Gazetteer: `scripts/build_processed.py` prints the sangkat share and how many communes have an unknown type. If the type is unknown for most rows, open the file and adjust `parse_gazetteer()` in `src/pipeline.py`. The parser looks for the words Khum/Sangkat (and ឃុំ/សង្កាត់) in each row.
4. The Gazetteer has **no licence**: say so on the data-quality page, and publish only derived counts.
