"""HABRI Shared Utilities — reusable spatial and data manipulation functions."""

import geopandas as gpd
import pandas as pd
import numpy as np
import requests
from typing import Optional
from scipy.stats import norm as scipy_norm

from src.config import CRS_PROJECT, CRS_WGS84, DATA_PROCESSED


# ── Data Loading ─────────────────────────────────────────────────────────────

def load_study_tracts() -> gpd.GeoDataFrame:
    """Load the processed study area census tracts GeoPackage."""
    path = DATA_PROCESSED / "study_tracts.gpkg"
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found. Run Notebook 01 first to generate tract boundaries."
        )
    return gpd.read_file(path)


# ── CRS Helpers ──────────────────────────────────────────────────────────────

def ensure_crs(gdf: gpd.GeoDataFrame, target_crs: str = CRS_PROJECT) -> gpd.GeoDataFrame:
    """Reproject a GeoDataFrame to the target CRS if needed.

    Raises ValueError if the input has no CRS set.
    """
    if gdf.crs is None:
        raise ValueError("GeoDataFrame has no CRS set. Assign a CRS before reprojecting.")
    if not gdf.crs.equals(target_crs):
        return gdf.to_crs(target_crs)
    return gdf


def get_study_area_bbox(
    tracts_gdf: gpd.GeoDataFrame, crs: str = CRS_WGS84
) -> tuple[float, float, float, float]:
    """Return (minx, miny, maxx, maxy) bounding box of the study area in the given CRS."""
    gdf = tracts_gdf.to_crs(crs) if not tracts_gdf.crs.equals(crs) else tracts_gdf
    return tuple(gdf.total_bounds)


# ── Normalization ────────────────────────────────────────────────────────────

def min_max_normalize(series: pd.Series, invert: bool = False) -> pd.Series:
    """Min-max normalize a Series to [0, 1].

    Parameters
    ----------
    series : pd.Series
        Numeric values to normalize.
    invert : bool
        If True, high raw values produce low normalized values (1 - norm).

    Returns
    -------
    pd.Series with values in [0, 1]. Constant series returns 0.5.
    """
    s_min, s_max = series.min(), series.max()
    if s_max == s_min:
        return pd.Series(0.5, index=series.index)
    normalized = (series - s_min) / (s_max - s_min)
    return (1 - normalized) if invert else normalized


def z_score_normalize(series: pd.Series, invert: bool = False) -> pd.Series:
    """Z-score normalize a Series, then map to [0, 1] via standard normal CDF.

    Parameters
    ----------
    series : pd.Series
        Numeric values to normalize.
    invert : bool
        If True, high raw values produce low normalized values.

    Returns
    -------
    pd.Series with values in [0, 1]. Constant series (std=0) returns 0.5.
    """
    std = series.std()
    if std == 0 or pd.isna(std):
        return pd.Series(0.5, index=series.index)
    z = (series - series.mean()) / std
    if invert:
        z = -z
    return pd.Series(scipy_norm.cdf(z), index=series.index)


def impute_with_median(
    df: pd.DataFrame,
    column: str,
    label: str = "",
) -> tuple[pd.DataFrame, list[str]]:
    """Fill NaN values in a column with the column's median.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame to modify (in-place AND returned).
    column : str
        Column name to impute.
    label : str
        Human-readable label for logging.

    Returns
    -------
    (df, imputed_geoids) — the DataFrame and a list of GEOID values that were imputed.
    """
    mask = df[column].isna()
    imputed_geoids = df.loc[mask, "GEOID"].tolist() if "GEOID" in df.columns else []
    median_val = df[column].median()
    n_imputed = mask.sum()
    if n_imputed > 0:
        df[column] = df[column].fillna(median_val)
        display_label = label or column
        print(f"  Imputed {n_imputed} missing values in '{display_label}' with median={median_val:.4f}")
        if imputed_geoids:
            preview = imputed_geoids[:10]
            suffix = f"... (+{len(imputed_geoids) - 10} more)" if len(imputed_geoids) > 10 else ""
            print(f"    GEOIDs: {preview}{suffix}")
    return df, imputed_geoids


# ── Spatial Joins ────────────────────────────────────────────────────────────

def spatial_join_to_tracts(
    points_gdf: gpd.GeoDataFrame,
    tracts_gdf: gpd.GeoDataFrame,
    agg_dict: dict,
    how: str = "left",
) -> gpd.GeoDataFrame:
    """Spatial join features to tracts and aggregate per tract.

    Parameters
    ----------
    points_gdf : GeoDataFrame
        Features (points or polygons) to join.
    tracts_gdf : GeoDataFrame
        Census tracts with GEOID column.
    agg_dict : dict
        Column → aggregation function mapping (e.g., {"count": "sum"}).
    how : str
        Merge type for final join back to tracts ("left" keeps all tracts).

    Returns
    -------
    GeoDataFrame with tract geometries and aggregated columns.
    """
    features = ensure_crs(points_gdf)
    tracts = ensure_crs(tracts_gdf)
    joined = gpd.sjoin(features, tracts[["GEOID", "geometry"]], how="inner", predicate="within")
    aggregated = joined.groupby("GEOID").agg(agg_dict).reset_index()
    return tracts.merge(aggregated, on="GEOID", how=how)


# ── ArcGIS REST API ──────────────────────────────────────────────────────────

def query_arcgis_feature_layer(
    url: str,
    where: str = "1=1",
    out_fields: str = "*",
    max_records: int = 2000,
    geometry_filter: Optional[dict] = None,
) -> gpd.GeoDataFrame:
    """Page through an ArcGIS REST FeatureServer and return all features as a GeoDataFrame.

    Handles pagination automatically (the server caps each response at max_records).
    """
    all_features = []
    offset = 0

    while True:
        params = {
            "where": where,
            "outFields": out_fields,
            "f": "geojson",
            "resultOffset": offset,
            "resultRecordCount": max_records,
            "returnGeometry": "true",
        }
        if geometry_filter:
            params.update(geometry_filter)

        resp = requests.get(url, params=params, timeout=120)
        resp.raise_for_status()
        data = resp.json()

        features = data.get("features", [])
        if not features:
            break

        all_features.extend(features)

        if len(features) < max_records:
            break
        offset += max_records

    if not all_features:
        return gpd.GeoDataFrame()

    geojson = {"type": "FeatureCollection", "features": all_features}
    return gpd.GeoDataFrame.from_features(geojson, crs=CRS_WGS84)


# ── IODA API ─────────────────────────────────────────────────────────────────

def fetch_ioda_timeseries(
    entity_type: str,
    entity_code: str,
    start_unix: int,
    end_unix: int,
    datasource: str = "bgp",
) -> pd.DataFrame:
    """Query the IODA API v2 for outage time-series data.

    Parameters
    ----------
    entity_type : str
        "asn", "region", or "country".
    entity_code : str
        Entity identifier (e.g., "53488" for an ASN).
    start_unix : int
        Unix epoch start timestamp.
    end_unix : int
        Unix epoch end timestamp.
    datasource : str
        "bgp", "active-probing", or "merit-nt".

    Returns
    -------
    DataFrame with time-series data. Exact columns depend on API response.
    """
    from src.config import IODA_API_BASE

    url = f"{IODA_API_BASE}/signals/raw/{entity_type}/{entity_code}"
    params = {
        "from": start_unix,
        "until": end_unix,
        "datasource": datasource,
    }
    resp = requests.get(url, params=params, timeout=60)
    resp.raise_for_status()
    payload = resp.json()

    # API returns nested: data -> [batch] -> [series_dict]
    # Each series_dict has "values", "from", "step", etc.
    rows = []
    for batch in payload.get("data", []):
        for series in batch:
            from_ts = series["from"]
            step = series["step"]
            values = series.get("values", [])
            for i, val in enumerate(values):
                rows.append({
                    "datetime": pd.Timestamp(from_ts + i * step, unit="s", tz="UTC"),
                    "value": val,
                    "entityCode": series.get("entityCode", ""),
                    "entityName": series.get("entityName", ""),
                    "datasource": series.get("datasource", ""),
                })
    return pd.DataFrame(rows)


# ── Census API ───────────────────────────────────────────────────────────────

def fetch_acs_tract_data(
    variables: list[str],
    state_fips: str,
    county_fips: str,
    year: int = 2022,
    api_key: str = "",
) -> pd.DataFrame:
    """Fetch ACS 5-year tract-level data from the Census API.

    Parameters
    ----------
    variables : list[str]
        ACS variable codes (e.g., ["B01003_001E", "B08141_002E"]).
    state_fips : str
        2-digit state FIPS code.
    county_fips : str
        3-digit county FIPS code.
    year : int
        ACS vintage year.
    api_key : str
        Optional Census API key.

    Returns
    -------
    DataFrame with columns: variable codes + "state", "county", "tract", "GEOID".
    """
    from src.config import CENSUS_API_BASE

    var_str = ",".join(["NAME"] + variables)
    url = f"{CENSUS_API_BASE}/{year}/acs/acs5"
    params = {
        "get": var_str,
        "for": "tract:*",
        "in": f"state:{state_fips} county:{county_fips}",
    }
    if api_key:
        params["key"] = api_key

    resp = requests.get(url, params=params, timeout=60)
    resp.raise_for_status()
    data = resp.json()

    df = pd.DataFrame(data[1:], columns=data[0])
    df["GEOID"] = df["state"] + df["county"] + df["tract"]

    # Convert numeric columns (Census API returns everything as strings)
    for var in variables:
        df[var] = pd.to_numeric(df[var], errors="coerce")
        # Replace Census missing-data sentinel with NaN
        df.loc[df[var] == -666666666, var] = np.nan

    return df


def fetch_acs_state_tracts(
    variables: list[str],
    state_fips: str,
    year: int = 2022,
    api_key: str = "",
) -> pd.DataFrame:
    """Fetch ACS 5-year tract-level data for ALL tracts in a state.

    Uses county=* wildcard to fetch all counties in one API call,
    rather than looping per-county.

    Parameters
    ----------
    variables : list[str]
        ACS variable codes.
    state_fips : str
        2-digit state FIPS code.
    year : int
        ACS vintage year.
    api_key : str
        Optional Census API key.

    Returns
    -------
    DataFrame with columns: variable codes + "state", "county", "tract", "GEOID".
    """
    from src.config import CENSUS_API_BASE

    var_str = ",".join(["NAME"] + variables)
    url = f"{CENSUS_API_BASE}/{year}/acs/acs5"
    params = {
        "get": var_str,
        "for": "tract:*",
        "in": f"state:{state_fips}",
    }
    if api_key:
        params["key"] = api_key

    resp = requests.get(url, params=params, timeout=120)
    resp.raise_for_status()
    data = resp.json()

    df = pd.DataFrame(data[1:], columns=data[0])
    df["GEOID"] = df["state"] + df["county"] + df["tract"]

    for var in variables:
        df[var] = pd.to_numeric(df[var], errors="coerce")
        df.loc[df[var] == -666666666, var] = np.nan

    return df
