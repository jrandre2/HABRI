# Nationwide Data Acquisition Plan

This document turns the nationwide HABRI-GRID data ask into a repo-level acquisition plan. The goal is not to accumulate every available dataset. The goal is to build a training corpus with a clear separation between:

- hard outage labels
- degradation proxies
- hazard-event context
- power-side coupling data

The machine-readable source list lives in [docs/national_data_sources.json](/Volumes/T9/Projects/HABRI/docs/national_data_sources.json). Use the helper script below to render a checklist by phase, priority, or category:

```bash
python scripts/print_national_data_acquisition.py --phase 1
python scripts/print_national_data_acquisition.py --priority P0 --format markdown
```

## Core rule

Do not train the nationwide model on speed and latency collapse alone. Treat [M-Lab](https://www.measurementlab.net/data/) and [Ookla Open Data](https://github.com/teamookla/ookla-open-data) as **silver-label degradation proxies**, not as direct outage truth. Binary or probabilistic outage labels should come from event-triggered outage sources such as:

- [FCC DIRS public communications status reports](https://docs.fcc.gov/public/attachments/DOC-418362A1.pdf)
- [IODA](https://ioda.inetintel.cc.gatech.edu/) and the related [CSV download notes](https://ioda.inetintel.cc.gatech.edu/reports/ioda-markup/)
- [Cloudflare Radar Outage Center](https://radar.cloudflare.com/outage-center) and the [Radar anomaly API](https://developers.cloudflare.com/api/resources/radar/subresources/traffic_anomalies/methods/get/)

## Repo layout

Store new nationwide inputs and derived tables under the existing raw and processed split:

```text
data/raw/
  disaster_labels/
    fcc_dirs/
    ioda/
    cloudflare_radar/
  performance/
    mlab/
    ookla/
  hazards/
    openfema/
    noaa_storm_events/
    noaa_swdi/
    nhc_hurdat2/
    ibtracs/
  power/
    eia_disturbances/
    poweroutage_us/
  validation/
    ripe_atlas/

data/processed/national_events/
  disaster_declarations.parquet
  storm_events.parquet
  severe_weather_footprints.parquet
  connectivity_labels_dirs.parquet
  connectivity_labels_ioda.parquet
  connectivity_labels_cloudflare.parquet
  connectivity_validation_ripe_atlas.parquet
  degradation_proxy_mlab.parquet
  degradation_proxy_ookla.parquet
  power_disturbance_events.parquet
  national_outage_training_windows.parquet
```

## Phase plan

### Phase 1: build the nationwide event spine and hard-label layer

This phase is the minimum viable training dataset.

- [OpenFEMA Disaster Declarations Summaries v2](https://www.fema.gov/openfema-data-page/disaster-declarations-summaries-v2)
  - Use this as the canonical disaster-event index.
  - Normalize declaration, incident, county, and designated-area records into `disaster_declarations.parquet`.
- [NOAA Storm Events Database](https://www.ncei.noaa.gov/stormevents/)
  - Pull monthly bulk CSV releases and normalize county-level event timing and narrative metadata into `storm_events.parquet`.
- [FCC DIRS public communications status reports](https://docs.fcc.gov/public/attachments/DOC-418362A1.pdf)
  - Parse county-level cell-site outage tables from event reports into `connectivity_labels_dirs.parquet`.
  - Keep report timestamp, disaster slug, state, county FIPS, and each outage measure as separate fields.
- [IODA](https://ioda.inetintel.cc.gatech.edu/)
  - Backfill ISP and ASN windows for disaster periods into `connectivity_labels_ioda.parquet`.
  - Join ASN labels to county or tract geography later through FCC BDC providers, service-territory proxies, or partner data.
- [Cloudflare Radar Outage Center](https://radar.cloudflare.com/outage-center)
  - Pull event windows and provider or location anomalies into `connectivity_labels_cloudflare.parquet`.
  - Use this as corroborating supervision rather than standalone ground truth.
- [EIA Major Disturbances archive](https://www.eia.gov/electricity/data/disturbance/disturb_events_archive.html)
  - Normalize power disturbance events into `power_disturbance_events.parquet`.
  - This creates the first power-coupling layer without paying for a commercial feed.

### Phase 2: add hazard geometry, degradation proxies, and validation

This phase improves feature coverage and model evaluation.

- [NOAA SWDI](https://www.ncei.noaa.gov/products/severe-weather-data-inventory)
  - Pull bulk CSV or API outputs for flood, hail, mesocyclone, tornado, and other severe-weather footprints.
  - Write to `severe_weather_footprints.parquet`.
- [OpenFEMA IPAWS Archived Alerts v1](https://www.fema.gov/openfema-data-page/ipaws-archived-alerts-v1)
  - Normalize alert polygons, CAP event codes, and timestamps into `ipaws_archived_alerts.parquet`.
  - This helps align warning issuance with outage onset.
- [RIPE Atlas REST API](https://atlas.ripe.net/docs/apis/rest-api-reference/)
  - Pull event-targeted probe measurements for validation, especially ping, DNS, HTTP, and traceroute.
  - Store as `connectivity_validation_ripe_atlas.parquet`.
- [M-Lab](https://www.measurementlab.net/data/)
  - Use NDT and traceroute data as degradation proxies in `degradation_proxy_mlab.parquet`.
- [Ookla Open Data](https://github.com/teamookla/ookla-open-data)
  - Extend the existing `scripts/update_ookla_quarterly.py` pattern to a national tiling workflow and write `degradation_proxy_ookla.parquet`.
- [NHC HURDAT2](https://www.nhc.noaa.gov/data/#hurdat)
  - Use this as the primary hurricane track source for U.S. work.
- [IBTrACS](https://www.ncei.noaa.gov/products/international-best-track-archive)
  - Keep this as the broader tropical-cyclone archive for transfer learning or future non-U.S. expansion.

### Phase 3: add higher-cost or partner-gated coupling data

Only do this after Phase 1 is stable.

- [PowerOutage.us historical data](https://poweroutage.us/use-our-data/historical-poweroutage-data)
  - Optional commercial power-outage feed for city and utility history at 10-minute resolution.
  - Use if budget permits and the team wants much stronger power-communications coupling.
- Utility partner OMS, feeder, and restoration data
  - These are not public, but they become critical if the project moves from public-data pilot to a Genesis-grade grid operations workflow.

## Training table design

The first model-ready table should be `data/processed/national_events/national_outage_training_windows.parquet`. Each row should represent a geography-provider-event-time window, not just a county snapshot. Recommended fields:

- `event_id`
- `event_family`
- `event_source`
- `hazard_type`
- `hazard_start_utc`
- `hazard_end_utc`
- `geography_type`
- `geography_id`
- `provider_id`
- `asn`
- `label_source`
- `outage_probability`
- `outage_binary`
- `outage_duration_hours`
- `degradation_score`
- `power_outage_overlap`
- `alert_overlap`
- `hazard_severity_score`
- `source_confidence`
- `notes`

Normalize timestamps to UTC. Keep source-specific native fields in side tables rather than flattening everything into one wide raw ingest table.

## Script backlog

Existing scripts that already fit the plan:

- [scripts/fetch_fcc_bdc.py](/Volumes/T9/Projects/HABRI/scripts/fetch_fcc_bdc.py)
- [scripts/update_ookla_quarterly.py](/Volumes/T9/Projects/HABRI/scripts/update_ookla_quarterly.py)

Planned next scripts, in recommended order:

1. `scripts/fetch_openfema_disaster_declarations.py`
2. `scripts/fetch_noaa_storm_events.py`
3. `scripts/fetch_fcc_dirs_public_reports.py`
4. `scripts/fetch_ioda_event_windows.py`
5. `scripts/fetch_cloudflare_radar_outages.py`
6. `scripts/fetch_eia_disturbance_events.py`
7. `scripts/build_national_event_catalog.py`
8. `scripts/fetch_noaa_swdi.py`
9. `scripts/fetch_openfema_ipaws.py`
10. `scripts/fetch_ripe_atlas_event_windows.py`
11. `scripts/fetch_mlab_disaster_windows.py`
12. `scripts/build_national_outage_training_windows.py`

## Immediate repo next step

The next engineering task should be Phase 1 only:

1. ingest OpenFEMA declarations
2. ingest NOAA Storm Events
3. normalize a disaster event catalog
4. backfill DIRS, IODA, and Cloudflare labels for a small set of benchmark events
5. build `national_outage_training_windows.parquet`

That gets the repo to a real nationwide supervised-learning dataset without pretending that quarterly speed data is outage truth.
