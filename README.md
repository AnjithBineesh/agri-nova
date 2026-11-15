# Agri Nova

**AI crop prediction. Smarter rotation strategy. Healthier soil.**
A NASA Space Apps Challenge project: a crop rotation and soil health decision-support platform built on
NASA Earth observations.

Agri Nova helps farmers, researchers and agricultural organisations to:
* understand a farm's climate, rainfall, soil moisture, vegetation and terrain from NASA data;
* interpret soil tests;
* see which crops fit the farm, and why;
* generate and compare alternative crop rotations;
* get an **AI crop prediction** (machine learning) for each growing season;
* simulate five years of soil carbon, nutrient balance, water demand, diversity and climate risk.

> **Website wording.** The public website talks only about crop prediction, rotation strategy and soil
> health. Data providers are not named in the interface or the PDF reports; they appear only in this
> README, the code and the researcher CSV/JSON export (raw provenance).

---

## What is in this release

| Area | Status |
|---|---|
| Landing page, registration, sign-in, role-based access (farmer / researcher / organisation / admin) | Working |
| Farm registration: Leaflet map, place search, opt-in GPS, manual coordinates, drawn field boundaries (geodesic area), multiple farms, seasons, crop history | Working |
| Soil: manual entry with units and measured/estimated flags; PDF/JPG/PNG upload with PDF-text or Tesseract OCR extraction, user review and confirmation; referenced per-parameter assessment | Working |
| NASA POWER: daily point request for the current year (`T2M, T2M_MAX, T2M_MIN, PRECTOTCORR, RH2M, WS2M`, AG community, UTC) plus a 10-year monthly climatology | Integrated; no credentials needed |
| "This year's weather": rain since 1 January vs the farm's normal, temperature anomaly, days above 35 °C, longest dry spell, weekly chart; a location check while adding a farm | Working |
| GPM IMERG Final and Late Run (Giovanni time-series API) | Integrated; needs an Earthdata token |
| SMAP L3/L4, MODIS NDVI/EVI, Landsat and Sentinel-2 NDVI (HLS), ECOSTRESS LST/ET, SRTM slope (AppEEARS) | Integrated, asynchronous; needs Earthdata login |
| ERA5, FAO GAEZ v5 | Adapter interfaces only, shown as "Planned" |
| Field conditions page (formerly Earth Insights): indicators, 7 charts, date and dataset filters, provenance, resolution, quality, missing-data states | Working |
| Crop database: 25 crops (cereals, legumes, oilseeds, cotton, sugarcane, vegetables, cover crops) from FAO ECOCROP and FAO-56 | Working; researchers can edit |
| Crop suitability engine: 8 weighted factors, critical-constraint override, data completeness | Working |
| Rotation planner: rule engine, beam search, 4–6 strategies (existing, soil-health, water-conscious, climate-resilient, balanced, custom), automatic or custom priorities that always sum to 100% | Working |
| Multi-season state-based simulator: scenarios (temperature, rainfall, irrigation), 1- or 5-year horizon, uncertainty bands, comparisons | Working |
| PDF reports: farmer and scientific versions | Working |
| Researcher portal (assumptions, weight sensitivity, CSV/JSON export, anonymised aggregates) and organisation portal (member farms map, regional indicators, CSV report) | Working |
| Redesigned interface: photo hero, floating pill navigation, lime call-to-action buttons, rounded cards, italic serif accents; four-step farm wizard; "next step" guidance on every page; mobile navigation drawer | Working |
| **AI crop prediction**: two trained classifiers (soil + season, 22 crops; detailed soil test, 6 crops), farm auto-fill per season, explanations, out-of-range warnings, "AI match" column in suitability, AI section in PDF reports, model evaluation in the researcher portal | Working |
| Tests: 41 backend tests (science reference values, adapters, engines, API, RBAC, AppEEARS flow, ML) | Passing |

**Verification note.** The development sandbox had no outbound access to NASA endpoints. The live
NASA calls were therefore **not executed here**. They are implemented against the documented API
formats and tested with recorded response shapes. On a machine with internet access, NASA POWER
works immediately, and GPM and AppEEARS products work once Earthdata credentials are set. The UI
walkthrough and screenshots used the explicitly labelled demonstration dataset (see below).

---

## Quick start (local development)

### Prerequisites
* Python 3.11+
* Node.js 20+
* Optional: Tesseract OCR (`apt install tesseract-ocr` / `brew install tesseract`) for image soil reports

### 1. Backend
```bash
cd backend
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env                                    # set JWT_SECRET_KEY; add Earthdata credentials
uvicorn app.main:app --reload --port 8000
```
The API docs are at http://localhost:8000/docs. The database tables are created on startup, and the
crop database is seeded automatically. SQLite is the default.

### 2. Frontend
```bash
cd frontend
npm install
cp .env.example .env.local          # BACKEND_URL=http://127.0.0.1:8000
npm run dev                         # http://localhost:3000
```
The browser calls `/api/*` on the Next.js origin, and Next.js proxies these calls to FastAPI. No
credentials ever reach the browser.

### 3. Run the tests
```bash
cd backend && pytest -q
cd frontend && npm run typecheck && npm run build
```

### Production-like stack (PostgreSQL + PostGIS)
```bash
cp backend/.env.example backend/.env    # set JWT_SECRET_KEY and EARTHDATA_* values
docker compose up --build               # db (PostGIS 16), backend :8000, frontend :3000
```
With `USE_POSTGIS=true`, farm points and boundaries are native `geometry(…, 4326)` columns, written
with `ST_GeomFromGeoJSON` and read with `ST_AsGeoJSON`. With SQLite they are stored as GeoJSON
text.

---

## Configuring NASA data access

1. **NASA POWER** needs no setup. Each refresh makes two requests:
   * **Daily, current year.** This is the request used by `fetch_nasa_power()` in
     `backend/app/earth_observation/nasa_power_service.py`:
     ```
     GET https://power.larc.nasa.gov/api/temporal/daily/point
         ?parameters=T2M,T2M_MAX,T2M_MIN,PRECTOTCORR,RH2M,WS2M&community=AG
         &longitude={lon}&latitude={lat}&start={YYYY0101}&end={today}&format=JSON&time-standard=UTC
     ```
     The start and end dates are computed (1 January to today, UTC) rather than hard-coded. POWER
     returns `-999` for days it hasn't processed yet; these are stored as missing, never as zero, and
     the UI says how many days are still pending.
   * **Monthly, last 10 complete years.** This gives the long-term normal the engines need. It adds
     `ALLSKY_SFC_SW_DWN` so that FAO-56 Penman–Monteith ET0 can be calculated.

   You can try it directly with `GET /api/power/preview?latitude=..&longitude=..` (signed in). The farm
   wizard calls this endpoint when you select "Check weather so far this year".
2. Create a free **NASA Earthdata Login** at https://urs.earthdata.nasa.gov/ and set
   `EARTHDATA_USERNAME` and `EARTHDATA_PASSWORD` in `backend/.env`. You can also set
   `EARTHDATA_TOKEN` (enough for GPM; AppEEARS needs username and password).
   * Authorise the **NASA GESDISC DATA ARCHIVE** application in your Earthdata profile (for GPM via
     Giovanni).
3. Check the current AppEEARS product versions (`GET /api/product`). Override them in `.env` if they
   have changed.

AppEEARS requests take minutes to hours. The Field conditions page shows "Processing" and checks again
every 30 seconds while open. See [docs/DATASETS.md](docs/DATASETS.md) for each dataset's products,
resolution, quality screening and limitations.

### Demonstration data (offline demos only)
Set `ENABLE_DEMO_DATA=true` to let a user load a synthetic dataset when NASA retrieval fails, for
example when presenting without internet. This happens only after an explicit click. Every value
is stored with `is_demo=true` and data type `demonstration`, and every page, strategy and report
built on it carries a "Demonstration data" warning. The data can be removed again with one click.
Keep this setting off in production.

---

## Farmer journey
1. Register and choose the **Farmer** role.
2. **Add a farm**: place a point, search a place, share GPS location (asked only when you click), or
   type coordinates. Optionally draw the field boundary. Then add seasons, irrigation and crop history.
3. **Field conditions** (formerly Earth Insights): click *Retrieve weather data*.
4. **Soil analysis**: enter values, or upload a report and confirm the extracted values.
5. **Crop prediction**: values are filled from the soil test and the farm's weather record for each
   season (or typed by hand); the model ranks crops and explains each pick.
6. **Crop suitability**: view scores, critical constraints and factor-level explanations, with
   optional climate scenarios.
7. **Rotation planner**: choose automatic or custom priorities, optionally add prices and yields or
   your own rotation, generate strategies, read the trade-offs and save one.
8. **Five-year simulator**: compare up to three strategies under a chosen climate and water scenario.
9. **Reports**: download the farmer or scientific PDF.

---

## Architecture

```
frontend/  Next.js 15 (App Router) · React 19 · TypeScript · Tailwind · Recharts · Leaflet · Lucide
  src/app/                 landing, login, register, /app/* modules
  src/components/          AppShell, MapPicker, FarmForm, charts, ribbons, sliders, UI kit
  src/lib/                 API client (JWT bearer), auth and farm context, types

backend/   FastAPI · Pydantic v2 · SQLAlchemy 2 · PostgreSQL/PostGIS (SQLite in dev)
  app/main.py, config.py, database.py
  app/models/              users, organisations, farms (geometry), soil profiles & reports, crops,
                           crop history, earth observations, fetch status, cache, recommendations,
                           simulations, reports, revoked tokens
  app/routers/             auth, farms, soil, earth, crops, rotations, simulations, reports,
                           research, organisations
  app/earth_observation/   nasa_power, gpm, appeears (+ smap, modis, landsat, sentinel, ecostress,
                           srtm), era5, gaez, registry, cache, http (timeouts/retries), demo
  app/agriculture/         crop_database, climate_analyser (environment profile, FAO-56 ET0),
                           soil_analyser, data/crops.json
  app/recommendation_engine/ crop_suitability, rotation_rules, priority_scoring,
                           recommendation_generator, seasons
  app/simulation/          soil_state, nutrient_balance, organic_matter_model, water_balance,
                           climate_scenarios, rotation_simulator, scenario_comparison
  app/soil_processing/     PDF text / OCR extraction, parameter parser
  app/reporting/           ReportLab PDF reports
  app/ml/                  features, training, predictor, train (CLI), artifacts/ (saved models + model_card.json)
  ml_data/                 training datasets (CSV)
  scripts/build_crop_database.py   regenerates crops.json from FAO ECOCROP
```

Every Earth observation adapter returns a standard `ObservationRecord` (dataset, product, variable,
value, unit, date, location, spatial and temporal resolution, source URL, processing status, quality,
data type). Upstream responses are cached in the database (default 7 days). HTTP calls have timeouts
and bounded retries with backoff, and respect `Retry-After`.

### Main API endpoints
`/api/auth/{register,login,logout,me}` ·
`/api/farms[/{id}]` ·
`/api/farms/{id}/soil`, `/soil/upload`, `/api/soil/{report_id}/confirm` ·
`/api/farms/{id}/earth-data[/rainfall|/temperature|/soil-moisture|/vegetation|/terrain|/refresh|/status|/demo]` ·
`/api/crops`, `/api/crops/{id}`, `/api/crops/suitability` ·
`/api/rotations/generate`, `/api/rotations/{id}`, `/api/rotations/compare` ·
`/api/simulations`, `/api/simulations/{id}`, `/api/simulations/compare` ·
`/api/reports/generate`, `/api/reports/{id}[/download]` ·
`/api/predict/{models,crop,soil}`, `/api/predict/farm/{id}[/inputs]` ·
`/api/research/*` · `/api/organisations/me/*`. The full schema is at `/docs`.

### Access control
Farmers see only their own farms. Organisation staff can view, but not edit, farms of members of
their organisation. Researchers get aggregates anonymised at k ≥ 3, plus exports of farms they are
authorised to view. Unauthorised farm IDs return 404. JWTs can be revoked on logout. Uploaded files
are stored under random names and served only through authorised endpoints.

---

## Machine learning (AI crop prediction)

Datasets (in `backend/ml_data/`) and how they are used:

| File | Rows | Used for | Result |
|---|---|---|---|
| `crop_recommendation.csv` (N, P, K, temperature, humidity, pH, rainfall → crop) | 2,200, 22 crops | **Crop prediction model** | Random forest, 99.6% accuracy / 0.996 macro-F1 on a 440-row held-out test set |
| `soil_nutrients_crop.csv` (N, P, K, pH, EC, S, Cu, Fe, Mn, Zn, B → crop) | 620, 6 crops | **Detailed soil test model** | Support vector machine, 96.0% accuracy on 124 held-out rows |
| `india_rainfall_crop_yield_2014_2024.csv` | 7,920 | Yield regression (tested) | **Not deployed**: best cross-validated R² = −0.007, no better than the mean; yield shows no correlation with any input (|r| ≤ 0.03) |
| `weather_daily_kochi_2020_2025.csv` (NASA POWER daily, Kochi) | 2,192 days | Season feature builder (monthly climatology → season temperature, humidity, mean monthly rainfall) and plausibility check | Kerala Kharif: coconut, papaya and rice rank highest |

Method: 80/20 stratified split; 5-fold stratified cross-validation on the 80% to compare logistic
regression, k-nearest neighbours, SVM, random forest, extra trees and gradient boosting; the best model
is scored once on the 20%, then refit on all rows. Explanations use permutation importance and per-crop
10th–90th percentile ranges; inputs outside the training range are flagged and lower the confidence.
On a farm, N/P/K come from the soil test (converted to kg/ha), pH from the soil test, and temperature,
humidity and rainfall from the farm's weather record (NASA POWER climatology) for each season's months.

Retrain with `cd backend && python -m app.ml.train` (about 2 minutes; most of it is cross-validating six algorithms). Saved models are pinned to
scikit-learn 1.9.1; if another version is installed, the backend refits the selected models on startup
(about 1 s) instead of failing.

---

## Scientific methodology (summary)

* **Reference ET0**: FAO-56 Penman–Monteith from POWER Tmax, Tmin, RH, wind and solar radiation,
  with Hargreaves as fallback. Tested against FAO-56 Examples 8 and 18.
* **Suitability**: ECOCROP trapezoid membership for monthly temperature (plus frost and heat-day
  penalties), annual rainfall and pH; FAO-56 crop water balance with FAO/AGLW effective rainfall,
  stored soil water and irrigation; season fit; texture and drainage; nutrients; salinity. The score is
  a weighted mean over factors that have data. Critical constraints override the score. Data
  completeness is reported.
* **Rotation rules**: same crop or family in succession, minimum break lengths, shared pathogen host
  groups (e.g. Sclerotinia, root-knot nematodes, bacterial wilt), legume inclusion, cereal–legume
  transitions, root-depth diversity, fallow exposure.
* **Strategy generation**: beam search over suitable options per season (including two-season crops),
  evaluated with the simulator under baseline and a stress test (+1.5 °C, −15% rain). Objectives:
  soil health, water conservation, climate resilience, economic potential (only with farmer prices)
  and diversity. Weights always total 100%. Automatic weights are explained.
* **Simulation** (state carried season to season):
  * single-pool soil organic carbon with ICBM humification (h = 0.125 above-ground, 0.35 roots) and
    Q10 = 2 temperature-scaled decomposition, with ±30% parameter bands;
  * partial N/P/K balance before fertiliser, with legume %Ndfa and residue-dependent N credits;
  * FAO-56 water demand with dry and wet year ranges from the observed rainfall CV;
  * Shannon diversity of crop families;
  * climate vulnerability;
  * a qualitative erosion index (cover × slope × rainfall; explicitly not a soil-loss model).
* **Soil interpretation**: USDA reaction classes for pH; India Soil Health Card ratings for
  OC/N/P/K, which are method-specific (the method is stated); FAO-56 Table 19 for available water
  capacity when it is not measured. There is no composite "soil health score".

### Limitations
* Coarse products (POWER, IMERG, SMAP) describe areas of 10–60 km, not individual fields.
* Yields are not predicted. Reference yields (or farmer-provided yields) are used only for nutrient
  removal and residue inputs.
* Nutrient and residue coefficients are indicative and should be calibrated locally.
* Recommendations are decision support. For high-impact decisions, consult local extension officers
  and agronomists.

## Photography
Landing, sign-in and dashboard photos come from Unsplash under the Unsplash License. They're listed with
credits in `frontend/src/lib/images.ts` and the site footer. The images load from the Unsplash CDN; to
self-host them, put the files in `frontend/public/images` and change the `src` values. Each photo
has a colour fallback, so pages stay readable offline.

## Next steps
* Integrate GAEZ v5 raster sampling and the ERA5 time-series adapter.
* Add native Sentinel-2 L2A (10 m) via Copernicus Data Space, and polygon (area) AppEEARS requests for
  drawn boundaries.
* Add localisation (farmer languages) and an offline-capable PWA for low-connectivity areas.
* Calibrate the SOC and nutrient coefficients with regional long-term rotation trials.
