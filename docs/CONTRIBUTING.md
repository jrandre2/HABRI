# Contributing & Developer Guide

This guide covers environment setup, architecture, coding conventions, and how to extend HABRI to new regions or indicators.

Scope note: the canonical validated baseline remains the North Carolina statewide layer. The repository also contains a Tennessee statewide pipeline and a shared NC+TN standardized layer for unified cross-state mapping.

---

## Table of Contents

- [Environment Setup](#environment-setup)
- [Architecture Overview](#architecture-overview)
- [Pipeline Execution](#pipeline-execution)
- [Current-Conditions Refresh](#current-conditions-refresh)
- [Code Organization](#code-organization)
- [Extending to a New Region](#extending-to-a-new-region)
- [Adding a New Indicator](#adding-a-new-indicator)
- [Adding a New Hazard Type](#adding-a-new-hazard-type)
- [Adding a New Validation Source](#adding-a-new-validation-source)
- [Data Pipeline Flow](#data-pipeline-flow)
- [Known Issues and Workarounds](#known-issues-and-workarounds)
- [Coding Conventions](#coding-conventions)

---

## Environment Setup

### Prerequisites

- Python 3.10+
- 4+ GB free RAM (Ookla parquet files are ~600 MB-1 GB each)
- Internet connection for initial data downloads

### Installation

```bash
# Clone the repository
git clone <repo-url>
cd HABRI

# Create and activate a virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate  # macOS/Linux
# .venv\Scripts\activate   # Windows

# Install dependencies
pip install -r requirements.txt
```

### Environment variables

Create a `.env` file in the project root (this file is gitignored):

```bash
# Optional — Census API works without a key for <500 requests/day
CENSUS_API_KEY=your_key_here
```

### Manual data download

The FEMA NRI CSV cannot be downloaded programmatically (the URL redirects). Download it once:

1. Visit https://hazards.fema.gov/nri/data-resources#csvDownload
2. Download the "Census Tracts" CSV (~200-400 MB zipped)
3. Extract to `data/raw/NRI_Table_CensusTracts.csv`

All other data sources are fetched automatically by Notebook 01.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                    src/config.py                         │
│  Global constants: paths, weights, URLs, NC defaults     │
└──────────────────────┬──────────────────────────────────┘
                       │ imported by
┌──────────────────────▼──────────────────────────────────┐
│         src/utils.py / src/region.py / src/combined.py   │
│  Shared helpers, multi-state RegionConfig, schema        │
│  harmonization, and NC+TN shared-scale standardization   │
└──────────────────────┬──────────────────────────────────┘
                       │ imported by
┌──────────────────────▼──────────────────────────────────┐
│        Notebooks (NC baseline) + scripts (TN/combined)   │
│  NC notebooks 01-04, TN statewide build, cross-state     │
│  comparison, shared NC+TN layer, quarterly refresh       │
└─────────────────────────────────────────────────────────┘
```

### Design principles

1. **Config is centralized.** All constants, weights, FIPS codes, URLs, and column mappings live in `src/config.py`. Notebooks never hardcode these values.
2. **Utils are stateless.** Functions in `src/utils.py` are pure (or nearly pure) and take data as arguments.
3. **NC notebooks are sequential.** Each NC baseline notebook reads outputs from prior notebooks. Outputs are GeoPackage or CSV files in `data/processed/`.
4. **Raw data is immutable.** Files in `data/raw/` are never modified after download. Processing always writes to `data/processed/`.
5. **Idempotent execution.** Each notebook checks for cached outputs before re-downloading. You can safely re-run any notebook.
6. **Cross-state products are explicit.** The combined NC+TN layer is built separately from the state baselines so within-state interpretation remains intact.

---

## Pipeline Execution

Run notebooks in order. Each checks for cached data and skips downloads if outputs already exist.

```
01_data_acquisition.ipynb
    ├── Downloads: tract boundaries, NRI, towers, Ookla, ACS, road network
    ├── Outputs:   study_tracts.gpkg, acs_demographics.csv, nri_study_area.csv,
    │              hifld_cellular_towers.geojson, ookla_*.gpkg, nc_road_network.graphml
    └── Time:      ~1-2 hours (dominated by statewide road graph download from Overpass API)

02_hazard_processing.ipynb
    ├── Reads:     nri_study_area.csv, study_tracts.gpkg
    ├── Outputs:   hazard_scores.gpkg
    └── Time:      <1 min

03_infra_proxy_generation.ipynb
    ├── Reads:     hifld_cellular_towers.geojson, ookla_fixed_pre_helene.gpkg,
    │              nc_road_network.graphml, study_tracts.gpkg
    ├── Outputs:   infra_fragility.gpkg
    └── Time:      ~1-2 hours (dominated by betweenness centrality on statewide graph)

04_index_calculation.ipynb
    ├── Reads:     hazard_scores.gpkg, infra_fragility.gpkg, acs_demographics.csv,
    │              study_tracts.gpkg, ookla_*.gpkg, ioda_asn_timeseries.csv
    ├── Outputs:   habri_composite.gpkg, habri_composite.csv, habri_map.html,
    │              habri_4panel.png, habri_profiles.png,
    │              ioda_outage_timeseries.png, fcc_county_validation.png
    └── Time:      ~5-10 min
```

### Full pipeline from scratch: ~2-4 hours (dominated by betweenness centrality on statewide road graph)

### Tennessee and cross-state products

After the NC baseline exists, the repo supports two additional workflows:

```bash
# Tennessee statewide baseline
python scripts/build_habri_tn.py

# WNC vs Eastern Tennessee Helene comparison figures
python scripts/compare_helene_nc_tn.py

# Shared NC+TN standardized layer and maps
python scripts/build_habri_nc_tn_combined.py
```

The combined layer preserves the original state-local scores in `*_state` columns and recomputes the main `H_E`, `I_F`, `C_C`, and `HABRI` fields on a shared NC+TN scale.

## Current-Conditions Refresh

The published North Carolina baseline (`habri_composite.*`) is the source of truth for `H_E` and `C_C` and is not updated during current-conditions runs. Current-conditions refreshes are currently implemented for the NC baseline path only.

To generate a new January 2026-style scenario from a fixed-network export:

```bash
python scripts/build_habri_current_2026_01.py --version-tag 2026_01
python scripts/build_ookla_jan_2026_validation.py --version-tag 2026_01
```

Both scripts support:

- `--input-csv`: explicit path to a FixedNetworkPerformance CSV
- `--max-location-accuracy-m`: optional GPS-accuracy filter
- `OOKLA_JAN2026_CSV`: environment variable fallback for the export path

Outputs are always versioned by tag and written to separate files (`habri_current_<tag>`, `habri_validation_<tag>`, etc.), leaving the published baseline unchanged.

```text
Output naming pattern:
- ookla_fixed_<tag>.gpkg
- ookla_tract_<tag>.csv / .gpkg
- infra_fragility_current_<tag>.gpkg
- habri_current_<tag>.csv / .gpkg
- habri_validation_<tag>.csv
- habri_validation_<tag>_summary.csv
- habri_validation_<tag>.png
```

---

## Code Organization

### src/config.py

Single source of truth for all project constants. Key sections:

| Section | What It Contains |
|---------|-----------------|
| Paths | `PROJECT_ROOT`, `DATA_RAW`, `DATA_PROCESSED` |
| CRS | `CRS_PROJECT` (NC default), `CRS_WGS84`, plus multi-state CRSs in `src/region.py` |
| Study area | `STATE_FIPS`, `COUNTY_FIPS` dict, `COUNTY_FIPS_FULL` list |
| NRI | Column name mappings for scores, ratings, EAL; rating ordinal encoding |
| Ookla | S3 base URL, quarter definitions, column list; `ookla_s3_path()` helper |
| HIFLD | ArcGIS REST FeatureServer URL, pagination size |
| Census | API base URL, ACS year, variable-to-name mapping |
| Weights | All index weights (top-level and sub-component) |
| IODA | API base URL, Helene date range, WNC ISP ASN list |

### src/utils.py

Reusable functions. Keep these stateless and general-purpose.

| Function | Purpose |
|----------|---------|
| `load_study_tracts()` | Load the study area GeoPackage (with existence check) |
| `ensure_crs(gdf, target)` | Reproject a GeoDataFrame if needed; raises on missing CRS |
| `get_study_area_bbox(gdf, crs)` | Return bounding box tuple in the specified CRS |
| `min_max_normalize(series, invert)` | Min-max normalization to [0,1]; handles constant series (retained for compatibility) |
| `z_score_normalize(series, invert)` | Z-score normalization mapped to [0,1] via standard normal CDF; primary normalization method |
| `impute_with_median(df, column, label)` | Fill NaN with column median; logs count and affected GEOIDs |
| `spatial_join_to_tracts(...)` | Spatial join + aggregate pattern (join features to tracts, groupby, merge back) |
| `query_arcgis_feature_layer(...)` | Paginated ArcGIS REST API query → GeoDataFrame |
| `fetch_ioda_timeseries(...)` | IODA API v2 time-series query |
| `fetch_acs_tract_data(...)` | Census ACS API query for a single county; handles sentinel value conversion |
| `fetch_acs_state_tracts(...)` | Census ACS API query for all tracts in a state (single API call) |

### src/region.py

Multi-state configuration layer for adapting HABRI beyond NC.

| Object | Purpose |
|--------|---------|
| `RegionConfig` | Dataclass for state FIPS, county FIPS, CRS, weights, and focal counties |
| `NC_CONFIG` | Built-in NC configuration matching the baseline |
| `TN_CONFIG` | Built-in TN configuration used by `build_habri_tn.py` |

### src/combined.py

Cross-state harmonization and shared-scale layer helpers.

| Function | Purpose |
|----------|---------|
| `harmonize_habri_schema(...)` | Standardize `state_*` and `county_*` metadata across state outputs |
| `build_joint_standardized_habri(...)` | Re-standardize NC and TN sub-indices on one shared NC+TN scale |
| `load_joint_standardized_habri(...)` | Load the saved state baselines and return the combined layer |

---

## Extending to a New Region

To apply HABRI to a different set of counties:

### Step 1: Update config.py or add a RegionConfig in src/region.py

```python
# Example: Coastal NC counties
STATE_FIPS = "37"
COUNTY_FIPS = {
    "New Hanover": "129",
    "Brunswick":   "019",
    "Pender":      "141",
    "Onslow":      "133",
}
```

The rest of the config (`COUNTY_FIPS_LIST`, `COUNTY_FIPS_FULL`) will update automatically.

For a reusable multi-state setup, prefer adding a dedicated `RegionConfig` entry in `src/region.py` and consuming that from a script, as the Tennessee pipeline does with `TN_CONFIG`.

### Step 2: Adjust hazard weights (if appropriate)

For a coastal region, you might increase the hurricane weight and add coastal flooding:

```python
# In config.py — add coastal flooding
NRI_SCORE_COLS = {
    "IFLD_RISKS": "Inland Flooding Risk Score",
    "HRCN_RISKS": "Hurricane Risk Score",
    "CFLD_RISKS": "Coastal Flooding Risk Score",  # new
}

# Adjust weights in config.py
W_HE_FLOOD = 0.30
W_HE_HURRICANE = 0.40
W_HE_COASTAL = 0.30  # new
```

You'll also need to update Notebook 02 to include the new hazard component in the H_E formula.

### Step 3: Re-download NRI data

The full NRI CSV covers the entire US, so no re-download is needed — just re-run Notebook 01 to filter to the new counties.

### Step 4: Re-run all notebooks

```bash
# Clear processed data (raw data can be reused for the same state)
rm data/processed/*.gpkg data/processed/*.csv data/processed/*.png data/processed/*.html
jupyter notebook notebooks/01_data_acquisition.ipynb
```

### Step 5: Update IODA validation ASNs

If you want to validate against a real disaster event in the new region, update `WNC_ASNS` in config.py with the relevant ISP ASNs, and adjust `HELENE_START`/`HELENE_END` to the relevant disaster date range.

---

## Adding a New Indicator

Example: adding "population over 65" as a coping capacity indicator.

### 1. Add the ACS variable to config.py

```python
ACS_VARIABLES = {
    # ... existing variables ...
    "B01001_020E": "pop_65_74_male",
    "B01001_044E": "pop_65_74_female",
    # (or use a simpler aggregate table if available)
}
```

### 2. Update the weight constants in config.py

With 6 indicators instead of 5, adjust weights to sum to 1.0:

```python
W_CC_NO_VEHICLE = 0.167
W_CC_MOBILE_ONLY = 0.167
W_CC_DISABILITY = 0.167
W_CC_INCOME = 0.167
W_CC_POVERTY = 0.167
W_CC_ELDERLY = 0.167
```

### 3. Update Notebook 04

Add the percentage computation and normalization:

```python
acs["pct_elderly"] = (acs["pop_65_74_male"] + acs["pop_65_74_female"]) / acs["total_population"]
acs["elderly_vuln"] = z_score_normalize(acs["pct_elderly"])
```

Update the C_C formula to include the new term.

### 4. Re-run Notebook 01 (to fetch the new ACS variable) and Notebook 04

---

## Adding a New Hazard Type

Example: adding wildfire risk.

### 1. Add the NRI column to config.py

```python
NRI_SCORE_COLS = {
    "IFLD_RISKS": "Inland Flooding Risk Score",
    "HRCN_RISKS": "Hurricane Risk Score",
    "LNDS_RISKS": "Landslide Risk Score",
    "WFIR_RISKS": "Wildfire Risk Score",  # new
}
```

### 2. Adjust H_E sub-component weights

```python
W_HE_FLOOD = 0.30
W_HE_HURRICANE = 0.25
W_HE_LANDSLIDE = 0.20
W_HE_WILDFIRE = 0.25  # new
```

### 3. Update Notebook 02

Add the normalization and weighted sum for the new hazard.

---

## Adding a New Validation Source

To add a new external validation dataset:

1. Acquire the data (add download logic to Notebook 01 or 04)
2. Join or aggregate to the tract or county level
3. Merge with HABRI scores
4. Compute an appropriate correlation statistic (Spearman for ordinal/rank relationships)
5. Add the visualization to Notebook 04, Section E

Good candidates for additional validation:

- Power outage data (if available from utilities)
- 911 call volume surges during events
- FEMA Individual Assistance claims per tract
- Satellite imagery-based damage assessments

---

## Data Pipeline Flow

```
                                    ┌─────────────┐
                                    │ FEMA NRI CSV │ (manual download)
                                    └──────┬──────┘
                                           │
┌──────────┐  ┌──────────┐  ┌─────────┐   │   ┌──────────┐  ┌─────────┐
│  pygris   │  │  HIFLD   │  │  Ookla  │   │   │  Census  │  │  OSMnx  │
│  (tracts) │  │  (towers)│  │  (S3)   │   │   │  ACS API │  │  (roads)│
└─────┬─────┘  └────┬─────┘  └────┬────┘   │   └────┬─────┘  └────┬────┘
      │              │             │         │        │             │
      ▼              ▼             ▼         ▼        ▼             ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                     Notebook 01: Data Acquisition                       │
│  study_tracts.gpkg  towers.geojson  ookla_*.gpkg  nri.csv  acs.csv     │
│                                                         roads.graphml   │
└───┬──────────────────────┬─────────────────────┬────────────────────┬──┘
    │                      │                     │                    │
    ▼                      ▼                     ▼                    │
┌────────────┐    ┌────────────────┐    ┌────────────────┐           │
│ Notebook 02│    │  Notebook 03   │    │  Notebook 04   │◄──────────┘
│ Hazard     │    │  Infra Proxy   │    │  Index Calc    │
│ Processing │    │  Generation    │    │  + Validation  │
└─────┬──────┘    └───────┬────────┘    └───────┬────────┘
      │                   │                     │
      ▼                   ▼                     ▼
  hazard_scores     infra_fragility      habri_composite
     .gpkg              .gpkg            .gpkg / .csv
                                         + maps + charts
```

---

## Known Issues and Workarounds

### pandas 2.3 + pyarrow 16 compatibility

`pd.read_parquet()` fails with an ndim error when reading Ookla parquets. **Workaround:** Use `pyarrow.parquet.read_table()` and convert column-by-column via `.to_pylist()`:

```python
import pyarrow.parquet as pq

table = pq.read_table(file, columns=OOKLA_COLUMNS)
data = {col: table.column(col).to_pylist() for col in OOKLA_COLUMNS}
df = pd.DataFrame(data)
```

Local Ookla data is saved as GeoPackage (not Parquet) to avoid this issue on subsequent loads.

### FEMA NRI URL redirects

The NRI download URL changes periodically. As of December 2025, v1.20 can be downloaded from:
```
https://www.fema.gov/about/reports-and-data/openfema/nri/v120/NRI_Table_CensusTracts.zip
```

If this URL stops working, download manually from https://hazards.fema.gov/nri/data-resources#csvDownload.

### OSMnx edge length units

OSMnx always stores the `length` edge attribute in **meters**, regardless of the output CRS. Do not multiply by CRS unit factors when computing road statistics.

### Census API rate limits

Without an API key, the Census API allows up to 500 requests per day. HABRI makes a single statewide request via `fetch_acs_state_tracts()`, well within this limit. Add a key to `.env` if running repeatedly.

### Betweenness centrality runtime

Exact betweenness on the statewide road graph (648,424 nodes, 1,528,603 edges) would take days. The k=500 approximation runs in approximately 1-2 hours for the statewide graph. If you need exact values (e.g., for publication), set `k_samples = G.number_of_nodes()` in Notebook 03, cell 9, and expect a very long wait (potentially days).

---

## Coding Conventions

### General

- Python 3.10+ (type hints use `X | Y` union syntax where applicable)
- `pathlib.Path` for all file paths (no `os.path.join`)
- All constants in `src/config.py`, not hardcoded in notebooks
- Notebooks use relative imports via `sys.path.insert(0, str(Path("..").resolve()))`

### Spatial data

- Always call `ensure_crs()` before spatial joins or area calculations
- Use the region-appropriate projected CRS for processing (`EPSG:2264` for NC, `EPSG:2274` for TN); convert to EPSG:4326 for display or external APIs
- Prefer GeoPackage (`.gpkg`) over Shapefile or GeoParquet for intermediate outputs

### Naming

- Sub-index variables: `H_E`, `I_F`, `C_C`, `HABRI` (uppercase in DataFrames)
- Normalized component columns: `*_norm` or `*_vuln` (lowercase)
- Raw source columns: preserve original names (e.g., `IFLD_RISKS`, `avg_lat_ms`)

### Output files

- Geospatial outputs: GeoPackage (`.gpkg`)
- Tabular exports: CSV (`.csv`)
- Static maps: PNG at 200-300 DPI
- Interactive maps: HTML (Folium)
