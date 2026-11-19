# Where do Cambodians live?
### Population density, urbanisation and projected growth across Cambodian provinces, 1950–2100

**Live portal:** https://cambodia-population.streamlit.app/
**Course:** Data Modeling final project, Topic 4

Research question: *How unevenly is Cambodia's population spread, how fast is the urban share growing, and what do UN projections imply for 2050?*

- **H1:** Population is concentrating in Phnom Penh and nearby provinces faster than elsewhere.
- **H2:** Households are smaller where density is higher.

---

## Run it (3 commands)

```bash
pip install -r requirements.txt          # the app only (Python 3.11+, 3.12 recommended)
pip install -r requirements-dev.txt      # app + pytest + notebooks
python scripts/download_data.py && python scripts/build_processed.py
streamlit run app.py
```

Recommended first: create a virtual environment.

```bash
python3.12 -m venv .venv && source .venv/bin/activate      # macOS / Linux
```

Run the tests with `python -m pytest -q`; they use small synthetic files and need no internet.

---

## Data sources and licences

| ID | Source | Licence | How it arrives |
|---|---|---|---|
| S1 | [Census 2019 final totals by province](https://data.opendevelopmentcambodia.net/en/dataset/population-census-2019-final-population-totals) (NIS via Open Development Cambodia) | CC BY-SA 4.0 | Automatic (API dump) |
| S2 | [Basic map of Cambodia 2014](https://data.opendevelopmentcambodia.net/dataset/administrative-boundaries-of-cambodia-2014) (OCHA/HDX via ODC) | CC BY 4.0 | Download script |
| S3 | [Cambodia Gazetteer](https://data.opendevelopmentmekong.net/dataset/cambodia-gazetteer) (NCDD via ODC) | **No licence given** | Download script |
| S4 | [Cambodia Commune List 2025 (MEF data portal)](https://data.mef.gov.kh/datasets/pd_66a8603900604c000123e146) | Check portal | Manual |
| S5 | [Commune database 2011](https://data.opendevelopmentcambodia.net/dataset/commune-database-of-cambodia-commune-level-2011) (NCDD via ODC) | CC BY 4.0 | Download script |
| S6 | [UN World Population Prospects 2024](https://population.un.org/wpp/downloads/) | CC BY 3.0 IGO | Download script |
| S7 | [World Bank WDI API](https://data.worldbank.org/indicator/SP.URB.TOTL.IN.ZS) | CC BY 4.0 | Automatic (API, weekly GitHub Action + refresh button) |

Full details, file names and manual fallbacks: [`docs/DATA_SOURCES.md`](docs/DATA_SOURCES.md).

---

## Repository layout

```
app.py                       overview page (map + time chart + linked province view)
pages/                       map explorer, time & forecast, urban commune model,
                             upload, data quality, findings
src/config.py                paths, URLs, indicator codes, seed
src/fetch.py                 one function per source, every pull logged
src/validate.py              upload checks: columns, types, units (Upload page switched off in app.py)
src/pipeline.py              cleaning, name matching, joins, features
src/forecast.py              time split, naive baseline, Holt
src/model.py                 sangkat classifier (one imblearn Pipeline)
src/charts.py                Plotly figures
src/appdata.py               cached loaders + sidebar for Streamlit
scripts/download_data.py     first-time download of every source
scripts/build_processed.py   raw -> processed tables
data/raw/                    files as retrieved, never edited by hand
data/processed/              tables the portal reads
data/boundaries/             province / commune GeoJSON
data/logs/                   fetch_log.csv, upload_log.csv
notebooks/analysis.ipynb     reproduces every number on the findings page
tests/                       pytest (synthetic data, no network)
docs/PROJECT_PLAN.md         plan, status and to-do list
.github/workflows/           weekly data pull + tests on every push
```

## Deploy to Streamlit Community Cloud

1. Push this repository to GitHub (public), **including `data/raw`, `data/processed` and `data/boundaries`**.
2. On [share.streamlit.io](https://share.streamlit.io) choose *New app* → your repo → `app.py`, Python 3.12.
3. The app link is at the top of this README. To change the address, open the app's *Settings* on share.streamlit.io and edit *Custom subdomain*.

No passwords or API keys are needed; none are stored in the code.

## Team

| Member | Role |
|---|---|
| … | Data lead |
| … | Pipeline lead |
| … | Model lead |
| … | App lead |
