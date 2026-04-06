#!/usr/bin/env python3
"""Fetch HIFLD electric substations and compute a power-grid fragility layer.

This script adds an optional power-grid component to the HABRI Infrastructure
Fragility sub-index. It is intentionally kept separate from the baseline
notebooks to avoid changing validated index scores.

What it produces
----------------
data/raw/hifld_substations_nc.geojson
    Raw substation point features for NC from HIFLD.

data/processed/power_grid_fragility.csv / .gpkg
    Tract-level substation density and normalized power-grid fragility score.
    Columns:
      GEOID                  — 11-digit census tract FIPS
      substation_count       — raw count of substations within the tract
      substation_density     — substations per km² (EPSG:2264 area)
      power_grid_norm        — z-score normalized, inverted: high density → low fragility score
      substation_max_volt    — maximum voltage (kV) of substations in tract (proxy for grid tier)

Integration guidance
---------------------
To incorporate into the I_F sub-index, adjust weights in src/config.py and
recompute I_F as a weighted average of the four components:

    I_F = w_tower * tower_density_norm
        + w_latency * latency_norm
        + w_road * road_fragility
        + w_power * power_grid_norm

Suggested weight rebalancing (sums to 1.0):
    tower:    0.25
    latency:  0.25
    road:     0.30
    power:    0.20

Usage
-----
    python scripts/fetch_power_grid.py
    python scripts/fetch_power_grid.py --state-fips 37  # explicit NC
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import (
    CRS_PROJECT,
    CRS_WGS84,
    DATA_PROCESSED,
    DATA_RAW,
    HIFLD_MAX_RECORDS,
    HIFLD_SUBSTATION_FIELDS,
    HIFLD_SUBSTATION_URL,
    SQFT_PER_SQKM,
    STATE_FIPS,
)
from src.utils import ensure_crs, impute_with_median, load_study_tracts, z_score_normalize


def fetch_substations(state_fips: str) -> gpd.GeoDataFrame:
    """Download electric substation points from HIFLD for the given state.

    Filters server-side to the target state FIPS to minimise download size.
    Paginates automatically (HIFLD caps responses at 2,000 features).
    """
    from src.utils import query_arcgis_feature_layer

    # HIFLD COUNTYFIPS is a 5-digit string e.g. "37021"; filter on first 2 digits
    # Use LIKE operator since server-side SUBSTRING is not universally supported
    where = f"STATE = '{state_fips}' OR COUNTYFIPS LIKE '{state_fips}%'"

    print(f"  Querying HIFLD substations for state {state_fips}...")
    gdf = query_arcgis_feature_layer(
        url=HIFLD_SUBSTATION_URL,
        where=where,
        out_fields=HIFLD_SUBSTATION_FIELDS,
        max_records=HIFLD_MAX_RECORDS,
    )

    if gdf.empty:
        print("  WARNING: No substations returned. Check the HIFLD URL or state filter.")
        return gdf

    # Keep only active or in-service substations (exclude decommissioned)
    if "STATUS" in gdf.columns:
        active_statuses = {"IN SERVICE", "UNDER CONSTRUCTION", "PROPOSED"}
        before = len(gdf)
        gdf = gdf[
            gdf["STATUS"].str.upper().isin(active_statuses)
            | gdf["STATUS"].isna()
        ].copy()
        removed = before - len(gdf)
        if removed:
            print(f"  Removed {removed} non-active substations")

    print(f"  Retrieved {len(gdf):,} substations")
    return gdf


def compute_substation_density(
    substations: gpd.GeoDataFrame,
    tracts: gpd.GeoDataFrame,
) -> gpd.GeoDataFrame:
    """Join substations to tracts and compute density (substations/km²)."""
    subs = ensure_crs(substations, CRS_PROJECT)
    tracts_proj = ensure_crs(tracts, CRS_PROJECT)

    # Spatial join: assign each substation to the tract it falls within
    joined = gpd.sjoin(subs, tracts_proj[["GEOID", "geometry"]], how="inner", predicate="within")

    # Aggregate per tract
    agg = (
        joined.groupby("GEOID")
        .agg(
            substation_count=("geometry", "count"),
            substation_max_volt=("MAX_VOLT", lambda x: pd.to_numeric(x, errors="coerce").max()),
        )
        .reset_index()
    )

    # Compute tract area in km²
    result = tracts_proj[["GEOID", "geometry"]].copy()
    result["area_sqkm"] = result.geometry.area / SQFT_PER_SQKM
    result = result.merge(agg, on="GEOID", how="left")
    result["substation_count"] = result["substation_count"].fillna(0).astype(int)
    result["substation_max_volt"] = result["substation_max_volt"].fillna(0.0)

    # Density: substations per km²
    result["substation_density"] = result["substation_count"] / result["area_sqkm"].replace(0, float("nan"))

    return result


def normalize_power_grid(result: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Compute inverted z-score norm: high substation density → low fragility."""
    density = result["substation_density"]

    # Tracts with zero substations stay at 0 density; they represent highest fragility
    # We impute missing (geometry issues) but keep zeros as real data
    has_density = density.notna() & (result["area_sqkm"] > 0)

    result["power_grid_norm"] = float("nan")
    if has_density.any():
        # invert=True: more substations (higher density) → lower fragility score
        result.loc[has_density, "power_grid_norm"] = z_score_normalize(
            density[has_density], invert=True
        )

    result, _ = impute_with_median(result, "power_grid_norm", "Power grid fragility (normalized)")
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch HIFLD substations and compute power-grid fragility.")
    parser.add_argument("--state-fips", default=STATE_FIPS, help="2-digit state FIPS (default: 37 for NC)")
    parser.add_argument("--force", action="store_true", help="Re-fetch even if local file exists")
    return parser.parse_args()


def main() -> None:
    DATA_RAW.mkdir(parents=True, exist_ok=True)
    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)

    args = parse_args()
    state_fips = args.state_fips

    raw_path = DATA_RAW / f"hifld_substations_{state_fips}.geojson"
    out_csv = DATA_PROCESSED / "power_grid_fragility.csv"
    out_gpkg = DATA_PROCESSED / "power_grid_fragility.gpkg"

    print(f"\n{'='*60}")
    print("HABRI — Power Grid Fragility Layer")
    print(f"{'='*60}\n")

    # Step 1: Fetch or load substations
    print("[1/3] Substation data")
    if raw_path.exists() and not args.force:
        print(f"  Loading cached file: {raw_path}")
        substations = gpd.read_file(raw_path)
    else:
        substations = fetch_substations(state_fips)
        if substations.empty:
            print("No substations found. Exiting.")
            sys.exit(1)
        substations.to_file(raw_path, driver="GeoJSON")
        print(f"  Saved raw substations → {raw_path}")

    # Step 2: Join to tracts and compute density
    print("\n[2/3] Computing substation density per tract")
    tracts = load_study_tracts()
    tracts["GEOID"] = tracts["GEOID"].astype(str).str.zfill(11)

    result = compute_substation_density(substations, tracts)
    coverage = (result["substation_count"] > 0).sum()
    print(f"  {coverage:,} / {len(result):,} tracts contain at least one substation")
    print(f"  Density range: [{result['substation_density'].min():.4f}, "
          f"{result['substation_density'].max():.4f}] substations/km²")

    # Step 3: Normalize
    print("\n[3/3] Normalizing and saving")
    result = normalize_power_grid(result)

    keep_cols = ["GEOID", "substation_count", "substation_density",
                 "power_grid_norm", "substation_max_volt"]
    result[keep_cols].to_csv(out_csv, index=False)
    result[keep_cols + ["geometry"]].to_file(out_gpkg, driver="GPKG")

    print(f"  {out_csv}")
    print(f"  {out_gpkg}")

    print("\nTo integrate power_grid_norm into I_F, see the docstring at the top of this script.")


if __name__ == "__main__":
    main()
