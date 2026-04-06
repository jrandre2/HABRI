# HABRI — Claude Code Instructions

Hazard-Adjusted Broadband Reliability Index for North Carolina.
Composite outage-risk score for all 2,660 NC census tracts across 100 counties.
Formula: `HABRI = 0.40·H_E + 0.35·I_F + 0.25·C_C` (range [0,1]; 1 = highest risk)

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
| `scripts/update_ookla_quarterly.py` | Automated S3 quarterly refresh | READY — awaiting Q1-Q4 2025 downloads |
| `scripts/fetch_power_grid.py` | HIFLD transmission line density → power_grid_norm | DONE — NOT YET INTEGRATED |
| `scripts/build_site.py` | GitHub Pages static site | DONE |
| `app.py` | Streamlit dashboard | DONE — not yet tested end-to-end |

**Quarterly time series (Q1–Q4 2025):** Downloads in progress as of 2026-04-06.
Check: `tail -5 /tmp/habri_q[1-4]_2025.log`

**Power grid decision pending:** `power_grid_fragility.gpkg` exists in `data/processed/`
but `power_grid_norm` has NOT been incorporated into I_F. Doing so requires changing
all I_F weights, rerunning notebooks 03–04, and regenerating all validation figures.
**Do not write the final manuscript until this decision is made.**

---

## Non-Negotiable Technical Conventions

1. **CRS: always EPSG:2264 (NAD83 / NC State Plane, US survey feet) for all spatial analysis.**
   Area unit: sq ft. Conversion: `area_sqkm = geometry.area / 10_763_910.4`
   Outputs saved in WGS84 (EPSG:4326) for portability.

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
   pass `invert=True` to negate z before CDF.

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
# Main outputs
data/processed/habri_composite.csv / .gpkg        # 2,660 tracts × 16 score columns (BASELINE)
data/processed/habri_current_{tag}.csv / .gpkg    # versioned quarterly updates
data/processed/hazard_scores.gpkg                 # H_E sub-index + components
data/processed/infra_fragility.gpkg               # I_F sub-index + components
data/processed/acs_demographics.csv               # ACS 2022 tract-level covariates
data/processed/power_grid_fragility.gpkg          # PENDING integration — power_grid_norm per tract

# Raw data
data/raw/NRI_Table_CensusTracts.csv               # FEMA NRI v1.20 (manual download, 605 MB)
data/raw/nc_road_network.graphml                  # OSMnx statewide road graph (866 MB)
data/raw/ookla_fixed_pre_helene.gpkg              # Q3 2024 Ookla baseline
data/raw/ookla_fixed_post_helene.gpkg             # Q4 2024 Ookla (post-Helene)
data/raw/ookla_fixed_{tag}.gpkg                   # quarterly versioned Ookla tiles
data/raw/hifld_cellular_towers.geojson            # 1,275 NC cell towers
data/raw/hifld_transmission_lines_nc.geojson      # 8,263 NC transmission line segments
data/raw/ioda_asn_timeseries.csv                  # Helene outage telemetry (3 ISPs, 28,512 rows)

# Visualizations
data/processed/habri_4panel.png / .pdf            # publication-quality 4-panel map
data/processed/habri_profiles.png / .pdf          # vulnerability profile map
data/processed/habri_map.html                     # interactive Folium web map (21 MB)
data/processed/ioda_outage_timeseries.png         # Morris Broadband BGP blackout
data/processed/fcc_county_validation.png          # FCC DIRS county correlation plot
```

---

## Index Facts

**Weights:**
- Top-level: H_E=0.40, I_F=0.35, C_C=0.25
- H_E sub-weights: flood=0.40, hurricane=0.35, landslide=0.25
- I_F sub-weights: tower density=0.30, latency=0.30, road centrality=0.40
- Road sub-weights: betweenness=0.60, density=0.40
- C_C sub-weights: all 5 indicators equal at 0.20

**Baseline results (Feb 2025 run):**
- 2,660 tracts; scores range [0.203, 0.818]; mean=0.495, SD=0.106
- Profiles: Power-Dependent=1,359 (51%), Dual-Risk=1,075 (40%), Transport-Fragile=226 (9%)

**Validation (Hurricane Helene, Sep 2024):**
- Ookla Q3→Q4 latency change: Spearman ρ=−0.113, p<0.001, n=2,650 tracts
- FCC DIRS county outages: ρ=0.236, p=0.018, n=100 counties
- IODA Morris Broadband (ASN 53488): 80-hour complete BGP blackout — Henderson Co. (HABRI 92nd pctile)
- Weight sensitivity: Spearman ρ>0.85 across all 5 alternative weight schemes

**NRI version note:** v1.20 (Dec 2025) renamed Riverine Flooding → Inland Flooding (RFLD → IFLD columns).

---

## Manuscript Status

See `docs/article_outline.md` for the submission plan and section-by-section content guide.
See `docs/manuscript_draft.md` for the current draft (SKELETON — results section
incomplete pending Q1–Q4 2025 time series analysis and power grid integration decision).

**Do not finalize the manuscript until:**
1. Q1–Q4 2025 quarterly downloads complete and time series analysis runs
2. Power grid integration decision is made (yes/no) and index recomputed if yes
3. All validation figures reflect final data

---

## What Not To Do

- Do not use `pd.read_parquet()` for Ookla S3 data (pyarrow compat bug — see Convention 2)
- Do not modify `data/processed/habri_composite.gpkg` — it is the validated baseline
- Do not change top-level index weights without rerunning all notebooks and regenerating all validation figures
- Do not add `power_grid_norm` to I_F without updating `src/config.py` weights and re-running notebooks 03–04
- Do not finalize the manuscript before the time series data is ready (see Manuscript Status above)
- Do not use relative `cache/` path with OSMnx on external volumes (see Convention 8)
- Do not attempt exact betweenness centrality on the full road graph (see Convention 7)
