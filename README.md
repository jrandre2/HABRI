# HABRI — Hazard-Adjusted Broadband Reliability Index

**A data-driven tool for identifying communities at highest risk of losing internet and cellular service during natural disasters.**

---

## Why This Matters

When Hurricane Helene struck Western North Carolina in September 2024, entire communities lost phone and internet service for days or weeks. Emergency calls couldn't go through. Families couldn't reach loved ones. Relief coordinators couldn't communicate with the people who needed help most.

The hardest-hit areas weren't random. They were communities where environmental hazards, fragile infrastructure, and socioeconomic vulnerability overlapped — places that were predictably at risk, if anyone had been looking.

**HABRI is that look.** It combines publicly available data on natural hazards, broadband infrastructure, and community demographics into a single score that answers one question: *Where is communications failure most likely during the next disaster?*

The goal is to help planners, emergency managers, and policymakers direct resources — backup generators, fiber route improvements, mobile cell towers — to the places that need them most, *before* the next storm.

---

## Study Area

This study covers **all 100 counties in North Carolina** (2,660 census tracts), expanded from the original 6-county Western NC pilot to provide statewide coverage. The western mountain region most severely impacted by Hurricane Helene serves as the primary validation case study.

The methodology is designed to be replicable for any state or region in the United States using the same freely available data sources.

---

## How the Index Works

HABRI produces a score between 0 and 1 for every census tract in the study area, where **higher scores indicate greater risk** of prolonged communications failure during a disaster. The score combines three dimensions of risk:

### The Three Pillars of Risk

```
HABRI = 40% Hazard Exposure + 35% Infrastructure Fragility + 25% Coping Capacity Deficit
```

#### 1. Hazard Exposure (40% of score)

*How likely is this area to experience a severe natural disaster?*

This component draws on FEMA's National Risk Index, which estimates risk levels for every census tract in the country. For North Carolina, three hazard types are most relevant:

- **Inland flooding** (40%) — The primary cause of infrastructure damage during Helene
- **Hurricanes** (35%) — Wind damage to towers, power lines, and above-ground fiber
- **Landslides** (25%) — Slope failures that sever roads and buried cable routes

#### 2. Infrastructure Fragility (35% of score)

*How vulnerable is the communications infrastructure itself?*

This component measures the physical resilience of the broadband and cellular network using three indicators:

- **Cell tower scarcity** (30%) — Areas with fewer towers per square mile have less redundancy; if one tower goes down, there may be no backup
- **Broadband latency** (30%) — Higher baseline latency (the delay in internet response times) indicates overloaded or poorly maintained network infrastructure that is more likely to degrade under stress
- **Road network bottlenecks** (40%) — Areas where all traffic funnels through a single road or bridge are vulnerable to isolation if that route is severed; this also affects the fiber and cable routes that follow road corridors

#### 3. Coping Capacity Deficit (25% of score)

*How well can the community cope when communications go down?*

This component uses U.S. Census data to identify populations that are disproportionately affected by service outages:

- **No vehicle access** (20%) — Cannot drive to reach cell service or an emergency shelter
- **Mobile-only internet** (20%) — Relies entirely on cellular networks with no fixed broadband fallback
- **Disability prevalence** (20%) — May have mobility, sensory, or cognitive barriers to adapting when service is lost
- **Low household income** (20%) — Fewer financial resources to purchase backup power, satellite phones, or relocate temporarily
- **Poverty rate** (20%) — Concentrated economic hardship that compounds all other vulnerabilities

---

## Key Findings

### Overall Risk Landscape

HABRI scores across the 2,660 census tracts range from 0.20 to 0.82 (mean 0.49, std 0.11). The highest-risk tracts are concentrated in rural eastern and western counties:

- **Bertie County** (mean HABRI 0.73) — Highest county-level risk, combining flood exposure with sparse infrastructure and high poverty
- **Lee County** (mean HABRI 0.70) — High hazard exposure and infrastructure fragility
- **Gates County** (mean HABRI 0.67) — Remote rural area with limited tower coverage and road redundancy
- **Warren County** (mean HABRI 0.67) — Dual-risk tracts with high vulnerability on both power-dependence and transport-fragility axes

### Vulnerability Profiles

Using statistical clustering, every tract is classified into one of three risk profiles — each suggesting a different type of investment:

| Profile | Tracts | Mean HABRI | Recommended Interventions |
|---------|--------|------------|--------------------------|
| **Power-Dependent** (51%) | 1,359 | 0.44 | Backup generators, battery storage, mobile cell-on-wheels deployment |
| **Dual-Risk** (40%) | 1,075 | 0.57 | Priority for combined investment: generators + route redundancy |
| **Transport-Fragile** (9%) | 226 | 0.47 | Fiber route diversification, microwave backup links, bridge hardening |

### Validation Against Hurricane Helene

The index was validated against real-world outage data from Hurricane Helene (September 2024):

**Internet Outage Detection (IODA)** — Georgia Tech's Internet Outage Detection and Analysis project tracked three Western NC internet providers through the storm:

- **Morris Broadband** (Henderson County) experienced 80 hours of complete BGP blackout — their entire network disappeared from the global internet
- **Skyline Telephone** (Mitchell/Avery counties) and **Wilkes Communications** (Wilkes/Ashe counties) maintained BGP visibility but showed degraded active probing metrics
- These real outage patterns align with the areas HABRI identifies as highest-risk

**Broadband Performance Degradation** — Comparing Ookla speedtest data from before Helene (Q3 2024, 123,435 tiles) to after (Q4 2024, 127,192 tiles), HABRI showed a statistically significant correlation with absolute latency change (Spearman rho = -0.113, p < 0.001, n = 2,650 tracts). The Infrastructure Fragility sub-index was the strongest predictor (rho = -0.216, p < 0.001).

**FCC Cell Site Outages** — The FCC activated DIRS for 21 western NC counties during Helene. County-level HABRI scores correlate significantly with FCC-reported cell site outage percentages (Spearman rho = 0.236, p = 0.018, n = 100 counties). Counties with higher HABRI scores had higher outage rates, validating the index's predictive value.

---

## Data Sources

All data used in this project is publicly available and free to access:

| Data Source | What It Provides | Provider |
|-------------|-----------------|----------|
| **FEMA National Risk Index** | Flood, hurricane, and landslide risk scores for every census tract | Federal Emergency Management Agency |
| **HIFLD Cellular Towers** | Locations of cell towers nationwide | Homeland Infrastructure Foundation-Level Data |
| **Ookla Speedtest Open Data** | Broadband download/upload speeds and latency, measured by real users | Ookla (published under open data license) |
| **Census ACS 5-Year Estimates** | Demographics including income, vehicle access, disability, internet type | U.S. Census Bureau |
| **OpenStreetMap Road Network** | Road connectivity and routing topology | OpenStreetMap contributors |
| **IODA Outage Detection** | Real-time internet outage monitoring via BGP and active probing | Georgia Tech Internet Intelligence Lab |
| **FCC Communications Status Reports** | Cell site outage counts during declared disasters | Federal Communications Commission |

---

## Outputs and Deliverables

The analysis produces several outputs, all stored in the `data/processed/` folder.

January 2026 updates are modeled as **versioned current-conditions layers** so the published baseline remains unchanged.

| File | Description |
|------|-------------|
| `habri_composite.csv` | Complete tract-level results: HABRI scores, sub-index scores, vulnerability profiles |
| `habri_composite.gpkg` | Same data as a geospatial file (GeoPackage) for use in GIS software |
| `habri_map.html` | Interactive web map — open in any browser to explore tracts, scores, and profiles |
| `habri_4panel.png` | Publication-quality map showing all three sub-indices and the composite score |
| `habri_profiles.png` | Map showing vulnerability profile classifications |
| `ioda_outage_timeseries.png` | Timeline of internet outages for three WNC providers during Hurricane Helene |
| `fcc_county_validation.png` | Comparison of HABRI scores against FCC-reported cell site outages by county |
| `habri_current_2026_01.csv` | Versioned current-conditions HABRI layer for January 2026; only latency-driven infrastructure fragility is updated |
| `habri_current_2026_01.gpkg` | Same as above with geometry |
| `infra_fragility_current_2026_01.gpkg` | January 2026 latency-updated infrastructure fragility layer |
| `ookla_fixed_2026_01.gpkg` | January 2026 fixed-broadband tile centroids and aggregates |
| `ookla_tract_2026_01.csv` | January 2026 tract-level Ookla metrics used as intermediate inputs |
| `ookla_tract_2026_01.gpkg` | Geospatial version of January 2026 tract-level Ookla metrics |
| `habri_validation_2026_01.csv` | Baseline-vs-January 2026 validation table with delta metrics |
| `habri_validation_2026_01_summary.csv` | Correlation and median statistic summary for January 2026 scenario |
| `habri_validation_2026_01.png` | January 2026 validation scatter plots |

---

## How to Read the Results

### The CSV File

The main results file (`habri_composite.csv`) contains one row per census tract with these key columns:

| Column | Meaning |
|--------|---------|
| `GEOID` | Census tract identifier (11-digit FIPS code) |
| `HABRI` | Overall risk score (0–1, higher = more at risk) |
| `H_E` | Hazard Exposure sub-score |
| `I_F` | Infrastructure Fragility sub-score |
| `C_C` | Coping Capacity Deficit sub-score |
| `HABRI_quintile` | Risk tier: Very Low, Low, Moderate, High, or Very High |
| `risk_profile` | Vulnerability type: Power-Dependent, Transport-Fragile, or Dual-Risk |

### The Interactive Map

Open `habri_map.html` in a web browser to explore the results visually. The map includes toggleable layers:

- **HABRI Score** — Color-coded choropleth from yellow (low risk) to dark red (high risk)
- **Risk Profiles** — Color-coded by vulnerability type (red = Power-Dependent, blue = Transport-Fragile, purple = Dual-Risk)
- **Cellular Towers** — Blue dots showing cell tower locations

Hover over any tract to see its ID, risk profile, and HABRI score.

### Current-conditions January 2026 Run (Optional)

To produce the versioned current-conditions output without changing the published baseline:

```bash
python scripts/build_habri_current_2026_01.py \
  --input-csv /path/FixedNetworkPerformance_54196_2026-01-01.csv \
  --version-tag 2026_01 \
  --max-location-accuracy-m 75

python scripts/build_ookla_jan_2026_validation.py \
  --input-csv /path/FixedNetworkPerformance_54196_2026-01-01.csv \
  --version-tag 2026_01 \
  --max-location-accuracy-m 75
```

You can also set `OOKLA_JAN2026_CSV` in your shell to avoid repeating `--input-csv`.

By default, `--max-location-accuracy-m` is disabled, so all rows with available location and latency fields are included. When set, rows with `attr_location_accuracy_m` above the threshold are filtered out.

The baseline files `habri_composite.csv` and `habri_composite.gpkg` remain unchanged; current-conditions outputs are intentionally separated by version tag.

### Technical Reproducibility with Notebooks

---

## Methodology Notes

### Weight Selection

The weights assigned to each component (40/35/25 for the three pillars; sub-weights within each pillar) reflect the relative importance of each factor for communications resilience, informed by disaster communications literature and post-Helene field reports.

A **sensitivity analysis** tested five different weight configurations (equal weights, hazard-dominant, infrastructure-dominant, community-dominant, and the default). The tract rankings remained highly correlated across all configurations (Spearman rank correlation > 0.85), meaning the results are robust — the same communities emerge as highest-risk regardless of the exact weight choices.

### Normalization

All indicators are z-score normalized within the study area and mapped to [0, 1] via the standard normal CDF. This approach is more robust to outliers than min-max normalization and maps the study area mean to 0.5. The scores represent *relative* risk among the 2,660 NC tracts. Road edges are assigned to tracts via midpoint interpolation to avoid double-counting edges that cross tract boundaries.

### Limitations

- **Temporal snapshot**: Infrastructure and demographic data reflect a single point in time (2022–2024) and will need periodic updates
- **Proxy measures**: Cell tower density and road centrality are proxies for true network topology, which is proprietary information held by carriers
- **Study area scope**: Normalization is local to North Carolina — scores are not directly comparable to other states without re-running the analysis
- **No power grid data**: Electricity outages are a primary cause of communications failure but are not included due to data availability constraints

---

## Project Structure

```
HABRI/
├── data/
│   ├── raw/                    # Downloaded source data (not modified)
│   └── processed/              # Analysis outputs (scores, maps, charts)
├── docs/
│   ├── DATA_DICTIONARY.md      # Column-level definitions for all data files
│   ├── HABRI_EXPLAINED.md      # Plain-language summary of the index
│   ├── METHODOLOGY.md          # Formulas, statistical methods, design decisions
│   └── CONTRIBUTING.md         # Developer setup, architecture, extending HABRI
├── notebooks/
│   ├── 01_data_acquisition     # Downloads and caches all data sources
│   ├── 02_hazard_processing    # Computes Hazard Exposure (H_E)
│   ├── 03_infra_proxy_gen      # Computes Infrastructure Fragility (I_F)
│   └── 04_index_calculation    # Computes Coping Capacity (C_C), assembles
│                               #   HABRI, profiles tracts, validates, maps
├── scripts/
│   ├── build_habri_current_2026_01.py   # Versioned current-conditions HABRI
│   └── build_ookla_jan_2026_validation.py  # Validation against baseline
├── src/
│   ├── config.py               # All project settings and constants
│   └── utils.py                # Shared helper functions
├── requirements.txt            # Python package dependencies
├── research_spec.md            # Original research specification
└── README.md                   # This file
```

The four notebooks run sequentially — each depends on outputs from the previous one. The full pipeline takes approximately 2–4 hours to run from scratch (the road network download and betweenness centrality computation are the bottlenecks).

---

## Further Documentation

| Document | Audience | Contents |
| -------- | -------- | -------- |
| [Data Dictionary](docs/DATA_DICTIONARY.md) | Analysts, data users | Column-by-column definitions for every input and output file, data types, value ranges, provenance |
| [HABRI Explained](docs/HABRI_EXPLAINED.md) | General audience | Plain-language summary of what HABRI is, what data it uses, and how it was validated |
| [Methodology](docs/METHODOLOGY.md) | Researchers, reviewers | Complete formulas, statistical methods, normalization approach, design decision rationale |
| [Contributing Guide](docs/CONTRIBUTING.md) | Developers | Environment setup, architecture, how to extend HABRI to new regions or add new indicators |

---

## For Technical Users

### Reproducing the Analysis

```bash
# 1. Clone the repository and install dependencies
pip install -r requirements.txt

# 2. (Optional) Add a Census API key to .env for higher rate limits
echo "CENSUS_API_KEY=your_key" > .env

# 3. Download the FEMA NRI CSV manually (see Notebook 01 for instructions)
#    Place at: data/raw/NRI_Table_CensusTracts.csv

# 4. Run notebooks in order
jupyter notebook notebooks/01_data_acquisition.ipynb
# Then 02, 03, 04

# 5. Optional: regenerate January 2026 current-conditions comparison from a fixed-network export
python scripts/build_habri_current_2026_01.py --version-tag 2026_01
python scripts/build_ookla_jan_2026_validation.py --version-tag 2026_01
```

### Coordinate Reference System

All spatial analysis uses **EPSG:2264** (NAD83 / North Carolina, US survey feet). This ensures accurate distance and area calculations for the study region. Area conversions: 1 km² = 10,763,910.4 square feet.

### Extending to Other Regions

To apply HABRI to a different region:

1. Update the county FIPS codes in `src/config.py`
2. Re-run the notebooks — all data sources are fetched programmatically (except the FEMA NRI CSV, which requires a one-time manual download)
3. Consider adjusting hazard weights if the region faces different primary threats (e.g., wildfire instead of landslide)

---

## Citation and License

This project uses open government data and open-source software. If you use HABRI in your work, please cite the data sources listed above and this repository.

**Ookla Data**: Speedtest by Ookla Global Fixed and Mobile Network Performance Maps. Based on analysis by Ookla of Speedtest Intelligence data. Provided under the Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License.

**IODA Data**: Internet Outage Detection and Analysis (IODA), Center for Applied Internet Data Analysis (CAIDA), Georgia Institute of Technology.

---

## Contact

For questions about the methodology, data, or potential applications of HABRI, please open an issue in this repository.
