# HABRI Skills Reference

Quick command reference for all HABRI pipeline operations.

---

## Pipeline Skills

### /acquire

Run data acquisition notebook (NRI, Ookla, HIFLD towers, OSMnx road network, ACS, IODA).

```bash
jupyter nbconvert --to notebook --execute notebooks/01_data_acquisition.ipynb
```

**Outputs:** `data/raw/` — NRI CSV, Ookla gpkg files, HIFLD geojson, road graphml, ACS CSV, IODA CSV

**Note:** FEMA NRI CSV requires manual download from FEMA's OpenFEMA portal before running.

### /hazard

Compute Hazard Exposure sub-index (H_E).

```bash
jupyter nbconvert --to notebook --execute notebooks/02_hazard_processing.ipynb
```

**Output:** `data/processed/hazard_scores.gpkg`

### /infra

Compute Infrastructure Fragility sub-index (I_F).

```bash
jupyter nbconvert --to notebook --execute notebooks/03_infra_proxy_generation.ipynb
```

**Output:** `data/processed/infra_fragility.gpkg`

**Note:** Betweenness centrality uses k=500 approximation (~30–40 min). Do not attempt exact.

### /index

Assemble HABRI composite index, run k-means profiles, validate, generate figures.

```bash
jupyter nbconvert --to notebook --execute notebooks/04_index_calculation.ipynb
```

**Output:** `data/processed/habri_composite.csv` / `.gpkg`

---

## Data Update Skills

### /quarterly-update

Run automated quarterly Ookla refresh and recompute current-conditions HABRI.

```bash
python scripts/update_ookla_quarterly.py
```

Detects the latest available quarter (8 weeks after quarter end), downloads NC tiles from S3,
aggregates to tracts, recomputes I_F (latency only), recomputes HABRI, saves versioned outputs.

**Output:** `data/raw/ookla_fixed_{tag}.gpkg`, `data/processed/habri_current_{tag}.csv` / `.gpkg`

**Check quarterly download logs:**

```bash
tail -20 /tmp/habri_q1_2025.log
tail -20 /tmp/habri_q2_2025.log
tail -20 /tmp/habri_q3_2025.log
tail -20 /tmp/habri_q4_2025.log
```

### /power-grid

Fetch HIFLD transmission lines and compute power-grid fragility layer.

```bash
python scripts/fetch_power_grid.py            # use cached if available
python scripts/fetch_power_grid.py --force    # re-fetch from HIFLD
```

**Output:** `data/processed/power_grid_fragility.gpkg`

### /integrate

Integrate power grid + FCC BDC adaptive weights into I_F and rebuild the baseline.

```bash
python scripts/integrate_power_grid.py                   # baseline only
python scripts/integrate_power_grid.py --regen-quarterly # also regenerate all quarterly outputs
```

**Output:** Updated `data/processed/habri_composite.csv` / `.gpkg` and all `habri_current_*.csv` files.

**Note:** Requires `data/processed/power_grid_fragility.gpkg` (run `/power-grid` first) and
optionally `data/processed/fcc_bdc_wired_fraction.csv` for adaptive weights (run `/bdc` first).

### /bdc

Download FCC BDC wired availability data and compute p_wired per tract.

```bash
python scripts/fetch_fcc_bdc.py
```

**Output:** `data/processed/fcc_bdc_wired_fraction.csv`

---

## Visualization and App Skills

### /maps

Regenerate all HABRI static and interactive map figures from the current baseline.

```bash
python scripts/plot_habri_maps.py              # all figures including Folium HTML
python scripts/plot_habri_maps.py --skip-folium  # static PNG/PDF only (faster)
```

**Outputs:** `habri_statewide_4panel.png/.pdf`, `habri_4panel.png/.pdf`, `habri_profiles.png/.pdf`, `habri_map.html`

### /timeseries

Generate multi-quarter HABRI trend figures (WNC recovery monitoring).

```bash
python scripts/plot_time_series.py
```

**Outputs:** `habri_timeseries_statewide.png`, `habri_timeseries_wnc.png`, `habri_timeseries_profiles.png`, `habri_recovery_scatter.png`

### /build-tn

Run the full HABRI pipeline for Tennessee (resume-safe; skips completed steps).

```bash
python scripts/build_habri_tn.py               # all steps
python scripts/build_habri_tn.py --skip-road   # skip OSMnx if graphml not cached
python scripts/build_habri_tn.py --force       # rerun everything
```

**Long-running steps:** OSMnx TN road network download (~1–2 hr), betweenness centrality (~30–40 min).
Script is checkpoint-safe — intermediate files are cached and re-used on re-runs.

**Outputs:** `habri_tn_composite.csv/.gpkg`, `hazard_tn_scores.gpkg`, `infra_tn_fragility.gpkg`,
`habri_tn_statewide_4panel.png`, `habri_tn_profiles.png`, `habri_tn_helene_validation.png`

### /compare-helene

Produce WNC vs. Eastern TN cross-state Helene comparison figures.
Requires both NC and TN pipelines to have been run.

```bash
python scripts/compare_helene_nc_tn.py
```

**Outputs:** `habri_wnc_etn_map.png`, `habri_helene_validation_combined.png`,
`habri_wnc_etn_profiles.png`, `habri_wnc_etn_recovery.png`

### /validate-road-proxy

Reproduce fixed vs. mobile Ookla validation of road network proxy.

```bash
python scripts/validate_road_proxy_mobile.py
```

**Expected:** WNC fixed ρ = −0.287 (p < 0.001), mobile ρ = +0.078 (n.s.), ratio 3.69×
**Output:** `data/processed/road_proxy_validation.csv` / `.png`

### /dashboard

Launch the Streamlit interactive dashboard.

```bash
streamlit run app.py
```

Tabs: interactive map (color by score/profile/quintile), data table with download,
charts (distribution, profile bar, top-20, county summary), baseline vs. current comparison.

### /build-site

Generate static GitHub Pages site.

```bash
python scripts/build_site.py
```

**Output:** `_site/index.html`

---

## Manuscript and Review Skills

### /review-new

Start a synthetic peer review of the manuscript draft. Choose a focus relevant to the next
submission stage. For *Telecommunications Policy*, prioritize `policy` and `methods`.

**Procedure:**

1. Open `docs/REVISION_TRACKER.md`
2. Add a new review cycle section with the date and focus
3. Use Claude to generate synthetic reviewer comments with the chosen focus:
   - `policy` — practitioner perspective, actionability, policy relevance
   - `methods` — statistical rigor, index construction, validation design
   - `clarity` — writing quality, accessibility, structure
   - `social_sciences` — theory, generalizability, equity framing
4. Triage each comment: Accept / Revise / Decline
5. Track changes in the REVISION_TRACKER checklist

### /review-verify

Check that all REVISION_TRACKER items are resolved before submission.

**Procedure:**

1. Open `docs/REVISION_TRACKER.md`
2. Confirm all `- [ ]` items are resolved or explicitly deferred with rationale
3. Run `python -m pytest tests/` to confirm no regressions

### /review-archive

Archive a completed review cycle.

**Procedure:**

1. Copy the completed REVISION_TRACKER section to `docs/reviews/archive/`
2. Clear the active section in REVISION_TRACKER
3. Tag the git commit: `git tag telecom-policy-r1-final`

---

## Validation Skills

### /validate-fcc

Reproduce FCC DIRS county-level correlation.

```bash
# Re-run the FCC validation cell in notebook 04, or:
python -c "
import pandas as pd, scipy.stats as ss
df = pd.read_csv('data/processed/habri_composite.csv')
# merge with FCC DIRS data...
"
```

**Expected:** Spearman ρ=0.236, p=0.018, n=100 counties

### /validate-ookla

Reproduce Ookla latency-change correlation.

**Expected:** Spearman ρ=−0.113, p<0.001, n=2,650 tracts

### /validate-ioda

Reproduce IODA Morris Broadband BGP blackout visualization.

**Output:** `data/processed/ioda_outage_timeseries.png`

---

## Testing and Quality Skills

### /test

Run the full test suite.

```bash
python -m pytest tests/ -v
```

**Expected:** 44 tests passing in `tests/test_utils.py`

### /lint

Run the linter.

```bash
ruff check src/ scripts/ tests/
```

---

## Journal Submission Skills

### /journal-check

Manual checklist for *Telecommunications Policy* submission requirements.

- [ ] Word count ≤ 10,000 (body text, excluding references and abstract)
- [ ] Abstract ≤ 250 words, structured (background / methods / results / conclusions)
- [ ] 5–8 keywords
- [ ] All figures ≥ 300 DPI, saved as TIFF or high-res PNG
- [ ] References formatted as APA (author-date)
- [ ] Highlights: 3–5 bullet points, ≤ 85 characters each
- [ ] Cover letter addresses scope fit and policy relevance
- [ ] No author-identifying information in manuscript file
- [ ] Supplementary materials (methodology appendix) uploaded separately
- [ ] Data and code availability statement included
- [ ] CRediT author contribution statement

**Manuscript status gate (from `CLAUDE.md`):**
Time series (Q3 2024 – Q4 2025) and power grid integration are complete. Remaining gate:
results/discussion draft must be rewritten to address F1–F8 flags in `docs/article_outline.md`.

---

## Git Skills

### /status

```bash
git status
git log --oneline -5
```

### /commit

```bash
git add <files>
git commit -m "Description"
```

### /push

```bash
git push origin main
```

---

## Troubleshooting Skills

### /check-env

```bash
python --version
pip list | grep -E "(pandas|geopandas|osmnx|streamlit|pytest)"
```

### /fix-osmnx-cache

If OSMnx raises a cache path error on the external volume:

```python
import osmnx as ox
from pathlib import Path
ox.settings.cache_folder = str(Path(__file__).resolve().parent.parent / "cache")
```

### /fix-ookla-parquet

If `pd.read_parquet()` raises an ndim error on Ookla S3 parquets:

```python
import pyarrow.parquet as pq
import s3fs
fs = s3fs.S3FileSystem(anon=True)
table = pq.read_table(s3_path, filesystem=fs, columns=[...])
# convert column-by-column via .to_pylist()
```
