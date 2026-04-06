# HABRI Data Dictionary

This document defines every data file produced and consumed by the HABRI pipeline, including column-level definitions, data types, value ranges, and provenance.

---

## Table of Contents

- [Output Files](#output-files)
  - [habri_composite.csv / .gpkg](#habri_compositecsv--gpkg)
  - [hazard_scores.gpkg](#hazard_scoresgpkg)
  - [infra_fragility.gpkg](#infra_fragilitygpkg)
  - [acs_demographics.csv](#acs_demographicscsv)
  - [study_tracts.gpkg](#study_tractsgpkg)
- [Intermediate and Raw Files](#intermediate-and-raw-files)
  - [nri_study_area.csv](#nri_study_areacsv)
  - [hifld_cellular_towers.geojson](#hifld_cellular_towersgeojson)
  - [Ookla GeoPackages](#ookla-geopackages)
  - [nc_road_network.graphml](#nc_road_networkgraphml)
  - [ioda_asn_timeseries.csv](#ioda_asn_timeseriescsv)
- [Visualization Outputs](#visualization-outputs)
- [Common Identifiers](#common-identifiers)
- [Value Conventions](#value-conventions)

---

## Output Files

### habri_composite.csv / .gpkg

**Location:** `data/processed/habri_composite.csv` (tabular) and `data/processed/habri_composite.gpkg` (geospatial)
**Produced by:** Notebook 04
**Records:** 2,660 (one per census tract)
**CRS:** EPSG:2264 (.gpkg only)

This is the primary deliverable — the final HABRI scores with all sub-indices, component scores, and classifications.

| Column | Type | Range | Description |
|--------|------|-------|-------------|
| `GEOID` | string (11 chars) | e.g. `37021000100` | Census tract FIPS identifier (state + county + tract) |
| `H_E` | float | [0, 1] | **Hazard Exposure** sub-index. Weighted combination of normalized flood, hurricane, and landslide risk scores. Higher = more exposed. |
| `ifld_norm` | float | [0, 1] | Normalized inland flooding risk score (z-score + CDF within study area) |
| `hrcn_norm` | float | [0, 1] | Normalized hurricane risk score (z-score + CDF within study area) |
| `lnds_norm` | float | [0, 1] | Normalized landslide risk score (z-score + CDF within study area) |
| `I_F` | float | [0, 1] | **Infrastructure Fragility** sub-index. Weighted combination of tower density, latency, and road centrality. Higher = more fragile. |
| `tower_density_norm` | float | [0, 1] | Z-score + CDF normalized cell tower density, **inverted** (higher = fewer towers = more fragile) |
| `latency_norm` | float | [0, 1] | Z-score + CDF normalized pre-Helene broadband latency (higher = worse baseline performance) |
| `road_fragility` | float | [0, 1] | Composite road network fragility (betweenness centrality + inverse road density) |
| `C_C` | float | [0, 1] | **Coping Capacity Deficit** sub-index. Weighted combination of five demographic vulnerability indicators. Higher = less capacity to cope. |
| `no_vehicle_vuln` | float | [0, 1] | Normalized % of workers with no vehicle available |
| `mobile_only_vuln` | float | [0, 1] | Normalized % of households with cellular-only internet |
| `disability_vuln` | float | [0, 1] | Normalized % of population with a disability (ages 18+) |
| `income_vuln` | float | [0, 1] | Normalized median household income, **inverted** (1.0 = lowest income) |
| `poverty_vuln` | float | [0, 1] | Normalized % of population below poverty level |
| `HABRI` | float | [0, 1] | **Composite HABRI score.** `0.40*H_E + 0.35*I_F + 0.25*C_C`. Higher = higher risk of communications failure. |
| `HABRI_quintile` | string | `Very Low`, `Low`, `Moderate`, `High`, `Very High` | Quintile classification of HABRI score (5 equal-count groups) |
| `cluster` | int | 0, 1, or 2 | Raw k-means cluster assignment (internal; use `risk_profile` instead) |
| `risk_profile` | string | `Power-Dependent`, `Transport-Fragile`, `Dual-Risk` | Interpreted vulnerability profile label derived from cluster analysis |
| `geometry` | geometry | — | Census tract polygon boundary (.gpkg only) |

### habri_current_<version>.csv / .gpkg

**Location:** `data/processed/habri_current_<VERSION>.csv` and `data/processed/habri_current_<VERSION>.gpkg`  
**Produced by:** `scripts/build_habri_current_2026_01.py`  
**Records:** 2,660 (one per census tract)  
**CRS:** EPSG:2264 (.gpkg only)  
**Current versions:** `2026_01` (January 2026)

This is a versioned re-computation that keeps baseline `H_E` and `C_C` fixed, replacing only latency-driven infrastructure fragility.

| Column | Type | Range | Description |
|--------|------|-------|-------------|
| `GEOID` | string (11 chars) | e.g. `37021000100` | Census tract FIPS identifier |
| `latency_norm_<VERSION>` | float | [0, 1] | Z-score + CDF normalized current latency |
| `latency_norm_<VERSION>_imputed` | float | [0, 1] | Imputed version of `latency_norm_<VERSION>` |
| `avg_latency_ms_<VERSION>` | float | > 0 | Versioned tract-level average latency |
| `avg_download_mbps_<VERSION>` | float | > 0 | Versioned tract-level average download speed |
| `avg_upload_mbps_<VERSION>` | float | > 0 | Versioned tract-level average upload speed |
| `avg_jitter_ms_<VERSION>` | float | > 0 | Versioned tract-level average jitter (NaN if source jitter is unavailable) |
| `latency_delta_ms_vs_q3_2024` | float | any | Difference vs baseline latency (version minus baseline) |
| `latency_abs_delta_ms_vs_q3_2024` | float | >= 0 | Absolute latency delta |
| `latency_pct_change_vs_q3_2024` | float | any | Percentage change vs baseline latency |
| `geometry` | geometry | — | Census tract polygon boundary (.gpkg only) |

### infra_fragility_current_<version>.gpkg

**Location:** `data/processed/infra_fragility_current_<VERSION>.gpkg`  
**Produced by:** `scripts/build_habri_current_2026_01.py`  
**Records:** 2,660  
**CRS:** EPSG:2264

Versioned infrastructure layer used by the current-conditions HABRI recomputation.

| Column | Type | Range | Description |
|--------|------|-------|-------------|
| `GEOID` | string | 11 chars | Census tract FIPS identifier |
| `tower_density_norm` | float | [0, 1] | Baseline tower-density component |
| `road_fragility` | float | [0, 1] | Baseline road-fragility component |
| `latency_norm_<VERSION>` | float | [0, 1] | Versioned latency normalization |
| `latency_norm_<VERSION>_imputed` | float | [0, 1] | Median-imputed latency normalization |
| `avg_latency_ms_<VERSION>` | float | > 0 | Versioned tract-level average latency |
| `I_F` | float | [0, 1] | Recomputed infrastructure fragility value using versioned latency |
| `geometry` | geometry | — | Census tract polygon boundary |

---

### hazard_scores.gpkg

**Location:** `data/processed/hazard_scores.gpkg`
**Produced by:** Notebook 02
**Records:** 2,660
**CRS:** EPSG:2264

Intermediate output containing the Hazard Exposure sub-index and its components, joined to tract geometries.

| Column | Type | Range | Description |
|--------|------|-------|-------------|
| `GEOID` | string | 11 chars | Census tract FIPS identifier |
| `TRACTFIPS` | string | 11 chars | NRI tract identifier (same value as GEOID; from join key) |
| `IFLD_RISKS` | float | >= 0 | Raw FEMA NRI inland flooding risk score (nationally relative) |
| `HRCN_RISKS` | float | >= 0 | Raw FEMA NRI hurricane risk score (nationally relative) |
| `LNDS_RISKS` | float | >= 0 | Raw FEMA NRI landslide risk score (nationally relative) |
| `ifld_norm` | float | [0, 1] | Z-score + CDF normalized inland flooding score (within study area) |
| `hrcn_norm` | float | [0, 1] | Z-score + CDF normalized hurricane score (within study area) |
| `lnds_norm` | float | [0, 1] | Z-score + CDF normalized landslide score (within study area) |
| `H_E` | float | [0, 1] | Hazard Exposure composite: `0.40*ifld + 0.35*hrcn + 0.25*lnds` |
| `geometry` | geometry | — | Census tract polygon boundary |

Plus additional columns inherited from the pygris tract download (e.g., `STATEFP`, `COUNTYFP`, `TRACTCE`, `NAME`, `ALAND`, `AWATER`).

---

### infra_fragility.gpkg

**Location:** `data/processed/infra_fragility.gpkg`
**Produced by:** Notebook 03
**Records:** 2,660
**CRS:** EPSG:2264

Intermediate output containing the Infrastructure Fragility sub-index and its components.

| Column | Type | Range | Description |
|--------|------|-------|-------------|
| `GEOID` | string | 11 chars | Census tract FIPS identifier |
| `tower_count` | int | >= 0 | Number of HIFLD cellular towers within the tract |
| `tower_density_km2` | float | >= 0 | Cellular towers per square kilometer |
| `tower_density_norm` | float | [0, 1] | Z-score + CDF normalized tower density, **inverted** (1.0 = zero towers) |
| `avg_latency_ms` | float | > 0 | Test-count-weighted average broadband latency in milliseconds (Ookla Q3 2024). NaN if no Ookla tiles in tract. |
| `latency_norm` | float | [0, 1] | Z-score + CDF normalized latency (higher = worse). Tracts with no data imputed with study area median. |
| `max_betweenness` | float | [0, 1] | Maximum edge betweenness centrality of any road segment in the tract (higher = more critical single-point-of-failure road) |
| `edge_count` | int | >= 0 | Number of road network edges assigned to the tract (via midpoint-in-polygon) |
| `road_fragility` | float | [0, 1] | Composite: `0.60*norm(max_betweenness) + 0.40*norm_inv(road_density)` |
| `I_F` | float | [0, 1] | Infrastructure Fragility composite: `0.30*tower + 0.30*latency + 0.40*road` |
| `geometry` | geometry | — | Census tract polygon boundary |

---

### acs_demographics.csv

**Location:** `data/processed/acs_demographics.csv`
**Produced by:** Notebook 01
**Records:** 2,672
**Source:** U.S. Census Bureau ACS 5-Year Estimates (2018-2022 vintage, using 2020 Census tract definitions)

Raw demographic counts fetched from the Census API. These are the inputs to the Coping Capacity calculation in Notebook 04.

| Column | Type | ACS Variable | Description |
|--------|------|-------------|-------------|
| `NAME` | string | — | Census tract name (e.g., "Census Tract 1; Buncombe County; North Carolina") |
| `total_population` | float | B01003_001E | Total population of the tract |
| `total_workers` | float | B08141_001E | Total workers (denominator for no-vehicle rate) |
| `total_hh_internet` | float | B28011_001E | Total households with internet access (denominator for mobile-only rate) |
| `no_vehicle` | float | B08141_002E | Workers with no vehicle available for commuting |
| `mobile_only_internet` | float | B28011_008E | Households with cellular data plan only (no fixed broadband) |
| `disability_18_64` | float | C18108_006E | Population aged 18-64 with a disability |
| `disability_65plus` | float | C18108_010E | Population aged 65+ with a disability |
| `median_household_income` | float | B19013_001E | Median household income in dollars. NaN for 48 tracts with suppressed data. |
| `below_poverty_level` | float | B17001_002E | Population with income below poverty level in past 12 months |
| `state` | string | — | State FIPS code (`37`) |
| `county` | string | — | County FIPS code (3-digit) |
| `tract` | string | — | Tract code (6-digit) |
| `GEOID` | string | — | Concatenated state+county+tract (11-digit) |

**Missing data:** The Census API returns `-666666666` for suppressed values; these are converted to `NaN` during acquisition. 48 tracts have missing `median_household_income`.

---

### study_tracts.gpkg

**Location:** `data/processed/study_tracts.gpkg`
**Produced by:** Notebook 01
**Records:** 2,660
**CRS:** EPSG:2264
**Source:** pygris cartographic boundary files (year 2022)

Census tract boundary polygons for all 100 North Carolina counties. This is the spatial backbone that all other data is joined to.

| Column | Type | Description |
|--------|------|-------------|
| `STATEFP` | string | State FIPS code (`37`) |
| `COUNTYFP` | string | County FIPS code (3-digit) |
| `TRACTCE` | string | Census tract code (6-digit) |
| `GEOID` | string | Full tract FIPS (11-digit) |
| `NAME` | string | Tract number (e.g., `1`, `210.02`) |
| `NAMELSAD` | string | Full tract name (e.g., "Census Tract 1") |
| `ALAND` | int | Land area in square meters |
| `AWATER` | int | Water area in square meters |
| `geometry` | geometry | Tract boundary polygon (cartographic, clipped to shoreline) |

---

## Intermediate and Raw Files

### nri_study_area.csv

**Location:** `data/raw/nri_study_area.csv`
**Produced by:** Notebook 01 (filtered from full NRI CSV)
**Records:** 2,660
**Source:** FEMA National Risk Index v1.20 (December 2025)

Filtered extract of the nationwide NRI dataset, containing only the 2,660 census tracts in the North Carolina study area. The full NRI has ~800 columns covering 18 hazard types. Key columns used by HABRI:

| Column | Type | Description |
|--------|------|-------------|
| `TRACTFIPS` | string | Census tract FIPS (11-digit), used as join key to `GEOID` |
| `STCOFIPS` | string | State+county FIPS (5-digit), used for study area filtering |
| `IFLD_RISKS` | float | Inland Flooding — Risk Score (continuous, nationally relative) |
| `HRCN_RISKS` | float | Hurricane — Risk Score |
| `LNDS_RISKS` | float | Landslide — Risk Score |
| `IFLD_RISKR` | string | Inland Flooding — Risk Rating (categorical: Very Low through Very High) |
| `HRCN_RISKR` | string | Hurricane — Risk Rating |
| `LNDS_RISKR` | string | Landslide — Risk Rating |
| `IFLD_EALT` | float | Inland Flooding — Expected Annual Loss, Total ($) |
| `HRCN_EALT` | float | Hurricane — Expected Annual Loss, Total ($) |
| `LNDS_EALT` | float | Landslide — Expected Annual Loss, Total ($) |

**NRI column naming convention:** `{HAZARD}_{METRIC}` where:

| Prefix | Hazard |
|--------|--------|
| `IFLD` | Inland Flooding (renamed from `RFLD` in v1.20) |
| `HRCN` | Hurricane |
| `LNDS` | Landslide |
| `AVLN` | Avalanche |
| `CFLD` | Coastal Flooding |
| `CWAV` | Cold Wave |
| `DRGT` | Drought |
| `ERQK` | Earthquake |
| `HAIL` | Hail |
| `HWAV` | Heat Wave |
| `ISTM` | Ice Storm |
| `LTNG` | Lightning |
| `SWND` | Strong Wind |
| `TRND` | Tornado |
| `TSUN` | Tsunami |
| `VLCN` | Volcanic Activity |
| `WFIR` | Wildfire |
| `WNTW` | Winter Weather |

| Suffix | Metric |
|--------|--------|
| `_RISKS` | Risk Score (continuous, 0-100) |
| `_RISKR` | Risk Rating (categorical text) |
| `_RISKV` | Risk Value (raw) |
| `_EALT` | Expected Annual Loss, Total ($) |
| `_EALS` | Expected Annual Loss, Score |
| `_EALR` | Expected Annual Loss, Rating |
| `_AFREQ` | Annualized Frequency |
| `_EVNTS` | Number of historical events |
| `_EXPB` | Exposure, Building Value ($) |
| `_EXPP` | Exposure, Population |
| `_HLRB` | Historic Loss Ratio, Building |
| `_HLRP` | Historic Loss Ratio, Population |

The full NRI data dictionary is available at `data/raw/NRIDataDictionary.csv`.

**Risk Rating values:** `Very Low`, `Relatively Low`, `Relatively Moderate`, `Relatively High`, `Very High`, `No Rating`, `Not Applicable`, `Insufficient Data`

---

### hifld_cellular_towers.geojson

**Location:** `data/raw/hifld_cellular_towers.geojson`
**Produced by:** Notebook 01
**Records:** 1,275 towers within study area (statewide NC)
**CRS:** EPSG:4326 (WGS84) on disk; reprojected to EPSG:2264 during processing
**Source:** HIFLD Open Data, via ArcGIS REST FeatureServer

Point locations of cellular towers within the study area bounding box. Fetched using paginated queries to the ArcGIS REST API.

Key fields include tower location (geometry), owner/operator information, and structure type. The exact schema varies by the HIFLD dataset version; HABRI uses only the point geometry for spatial join (tower count per tract).

---

### Ookla GeoPackages

**Location:**  
- `data/raw/ookla_fixed_pre_helene.gpkg`  
- `data/raw/ookla_fixed_post_helene.gpkg`  
- `data/raw/ookla_fixed_<VERSION>.gpkg` (e.g., `ookla_fixed_2026_01.gpkg`)
**Produced by:** Notebook 01
**Records:** 123,435 (pre) and 127,192 (post) tiles within study area (statewide NC); versioned current-conditions files depend on input export size
**CRS:** EPSG:4326 (WGS84)
**Source:** Ookla Open Data, AWS S3 public bucket

Speedtest performance tiles for fixed broadband. Each tile represents a ~596m x 596m area (Bing Maps zoom level 16 quadkey). Point geometries are tile centroids.

Versioned current-conditions pipelines also write tract-level outputs:

- `data/processed/ookla_tract_<VERSION>.csv`
- `data/processed/ookla_tract_<VERSION>.gpkg`

| Column | Type | Description |
|--------|------|-------------|
| `tile_x` | float | Tile centroid longitude |
| `tile_y` | float | Tile centroid latitude |
| `avg_d_kbps` | int | Average download speed (kilobits per second) |
| `avg_u_kbps` | int | Average upload speed (kilobits per second) |
| `avg_lat_ms` | float | **Average latency in milliseconds** (primary metric used by HABRI) |
| `avg_lat_down_ms` | float | Average download latency (ms) |
| `avg_lat_up_ms` | float | Average upload latency (ms) |
| `avg_jitter_ms` | float | Average jitter in milliseconds, when available |
| `tests` | int | Number of speedtests in this tile during the quarter |
| `devices` | int | Number of unique devices in this tile during the quarter |
| `quadkey` | string | Bing Maps tile quadkey identifier |
| `geometry` | geometry | Point geometry (tile centroid) |

**Temporal coverage:**

- `pre_helene` = Q3 2024 (July 1 - September 30, 2024) — baseline before Hurricane Helene
- `post_helene` = Q4 2024 (October 1 - December 31, 2024) — period including and following Helene
- `2026_01` = January 2026 current-conditions snapshot

---

### nc_road_network.graphml

**Location:** `data/raw/nc_road_network.graphml`
**Produced by:** Notebook 01
**Source:** OpenStreetMap via OSMnx / Overpass API
**Format:** GraphML (XML-based graph format)

Driveable road network for the study area. Nodes represent intersections or road endpoints; edges represent road segments.

| Attribute | Applies To | Description |
|-----------|-----------|-------------|
| `x`, `y` | nodes | Longitude, latitude (WGS84) |
| `osmid` | nodes/edges | OpenStreetMap element ID |
| `length` | edges | Road segment length in **meters** (always meters, regardless of output CRS) |
| `highway` | edges | OSM road classification (e.g., `primary`, `residential`, `motorway`) |
| `name` | edges | Road name, if available |
| `geometry` | edges | LineString geometry of the road segment |

**Network stats:** 648,424 nodes, 1,528,603 edges (statewide NC). Network type is `drive` (excludes pedestrian/cycling-only paths).

---

### ioda_asn_timeseries.csv

**Location:** `data/raw/ioda_asn_timeseries.csv`
**Produced by:** Notebook 01
**Source:** Georgia Tech IODA API v2

Time-series outage data for Western NC internet service providers during the Hurricane Helene period.

| Column | Type | Description |
|--------|------|-------------|
| `datetime` | datetime | Timestamp of observation (UTC) |
| `value` | float | Signal value: number of visible /24 prefixes (BGP) or responsive /24 blocks (ping) |
| `provider` | string | ISP name (e.g., "Morris Broadband", "Skyline Telephone") |
| `asn` | int | Autonomous System Number (e.g., 53488 for Morris Broadband) |
| `datasource` | string | `bgp` (BGP prefix visibility) or `ping-slash24` (active probing) |

**ASNs tracked:**

| Provider | ASN | Primary Service Area |
|----------|-----|---------------------|
| Morris Broadband | 53488 | Henderson County |
| Skyline Telephone | 23118 | Mitchell, Avery, Watauga counties |
| Wilkes Communications | 22191 | Wilkes, Ashe counties |

**Time window:** September 15, 2024 through October 7, 2024 (Helene landfall: September 27, 2024 ~06:00 UTC). 28,512 total rows across 3 providers and 2 datasources.

---

## Visualization Outputs

All stored in `data/processed/`. These are generated by Notebook 04 and are not machine-readable data.

| File | Format | Description |
|------|--------|-------------|
| `habri_4panel.png` | PNG (300 DPI) | Four-panel map: H_E, I_F, C_C, and HABRI composite with Natural Breaks classification |
| `habri_4panel.pdf` | PDF | Vector version of the four-panel map for print/publication |
| `habri_4panel_preview.jpg` | JPEG | Low-resolution preview of the four-panel map |
| `habri_profiles.png` | PNG (300 DPI) | Map of k-means vulnerability profiles (Power-Dependent, Transport-Fragile, Dual-Risk) |
| `habri_profiles.pdf` | PDF | Vector version of the profiles map for print/publication |
| `habri_profiles_preview.jpg` | JPEG | Low-resolution preview of the profiles map |
| `habri_validation_2026_01.png` | PNG (200 DPI) | January 2026 current-conditions validation scatter plots and summary statistics |
| `ioda_outage_timeseries.png` | PNG (200 DPI) | 3x2 panel: BGP and ping time-series for 3 WNC ISPs during Helene |
| `fcc_county_validation.png` | PNG (200 DPI) | HABRI vs FCC cell site outage % by county, plus sub-index bar chart |
| `habri_map.html` | HTML | Interactive Folium map with HABRI choropleth, risk profiles, and tower overlays |

### Validation tables (versioned current-conditions)

| File | Type | Description |
|------|------|-------------|
| `habri_validation_2026_01.csv` | CSV | Joined baseline and January 2026 tract metrics with delta and percentage-change columns |
| `habri_validation_2026_01_summary.csv` | CSV | Spearman correlation and median summaries for January 2026 scenario |

---

## Common Identifiers

All HABRI data files use a consistent tract identification scheme:

| Name | Format | Example | Description |
|------|--------|---------|-------------|
| `GEOID` | 11-digit string | `37021000100` | Standard Census tract FIPS. Used in all processed outputs. |
| `TRACTFIPS` | 11-digit string | `37021000100` | Same value as GEOID. Used in the NRI source data. |
| `STCOFIPS` | 5-digit string | `37021` | State+county FIPS. Used for county-level filtering. |

**GEOID structure:** `SS` + `CCC` + `TTTTTT` where SS = state FIPS (37 = NC), CCC = county FIPS, TTTTTT = tract code.

The study area covers all 100 North Carolina counties. The full county FIPS mapping is in `src/config.py` (`COUNTY_FIPS` dict). Example entries:

| County | County FIPS | Full STCOFIPS |
|--------|-----------|---------------|
| Buncombe | 021 | 37021 |
| Mecklenburg | 119 | 37119 |
| Wake | 183 | 37183 |
| Yancey | 199 | 37199 |

---

## Value Conventions

| Convention | Meaning |
|------------|---------|
| All normalized scores in [0, 1] | 0 = lowest risk / best condition; 1 = highest risk / worst condition |
| Z-score + CDF normalization | `norm(x) = Φ((x - mean) / std)` — maps study area mean to 0.5, bounded [0, 1] |
| "Inverted" normalization | Applied when high raw values indicate *lower* risk (e.g., more towers, higher income). Formula: `Φ(-z)` |
| NaN / missing values | Uniformly imputed with study area median via `impute_with_median()` |
| Constant series | If all tracts have the same value for an indicator, normalized score is set to 0.5 (neutral) |
| Census sentinel `-666666666` | Converted to NaN during data acquisition |
| CRS for all spatial files | EPSG:2264 (NAD83 / North Carolina, US survey feet) |
| Area conversion | 1 km^2 = 10,763,910.4 sq ft (EPSG:2264 native units) |
| Road segment length | Always in meters (OSMnx convention), regardless of CRS |
