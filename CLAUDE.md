# HABRI — Claude Code Instructions

Hazard-Adjusted Broadband Reliability Index — North Carolina (validated baseline) + Tennessee (statewide extension) + shared NC+TN standardized layer.
NC: composite outage-risk score for all 2,660 NC census tracts across 100 counties.
TN: full statewide index for all 1,701 TN census tracts across 95 counties.
Formula: `HABRI = 0.40·H_E + 0.35·I_F + 0.25·C_C` (range [0,1]; 1 = highest risk)
Shared cross-state map: `data/processed/habri_nc_tn_standardized.*` re-standardizes the completed NC and TN baselines onto one common scale.

Related project: `/Volumes/T9/Projects/Harris County Modeling Future Damage`

---

## Pipeline Status

| Notebook / Script | Purpose | Status |
|---|---|---|
| `notebooks/01_data_acquisition.ipynb` | Download NRI, Ookla, HIFLD towers, OSMnx road network, ACS, IODA | DONE |
| `notebooks/02_hazard_processing.ipynb` | Compute H_E sub-index (flood/hurricane/landslide NRI scores) | DONE |
| `notebooks/03_infra_proxy_generation.ipynb` | Compute I_F sub-index (tower density, latency, road centrality) | DONE |
| `notebooks/04_index_calculation.ipynb` | Assemble HABRI, k-means profiles, validate, visualize | DONE |
| `scripts/build_habri_current_2026_01.py` | Jan 2026 current-conditions HABRI (replaces latency only) | DONE |
| `scripts/build_ookla_jan_2026_validation.py` | Baseline vs Jan 2026 comparison plots | DONE |
| `scripts/update_ookla_quarterly.py` | Automated S3 quarterly refresh | DONE — quarterly NC files through Q4 2025 generated |
| `scripts/fetch_power_grid.py` | HIFLD transmission line density → power_grid_norm | DONE |
| `scripts/fetch_fcc_bdc.py` | FCC BDC wired availability → p_wired per tract | DONE — Apr 2026 (programmatic download) |
| `scripts/integrate_power_grid.py` | Integrate power_grid_norm + adaptive BDC weights, rebuild baseline | DONE — Apr 2026 |
| `scripts/validate_road_proxy_mobile.py` | Fixed vs. mobile latency validation of road proxy | DONE — Apr 2026 |
| `scripts/plot_time_series.py` | Multi-quarter HABRI trend figures (WNC recovery) | DONE |
| `scripts/plot_habri_maps.py` | Regenerate all static and interactive HABRI maps | DONE — Apr 2026 |
| `scripts/build_site.py` | GitHub Pages static site | DONE |
| `scripts/build_habri_tn.py` | Full HABRI pipeline for Tennessee (95 counties, 1,701 tracts) | DONE — Apr 2026 |
| `scripts/compare_helene_nc_tn.py` | Cross-state WNC vs. Eastern TN Helene comparison figures | DONE — Apr 2026 |
| `scripts/build_habri_nc_tn_combined.py` | Shared-scale NC+TN standardized layer + maps | DONE — Apr 2026 |
| `app.py` | Streamlit dashboard | DONE — supports NC baseline and NC+TN standardized layer |

**Quarterly time series (Q3 2024 – Q4 2025):** Complete. All 6 quarters processed.
Q4 2024 post-Helene file copied from `ookla_fixed_post_helene.gpkg` to `ookla_fixed_2024_q4.gpkg`.

**Power grid integrated (Apr 2026):** `power_grid_norm` incorporated into I_F via
`scripts/integrate_power_grid.py`. New 4-component I_F weights: tower=0.25, latency=0.25,
road=0.30, power=0.20. Baseline files updated; all quarterly outputs regenerated.

**FCC BDC adaptive weighting (Apr 2026):**
Adaptive per-tract I_F weights are active for the NC baseline/current-conditions path.
Road/tower weights interpolate between wired-endpoint (road=0.40, tower=0.15) and
wireless-endpoint (road=0.15, tower=0.40) based on each tract's `p_wired` from FCC BDC
availability data. Latency and power_grid weights remain constant (0.25 and 0.20).
Existing NC baseline and quarterly outputs in `data/processed/` already reflect this.
To refresh from a newer BDC bulk download:

1. Download NC Fixed Broadband BDC CSV from the [FCC BDC bulk download page](https://broadbandmap.fcc.gov/data-download/bulk-download)
2. Place at `data/raw/bdc_nc_fixed_availability.csv`
3. Run `python scripts/fetch_fcc_bdc.py`
4. Re-run `python scripts/integrate_power_grid.py --regen-quarterly`

**Road proxy empirically validated (Apr 2026):** Fixed vs. mobile Ookla comparison shows
road_fragility predicts post-Helene fixed broadband degradation (WNC ρ = −0.287, p<0.001)
but not cellular degradation (ρ = +0.078, p=0.38), supporting road ROW colocation assumption.
See `data/processed/road_proxy_validation.csv` and `road_proxy_validation.png`.

---

## Non-Negotiable Technical Conventions

1. **CRS by state:**
   - NC: EPSG:2264 (NAD83 / NC State Plane, US survey feet). Area: `geometry.area / 10_763_910.4`
   - TN: EPSG:2274 (NAD83 / Tennessee, US survey feet). Same conversion factor.
   All outputs saved in WGS84 (EPSG:4326) for portability.
   Use `ensure_crs(gdf, cfg.crs_project)` with the relevant `RegionConfig`.

2. **Never use `pd.read_parquet()` for Ookla S3 parquets.**
   pandas 2.3 + pyarrow 16 has an ndim compatibility bug on chunked reads.
   Use `pq.read_table(path, filesystem=fs, columns=[...])` then convert column-by-column
   via `.to_pylist()`. Local Ookla data is saved as `.gpkg`, not `.parquet`.

3. **Ookla v2024+: use `tile_x` / `tile_y` centroid columns, not WKT polygons.**
   The WKT tile geometry column was removed in the 2024 S3 format.

4. **Road edge → tract assignment: midpoint interpolation + `predicate="within"`.**
   `edge.interpolate(0.5, normalized=True)` finds the midpoint; `predicate="within"`
   prevents double-counting edges that cross tract boundaries.

5. **Normalization: z-score → standard normal CDF, not min-max.**
   `z_score_normalize()` in `src/utils.py`. Maps mean→0.5, bounded [0,1], outlier-robust.
   For indicators where high values = low risk (tower density, road density, income):
   pass `invert=True` to negate z before CDF. NC and TN baseline files are normalized
   within each state; `habri_nc_tn_standardized.*` performs a second-pass shared
   standardization across the union of both baselines.

6. **Missing data: uniform median imputation via `impute_with_median()`.**
   All imputed GEOIDs are logged. Never silently drop tracts.

7. **Betweenness centrality: k=500 approximation only.**
   Full exact centrality on the statewide graph (648K nodes, 1.5M edges) is infeasible.
   k=500 takes ~30-40 min. Do not attempt exact computation.

8. **OSMnx on external volumes: set cache folder to absolute path.**
   `ox.settings.cache_folder = str(PROJECT_ROOT / "cache")` — relative `cache/` fails
   when the working directory is not the project root.

9. **Census API: use `fetch_acs_state_tracts()`, not per-county loops.**
   Single wildcard call (`county=*`) for the whole state. Sentinel -666666666 = NaN.

10. **pygris year=2022 for tract boundaries.**
    Matches ACS 2022 5-year estimates; both use 2020 Census tract definitions.

---

## Key File Paths

```
# Main outputs — NC
data/processed/habri_composite.csv / .gpkg        # 2,660 tracts × 16 score columns (BASELINE)
data/processed/habri_current_{tag}.csv / .gpkg    # versioned quarterly updates
data/processed/hazard_scores.gpkg                 # H_E sub-index + components
data/processed/infra_fragility.gpkg               # I_F sub-index + components (4-component)
data/processed/acs_demographics.csv               # ACS 2022 tract-level covariates
data/processed/fcc_bdc_wired_fraction.csv         # FCC BDC p_wired per tract (adaptive weights)

# Main outputs — Tennessee
data/processed/habri_tn_composite.csv / .gpkg     # 1,701 TN tracts × HABRI + sub-indices
data/processed/hazard_tn_scores.gpkg              # TN H_E sub-index
data/processed/infra_tn_towers.csv                # TN tower-density component
data/processed/road_tn_fragility.csv              # TN road fragility component
data/processed/power_tn_grid.csv                  # TN power-grid component
data/processed/acs_tn_demographics.csv            # TN ACS 2022 covariates

# Main outputs — Combined NC + TN
data/processed/habri_nc_tn_standardized.csv / .gpkg   # shared-scale cross-state layer
data/processed/habri_nc_tn_standardized.html          # interactive combined map
data/processed/habri_nc_tn_standardized.png           # single-panel combined HABRI map
data/processed/habri_nc_tn_standardized_4panel.png    # four-panel combined sub-index map

# Raw data — shared
data/raw/NRI_Table_CensusTracts.csv               # FEMA NRI v1.20 (all states incl. TN, 605 MB)

# Raw data — NC
data/raw/nc_road_network.graphml                  # OSMnx statewide NC road graph (866 MB)
data/raw/ookla_fixed_pre_helene.gpkg              # NC Q3 2024 Ookla baseline
data/raw/ookla_fixed_post_helene.gpkg             # NC Q4 2024 Ookla (post-Helene)
data/raw/ookla_fixed_{tag}.gpkg                   # NC quarterly versioned Ookla tiles
data/raw/hifld_cellular_towers.geojson            # 1,275 NC cell towers
data/raw/hifld_transmission_lines_nc.geojson      # 8,263 NC transmission line segments
data/raw/ioda_asn_timeseries.csv                  # Helene outage telemetry (3 ISPs, 28,512 rows)

# Raw data — Tennessee
data/raw/tn_road_network.graphml                  # OSMnx statewide TN road graph (to be generated)
data/raw/ookla_tn_fixed_q3_2024.gpkg              # TN Q3 2024 Ookla baseline (pre-Helene)
data/raw/ookla_tn_fixed_q4_2024.gpkg              # TN Q4 2024 Ookla (post-Helene)

# Visualizations — NC
data/processed/habri_statewide_4panel.png / .pdf  # statewide 4-panel choropleth (all 100 counties, 2,660 tracts)
data/processed/habri_4panel.png / .pdf            # Land of the Sky 4-panel detail (Buncombe/Henderson/Madison/Transylvania)
data/processed/habri_profiles.png / .pdf          # Land of the Sky vulnerability profile map
data/processed/habri_map.html                     # interactive Folium web map (statewide, 21 MB)
data/processed/ioda_outage_timeseries.png         # Morris Broadband BGP blackout
data/processed/fcc_county_validation.png          # FCC DIRS county correlation plot

# Visualizations — Tennessee
data/processed/habri_tn_statewide_4panel.png      # TN statewide 4-panel (generated by build_habri_tn.py)
data/processed/habri_tn_profiles.png              # Eastern TN vulnerability profile map
data/processed/habri_tn_helene_validation.png     # ETN HABRI vs. Q3→Q4 latency delta scatter

# Visualizations — Cross-state comparison
data/processed/habri_wnc_etn_map.png              # Side-by-side WNC vs. ETN choropleth
data/processed/habri_helene_validation_combined.png  # WNC + ETN Helene validation scatter
data/processed/habri_wnc_etn_profiles.png         # Profile distribution comparison (4 groups)
data/processed/habri_wnc_etn_recovery.png         # Quarterly recovery trend comparison
```

---

## Index Facts

**Weights (identical for NC and TN):**
- Top-level: H_E=0.40, I_F=0.35, C_C=0.25
- H_E sub-weights: flood=0.40, hurricane=0.35, landslide=0.25
- I_F sub-weights: tower=0.25, latency=0.25, road=0.30, power_grid=0.20
- Road sub-weights: betweenness=0.60, density=0.40
- C_C sub-weights: all 5 indicators equal at 0.20

**Baseline results (NC baseline, Apr 2026 — 4-component I_F including power grid):**
- 2,660 tracts; scores range [0.183, 0.820]; mean=0.499, SD=0.105
- Profiles: Power-Dependent=1,359 (51.1%), Dual-Risk=1,075 (40.4%), Transport-Fragile=226 (8.5%)

**Validation (Hurricane Helene, Sep 2024):**
- Ookla Q3→Q4 latency change: Spearman ρ=−0.113, p<0.001, n=2,650 tracts
- FCC DIRS county outages: ρ=0.236, p=0.018, n=100 counties
- IODA Morris Broadband (ASN 53488): 80-hour complete BGP blackout — Henderson Co. (HABRI 92nd pctile)
- Weight sensitivity: Spearman ρ>0.85 across all 5 alternative weight schemes

**NRI version note:** v1.20 (Dec 2025) renamed Riverine Flooding → Inland Flooding (RFLD → IFLD columns).

---

## Manuscript Status

See `docs/article_outline.md` for the submission plan and section-by-section content guide.
See `docs/manuscript_draft.md` for the current draft (still intentionally NC-focused;
the Tennessee and combined operational outputs exist but are not yet woven into the paper).

**Operational status (Apr 2026):**

1. NC baseline final; Q3 2024 – Q4 2025 time series complete and Jan 2026 validation built
2. Power grid integrated (4-component I_F); baseline and all quarterly outputs regenerated
3. Tennessee baseline built; statewide and Helene validation figures generated
4. Shared NC+TN standardized layer built for common-scale mapping
5. Manuscript still needs results/discussion revision and an explicit decision on whether to incorporate the TN/combined products

---

## Manuscript Writing Standards

**DO NOT include in manuscript prose:**

- References to Python scripts or file paths (e.g., `notebook_03.ipynb`, `src/config.py`)
- Internal documentation references or project-internal terminology
- Metacommentary about the writing process (avoid "in this paper", "the next section discusses")
- TODO/FIXME placeholders — resolve before committing any draft section
- Hedging that belongs in methods, not results ("the model attempted to…", "we tried to…")

**All manuscript text must be:**

- Self-contained academic prose a reviewer can read without access to the code
- Supported by formal citations where making empirical claims beyond this study
- Free of implementation details visible only to developers

See `docs/skills.md` for all HABRI commands.
See `docs/REVISION_TRACKER.md` for active peer review tracking.

---

## What Not To Do

- Do not use `pd.read_parquet()` for Ookla S3 data (pyarrow compat bug — see Convention 2)
- Do not modify `data/processed/habri_composite.gpkg` — it is the validated baseline
- Do not change top-level index weights without rerunning all notebooks and regenerating all validation figures
- Do not add `power_grid_norm` to I_F without updating `src/config.py` weights and re-running notebooks 03–04
- Do not compare `habri_composite.*` and `habri_tn_composite.*` directly across states — use `habri_nc_tn_standardized.*` for shared-scale interpretation
- Do not use relative `cache/` path with OSMnx on external volumes (see Convention 8)
- Do not attempt exact betweenness centrality on the full road graph (see Convention 7)
