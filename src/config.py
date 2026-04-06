"""HABRI Project Configuration — Single source of truth for all constants."""

from pathlib import Path
import os
from dotenv import load_dotenv

load_dotenv()

# ── Paths ────────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_RAW = PROJECT_ROOT / "data" / "raw"
DATA_PROCESSED = PROJECT_ROOT / "data" / "processed"
NOTEBOOKS = PROJECT_ROOT / "notebooks"

# ── Coordinate Reference Systems ─────────────────────────────────────────────
CRS_PROJECT = "EPSG:2264"  # NAD83 / North Carolina (US survey feet)
CRS_WGS84 = "EPSG:4326"   # WGS84 geographic

# ── Study Area ───────────────────────────────────────────────────────────────
STATE_FIPS = "37"  # North Carolina

# All 100 North Carolina counties
COUNTY_FIPS = {
    "Alamance":      "001",
    "Alexander":     "003",
    "Alleghany":     "005",
    "Anson":         "007",
    "Ashe":          "009",
    "Avery":         "011",
    "Beaufort":      "013",
    "Bertie":        "015",
    "Bladen":        "017",
    "Brunswick":     "019",
    "Buncombe":      "021",
    "Burke":         "023",
    "Cabarrus":      "025",
    "Caldwell":      "027",
    "Camden":        "029",
    "Carteret":      "031",
    "Caswell":       "033",
    "Catawba":       "035",
    "Chatham":       "037",
    "Cherokee":      "039",
    "Chowan":        "041",
    "Clay":          "043",
    "Cleveland":     "045",
    "Columbus":      "047",
    "Craven":        "049",
    "Cumberland":    "051",
    "Currituck":     "053",
    "Dare":          "055",
    "Davidson":      "057",
    "Davie":         "059",
    "Duplin":        "061",
    "Durham":        "063",
    "Edgecombe":     "065",
    "Forsyth":       "067",
    "Franklin":      "069",
    "Gaston":        "071",
    "Gates":         "073",
    "Graham":        "075",
    "Granville":     "077",
    "Greene":        "079",
    "Guilford":      "081",
    "Halifax":       "083",
    "Harnett":       "085",
    "Haywood":       "087",
    "Henderson":     "089",
    "Hertford":      "091",
    "Hoke":          "093",
    "Hyde":          "095",
    "Iredell":       "097",
    "Jackson":       "099",
    "Johnston":      "101",
    "Jones":         "103",
    "Lee":           "105",
    "Lenoir":        "107",
    "Lincoln":       "109",
    "McDowell":      "111",
    "Macon":         "113",
    "Madison":       "115",
    "Martin":        "117",
    "Mecklenburg":   "119",
    "Mitchell":      "121",
    "Montgomery":    "123",
    "Moore":         "125",
    "Nash":          "127",
    "New Hanover":   "129",
    "Northampton":   "131",
    "Onslow":        "133",
    "Orange":        "135",
    "Pamlico":       "137",
    "Pasquotank":    "139",
    "Pender":        "141",
    "Perquimans":    "143",
    "Person":        "145",
    "Pitt":          "147",
    "Polk":          "149",
    "Randolph":      "151",
    "Richmond":      "153",
    "Robeson":       "155",
    "Rockingham":    "157",
    "Rowan":         "159",
    "Rutherford":    "161",
    "Sampson":       "163",
    "Scotland":      "165",
    "Stanly":        "167",
    "Stokes":        "169",
    "Surry":         "171",
    "Swain":         "173",
    "Transylvania":  "175",
    "Tyrrell":       "177",
    "Union":         "179",
    "Vance":         "181",
    "Wake":          "183",
    "Warren":        "185",
    "Washington":    "187",
    "Watauga":       "189",
    "Wayne":         "191",
    "Wilkes":        "193",
    "Wilson":        "195",
    "Yadkin":        "197",
    "Yancey":        "199",
}
COUNTY_FIPS_LIST = list(COUNTY_FIPS.values())
# Full 5-digit state+county FIPS (e.g., "37021")
COUNTY_FIPS_FULL = [f"{STATE_FIPS}{c}" for c in COUNTY_FIPS_LIST]

# Original 6-county WNC subset (preserved for IODA validation case study)
WNC_COUNTY_FIPS = {
    "Buncombe": "021", "Haywood": "087", "Henderson": "089",
    "Madison": "115", "Mitchell": "121", "Yancey": "199",
}
WNC_COUNTY_FIPS_FULL = [f"{STATE_FIPS}{c}" for c in WNC_COUNTY_FIPS.values()]

# Unit conversion: EPSG:2264 uses US survey feet
# 1 km = 3280.84 US survey feet → 1 km² = 10,763,910.4 sq ft
SQFT_PER_SQKM = 10_763_910.4

# ── FEMA National Risk Index ─────────────────────────────────────────────────
# Numeric risk score columns (continuous, used for index calculation)
# NOTE: NRI v1.20 (Dec 2025) renamed "Riverine Flooding" to "Inland Flooding" (RFLD → IFLD)
NRI_SCORE_COLS = {
    "IFLD_RISKS": "Inland Flooding Risk Score",
    "HRCN_RISKS": "Hurricane Risk Score",
    "LNDS_RISKS": "Landslide Risk Score",
}
# Categorical risk rating columns (ordinal text, used for validation/display)
NRI_RATING_COLS = {
    "IFLD_RISKR": "Inland Flooding Risk Rating",
    "HRCN_RISKR": "Hurricane Risk Rating",
    "LNDS_RISKR": "Landslide Risk Rating",
}
# Expected Annual Loss columns (dollar values)
NRI_EAL_COLS = {
    "IFLD_EALT": "Inland Flooding Expected Annual Loss",
    "HRCN_EALT": "Hurricane Expected Annual Loss",
    "LNDS_EALT": "Landslide Expected Annual Loss",
}
# Key identifier columns
NRI_TRACTFIPS_COL = "TRACTFIPS"  # 11-digit tract FIPS
NRI_STCOFIPS_COL = "STCOFIPS"   # 5-digit state+county FIPS

# Risk rating text → ordinal encoding
NRI_RATING_MAP = {
    "Very Low": 1,
    "Relatively Low": 2,
    "Relatively Moderate": 3,
    "Relatively High": 4,
    "Very High": 5,
}
# Values to treat as missing
NRI_MISSING_RATINGS = {"No Rating", "Not Applicable", "Insufficient Data"}

# ── Ookla Open Data (AWS S3) ─────────────────────────────────────────────────
OOKLA_S3_BASE = "s3://ookla-open-data/parquet/performance/type=fixed"
OOKLA_QUARTERS = [
    {"year": 2024, "quarter": 3, "label": "pre_helene"},
    {"year": 2024, "quarter": 4, "label": "post_helene"},
]

def ookla_s3_path(year: int, quarter: int) -> str:
    """Build the full S3 path for an Ookla performance tile parquet file."""
    month = quarter * 3 - 2  # Q1→1, Q2→4, Q3→7, Q4→10
    date_str = f"{year}-{month:02d}-01"
    return (
        f"{OOKLA_S3_BASE}/year={year}/quarter={quarter}/"
        f"{date_str}_performance_fixed_tiles.parquet"
    )

# Columns to read from Ookla parquet (minimize memory)
# NOTE: v2024+ Ookla tiles include tile_x, tile_y (centroid coords) instead of WKT tile polygons.
# Local data is saved as .gpkg (GeoPackage) due to pyarrow/pandas compat issues with .parquet.
OOKLA_COLUMNS = [
    "tile_x", "tile_y", "avg_d_kbps", "avg_u_kbps", "avg_lat_ms",
    "avg_lat_down_ms", "avg_lat_up_ms", "tests", "devices", "quadkey",
]

# ── HIFLD Cellular Towers ────────────────────────────────────────────────────
HIFLD_TOWER_URL = (
    "https://services2.arcgis.com/FiaPA4ga0iQKduv3/ArcGIS/rest/services/"
    "Cellular_Towers_in_the_United_States/FeatureServer/0/query"
)
HIFLD_MAX_RECORDS = 2000  # ArcGIS default page size

# ── HIFLD Power Grid (Electric Substations) ──────────────────────────────────
# Source: Homeland Infrastructure Foundation-Level Data (HIFLD) — public layer
# Substations are a proxy for grid vulnerability: fewer substations per tract →
# higher infrastructure fragility (single points of failure for grid-dependent
# communication equipment such as cellular towers and fiber amplifiers).
HIFLD_SUBSTATION_URL = (
    "https://services1.arcgis.com/Hp6G80Pky0om7QvQ/ArcGIS/rest/services/"
    "Electric_Substations/FeatureServer/0/query"
)
# Relevant attribute fields to retain from the HIFLD substations layer
HIFLD_SUBSTATION_FIELDS = "OBJECTID,STATUS,COUNTY,STATE,COUNTYFIPS,LINES,MAX_VOLT,MIN_VOLT"

# ── Census ACS 5-Year Estimates ──────────────────────────────────────────────
CENSUS_API_KEY = os.getenv("CENSUS_API_KEY", "")
ACS_YEAR = 2022  # Most recent 5-year: 2018–2022 (uses 2020 Census tracts)

# Variable code → human-readable name
# Expanded set: original proposal variables + socioeconomic indicators
ACS_VARIABLES = {
    # Denominators
    "B01003_001E": "total_population",
    "B08141_001E": "total_workers",        # denominator for no-vehicle
    "B28011_001E": "total_hh_internet",    # denominator for mobile-only
    # Original proposal variables (community coping)
    "B08141_002E": "no_vehicle",           # workers with no vehicle available
    "B28011_008E": "mobile_only_internet", # households with cellular data only
    "C18108_006E": "disability_18_64",     # with disability, age 18–64
    "C18108_010E": "disability_65plus",    # with disability, age 65+
    # Socioeconomic indicators
    "B19013_001E": "median_household_income",
    "B17001_002E": "below_poverty_level",
}

# Census API base URL (no key required for ≤500 requests/day)
CENSUS_API_BASE = "https://api.census.gov/data"

# ── HABRI Index Weights ──────────────────────────────────────────────────────
# Top-level sub-index weights (must sum to 1.0)
W_HAZARD_EXPOSURE = 0.40
W_INFRA_FRAGILITY = 0.35
W_COPING_CAPACITY = 0.25

# Hazard Exposure sub-component weights
W_HE_FLOOD = 0.40
W_HE_HURRICANE = 0.35
W_HE_LANDSLIDE = 0.25

# Infrastructure Fragility sub-component weights
W_IF_TOWER_DENSITY = 0.30
W_IF_LATENCY = 0.30
W_IF_ROAD_CENTRALITY = 0.40

# Road fragility internal weights
W_ROAD_BETWEENNESS = 0.60
W_ROAD_DENSITY = 0.40

# Community Coping Capacity sub-component weights (equal across 5 indicators)
W_CC_NO_VEHICLE = 0.20
W_CC_MOBILE_ONLY = 0.20
W_CC_DISABILITY = 0.20
W_CC_INCOME = 0.20
W_CC_POVERTY = 0.20

# ── IODA Validation ──────────────────────────────────────────────────────────
IODA_API_BASE = "https://api.ioda.inetintel.cc.gatech.edu/v2"
HELENE_START = "2024-09-26"
HELENE_END = "2024-10-07"
# Western NC ISP ASNs known to have been heavily impacted
WNC_ASNS = {
    "Morris Broadband": 53488,
    "Skyline Telephone": 23118,
    "Wilkes Communications": 22191,
}
