"""Project-wide settings: paths, source URLs, indicator codes and the random seed.

Everything that might change (a URL, a folder) lives here so the rest of the
code never hard-codes it.
"""
from pathlib import Path

# ---------------------------------------------------------------- paths
ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
BOUNDARY_DIR = DATA_DIR / "boundaries"
UPLOAD_DIR = DATA_DIR / "uploads"
LOG_DIR = DATA_DIR / "logs"
FETCH_LOG = LOG_DIR / "fetch_log.csv"
UPLOAD_LOG = LOG_DIR / "upload_log.csv"
MANIFEST = RAW_DIR / "MANIFEST.csv"

for _d in (RAW_DIR, PROCESSED_DIR, BOUNDARY_DIR, UPLOAD_DIR, LOG_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------- raw file names
CENSUS_FILE = RAW_DIR / "census2019_province.csv"
GAZETTEER_FILE = RAW_DIR / "gazetteer"            # extension added on download
COMMUNE_DB_FILE = RAW_DIR / "commune_db_2011.csv"
WPP_MEDIUM_FILE = RAW_DIR / "wpp2024_khm_medium.csv"
WPP_VARIANTS_FILE = RAW_DIR / "wpp2024_khm_variants.csv"
MEF_COMMUNE_FILE = RAW_DIR / "mef_commune_2025.csv"
MEF_DISTRICT_FILE = RAW_DIR / "mef_district_2025.csv"
MEF_PROVINCE_FILE = RAW_DIR / "mef_province_2025.csv"
MEF_VILLAGE_FILE = RAW_DIR / "mef_village_2025.csv"
CENSUS_1998_FILE = RAW_DIR / "census1998_province.csv"
CENSUS_2008_FILE = RAW_DIR / "census2008_province.csv"
PROVINCE_GEOJSON = BOUNDARY_DIR / "province.geojson"
COMMUNE_GEOJSON = BOUNDARY_DIR / "commune.geojson"

# ---------------------------------------------------------------- reproducibility
SEED = 42

# ---------------------------------------------------------------- Open Development Cambodia (CKAN)
ODC_BASE = "https://data.opendevelopmentcambodia.net"
ODC_CKAN_APIS = [
    f"{ODC_BASE}/api/3/action",
    f"{ODC_BASE}/en/api/3/action",
    "https://data.opendevelopmentmekong.net/api/3/action",
]
ODC_CENSUS_DUMP = (
    f"{ODC_BASE}/datastore/dump/6095b312-5e7d-4723-8cab-9631a38a2f21"
)
ODC_PACKAGES = {
    "census": "population-census-2019-final-population-totals",
    "boundaries": "administrative-boundaries-of-cambodia-2014",
    "gazetteer": "cambodia-gazetteer",
    "commune_db": "commune-database-of-cambodia-commune-level-2011",
}

# Fallback boundaries (CC BY 4.0) if the ODC GeoJSON cannot be found
GEOBOUNDARIES_API = "https://www.geoboundaries.org/api/current/gbOpen/KHM/{level}/"

# Official national totals printed in the NIS reports, used to check that the province rows add up
CENSUS_NATIONAL_TOTALS = {1998: 11_437_656, 2008: 13_395_682, 2019: 15_552_211}

# ---------------------------------------------------------------- MEF open data portal (administrative lists 2025)
MEF_API = "https://data.mef.gov.kh/api/v1/public-datasets/{dataset}/json"
MEF_DATASETS = {   # name -> (dataset id, file)
    "province": ("pd_66a8603700604c000123e144", MEF_PROVINCE_FILE),
    "district": ("pd_66a8603800604c000123e145", MEF_DISTRICT_FILE),
    "commune": ("pd_66a8603900604c000123e146", MEF_COMMUNE_FILE),
    "village": ("pd_66a8603a00604c000123e147", MEF_VILLAGE_FILE),
}

# ---------------------------------------------------------------- UN World Population Prospects 2024
WPP_BASE = (
    "https://population.un.org/wpp/assets/Excel%20Files/"
    "1_Indicator%20(Standard)/CSV_FILES/"
)
WPP_FILES = {
    "medium": WPP_BASE + "WPP2024_Demographic_Indicators_Medium.csv.gz",
    "variants": WPP_BASE + "WPP2024_Demographic_Indicators_OtherVariants.csv.gz",
}

# ---------------------------------------------------------------- World Bank API
WB_BASE = "https://api.worldbank.org/v2"
WB_INDICATORS = {
    "urban_pct": "SP.URB.TOTL.IN.ZS",   # urban population, % of total
    "population": "SP.POP.TOTL",        # total population
    "density": "EN.POP.DNST",           # people per km² of land
    "urban_growth": "SP.URB.GROW",      # urban population growth, annual %
}
ASEAN = ["KHM", "THA", "VNM", "LAO", "MMR", "MYS", "IDN", "PHL", "SGP", "BRN"]

# ---------------------------------------------------------------- sources shown on the data-quality page
SOURCES = [
    {"id": "S1", "name": "Census 2019 final totals by province (NIS via ODC)",
     "licence": "CC BY-SA 4.0", "url": f"{ODC_BASE}/en/dataset/{ODC_PACKAGES['census']}",
     "file": "census2019_province.csv", "fetch": "automatic"},
    {"id": "S2", "name": "Basic map of Cambodia 2014 (OCHA/HDX via ODC)",
     "licence": "CC BY 4.0", "url": f"{ODC_BASE}/dataset/{ODC_PACKAGES['boundaries']}",
     "file": "boundaries/province.geojson", "fetch": "download script"},
    {"id": "S3", "name": "Cambodia Gazetteer (NCDD via ODC)",
     "licence": "No licence given", "url": "https://data.opendevelopmentmekong.net/dataset/cambodia-gazetteer",
     "file": "gazetteer.*", "fetch": "download script"},
    {"id": "S4", "name": "Cambodia Commune List 2025 (MEF data portal)",
     "licence": "Check portal", "url": "https://data.mef.gov.kh/datasets/pd_66a8603900604c000123e146",
     "file": "mef_commune_2025.csv", "fetch": "automatic"},
    {"id": "S5", "name": "Commune database 2011 (NCDD via ODC)",
     "licence": "CC BY 4.0", "url": f"{ODC_BASE}/dataset/{ODC_PACKAGES['commune_db']}",
     "file": "commune_db_2011.csv", "fetch": "download script"},
    {"id": "S6", "name": "UN World Population Prospects 2024",
     "licence": "CC BY 3.0 IGO", "url": "https://population.un.org/wpp/downloads/",
     "file": "wpp2024_khm_*.csv", "fetch": "download script"},
    {"id": "S8", "name": "Census 1998 final results by province (NIS report, PDF)",
     "licence": "Check NIS terms", "url": "https://nis.gov.kh/wp-content/uploads/2025/09/General-Population-Census1998.pdf",
     "file": "census1998_province.csv", "fetch": "manual (extracted from PDF)"},
    {"id": "S9", "name": "Census 2008 final results by province (NIS report, PDF, scanned)",
     "licence": "Check NIS terms", "url": "https://nis.gov.kh/wp-content/uploads/2025/09/GPC2008_Report_ENG.pdf",
     "file": "census2008_province.csv", "fetch": "manual (read from scanned PDF)"},
    {"id": "S7", "name": "World Bank World Development Indicators (API)",
     "licence": "CC BY 4.0", "url": "https://data.worldbank.org/indicator/SP.URB.TOTL.IN.ZS",
     "file": "wb_*.csv", "fetch": "automatic"},
]
