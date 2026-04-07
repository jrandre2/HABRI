# Research Specification: HABRI Project Initialization

Historical note: this file is the original North Carolina project initialization spec. The live repository has since added a Tennessee statewide pipeline and a shared NC+TN standardized layer, but this document is intentionally preserved as the starting NC scope.

## 1. Project Overview
We are building a Python-based geospatial analysis pipeline to create the **Hazard-Adjusted Broadband Reliability Index (HABRI)**. The goal is to merge hazard data (floods, landslides) with broadband infrastructure proxies to identify areas at high risk of communications failure.

## 2. Technical Stack
* **Language:** Python 3.10+
* **Core Libraries:** `geopandas`, `pandas`, `numpy`, `rasterio`, `shapely`
* **Visualization:** `folium` (interactive maps), `matplotlib` (static plots)
* **APIs/Tools:** `pygris` (for Census tract boundaries), `osmnx` (for OpenStreetMap road networks), direct Census API calls via `requests`

## 3. Directory Structure
```
HABRI/
    data/
        raw/           # For immutable downloads (FEMA CSVs, HIFLD GeoJSON, Ookla GeoPackages)
        processed/     # For cleaned/reprojected GeoPackage files and visualizations
    docs/
        DATA_DICTIONARY.md
        HABRI_EXPLAINED.md
        METHODOLOGY.md
        CONTRIBUTING.md
    notebooks/
        01_data_acquisition.ipynb
        02_hazard_processing.ipynb
        03_infra_proxy_generation.ipynb
        04_index_calculation.ipynb
    scripts/
        build_habri_current_2026_01.py
        build_ookla_jan_2026_validation.py
    src/
        config.py      # All project constants, FIPS codes, weights, URLs, column mappings
        utils.py       # Shared helper functions (CRS, normalization, spatial joins, APIs)
    README.md
    requirements.txt
    research_spec.md
```

## 4. Data Acquisition Strategy (Phase 1)
The agent should generate scripts to acquire the following:

### A. Hazard Data (FEMA)
* **Target:** FEMA National Risk Index (NRI) - Census Tract level.
* **Action:** Write a script to download the latest NRI ZIP archive programmatically (or provide the direct URL if scraping is blocked) and extract the CSV.
* **Key Columns to Keep:** `TRACTFIPS`, `IFLD_RISKS` (Inland Flooding), `HRCN_RISKS` (Hurricane), `LNDS_RISKS` (Landslide). Note: NRI v1.20 (Dec 2025) renamed Riverine Flooding to Inland Flooding (`RFLD` → `IFLD`).

### B. Infrastructure Data (HIFLD & OSM)
* **Target 1:** HIFLD Cellular Towers.
    * *Source:* HIFLD Open Data portal (GeoJSON URL).
* **Target 2:** Road Networks (Fiber Proxy).
    * *Action:* Use `osmnx` to download "drive" networks for the target study area (all North Carolina counties).

### C. Performance Data (Ookla)
* **Target:** Ookla Open Data (AWS S3 Parquet buckets).
* **Action:** Write a script using `boto3` or `pandas` to query the Ookla S3 bucket for the most recent quarter (Type: `fixed`, Year: `2024/2025`).
* **Filter:** Bounding box for North Carolina.
* **Metrics:** Average `avg_lat_ms` (latency). Jitter (`avg_jitter_ms`) is treated as optional — retained when present in source exports, but not available in the public S3 tiles.

## 5. Immediate Coding Tasks
1.  **Environment Setup:** Generate a `requirements.txt` file containing all libraries listed in Section 2.
2.  **Census Shapefile Fetcher:** Create a Python function `get_study_area_shapes(state_fips, county_fips)` using `pygris` or `cenpy` to download Census Tract boundaries for the target region.
3.  **Data Loader:** Create a skeleton script `01_data_acquisition.ipynb` that authenticates with the Census API and defines the logic to load the FEMA NRI CSV.

## 6. Study Area
* **Region:** All 100 counties in North Carolina (2,660 census tracts). Expanded from the original 6-county WNC pilot.
* **Validation focus:** Western NC mountain counties (Buncombe, Henderson, Haywood, Madison, Yancey, Mitchell) serve as the primary Hurricane Helene case study.
* **Coordinate Reference System (CRS):** Use `EPSG:2264` (NAD83 / North Carolina) for accurate distance measurements.
