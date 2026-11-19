# Project Plan: Topic 4
## Mapping Population Density, Urbanisation and Projected Growth across Cambodian Provinces, 1950 to 2050

This file is the team's working plan. Tick the boxes as you go and commit the changes,
so the commit history shows progress.

Legend: ✅ done in the starter code · 🟡 started, needs your work · ⬜ to do

---

## 1. Objectives

| ID | Hypothesis | Test | Where |
|---|---|---|---|
| H1 | Population is concentrating in Phnom Penh and surrounding provinces faster than elsewhere | Share of population and density for Phnom Penh, Kandal and Takeo vs. the rest; urban share trend 1960–2024 | Findings 1 + 4, Time page |
| H2 | Households are smaller where density is higher | Spearman r of household size vs. log density, 25 provinces | Overview tab 1, Findings 2 |

**Rare event (Week 10):** predict urban communes (*sangkat*) from Gazetteer attributes.
**Deliverables:** live Streamlit portal, public GitHub repo, notebook reproducing every number, tests, 10-minute defence.

---

## 2. Step-by-step: from zero to a running portal on your Mac

```bash
cd ~/Projects/cambodia-population-portal
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m pytest -q                      # 37 tests should pass (synthetic data, no internet)
python scripts/download_data.py          # downloads real data (needs internet)
python scripts/build_processed.py        # raw -> processed, prints row counts
streamlit run app.py                     # opens http://localhost:8501
```

If a download fails, follow the manual fallback in `docs/DATA_SOURCES.md`, then run
`build_processed.py` again.

---

## 3. Data download plan

| ID | Source | Licence | Method | File | Status |
|---|---|---|---|---|---|
| S1 | Census 2019 by province (ODC) | CC BY-SA | Automatic | `data/raw/census2019_province.csv` | ⬜ run script |
| S2 | Boundaries 2014 (ODC / geoBoundaries) | CC BY | Script | `data/boundaries/province.geojson` | ⬜ run script |
| S3 | Gazetteer (NCDD via ODC) | none given | Script | `data/raw/gazetteer_0.xlsx` | ⬜ run script, check parser |
| S4 | Cambodia Commune List 2025 (MEF portal) | check | Manual | `data/raw/mef_commune_2025.csv` | ⬜ optional |
| S5 | Commune database 2011 | CC BY 4.0 | Script | `data/raw/commune_db_2011_0.csv` | ⬜ optional |
| S6 | UN WPP 2024 | CC BY 3.0 IGO | Script (large) | `data/raw/wpp2024_khm_*.csv` | ⬜ run script |
| S7 | World Bank API, 10 ASEAN members | CC BY 4.0 | Automatic | `data/raw/wb_*.csv` | ⬜ run script |

Checklist after downloading:
- [ ] Census has 25 rows; all provinces matched (build script prints `unmatched names: 0`)
- [ ] Map explorer → boundary matching table has no empty `pro_code`
- [ ] Build script prints a sangkat share between 5% and 30% and few "type unknown"
- [ ] WPP covers 1950–2100; Low/High variants loaded (band visible on the time chart)
- [ ] World Bank files exist for all 4 indicators
- [ ] `data/raw/MANIFEST.csv` lists every file with its licence and date

---

## 4. What the starter code already does

| Part | File | Status | Notes |
|---|---|---|---|
| Paths, URLs, seed | `src/config.py` | ✅ | |
| Fetch + log every pull | `src/fetch.py` | ✅ | Census dump, World Bank (paged), CKAN resources, WPP filtered in chunks, boundaries with fallback |
| Download all sources | `scripts/download_data.py` | ✅ | Updates MANIFEST |
| Upload checks | `src/validate.py` | ✅ | 2 schemas; rejected rows get a reason; accepted rows stored with date |
| Province name matching | `src/pipeline.py` `PROVINCES`, `match_province` | ✅ | Add spellings if a source uses a new one |
| Census cleaning + rates | `load_census` | ✅ | density, shares, households/km², sex ratio, log density |
| Outlier flags | `flag_outliers` | ✅ | IQR and robust z; flags only |
| Missingness report | `missingness_report` | ✅ | Shown on data-quality page |
| National series 1950–2100 | `national_series` | ✅ | WPP + WB urban %, growth, lags, rolling mean |
| Gazetteer → commune table | `parse_gazetteer` | 🟡 | Heuristic parser: **check on the real file** |
| Forecast vs naive | `src/forecast.py` | ✅ | Time split, naive drift, damped Holt, MAE/MAPE |
| Sangkat classifier | `src/model.py` | 🟡 | Logistic + SMOTE in one imblearn Pipeline, 5-fold CV, cost threshold; add features |
| PCA index | `model.pca_index` | 🟡 | Function ready; use it in the notebook |
| Overview page | `app.py` | ✅ | Metrics, map (click → province details), time chart, 3 tabs |
| Map explorer | `pages/1_…` | ✅ | |
| Time and forecast | `pages/2_…` | ✅ | |
| Urban commune model | `pages/3_…` | ✅ | Threshold slider, cost curve, confusion matrix |
| Upload | `pages/4_…` | ⏸ | Switched off in `app.py`; the page and `src/validate.py` are kept |
| Data quality | `pages/5_…` | ✅ | Sources, licences, missingness, outliers, fetch log |
| Findings | `pages/6_…` | 🟡 | 3 findings computed; add 2 more |
| Notebook | `notebooks/analysis.ipynb` | 🟡 | One section per week with starter code |
| Tests | `tests/` | ✅ | 37 tests on synthetic data |
| Scheduled pull | `.github/workflows/fetch.yml` | ✅ | Weekly + manual button |

---

## 5. To-do list (in order)

### Week A: data in, app running locally
- [ ] Run `download_data.py`; fix any failures with the manual fallbacks
- [ ] Run `build_processed.py`; resolve unmatched province names
- [ ] Open the gazetteer file; confirm `parse_gazetteer` finds khum/sangkat correctly (fix if needed)
- [ ] `streamlit run app.py`; click through all 7 pages
- [ ] Create the GitHub repo, push, deploy to Streamlit Community Cloud, put the link in the README

### Week B: analysis depth (notebook sections 1–9)
- [ ] Week 1: data dictionary for every column used (table in notebook)
- [ ] Week 2: missingness map per source + explanation of each gap; show any fill before/after
- [ ] Week 3: explain each flagged outlier (Phnom Penh, Mondul Kiri…)
- [ ] Week 4: justify each scaler (StandardScaler in model; log for density)
- [ ] Week 5: compare one-hot vs. target encoding for province; report width added
- [ ] Week 6: write each feature as a claim about the world
- [ ] Week 8: correlation matrix of province indicators; PCA urbanisation index + variance kept
- [ ] Week 9: name-matching table + row counts before/after every join
- [ ] **Multi-year map (recommended):** add census 2008 and 1998 province totals (NIS reports) so the year slider can re-colour the map and H1 can be tested over time

### Week C: models and findings
- [ ] Week 10: add commune features (e.g. commune database 2011: families, area, % electricity); compare with/without `district_type` (leakage)
- [ ] Week 11: report whether Holt beats the naive baseline; discuss the UN projection band
- [ ] Week 13: confirm every fitted step is inside the Pipeline; test set used once
- [ ] Findings 4 and 5, each one sentence + number + chart + caveat
- [ ] Week 14 ethics section: small-area identification risk; census misses Cambodians abroad; "urban" is an administrative label (sangkat), not a measured density

### Week D: polish and defence
- [ ] Restart & Run All on the notebook with no error
- [ ] All tests pass on GitHub Actions
- [ ] README complete: live link, sources, licences, team
- [ ] Rehearse the 10-minute defence; every member speaks

---

## 6. Course week coverage

| Week | Where |
|---|---|
| 1 Pipeline | `pipeline.build_processed`, data dictionary in notebook |
| 2 Missing values | `missingness_report`, data-quality page, notebook §2 |
| 3 Outliers | `flag_outliers`, data-quality page |
| 4 Normalisation | rates on every map; scaler choice in `model.py` |
| 5 Encoding | `PROVINCES` codes; OneHotEncoder in `model.py`; notebook §5 comparison |
| 6 Features | `load_census`, `national_series` |
| 8 Selection / PCA | `model.pca_index`, notebook §8 |
| 9 Integration | `PROVINCES` alias table, `load_province_geojson`, row counts printed |
| 10 Imbalanced | `model.run`: base rate, SMOTE in folds, cost threshold, precision/recall |
| 11 Time series | `forecast.evaluate`: split in time, naive baseline |
| 12 Visualisation | `charts.py`: finding titles, stated class breaks |
| 13 One pipeline | imblearn `Pipeline`, `cross_val_predict`, test once |
| 14 Ethics | notebook §14, data-quality page |
| 7, 15 Defence | Restart & Run All, fixed seed (`config.SEED = 42`) |

---

## 7. Risks and fallbacks

| Risk | Fallback |
|---|---|
| ODC / UN site down when downloading | Retry later; use manual links in DATA_SOURCES.md |
| Boundary names don't match | Add spellings to `PROVINCES` aliases |
| Gazetteer format differs from what the parser expects | Adjust `parse_gazetteer`; test with `pytest tests/test_pipeline.py` |
| WPP files are large | Script streams and keeps only Cambodia; `.csv.gz` ignored by git |
| Streamlit Cloud memory | Province GeoJSON only on the overview; simplify commune GeoJSON before using it |
| Hypothesis rejected | Report it honestly: that is a valid result |
