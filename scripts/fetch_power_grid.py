#!/usr/bin/env python3
"""Fetch HIFLD electric transmission lines and compute a power-grid fragility layer.

This script adds an optional power-grid component to the HABRI Infrastructure
Fragility sub-index. It is intentionally separate from the baseline notebooks
so existing validated index scores are not altered.

What it produces
----------------
data/raw/hifld_transmission_lines_nc.geojson
    Raw transmission line polyline features for NC from HIFLD.

data/processed/power_grid_fragility.csv / .gpkg
    Tract-level transmission line density and normalized power-grid fragility.
    Columns:
      GEOID                     — 11-digit census tract FIPS
      transmission_line_km      — total km of in-service lines intersecting the tract
      transmission_density      — line-km per km² of tract area
      power_grid_norm           — z-score normalized, inverted:
                                  high density → low fragility score [0,1]
      max_voltage_kv            — max voltage (kV) of lines in tract (grid tier proxy)

Integration guidance
---------------------
To incorporate into I_F, adjust weights in src/config.py (must sum to 1.0):

    I_F = 0.25 * tower_density_norm
        + 0.25 * latency_norm
        + 0.30 * road_fragility
        + 0.20 * power_grid_norm

Usage
-----
    python scripts/fetch_power_grid.py
    python scripts/fetch_power_grid.py --force   # re-fetch even if cached
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import requests

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import (
    CRS_PROJECT,
    CRS_WGS84,
    DATA_PROCESSED,
    DATA_RAW,
    HIFLD_MAX_RECORDS,
    HIFLD_TRANSMISSION_FIELDS,
    HIFLD_TRANSMISSION_URL,
    NC_BBOX_WGS84,
    SQFT_PER_SQKM,
)
from src.utils import ensure_crs, impute_with_median, load_study_tracts, z_score_normalize


def fetch_transmission_lines() -> gpd.GeoDataFrame:
    """Download in-service electric transmission lines for NC from HIFLD.

    Uses a bounding-box spatial filter since the service has no state column.
    Paginates automatically until all features are retrieved.
    """
    minx, miny, maxx, maxy = NC_BBOX_WGS84
    geometry_filter = {
        "geometry": json.dumps({"xmin": minx, "ymin": miny, "xmax": maxx, "ymax": maxy,
                                 "spatialReference": {"wkid": 4326}}),
        "geometryType": "esriGeometryEnvelope",
        "spatialRel": "esriSpatialRelIntersects",
        "inSR": "4326",
    }

    all_features = []
    offset = 0
    print(f"  Querying HIFLD transmission lines for NC bounding box...")

    while True:
        params = {
            "where": "STATUS = 'IN SERVICE'",
            "outFields": HIFLD_TRANSMISSION_FIELDS,
            "f": "geojson",
            "resultOffset": offset,
            "resultRecordCount": HIFLD_MAX_RECORDS,
            "returnGeometry": "true",
            **geometry_filter,
        }
        resp = requests.get(HIFLD_TRANSMISSION_URL, params=params, timeout=120)
        resp.raise_for_status()
        data = resp.json()

        features = data.get("features", [])
        if not features:
            break
        all_features.extend(features)
        print(f"    Retrieved {len(all_features):,} features so far...")

        if len(features) < HIFLD_MAX_RECORDS:
            break
        offset += HIFLD_MAX_RECORDS

    if not all_features:
        raise RuntimeError("No transmission line features returned. Check URL or bbox.")

    geojson = {"type": "FeatureCollection", "features": all_features}
    gdf = gpd.GeoDataFrame.from_features(geojson, crs=CRS_WGS84)
    print(f"  Retrieved {len(gdf):,} in-service transmission line segments")
    return gdf


def compute_transmission_density(
    lines_gdf: gpd.GeoDataFrame,
    tracts: gpd.GeoDataFrame,
) -> gpd.GeoDataFrame:
    """Intersect transmission lines with census tracts and compute line-km density."""
    lines = ensure_crs(lines_gdf, CRS_PROJECT)
    tracts_proj = ensure_crs(tracts, CRS_PROJECT)

    # Clip lines to exact tract boundaries (not just bbox)
    print("  Clipping lines to tract boundaries...")
    lines_clipped = gpd.overlay(lines, tracts_proj[["GEOID", "geometry"]], how="intersection")

    # Length in the projected CRS (US survey feet for EPSG:2264) → convert to km
    # 1 US survey foot = 0.0003048006096 km
    FEET_TO_KM = 0.0003048006096
    lines_clipped["line_km"] = lines_clipped.geometry.length * FEET_TO_KM

    # Parse voltage: HIFLD uses -999999 for unknown
    lines_clipped["voltage_kv"] = pd.to_numeric(lines_clipped.get("VOLTAGE", np.nan), errors="coerce")
    lines_clipped.loc[lines_clipped["voltage_kv"] < 0, "voltage_kv"] = np.nan

    # Aggregate per tract
    agg = (
        lines_clipped.groupby("GEOID")
        .agg(
            transmission_line_km=("line_km", "sum"),
            max_voltage_kv=("voltage_kv", "max"),
        )
        .reset_index()
    )

    # Tract areas in km²
    result = tracts_proj[["GEOID", "geometry"]].copy()
    result["area_sqkm"] = result.geometry.area / SQFT_PER_SQKM
    result = result.merge(agg, on="GEOID", how="left")
    result["transmission_line_km"] = result["transmission_line_km"].fillna(0.0)
    result["max_voltage_kv"] = result["max_voltage_kv"].fillna(0.0)

    result["transmission_density"] = (
        result["transmission_line_km"] / result["area_sqkm"].replace(0, np.nan)
    )

    covered = (result["transmission_line_km"] > 0).sum()
    print(f"  {covered:,} / {len(result):,} tracts contain transmission lines")
    print(f"  Density range: [{result['transmission_density'].min():.4f}, "
          f"{result['transmission_density'].max():.4f}] line-km/km²")
    return result


def normalize_power_grid(result: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Compute inverted z-score norm: higher density → lower fragility score."""
    density = result["transmission_density"]
    valid = density.notna() & (result["area_sqkm"] > 0)

    result["power_grid_norm"] = np.nan
    if valid.any():
        result.loc[valid, "power_grid_norm"] = z_score_normalize(density[valid], invert=True)

    result, _ = impute_with_median(result, "power_grid_norm", "Power grid fragility (normalized)")
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch HIFLD transmission lines and compute power-grid fragility.")
    parser.add_argument("--force", action="store_true", help="Re-fetch even if local file exists")
    return parser.parse_args()


def main() -> None:
    DATA_RAW.mkdir(parents=True, exist_ok=True)
    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)

    args = parse_args()
    raw_path = DATA_RAW / "hifld_transmission_lines_nc.geojson"
    out_csv = DATA_PROCESSED / "power_grid_fragility.csv"
    out_gpkg = DATA_PROCESSED / "power_grid_fragility.gpkg"

    print(f"\n{'='*60}")
    print("HABRI — Power Grid Fragility Layer (Transmission Lines)")
    print(f"{'='*60}\n")

    print("[1/3] Transmission line data")
    if raw_path.exists() and not args.force:
        print(f"  Loading cached file: {raw_path}")
        lines = gpd.read_file(raw_path)
    else:
        lines = fetch_transmission_lines()
        lines.to_file(raw_path, driver="GeoJSON")
        print(f"  Saved raw transmission lines → {raw_path}")

    print(f"\n[2/3] Computing transmission density per tract")
    tracts = load_study_tracts()
    tracts["GEOID"] = tracts["GEOID"].astype(str).str.zfill(11)
    result = compute_transmission_density(lines, tracts)

    print(f"\n[3/3] Normalizing and saving")
    result = normalize_power_grid(result)

    keep_cols = ["GEOID", "transmission_line_km", "transmission_density",
                 "power_grid_norm", "max_voltage_kv"]
    result[keep_cols].to_csv(out_csv, index=False)
    result[keep_cols + ["geometry"]].to_file(out_gpkg, driver="GPKG")
    print(f"  {out_csv}")
    print(f"  {out_gpkg}")
    print("\nTo integrate power_grid_norm into I_F, see the docstring at the top of this script.")


if __name__ == "__main__":
    main()
