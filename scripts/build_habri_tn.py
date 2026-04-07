#!/usr/bin/env python3
"""Full HABRI pipeline for Tennessee — statewide index with Eastern TN Helene focus.

Produces the same outputs as the NC pipeline (notebooks 01-04 + integrate_power_grid.py)
but for all 95 Tennessee counties (1,701 census tracts).  Intermediate files are cached
so the script is resumable: re-running skips completed steps unless --force is passed.

Outputs (all in data/processed/ unless noted)
------------------------------------------
data/processed/habri_tn_composite.csv / .gpkg
    1,701 tracts × HABRI + sub-indices + profiles.
data/processed/hazard_tn_scores.gpkg
    H_E sub-index + NRI components for TN tracts.
data/processed/infra_tn_fragility.gpkg
    I_F sub-index + tower / latency / road / power components.
data/raw/ookla_tn_fixed_q3_2024.gpkg
    Pre-Helene Ookla tiles for TN (Q3 2024).
data/raw/ookla_tn_fixed_q4_2024.gpkg
    Post-Helene Ookla tiles for TN (Q4 2024).
data/raw/tn_road_network.graphml
    OSMnx statewide TN road graph (very large — ~2 hr download).
data/processed/habri_tn_statewide_4panel.png / .pdf
    Statewide 4-panel choropleth (H_E, I_F, C_C, HABRI).
data/processed/habri_tn_profiles.png
    Eastern TN vulnerability profile map.
data/processed/habri_tn_helene_validation.png
    Scatter: HABRI vs. Q3→Q4 latency change for Eastern TN tracts.

Usage
-----
    python scripts/build_habri_tn.py               # resume-safe (skips done steps)
    python scripts/build_habri_tn.py --force        # rerun everything
    python scripts/build_habri_tn.py --skip-road    # skip OSMnx (use cached graphml)
    python scripts/build_habri_tn.py --no-figures   # data only, skip map generation
"""
from __future__ import annotations

import argparse
import sys
import warnings
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import s3fs
from scipy.stats import spearmanr
from shapely.geometry import Point

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import osmnx as ox
ox.settings.cache_folder = str(PROJECT_ROOT / "cache")

from src.config import (
    DATA_PROCESSED, DATA_RAW,
    CRS_WGS84,
    SQFT_PER_SQKM,
    W_HE_FLOOD, W_HE_HURRICANE, W_HE_LANDSLIDE,
    W_IF_LATENCY, W_IF_ROAD_CENTRALITY, W_IF_TOWER_DENSITY, W_IF_POWER_GRID,
    W_ROAD_BETWEENNESS, W_ROAD_DENSITY,
    W_HAZARD_EXPOSURE, W_INFRA_FRAGILITY, W_COPING_CAPACITY,
    HIFLD_TOWER_URL, HIFLD_TRANSMISSION_URL, HIFLD_MAX_RECORDS,
)
from src.region import TN_CONFIG, ETN_HELENE_COUNTY_FIPS
from src.utils import z_score_normalize, impute_with_median, ensure_crs, query_arcgis_feature_layer

warnings.filterwarnings("ignore", category=UserWarning)

# ── Constants ─────────────────────────────────────────────────────────────────

STATE_FIPS = "47"
CRS_PROJECT = "EPSG:2274"          # NAD83 / Tennessee (US survey feet)
NRI_SCORE_COLS = {
    "IFLD_RISKS": "Inland Flooding",
    "HRCN_RISKS": "Hurricane",
    "LNDS_RISKS": "Landslide",
}

# ACS variables (same as NC)
ACS_VARS = [
    "B01003_001E",  # total population
    "B08141_001E",  # total workers
    "B08141_002E",  # no vehicle
    "B28011_001E",  # total HH internet
    "B28011_008E",  # mobile-only internet
    "C18108_006E",  # disability 18-64
    "C18108_010E",  # disability 65+
    "B19013_001E",  # median HH income
    "B17001_002E",  # below poverty
]
ACS_RENAME = {
    "B01003_001E": "total_population",
    "B08141_001E": "total_workers",
    "B08141_002E": "no_vehicle",
    "B28011_001E": "total_hh_internet",
    "B28011_008E": "mobile_only_internet",
    "C18108_006E": "disability_18_64",
    "C18108_010E": "disability_65plus",
    "B19013_001E": "median_household_income",
    "B17001_002E": "below_poverty_level",
}

# Ookla S3 paths
OOKLA_S3_FIXED = "s3://ookla-open-data/parquet/performance/type=fixed"
OOKLA_COLS = ["tile_x", "tile_y", "avg_lat_ms", "tests"]


# ── Helpers ───────────────────────────────────────────────────────────────────

def step(msg: str) -> None:
    print(f"\n{'─'*60}\n{msg}\n{'─'*60}")


def done(path: Path) -> bool:
    return path.exists()


def _ookla_s3_path(year: int, quarter: int) -> str:
    return f"{OOKLA_S3_FIXED}/year={year}/quarter={quarter}/"


def _read_ookla_s3(year: int, quarter: int, bbox_wgs: tuple) -> gpd.GeoDataFrame:
    """Download Ookla fixed tiles for a bounding box from S3, return GeoDataFrame."""
    xmin, ymin, xmax, ymax = bbox_wgs
    fs = s3fs.S3FileSystem(anon=True)
    s3_path = _ookla_s3_path(year, quarter)
    parquet_files = [f for f in fs.ls(s3_path) if f.endswith(".parquet")]
    frames = []
    for pf in parquet_files:
        tbl = pq.read_table(f"s3://{pf}", filesystem=fs, columns=OOKLA_COLS)
        tx = tbl.column("tile_x").to_pylist()
        ty = tbl.column("tile_y").to_pylist()
        lat = tbl.column("avg_lat_ms").to_pylist()
        tests = tbl.column("tests").to_pylist()
        mask = [(xmin <= x <= xmax) and (ymin <= y <= ymax)
                for x, y in zip(tx, ty)]
        if any(mask):
            frames.append(pd.DataFrame({
                "tile_x": [tx[i] for i in range(len(tx)) if mask[i]],
                "tile_y": [ty[i] for i in range(len(ty)) if mask[i]],
                "avg_lat_ms": [lat[i] for i in range(len(lat)) if mask[i]],
                "tests": [tests[i] for i in range(len(tests)) if mask[i]],
            }))
    if not frames:
        raise RuntimeError(f"No Ookla tiles found for bbox {bbox_wgs} in {s3_path}")
    df = pd.concat(frames, ignore_index=True)
    geom = [Point(x, y) for x, y in zip(df["tile_x"], df["tile_y"])]
    gdf = gpd.GeoDataFrame(df, geometry=geom, crs=CRS_WGS84)
    return gdf



# ── Step 1: Census tract boundaries ──────────────────────────────────────────

def build_study_tracts(force: bool = False) -> gpd.GeoDataFrame:
    out = DATA_PROCESSED / "study_tn_tracts.gpkg"
    if done(out) and not force:
        print(f"  Loading cached {out}")
        return gpd.read_file(out)

    step("1/9  Census tract boundaries (pygris, year=2022)")
    import pygris
    tracts = pygris.tracts(state=STATE_FIPS, year=2022)
    tracts = tracts.rename(columns={"GEOID": "GEOID"})
    tracts["GEOID"] = tracts["GEOID"].str.zfill(11)
    tracts = ensure_crs(tracts, CRS_PROJECT)
    tracts.to_file(out, driver="GPKG")
    print(f"  {len(tracts)} tracts saved → {out}")
    return tracts


# ── Step 2: Hazard Exposure ───────────────────────────────────────────────────

def build_hazard(tracts: gpd.GeoDataFrame, force: bool = False) -> gpd.GeoDataFrame:
    out = DATA_PROCESSED / "hazard_tn_scores.gpkg"
    if done(out) and not force:
        print(f"  Loading cached {out}")
        return gpd.read_file(out)

    step("2/9  Hazard Exposure (H_E) — FEMA NRI v1.20")
    nri_path = DATA_RAW / "NRI_Table_CensusTracts.csv"
    if not nri_path.exists():
        raise FileNotFoundError(f"NRI CSV not found at {nri_path}. Download from FEMA OpenFEMA.")
    nri = pd.read_csv(nri_path, dtype=str)
    nri_tn = nri[nri["STCOFIPS"].str.startswith(STATE_FIPS)].copy()
    nri_tn["GEOID"] = nri_tn["TRACTFIPS"].str.zfill(11)

    for col in NRI_SCORE_COLS:
        nri_tn[col] = pd.to_numeric(nri_tn[col], errors="coerce")
        invalid = nri_tn[col] < 0
        nri_tn.loc[invalid, col] = np.nan

    habri = tracts[["GEOID", "geometry"]].merge(
        nri_tn[["GEOID"] + list(NRI_SCORE_COLS.keys())], on="GEOID", how="left"
    )

    nri_cols = list(NRI_SCORE_COLS.keys())
    norm_names = ["ifld_norm", "hrcn_norm", "lnds_norm"]
    for col, norm_name in zip(nri_cols, norm_names):
        impute_with_median(habri, col)
        habri[norm_name] = z_score_normalize(habri[col])

    habri["H_E"] = (
        W_HE_FLOOD     * habri["ifld_norm"]
        + W_HE_HURRICANE * habri["hrcn_norm"]
        + W_HE_LANDSLIDE * habri["lnds_norm"]
    )
    habri.to_file(out, driver="GPKG")
    print(f"  H_E range [{habri['H_E'].min():.4f}, {habri['H_E'].max():.4f}]  → {out}")
    return habri


# ── Step 3: Tower density ─────────────────────────────────────────────────────

def build_tower_density(tracts: gpd.GeoDataFrame, force: bool = False) -> pd.Series:
    out = DATA_PROCESSED / "infra_tn_towers.csv"
    if done(out) and not force:
        print(f"  Loading cached tower density")
        df = pd.read_csv(out, dtype={"GEOID": str})
        return df.set_index("GEOID")["tower_density_norm"]

    step("3a/9  HIFLD cellular tower density")
    tracts_wgs = tracts.to_crs(CRS_WGS84)
    xmin, ymin, xmax, ymax = tracts_wgs.total_bounds
    geometry_filter = {
        "geometryType": "esriGeometryEnvelope",
        "geometry": f"{xmin},{ymin},{xmax},{ymax}",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
    }
    towers = query_arcgis_feature_layer(
        url=HIFLD_TOWER_URL,
        geometry_filter=geometry_filter,
        max_records=HIFLD_MAX_RECORDS,
    )
    if len(towers) == 0:
        raise RuntimeError("No towers returned from HIFLD API")
    towers = towers.to_crs(CRS_PROJECT)
    joined = gpd.sjoin(towers, tracts[["GEOID", "geometry"]], how="left",
                        predicate="within")
    counts = joined.groupby("GEOID").size().rename("tower_count")

    tracts_proj = tracts.copy()
    tracts_proj["area_km2"] = tracts_proj.geometry.area / SQFT_PER_SQKM
    density = tracts_proj.set_index("GEOID").join(counts).fillna({"tower_count": 0})
    density["tower_count"] = density["tower_count"].astype(float)
    density.loc[density["tower_count"] == 0, "tower_count"] = np.nan
    density["tower_density_km2"] = density["tower_count"] / density["area_km2"]

    ser = density["tower_density_km2"].copy()
    _tmp = pd.DataFrame({"GEOID": density.index, "v": ser.values}).set_index("GEOID")
    impute_with_median(_tmp, "v")
    ser = _tmp["v"]
    tower_norm = z_score_normalize(ser, invert=True)
    result = pd.DataFrame({"GEOID": density.index, "tower_density_norm": tower_norm})
    result.to_csv(out, index=False)
    print(f"  {len(towers)} towers → {out}")
    return result.set_index("GEOID")["tower_density_norm"]


# ── Step 4: Ookla latency ─────────────────────────────────────────────────────

def build_ookla(tracts: gpd.GeoDataFrame, force: bool = False
                ) -> tuple[pd.Series, pd.Series | None]:
    """Returns (latency_norm Q3, latency_norm Q4 or None)."""
    out_q3 = DATA_RAW / "ookla_tn_fixed_q3_2024.gpkg"
    out_q4 = DATA_RAW / "ookla_tn_fixed_q4_2024.gpkg"
    tracts_wgs = tracts.to_crs(CRS_WGS84)
    bbox_wgs = tuple(tracts_wgs.total_bounds)

    def _aggregate(gpkg: Path) -> pd.Series:
        tiles = gpd.read_file(gpkg).to_crs(CRS_PROJECT)
        joined = gpd.sjoin(tiles, tracts[["GEOID", "geometry"]], how="left",
                            predicate="within")
        joined = joined.dropna(subset=["GEOID", "avg_lat_ms"])
        joined["weighted"] = joined["avg_lat_ms"] * joined["tests"]
        grp = joined.groupby("GEOID").agg(
            weighted_sum=("weighted", "sum"),
            test_count=("tests", "sum"),
        )
        grp["avg_latency_ms"] = grp["weighted_sum"] / grp["test_count"]
        ser = grp["avg_latency_ms"]
        ser_df = pd.DataFrame({"GEOID": ser.index, "v": ser.values}).set_index("GEOID")
        impute_with_median(ser_df, "v")
        return z_score_normalize(ser_df["v"])

    step("4/9  Ookla fixed broadband latency (Q3 2024 baseline, Q4 2024 post-Helene)")
    if not done(out_q3) or force:
        print("  Downloading Q3 2024 Ookla tiles for TN…")
        gdf_q3 = _read_ookla_s3(2024, 3, bbox_wgs)
        gdf_q3.to_file(out_q3, driver="GPKG")
        print(f"  {len(gdf_q3)} tiles → {out_q3}")
    else:
        print(f"  Loading cached Q3 2024 ({out_q3})")
    latency_norm_q3 = _aggregate(out_q3)

    latency_norm_q4 = None
    if not done(out_q4) or force:
        print("  Downloading Q4 2024 Ookla tiles for TN…")
        try:
            gdf_q4 = _read_ookla_s3(2024, 4, bbox_wgs)
            gdf_q4.to_file(out_q4, driver="GPKG")
            print(f"  {len(gdf_q4)} tiles → {out_q4}")
        except Exception as exc:
            print(f"  WARNING: Q4 2024 download failed ({exc}) — skipping")
    if done(out_q4):
        latency_norm_q4 = _aggregate(out_q4)

    return latency_norm_q3, latency_norm_q4


# ── Step 5: Road network ──────────────────────────────────────────────────────

def build_road_fragility(tracts: gpd.GeoDataFrame, force: bool = False,
                          skip_road: bool = False) -> pd.Series:
    out = DATA_PROCESSED / "road_tn_fragility.csv"
    if done(out) and not force:
        print(f"  Loading cached road fragility")
        df = pd.read_csv(out, dtype={"GEOID": str})
        return df.set_index("GEOID")["road_fragility"]

    graphml_path = DATA_RAW / "tn_road_network.graphml"
    if skip_road and not done(graphml_path):
        print("  --skip-road set and no cached graphml — returning median-imputed road fragility")
        neutral = pd.Series(0.5, index=tracts["GEOID"])
        result = pd.DataFrame({"GEOID": tracts["GEOID"], "road_fragility": neutral.values})
        result.to_csv(out, index=False)
        return result.set_index("GEOID")["road_fragility"]

    step("5/9  Road network fragility (OSMnx betweenness + density)")

    if not done(graphml_path) or force:
        import pygris
        print("  Downloading TN road network via OSMnx (may take 1–2 hours)…")
        tn_polygon = pygris.states(year=2022).query("STATEFP == '47'").to_crs(
            CRS_WGS84).geometry.union_all()
        G = ox.graph_from_polygon(tn_polygon, network_type="drive")
        ox.save_graphml(G, graphml_path)
        print(f"  Saved {graphml_path}")
    else:
        print(f"  Loading cached {graphml_path}")
        G = ox.load_graphml(graphml_path)

    nodes, edges = ox.graph_to_gdfs(G)
    print(f"  Graph: {len(nodes)} nodes, {len(edges)} edges")

    print("  Computing betweenness centrality (k=500, ~30-40 min)…")
    import networkx as nx
    bc = nx.edge_betweenness_centrality(G, weight="length", k=500)
    edges["betweenness"] = edges.index.map(bc)

    edges_proj = edges.to_crs(CRS_PROJECT)
    edges_proj["midpoint"] = edges_proj.geometry.interpolate(0.5, normalized=True)
    mp_gdf = gpd.GeoDataFrame(
        edges_proj[["betweenness", "length"]].copy(),
        geometry=edges_proj["midpoint"],
        crs=CRS_PROJECT,
    )
    joined = gpd.sjoin(mp_gdf, tracts[["GEOID", "geometry"]], how="left",
                        predicate="within")
    joined = joined.dropna(subset=["GEOID"])

    tract_bc = joined.groupby("GEOID")["betweenness"].max().rename("max_betweenness")
    tract_edge_count = joined.groupby("GEOID").size().rename("edge_count")
    tract_road_len = joined.groupby("GEOID")["length"].sum().rename("total_road_len_m")

    road_df = tracts.set_index("GEOID").join(tract_bc).join(tract_edge_count).join(
        tract_road_len)
    road_df["road_density"] = road_df["edge_count"] / (
        road_df["total_road_len_m"] / 1000).replace(0, np.nan)

    impute_with_median(road_df, "max_betweenness")
    impute_with_median(road_df, "road_density")
    bc_norm = z_score_normalize(road_df["max_betweenness"])
    rd_norm = z_score_normalize(road_df["road_density"], invert=True)
    road_fragility = W_ROAD_BETWEENNESS * bc_norm + W_ROAD_DENSITY * rd_norm

    result = pd.DataFrame({"GEOID": road_df.index, "road_fragility": road_fragility.values})
    result.to_csv(out, index=False)
    print(f"  road_fragility range [{road_fragility.min():.4f}, {road_fragility.max():.4f}]")
    return result.set_index("GEOID")["road_fragility"]


# ── Step 6: Power grid ────────────────────────────────────────────────────────

def build_power_grid(tracts: gpd.GeoDataFrame, force: bool = False) -> pd.Series:
    out = DATA_PROCESSED / "power_tn_grid.csv"
    if done(out) and not force:
        print(f"  Loading cached power grid fragility")
        df = pd.read_csv(out, dtype={"GEOID": str})
        return df.set_index("GEOID")["power_grid_norm"]

    step("6/9  Power grid fragility (HIFLD transmission lines)")
    tracts_wgs = tracts.to_crs(CRS_WGS84)
    xmin, ymin, xmax, ymax = tracts_wgs.total_bounds
    geometry_filter = {
        "geometryType": "esriGeometryEnvelope",
        "geometry": f"{xmin},{ymin},{xmax},{ymax}",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
    }
    lines = query_arcgis_feature_layer(
        url=HIFLD_TRANSMISSION_URL,
        where="STATUS = 'IN SERVICE'",
        out_fields="VOLTAGE,STATUS",
        geometry_filter=geometry_filter,
        max_records=HIFLD_MAX_RECORDS,
    )

    if len(lines) == 0:
        print("  WARNING: No transmission lines returned — using neutral power_grid_norm=0.5")
        result = pd.DataFrame({"GEOID": tracts["GEOID"], "power_grid_norm": 0.5})
        result.to_csv(out, index=False)
        return result.set_index("GEOID")["power_grid_norm"]

    lines = lines.to_crs(CRS_PROJECT)
    tracts_proj = tracts.copy()
    tracts_proj["area_km2"] = tracts_proj.geometry.area / SQFT_PER_SQKM
    area_map = tracts_proj.set_index("GEOID")["area_km2"]

    # Clip each line to tracts and sum clipped length per tract
    clipped = gpd.overlay(lines[["geometry"]], tracts[["GEOID", "geometry"]],
                           how="intersection", keep_geom_type=False)
    clipped["line_len_km"] = clipped.geometry.length / 1000  # feet → km: /3280.84
    # actually in proj feet: / 3280.84 to get km
    clipped["line_len_km"] = clipped.geometry.length / 3280.84
    line_km = clipped.groupby("GEOID")["line_len_km"].sum()

    trans = pd.DataFrame({"area_km2": area_map})
    trans = trans.join(line_km).fillna({"line_len_km": 0.0})
    trans["transmission_density"] = trans["line_len_km"] / trans["area_km2"].replace(0, np.nan)
    impute_with_median(trans, "transmission_density")
    power_grid_norm = z_score_normalize(trans["transmission_density"], invert=True)
    power_grid_norm.name = "power_grid_norm"

    result = pd.DataFrame({"GEOID": power_grid_norm.index,
                            "power_grid_norm": power_grid_norm.values})
    result.to_csv(out, index=False)
    print(f"  {len(lines)} transmission segments → {out}")
    return result.set_index("GEOID")["power_grid_norm"]


# ── Step 7: ACS Coping Capacity ───────────────────────────────────────────────

def build_coping_capacity(force: bool = False) -> pd.DataFrame:
    out = DATA_PROCESSED / "acs_tn_demographics.csv"
    if done(out) and not force:
        print(f"  Loading cached ACS data")
        return pd.read_csv(out, dtype={"GEOID": str})

    step("7/9  ACS Coping Capacity demographics (2022 5-year)")
    import requests
    vars_str = ",".join(ACS_VARS)
    url = (f"https://api.census.gov/data/2022/acs/acs5"
           f"?get={vars_str},NAME&for=tract:*&in=state:{STATE_FIPS}%20county:*")
    resp = requests.get(url, timeout=120)
    resp.raise_for_status()
    data = resp.json()
    cols = data[0]
    rows = data[1:]
    df = pd.DataFrame(rows, columns=cols)
    df = df.rename(columns=ACS_RENAME)
    df["GEOID"] = df["state"] + df["county"] + df["tract"]

    for col in ACS_RENAME.values():
        df[col] = pd.to_numeric(df[col], errors="coerce")
        df.loc[df[col] == -666666666, col] = np.nan

    df.to_csv(out, index=False)
    print(f"  {len(df)} tracts → {out}")
    return df


# ── Step 8: Assemble HABRI ────────────────────────────────────────────────────

def assemble_habri(tracts: gpd.GeoDataFrame, hazard: gpd.GeoDataFrame,
                   tower_norm: pd.Series, latency_norm: pd.Series,
                   road_fragility: pd.Series, power_norm: pd.Series,
                   acs: pd.DataFrame, force: bool = False) -> gpd.GeoDataFrame:
    out_csv = DATA_PROCESSED / "habri_tn_composite.csv"
    out_gpkg = DATA_PROCESSED / "habri_tn_composite.gpkg"
    if done(out_csv) and not force:
        print(f"  Loading cached TN composite")
        return gpd.read_file(out_gpkg)

    step("8/9  Assemble HABRI composite index (TN)")

    # ── Infrastructure Fragility ──────────────────────────────────────────────
    infra = tracts[["GEOID", "geometry"]].copy()
    infra = infra.set_index("GEOID")
    infra["tower_density_norm"] = tower_norm
    infra["latency_norm"] = latency_norm
    infra["road_fragility"] = road_fragility
    infra["power_grid_norm"] = power_norm
    infra["I_F"] = (
        W_IF_TOWER_DENSITY   * infra["tower_density_norm"]
        + W_IF_LATENCY       * infra["latency_norm"]
        + W_IF_ROAD_CENTRALITY * infra["road_fragility"]
        + W_IF_POWER_GRID    * infra["power_grid_norm"]
    )

    # ── Coping Capacity ───────────────────────────────────────────────────────
    acs_cc = acs.copy()
    acs_cc["no_vehicle_rate"]   = acs_cc["no_vehicle"]        / acs_cc["total_workers"].replace(0, np.nan)
    acs_cc["mobile_only_rate"]  = acs_cc["mobile_only_internet"] / acs_cc["total_hh_internet"].replace(0, np.nan)
    acs_cc["disability_rate"]   = (acs_cc["disability_18_64"] + acs_cc["disability_65plus"]) / acs_cc["total_population"].replace(0, np.nan)
    acs_cc = acs_cc.set_index("GEOID")
    for col in ["no_vehicle_rate", "mobile_only_rate", "disability_rate",
                "median_household_income", "below_poverty_level"]:
        impute_with_median(acs_cc, col)
    acs_cc = acs_cc.reset_index()
    acs_cc = acs_cc.set_index("GEOID")
    acs_cc["no_vehicle_vuln"]  = z_score_normalize(acs_cc["no_vehicle_rate"])
    acs_cc["mobile_only_vuln"] = z_score_normalize(acs_cc["mobile_only_rate"])
    acs_cc["disability_vuln"]  = z_score_normalize(acs_cc["disability_rate"])
    acs_cc["income_vuln"]      = z_score_normalize(acs_cc["median_household_income"], invert=True)
    acs_cc["poverty_vuln"]     = z_score_normalize(acs_cc["below_poverty_level"])
    acs_cc["C_C"] = 0.20 * (acs_cc["no_vehicle_vuln"] + acs_cc["mobile_only_vuln"]
                             + acs_cc["disability_vuln"] + acs_cc["income_vuln"]
                             + acs_cc["poverty_vuln"])

    # ── Merge ─────────────────────────────────────────────────────────────────
    hz = hazard.set_index("GEOID")[["H_E", "ifld_norm", "hrcn_norm", "lnds_norm"]]
    habri = infra.join(hz).join(acs_cc[["C_C", "no_vehicle_vuln", "mobile_only_vuln",
                                         "disability_vuln", "income_vuln", "poverty_vuln"]])
    habri["HABRI"] = (
        W_HAZARD_EXPOSURE * habri["H_E"]
        + W_INFRA_FRAGILITY * habri["I_F"]
        + W_COPING_CAPACITY * habri["C_C"]
    )
    habri["HABRI_quintile"] = pd.qcut(
        habri["HABRI"], q=5, duplicates="drop",
        labels=["Very Low", "Low", "Moderate", "High", "Very High"],
    )

    # ── K-means risk profiles ─────────────────────────────────────────────────
    from sklearn.cluster import KMeans
    from sklearn.preprocessing import StandardScaler
    features = ["no_vehicle_vuln", "disability_vuln", "mobile_only_vuln",
                "tower_density_norm", "road_fragility", "latency_norm"]
    X = habri[features].fillna(0.5).values
    X_scaled = StandardScaler().fit_transform(X)
    km = KMeans(n_clusters=3, random_state=42, n_init=10).fit(X_scaled)
    habri["cluster"] = km.labels_

    centroids = pd.DataFrame(km.cluster_centers_, columns=features)
    power_cols = ["no_vehicle_vuln", "disability_vuln", "mobile_only_vuln", "tower_density_norm"]
    transport_cols = ["road_fragility", "latency_norm"]
    centroids["power_z"] = centroids[power_cols].mean(axis=1)
    centroids["transport_z"] = centroids[transport_cols].mean(axis=1)

    def label_cluster(row):
        if row["power_z"] > 0.5 and row["transport_z"] > 0.5:
            return "Dual-Risk"
        if row["power_z"] >= row["transport_z"]:
            return "Power-Dependent"
        return "Transport-Fragile"

    cluster_labels = centroids.apply(label_cluster, axis=1)
    habri["risk_profile"] = habri["cluster"].map(cluster_labels)

    # ── Save ──────────────────────────────────────────────────────────────────
    habri_reset = habri.reset_index()
    county_name_by_fips = {
        f"{TN_CONFIG.state_fips}{county_fips}": county_name
        for county_name, county_fips in TN_CONFIG.county_fips.items()
    }
    habri_reset["state_fips"] = TN_CONFIG.state_fips
    habri_reset["state_abbr"] = "TN"
    habri_reset["state_name"] = TN_CONFIG.state_name
    habri_reset["county_fips"] = habri_reset["GEOID"].astype(str).str.zfill(11).str[:5]
    habri_reset["county_name"] = habri_reset["county_fips"].map(county_name_by_fips).fillna("Unknown")
    habri_reset.to_csv(out_csv, index=False)
    habri_reset.to_file(out_gpkg, driver="GPKG")
    print(f"  HABRI TN: {len(habri_reset)} tracts  "
          f"range [{habri_reset['HABRI'].min():.4f}, {habri_reset['HABRI'].max():.4f}]  "
          f"mean={habri_reset['HABRI'].mean():.4f}")
    print(f"  → {out_csv}")
    for p, n in habri_reset["risk_profile"].value_counts().items():
        pct = n / len(habri_reset) * 100
        print(f"     {p:20s}: {n:4d} ({pct:.1f}%)")
    return habri_reset


# ── Step 9: Figures ───────────────────────────────────────────────────────────

def make_figures(habri: gpd.GeoDataFrame, latency_norm_q4: pd.Series | None,
                 latency_norm_q3: pd.Series, force: bool = False) -> None:
    step("9/9  Generating figures")

    import matplotlib.pyplot as plt
    import matplotlib.lines as mlines
    import contextily as cx

    ETN_FIPS_5 = set(ETN_HELENE_COUNTY_FIPS.values())
    ETN_COLORS = {
        "Unicoi":     "#d62728",
        "Carter":     "#1f77b4",
        "Johnson":    "#9467bd",
        "Sullivan":   "#ff7f0e",
        "Washington": "#2ca02c",
        "Greene":     "#8c564b",
        "Cocke":      "#e377c2",
        "Hamblen":    "#bcbd22",
    }
    PROFILE_COLORS = {
        "Power-Dependent":  "#88CCEE",
        "Transport-Fragile": "#CC6677",
        "Dual-Risk":        "#DDCC77",
    }

    habri = habri.copy()
    if "county_fips" not in habri.columns:
        habri["county_fips"] = habri["GEOID"].str[0:5]

    # ── 4-panel statewide ─────────────────────────────────────────────────────
    out_4panel = DATA_PROCESSED / "habri_tn_statewide_4panel.png"
    if not done(out_4panel) or force:
        fig, axes = plt.subplots(2, 2, figsize=(24, 16))
        etn_boundary = habri[habri["county_fips"].isin(ETN_FIPS_5)].dissolve().boundary
        xmin, ymin, xmax, ymax = habri.total_bounds
        xpad = (xmax - xmin) * 0.01
        ypad = (ymax - ymin) * 0.01
        for ax, (col, title) in zip(axes.flat, [
            ("H_E", "Hazard Exposure (H_E)"),
            ("I_F", "Infrastructure Fragility (I_F)"),
            ("C_C", "Coping Capacity Deficit (C_C)"),
            ("HABRI", "HABRI Composite Score"),
        ]):
            ax.set_xlim(xmin - xpad, xmax + xpad)
            ax.set_ylim(ymin - ypad, ymax + ypad)
            try:
                cx.add_basemap(ax, crs=habri.crs, source=cx.providers.CartoDB.Positron,
                               alpha=0.30)
            except Exception:
                pass
            habri.plot(column=col, ax=ax, legend=True, cmap="cividis_r",
                       scheme="NaturalBreaks", k=5, edgecolor="none", alpha=0.88,
                       legend_kwds={"loc": "lower left", "fontsize": 9, "frameon": True},
                       missing_kwds={"color": "#cccccc"}, zorder=3)
            etn_boundary.plot(ax=ax, color="#CC6677", linewidth=1.8, zorder=6)
            ax.set_title(title, fontsize=13, fontweight="bold")
            ax.set_axis_off()
        plt.suptitle("HABRI — Tennessee\nAll 1,701 Census Tracts | Eastern TN Helene counties outlined",
                     fontsize=14, fontweight="bold")
        fig.subplots_adjust(left=0.02, right=0.98, top=0.91, bottom=0.02,
                            wspace=0.06, hspace=0.10)
        fig.savefig(out_4panel, dpi=300, bbox_inches="tight")
        plt.close(fig)
        print(f"  Saved: {out_4panel}")

    # ── Eastern TN profile map ────────────────────────────────────────────────
    out_prof = DATA_PROCESSED / "habri_tn_profiles.png"
    if not done(out_prof) or force:
        etn = habri[habri["county_fips"].isin(ETN_FIPS_5)].copy()
        if len(etn) > 0:
            etn_county_bounds = etn.dissolve(by="county_fips").boundary
            etn_outer = etn.dissolve().boundary
            xmin, ymin, xmax, ymax = etn.total_bounds
            xpad = (xmax - xmin) * 0.04
            ypad = (ymax - ymin) * 0.03

            fig, ax = plt.subplots(figsize=(20, 16))
            ax.set_xlim(xmin - xpad, xmax + xpad)
            ax.set_ylim(ymin - ypad, ymax + ypad)
            try:
                cx.add_basemap(ax, crs=etn.crs, source=cx.providers.CartoDB.Positron,
                               alpha=0.30)
            except Exception:
                pass
            for profile, color in PROFILE_COLORS.items():
                sub = etn[etn["risk_profile"] == profile]
                sub.plot(ax=ax, color=color, edgecolor="none", alpha=0.92, zorder=3)
            etn_county_bounds.plot(ax=ax, color="white", linewidth=4.5, zorder=8)
            etn_county_bounds.plot(ax=ax, color="black", linewidth=2.3, zorder=9)
            etn_outer.plot(ax=ax, color="black",   linewidth=7.0, zorder=10)
            etn_outer.plot(ax=ax, color="#ffd400", linewidth=3.2, zorder=11)

            # County name labels
            cty_centroids = etn.dissolve(by="county_fips").reset_index()
            cty_centroids["geometry"] = cty_centroids.representative_point()
            inv_fips = {v.lstrip("47"): k for k, v in ETN_HELENE_COUNTY_FIPS.items()}
            for _, row in cty_centroids.iterrows():
                name = inv_fips.get(row["county_fips"].lstrip("47"), "")
                ax.text(row.geometry.x, row.geometry.y, name, fontsize=11,
                        fontweight="bold", color="#1f1f1f", ha="center", va="center",
                        bbox=dict(facecolor="white", edgecolor="none", alpha=0.62, pad=0.20),
                        zorder=12)

            legend_handles = [
                mlines.Line2D([0], [0], marker="s", color="w", label=p,
                              markerfacecolor=c, markersize=16)
                for p, c in PROFILE_COLORS.items()
            ]
            ax.legend(handles=legend_handles, title="Risk Profile",
                      fontsize=14, title_fontsize=15, loc="upper right", frameon=True)
            ax.set_title("HABRI Vulnerability Profiles — Eastern Tennessee (Helene-Affected Counties)",
                         fontsize=16)
            ax.set_axis_off()
            fig.savefig(out_prof, dpi=300, bbox_inches="tight")
            plt.close(fig)
            print(f"  Saved: {out_prof}")

    # ── Helene validation scatter ─────────────────────────────────────────────
    if latency_norm_q4 is not None:
        out_val = DATA_PROCESSED / "habri_tn_helene_validation.png"
        if not done(out_val) or force:
            etn_habri = habri[habri["county_fips"].isin(ETN_FIPS_5)].set_index("GEOID")
            q3 = latency_norm_q3.rename("lat_q3")
            q4 = latency_norm_q4.rename("lat_q4")
            val = etn_habri[["HABRI", "I_F", "risk_profile"]].join(q3).join(q4).dropna()
            val["lat_delta"] = val["lat_q4"] - val["lat_q3"]

            fig, axes = plt.subplots(1, 2, figsize=(14, 6))
            for ax, xcol, xlabel in [
                (axes[0], "HABRI",    "HABRI Score (pre-Helene)"),
                (axes[1], "I_F",      "I_F Score (pre-Helene)"),
            ]:
                for profile, color in PROFILE_COLORS.items():
                    sub = val[val["risk_profile"] == profile]
                    ax.scatter(sub[xcol], sub["lat_delta"], color=color, alpha=0.65,
                               s=30, label=profile, zorder=3)
                rho, pval = spearmanr(val[xcol], val["lat_delta"])
                ax.axhline(0, color="grey", lw=1, ls="--")
                ax.set_xlabel(xlabel)
                ax.set_ylabel("Latency Δ (Q4 − Q3, normalized)")
                ax.set_title(f"ρ = {rho:.3f}  p = {pval:.3e}  n = {len(val)}")
                ax.legend(frameon=False, fontsize=9)
                ax.grid(alpha=0.3)
            plt.suptitle("Eastern TN — HABRI vs. Helene Latency Degradation (Q3→Q4 2024)",
                         fontweight="bold")
            fig.tight_layout()
            fig.savefig(out_val, dpi=200, bbox_inches="tight")
            plt.close(fig)

            rho_habri, pv_habri = spearmanr(val["HABRI"],  val["lat_delta"])
            rho_if,    pv_if    = spearmanr(val["I_F"],    val["lat_delta"])
            print(f"  ETN Helene validation:  "
                  f"HABRI ρ={rho_habri:.3f} (p={pv_habri:.3e})  "
                  f"I_F ρ={rho_if:.3f} (p={pv_if:.3e})  n={len(val)}")
            print(f"  Saved: {out_val}")


# ── Main ──────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build full HABRI composite for Tennessee.")
    p.add_argument("--force",      action="store_true", help="Rerun all steps")
    p.add_argument("--skip-road",  action="store_true",
                   help="Skip OSMnx road network download/compute (uses cached or neutral)")
    p.add_argument("--no-figures", action="store_true", help="Skip figure generation")
    return p.parse_args()


def main() -> None:
    args = parse_args()

    print(f"\n{'='*60}")
    print("HABRI — Tennessee Pipeline")
    print(f"{'='*60}")
    print(TN_CONFIG.summary())

    tracts     = build_study_tracts(force=args.force)
    hazard     = build_hazard(tracts, force=args.force)
    tower_norm = build_tower_density(tracts, force=args.force)
    lat_q3, lat_q4 = build_ookla(tracts, force=args.force)
    road_frag  = build_road_fragility(tracts, force=args.force,
                                       skip_road=args.skip_road)
    power_norm = build_power_grid(tracts, force=args.force)
    acs        = build_coping_capacity(force=args.force)

    habri = assemble_habri(tracts, hazard, tower_norm, lat_q3, road_frag,
                           power_norm, acs, force=args.force)

    if not args.no_figures:
        make_figures(habri, lat_q4, lat_q3, force=args.force)

    print(f"\n{'='*60}")
    print("Tennessee HABRI complete.")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
