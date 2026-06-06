# HABRI-GRID

HABRI-GRID is the Genesis-aligned extension of HABRI. It reframes the project from a static broadband risk index into a **public-data pilot for coupled power and communications resilience planning**.

## What changed

- HABRI remains the baseline tract-level vulnerability benchmark.
- HABRI-GRID adds a graph-oriented workflow focused on **grid planning, outage propagation, restoration lag, and mitigation ranking**.
- The default pilot geography is the Hurricane Helene comparison corridor:
  - Western North Carolina (WNC)
  - Eastern Tennessee (ETN)

## Public-data pilot bundle

The current implementation is a **public-data scaffold** for Genesis-style work. It uses the repo's processed NC/TN HABRI layers and builds three deliverables:

- `asset_graph`
  - Node types: `substation`, `transmission_segment`, `feeder`, `cell_site`, `backhaul_anchor`, `tract`
  - County-level substations and tract-level feeder/grid/backhaul/cell nodes are currently **proxy assets** derived from public grid and communications fragility metrics.
- `risk_forecast`
  - Scenario-specific outage probability
  - Expected outage duration
  - Expected restoration lag
  - Confidence intervals
  - Priority shift relative to the original HABRI ranking
- `scenario_runs`
  - Ranked mitigations under a budget constraint
  - Estimated outage minutes saved
  - Estimated reduction in critical-community exposure

## Default scenarios

- `helene_replay`: flood-forward event profile based on the WNC + ETN Helene footprint
- `regional_flood`: inland flood event with moderate landslide spillover
- `winter_ice`: lower hazard severity with slower restoration

## Default mitigation options

- Generator placement
- Sectionalizing and isolation
- Feeder hardening
- Route redundancy
- Tower battery backup
- Cell-on-wheels staging

## Running it

Build the pilot outputs:

```bash
python scripts/build_habri_grid_pilot.py
```

Review the nationwide data acquisition plan:

```bash
python scripts/print_national_data_acquisition.py --phase 1
```

Launch the dashboard and switch to **HABRI-GRID pilot** mode:

```bash
streamlit run app.py
```

## Important limitation

This implementation is intentionally a **public-data pilot**, not the final Genesis-ready system. It does **not** yet include:

- real feeder topology
- substation locations from utility partners
- outage management system history
- restoration timestamps
- asset-level electric operations data

Those partner datasets are the next step if the project moves into a full DOE Genesis application under Topic 16-A.

For the public-data nationwide expansion path, see [NATIONAL_DATA_ACQUISITION.md](/Volumes/T9/Projects/HABRI/docs/NATIONAL_DATA_ACQUISITION.md).
