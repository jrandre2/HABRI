# HABRI Technical Methodology

This document provides a complete specification of the computational methods, formulas, statistical techniques, and design decisions used to produce the Hazard-Adjusted Broadband Reliability Index.

---

## Table of Contents

- [1. Index Architecture](#1-index-architecture)
- [2. Hazard Exposure (H_E)](#2-hazard-exposure-h_e)
- [3. Infrastructure Fragility (I_F)](#3-infrastructure-fragility-i_f)
- [4. Coping Capacity Deficit (C_C)](#4-coping-capacity-deficit-c_c)
- [5. Composite Index Assembly](#5-composite-index-assembly)
- [6. Normalization](#6-normalization)
- [7. Vulnerability Profiling](#7-vulnerability-profiling)
- [8. Validation](#8-validation)
- [9. Sensitivity Analysis](#9-sensitivity-analysis)
- [10. Spatial Processing Details](#10-spatial-processing-details)
- [11. Missing Data Treatment](#11-missing-data-treatment)
- [12. Design Decisions and Rationale](#12-design-decisions-and-rationale)

---

## 1. Index Architecture

HABRI is a weighted linear composite of three sub-indices:

```
HABRI = W_H * H_E + W_I * I_F + W_C * C_C
```

Where:

| Symbol | Sub-Index | Weight | Description |
|--------|-----------|--------|-------------|
| H_E | Hazard Exposure | W_H = 0.40 | Environmental threat level |
| I_F | Infrastructure Fragility | W_I = 0.35 | Physical vulnerability of communications infrastructure |
| C_C | Coping Capacity Deficit | W_C = 0.25 | Community-level inability to cope with outages |

All sub-indices and the composite are bounded to [0, 1], where 1 = highest risk. The weights sum to 1.0.

### Unit of Analysis

The census tract (2020 definitions, as used by the ACS 2022 5-year estimates). The study area contains 2,660 tracts across all 100 North Carolina counties.

---

## 2. Hazard Exposure (H_E)

**Source:** FEMA National Risk Index v1.20 (December 2025), census tract level.

**Input columns:** `IFLD_RISKS` (Inland Flooding Risk Score), `HRCN_RISKS` (Hurricane Risk Score), `LNDS_RISKS` (Landslide Risk Score).

### Formula

```
H_E = 0.40 * norm(IFLD_RISKS) + 0.35 * norm(HRCN_RISKS) + 0.25 * norm(LNDS_RISKS)
```

### Sub-component weights

| Hazard | Weight | Rationale |
|--------|--------|-----------|
| Inland Flooding | 0.40 | Primary driver of infrastructure destruction in WNC mountain floods (e.g., Helene) |
| Hurricane | 0.35 | Wind and precipitation cause tower damage, power outages, and widespread debris |
| Landslide | 0.25 | Severs roads and buried fiber routes; common on WNC steep slopes |

### Processing steps

1. Load nationwide NRI CSV; filter to study area using 5-digit STCOFIPS
2. Check for missing ratings (`No Rating`, `Not Applicable`, `Insufficient Data`); set corresponding numeric scores to NaN
3. Impute remaining NaN risk scores with the study area median (via `impute_with_median()`)
4. Z-score normalize each score within the study area's 2,660 tracts, then map to [0, 1] via the standard normal CDF
5. Apply weighted sum

### NRI version note

NRI v1.20 (December 2025) renamed "Riverine Flooding" to "Inland Flooding". Column prefix changed from `RFLD` to `IFLD`. The project uses `IFLD` throughout. The NRI risk scores are nationally relative (computed across all ~73,000 US census tracts). Normalizing within the study area re-ranks tracts locally so that intra-state variation drives the index.

---

## 3. Infrastructure Fragility (I_F)

### Formula

```
I_F = 0.30 * tower_density_norm + 0.30 * latency_norm + 0.40 * road_fragility
```

### 3.1 Tower Density (weight: 0.30)

**Source:** HIFLD Cellular Towers, ArcGIS REST FeatureServer.

**Method:**

1. Query tower locations within the study area bounding box via paginated ArcGIS REST API calls (2000 records per page)
2. Reproject towers to EPSG:2264
3. Spatial join (point-in-polygon) to assign each tower to its census tract
4. Compute density: `tower_density_km2 = tower_count / (tract_area_sqft / 10,763,910.4)`
5. Z-score normalize with **inversion**: `tower_density_norm = z_score_normalize(density, invert=True)`

Inversion means that tracts with **more** towers get **lower** fragility scores (more redundancy).

**Missing data:** Tracts with zero towers receive NaN density, then imputed with the study area median via `impute_with_median()`.

### 3.2 Broadband Latency (weight: 0.30)

**Source:** Ookla Speedtest Open Data, fixed broadband tiles.  
For the baseline layer, Q3 2024 (pre-Helene) tiles are used.

**Metric:** `avg_lat_ms` — average round-trip latency in milliseconds, weighted by test count per tile.

**Method:**

1. Download Ookla parquet from AWS S3; filter to study area bounding box using tile centroid coordinates (`tile_x`, `tile_y`)
2. Create point geometries from tile centroids; reproject to EPSG:2264
3. Spatial join to tracts
4. Compute test-count-weighted average latency per tract:
   ```
   avg_latency_ms = sum(avg_lat_ms_i * tests_i) / sum(tests_i)
   ```
5. Z-score normalize (no inversion — higher latency = higher fragility)

**Missing data:** Tracts with no Ookla tiles receive NaN latency, then imputed with the study area median via `impute_with_median()`.

**Why latency instead of throughput:** Latency is more sensitive to backhaul congestion and infrastructure degradation than download speed, which can be artificially high on last-mile connections even when backbone connectivity is stressed.

### 3.3 Road Network Fragility (weight: 0.40)

**Source:** OpenStreetMap via OSMnx, network type = `drive`.

Road fragility is itself a composite of two metrics:

```
road_fragility = 0.60 * norm(max_betweenness) + 0.40 * norm_inv(road_density)
```

#### 3.3.1 Edge Betweenness Centrality

**Concept:** Betweenness centrality measures how often a road segment lies on the shortest path between pairs of nodes. A road with high betweenness is a critical chokepoint — if it is destroyed, large portions of the network become disconnected.

**Method:**

1. Load the GraphML road network (648,424 nodes, 1,528,603 edges for statewide NC)
2. Compute approximate edge betweenness centrality with `k=500` sampled source nodes (NetworkX `edge_betweenness_centrality(G, weight="length", k=500)`)
3. Convert edges to a GeoDataFrame; compute edge midpoints via `interpolate(0.5, normalized=True)` and spatial join to tracts using `within` predicate (each edge assigned to exactly one tract)
4. Aggregate per tract: use `max_betweenness` (the single highest-centrality road segment)
5. Z-score normalize (higher centrality = higher fragility)

**Why k=500 approximation:** Exact betweenness centrality on a 648,424-node statewide graph has O(VE) complexity and would take days. The k=500 approximation samples 500 random source nodes and produces stable rankings in approximately 1-2 hours for the statewide graph. Literature suggests k >= 200 yields good approximations for networks of this scale.

**Why midpoint assignment instead of intersects:** When road edges cross tract boundaries, using an `intersects` spatial join assigns the same edge to multiple tracts — double-counting edges and inflating metrics for border tracts. Computing the midpoint via `interpolate(0.5, normalized=True)` (guaranteed to lie on the line geometry) and joining with `within` assigns each edge to exactly one tract.

**Why max instead of mean:** The maximum betweenness identifies the single most critical road segment (SPOF). Mean betweenness would dilute this signal across many low-centrality residential streets.

#### 3.3.2 Road Density (inverted)

```
road_density = edge_count / (total_road_length_m / 1000)
```

This measures route redundancy: more edges per km of road means more alternative paths. Z-score normalized with inversion (low density = high fragility).

---

## 4. Coping Capacity Deficit (C_C)

**Source:** U.S. Census Bureau ACS 5-Year Estimates (2018-2022), tract level.

### Formula

```
C_C = 0.20 * no_vehicle_vuln + 0.20 * mobile_only_vuln + 0.20 * disability_vuln
    + 0.20 * income_vuln + 0.20 * poverty_vuln
```

### Indicator computation

| Indicator | Formula | Normalization |
|-----------|---------|---------------|
| `no_vehicle_vuln` | `no_vehicle / total_workers` | Direct (higher % = more vulnerable) |
| `mobile_only_vuln` | `mobile_only_internet / total_hh_internet` | Direct |
| `disability_vuln` | `(disability_18_64 + disability_65plus) / total_population` | Direct |
| `income_vuln` | `median_household_income` | **Inverted** (lower income = higher vulnerability) |
| `poverty_vuln` | `below_poverty_level / total_population` | Direct |

All percentages are z-score normalized (then mapped to [0, 1] via CDF) within the study area after computation.

### ACS variable mapping

| Human Name | ACS Variable Code | Table |
|------------|------------------|-------|
| Total population | B01003_001E | Total Population |
| Total workers | B08141_001E | Means of Transportation to Work by Vehicles Available |
| No vehicle | B08141_002E | Workers with no vehicle available |
| Total HH internet | B28011_001E | Internet Subscriptions in Household |
| Mobile-only internet | B28011_008E | Cellular data plan with no other type |
| Disability 18-64 | C18108_006E | Age by Disability Status (18-64, with disability) |
| Disability 65+ | C18108_010E | Age by Disability Status (65+, with disability) |
| Median household income | B19013_001E | Median Household Income in Past 12 Months |
| Below poverty level | B17001_002E | Poverty Status in Past 12 Months |

### Missing data treatment

- Division by zero (tracts with 0 workers or 0 households): resulting NaN percentages are filled with the study area median for that indicator
- Census suppressed values (sentinel `-666666666`): converted to NaN, then filled with study area median
- 48 tracts have missing `median_household_income`; filled with study area median

---

## 5. Composite Index Assembly

The final composite is computed in Notebook 04 by:

1. Loading the three intermediate GeoPackages (`hazard_scores.gpkg`, `infra_fragility.gpkg`)
2. Loading ACS demographics and computing C_C inline
3. Merging all three sub-indices on `GEOID`
4. Computing: `HABRI = 0.40 * H_E + 0.35 * I_F + 0.25 * C_C`
5. Classifying into quintiles using `pd.qcut(HABRI, q=5, duplicates="drop")` with labels `Very Low` through `Very High`  
If duplicate bins are removed, the label set is shortened to match available bins.

---

## 6. Normalization

All indicators use **z-score normalization** followed by mapping to [0, 1] via the **standard normal CDF**:

```
z = (x - mean(x)) / std(x)
norm(x) = Φ(z)         # standard normal CDF
```

For inverted indicators (where high raw values indicate lower risk):

```
norm_inv(x) = Φ(-z)    # equivalent to 1 - Φ(z)
```

**Edge case:** If all values in a series are identical (`std == 0`), the normalized value is set to 0.5 (neutral score).

### Why z-score + CDF instead of min-max

- **Outlier robustness:** With 2,660 tracts statewide, extreme outliers in a few tracts (e.g., very high latency in one rural tract) would compress the rest of the distribution near 0 under min-max. Z-score normalization maps the study area mean to 0.5, spreading values more evenly.
- **Bounded [0, 1]:** The CDF transform guarantees scores stay in [0, 1], and the weighted sum of [0, 1] scores is itself bounded to [0, 1].
- **Interpretable midpoint:** A score of 0.5 means "average for North Carolina" — an intuitive reference point.
- **Distribution preservation:** Unlike percentile rank (which forces uniformity), the CDF preserves the relative spacing of values while bounding them.

### Important implication

Scores are **relative to the study area**. A tract with H_E = 0.95 has the highest hazard exposure *among the 2,660 NC tracts*, not nationally. Re-running HABRI for a different region will produce a different normalization baseline.

---

## 7. Vulnerability Profiling

Tracts are classified into three vulnerability profiles using k-means clustering.

### Feature set

Six normalized component scores are used as clustering features:

**Power-dependence axis:**

- `no_vehicle_vuln` — transportation isolation
- `disability_vuln` — population with limited adaptive capacity
- `mobile_only_vuln` — dependence on cellular network
- `tower_density_norm` — scarcity of cellular infrastructure

**Transport-fragility axis:**

- `road_fragility` — road network chokepoints and low redundancy
- `latency_norm` — poor broadband performance

### Method

1. Fill any NaN in feature columns with 0.5 (neutral)
2. Standardize features using `StandardScaler` (zero mean, unit variance) — necessary because k-means is distance-based
3. Run `KMeans(n_clusters=3, random_state=42, n_init=10)`
4. Compute cluster centroids in the **standardized** (z-scored) feature space
5. Compute per-cluster mean z-scores on each axis:
   - `power_z = mean(z_no_vehicle_vuln, z_disability_vuln, z_mobile_only_vuln, z_tower_density_norm)`
   - `transport_z = mean(z_road_fragility, z_latency_norm)`
6. Assign labels based on which axis z-score exceeds a 0.5 threshold:
   - Both above 0.5 → **Dual-Risk**
   - Power z-score > transport z-score → **Power-Dependent**
   - Transport z-score > power z-score → **Transport-Fragile**
   - Tie-breaking: if z-scores are equal, the cluster with a higher combined score is labeled **Dual-Risk**

### Why k=3

Three clusters were chosen to produce actionable, distinct profiles that map to different investment strategies. Empirically, k=3 produces well-separated clusters on the two conceptual axes. Higher k values fragment the profiles into less interpretable subgroups.

---

## 8. Validation

HABRI is validated against three independent data sources from the Hurricane Helene event (September-October 2024).

### 8.1 Ookla Latency Degradation (tract-level)

**Hypothesis:** Tracts with higher HABRI scores should exhibit greater broadband performance degradation during Helene.

**Method:**

1. Compute per-tract test-count-weighted average latency for Q3 2024 (pre-Helene) and Q4 2024 (post-Helene)
2. Compute degradation metrics:
   - Percentage change: `(lat_post - lat_pre) / lat_pre * 100`
   - Absolute change: `lat_post - lat_pre` (in ms)
3. Merge with HABRI scores on GEOID
4. Compute Spearman rank correlation between HABRI and degradation

**Spearman correlation** is used instead of Pearson because:

- It is robust to non-linear monotonic relationships
- It is less sensitive to outliers
- The hypothesis is about rank ordering ("higher HABRI → worse degradation"), not linear proportionality

### 8.2 IODA ASN-Level Outages (narrative)

**Source:** Georgia Tech IODA API v2, BGP and active probing (ping-slash24) datasources.

**Method:**

1. Query time-series data for 3 WNC ISP ASNs over a ~3-week window around Helene
2. Compute pre-storm baseline (median signal value before landfall)
3. Normalize post-storm values as % of baseline
4. Compute outage severity metrics: hours at zero, hours below 50% of baseline, recovery percentage
5. Visual comparison with HABRI geographic patterns

This validation is **qualitative/narrative** — it demonstrates that real outages occurred in the areas and providers that HABRI would predict are at risk, but does not produce a single correlation statistic.

### 8.3 FCC Cell Site Outages (county-level, statewide)

**Source:** FCC Communications Status Reports and DIRS (Disaster Information Reporting System) activation data for Hurricane Helene (September-October 2024).

**Method:**

1. Collect FCC-reported cell site outage percentages for the 21 NC counties in the Helene DIRS activation area
2. Assign 0% outage to the remaining 79 NC counties not in the DIRS activation area (no reported outages)
3. Compute county-average HABRI scores by aggregating tract-level scores within each county
4. Compute Spearman correlation between county-mean HABRI and % cell sites out (n=100 counties)

**Statistical power:** With n=100 counties (21 with observed outages, 79 at 0%), this provides a meaningful correlation test — substantially more statistical power than the original 6-county analysis. DIRS counties with high outages should cluster among counties with high HABRI scores.

### 8.4 Current-conditions layer (January 2026)

The HABRI baseline is frozen at Q3 2024 and is not overwritten.  
January 2026 is processed as a separate, versioned scenario (default tag `2026_01`) to support refresh and comparison.

The current-conditions workflow:

1. Reads January 2026 fixed-network export and writes versioned tile/tract outputs (`ookla_fixed_2026_01.gpkg`, `ookla_tract_2026_01.csv/.gpkg`)
2. Merges with tract geometry and reuses the published baseline `habri_composite.gpkg` as source of truth
3. Rebuilds infrastructure fragility with `latency_norm_2026_01`, then recomputes `I_F` and `HABRI`
4. Writes `infra_fragility_current_2026_01.gpkg` and `habri_current_2026_01.csv/.gpkg`
5. Builds validation artifacts (`habri_validation_2026_01.csv`, `habri_validation_2026_01_summary.csv`, `habri_validation_2026_01.png`) as deltas against baseline latency

The scripts support optional row filtering by measurement quality:

- `--max-location-accuracy-m` drops records where `attr_location_accuracy_m` is missing or above the threshold.

---

## 9. Sensitivity Analysis

Five weight configurations are tested to assess robustness of tract rankings:

| Configuration | W_H (Hazard) | W_I (Infra) | W_C (Coping) |
|---------------|:---:|:---:|:---:|
| Default | 0.40 | 0.35 | 0.25 |
| Equal | 0.33 | 0.33 | 0.34 |
| Hazard-dominant | 0.50 | 0.30 | 0.20 |
| Infrastructure-dominant | 0.25 | 0.50 | 0.25 |
| Community-dominant | 0.25 | 0.25 | 0.50 |

For each configuration, HABRI is recomputed for all 2,660 tracts, and **pairwise Spearman rank correlations** are calculated between all configuration pairs. If the minimum off-diagonal correlation exceeds 0.85, the rankings are considered robust to weight choice.

---

## 10. Spatial Processing Details

### Coordinate Reference System

All spatial analysis uses **EPSG:2264** (NAD83 / North Carolina, US survey feet). This is a projected CRS optimized for North Carolina that provides accurate distance and area measurements.

**Area conversion:** Tract areas are computed in native CRS units (square US survey feet) and converted: `area_km2 = area_sqft / 10,763,910.4`

### Spatial joins

Three types of spatial joins are used:

| Join Type | Predicate | Used For |
|-----------|-----------|----------|
| Point-in-polygon | `within` | Towers → tracts, Ookla tiles → tracts, Road edge midpoints → tracts |
| Polygon boundary | `union_all()` | Dissolving tracts into study area boundary for OSMnx query |

**Road edge assignment:** Road edges are converted to midpoints via `interpolate(0.5, normalized=True)` before the spatial join. This avoids double-counting edges that cross tract boundaries (see Section 3.3.1).

All spatial joins ensure both GeoDataFrames are in EPSG:2264 before joining (via `ensure_crs()`).

### Bounding box filtering

Large datasets (Ookla, HIFLD) are pre-filtered to the study area bounding box in WGS84 before reprojection, to minimize memory usage.

---

## 11. Missing Data Treatment

| Data Gap | Treatment | Justification |
|----------|-----------|---------------|
| NRI risk score = NaN or "Insufficient Data" | Set to NaN, impute with study area median | Absence of data ≠ absence of risk; median = average-risk assumption |
| Tract with no HIFLD towers | Impute with study area median | Uniform strategy; avoids biasing toward worst-case |
| Tract with no Ookla tiles | Impute with study area median | Uniform strategy; avoids biasing toward worst-case |
| Tract with no road edges | Impute with study area median | Uniform strategy across all sub-indices |
| ACS percentage yields NaN (0/0 division) | Impute with study area median | Avoids bias from tracts with very small denominators |
| ACS median income suppressed (`-666666666`) | Convert to NaN, impute with median | Affects a small number of tracts |
| Tract not matched in NRI data | Impute H_E with study area median | 0 tracts affected in practice (all NC tracts matched) |

All imputation is performed via the `impute_with_median()` utility function, which logs the number of imputed values and affected GEOIDs for auditability.

---

## 12. Design Decisions and Rationale

### Why census tracts (not block groups or counties)?

Census tracts (~1,200-8,000 people) balance spatial resolution with data availability. Block groups are too small (many would have zero towers or zero Ookla tiles). Counties are too coarse (Buncombe County alone has ~60 tracts with very different risk profiles). With 2,660 tracts statewide, the dataset is large enough for robust statistical analysis while remaining computationally tractable.

### Why latency instead of download speed or jitter?

Download speed was considered but is less sensitive to backhaul degradation — a well-provisioned last-mile connection can report high throughput even when the backbone is congested.  
Latency reflects end-to-end path quality including backhaul.

Ookla jitter is treated as optional: when present in source exports, an optional `avg_jitter_ms` path is retained; when absent, the pipeline fills missing jitter with `NaN` and continues.

### Why pre-Helene Ookla data for the index (not post)?

The index is designed to predict risk *before* an event, using baseline conditions. Post-event data is used for validation or separate scenario runs, while the published baseline remains fixed.

### Why k-means for profiling (not hierarchical or DBSCAN)?

K-means with k=3 directly maps to the three conceptual profile types. The goal is interpretable, actionable categories, not discovering unknown cluster structure. K-means is simple, well-understood, and produces convex clusters that are easy to explain to stakeholders.

### Why approximate betweenness centrality?

Exact edge betweenness centrality on the statewide graph (648,424 nodes, 1,528,603 edges) has O(V*E) time complexity — roughly 1.7 trillion operations, which would take days. The k=500 random-node approximation provides stable rankings in approximately 1-2 hours and is standard practice in network analysis literature.

### Why equal weights for Coping Capacity indicators?

The five ACS indicators capture distinct, non-overlapping dimensions of vulnerability. Without strong empirical evidence that one dimension matters more than another for communications coping specifically, equal weights (0.20 each) are the most defensible choice. The sensitivity analysis confirms that the overall index rankings are robust to weight perturbation.

### Why GeoPackage format (not Shapefile or GeoParquet)?

GeoPackage is an open OGC standard that supports long field names (Shapefiles truncate to 10 characters), multiple geometry types, and is widely supported in QGIS, ArcGIS, and Python. GeoParquet was not used due to a compatibility issue between pandas 2.3 and pyarrow 16 (ndim error when round-tripping geometry columns).
