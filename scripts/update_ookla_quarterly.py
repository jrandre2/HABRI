#!/usr/bin/env python3
"""Automated quarterly Ookla broadband data refresh for HABRI.

Downloads the latest Ookla Fixed Network Performance parquet from the public
S3 bucket, aggregates to NC census tracts, recomputes I_F and HABRI with the
new latency data, and saves versioned outputs.

Usage:
    # Explicit quarter
    python scripts/update_ookla_quarterly.py --year 2025 --quarter 2

    # Auto-detect latest available quarter on S3
    python scripts/update_ookla_quarterly.py

    # Force re-download even if local file already exists
    python scripts/update_ookla_quarterly.py --force

Output files (all version-tagged):
    data/raw/ookla_fixed_{tag}.gpkg
    data/processed/ookla_tract_{tag}.csv / .gpkg
    data/processed/infra_fragility_current_{tag}.gpkg
    data/processed/habri_current_{tag}.csv / .gpkg
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import pyarrow.parquet as pq

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import (
    CRS_PROJECT,
    CRS_WGS84,
    DATA_PROCESSED,
    DATA_RAW,
    OOKLA_COLUMNS,
    OOKLA_S3_BASE,
    STATE_FIPS,
    W_COPING_CAPACITY,
    W_HAZARD_EXPOSURE,
    W_IF_LATENCY,
    W_IF_POWER_GRID,
    W_IF_ROAD_CENTRALITY,
    W_IF_TOWER_DENSITY,
    W_INFRA_FRAGILITY,
    ookla_s3_path,
)
from src.utils import (
    compute_adaptive_if_weights,
    ensure_crs,
    impute_with_median,
    load_study_tracts,
    z_score_normalize,
)

# ── Constants ─────────────────────────────────────────────────────────────────

# NC bounding box (WGS84) for pre-filtering the national parquet
NC_BBOX = (-84.5, 33.7, -75.2, 36.7)

HABRI_QUINTILE_LABELS = ["Very Low", "Low", "Moderate", "High", "Very High"]


# ── Quarter resolution ────────────────────────────────────────────────────────

def current_quarter() -> tuple[int, int]:
    """Return (year, quarter) for the most recently completed Ookla quarter.

    Ookla publishes data roughly 6-8 weeks after quarter end. We conservatively
    return the quarter that ended at least 8 weeks ago.
    """
    now = datetime.now(tz=timezone.utc)
    # Walk back through quarters until we find one that ended 8+ weeks ago
    year, month = now.year, now.month
    for _ in range(8):
        month -= 3
        if month <= 0:
            month += 12
            year -= 1
        quarter = (month - 1) // 3 + 1
        quarter_end_month = quarter * 3
        quarter_end = datetime(year, quarter_end_month, 1, tzinfo=timezone.utc)
        if (now - quarter_end).days >= 56:  # 8 weeks
            return year, quarter
    # Fallback: Q3 2024 (known good)
    return 2024, 3


def version_tag(year: int, quarter: int) -> str:
    return f"{year}_q{quarter}"


# ── S3 download ───────────────────────────────────────────────────────────────

def download_ookla_parquet(year: int, quarter: int, force: bool = False) -> Path:
    """Download Ookla parquet from S3 and save filtered NC tiles as GeoPackage.

    Uses pyarrow directly (not pd.read_parquet) to avoid the pandas 2.3 +
    pyarrow ndim compat bug. Reads only needed columns and filters to NC bbox.

    Parameters
    ----------
    year, quarter : int
        Ookla data period.
    force : bool
        Re-download even if local file already exists.

    Returns
    -------
    Path to the saved GeoPackage file.
    """
    tag = version_tag(year, quarter)
    out_path = DATA_RAW / f"ookla_fixed_{tag}.gpkg"

    if out_path.exists() and not force:
        print(f"  Local file already exists: {out_path} (use --force to re-download)")
        return out_path

    s3_path = ookla_s3_path(year, quarter)
    print(f"  Reading from S3: {s3_path}")
    print("  (This may take several minutes — the parquet is ~600 MB)")

    try:
        import s3fs
        fs = s3fs.S3FileSystem(anon=True)
        table = pq.read_table(
            s3_path.replace("s3://", ""),
            filesystem=fs,
            columns=[c for c in OOKLA_COLUMNS if c in ["tile_x", "tile_y", "avg_d_kbps",
                                                         "avg_u_kbps", "avg_lat_ms",
                                                         "avg_lat_down_ms", "avg_lat_up_ms",
                                                         "tests", "devices", "quadkey"]],
        )
    except Exception as exc:
        print(f"  ERROR reading from S3: {exc}")
        print("  Ensure s3fs and pyarrow are installed and you have internet access.")
        raise

    # Convert column-by-column to avoid pyarrow/pandas compat issue
    df = pd.DataFrame()
    for col in table.schema.names:
        col_arr = table.column(col)
        try:
            df[col] = col_arr.to_pylist()
        except Exception:
            df[col] = pd.array(col_arr.to_pylist())

    print(f"  Downloaded {len(df):,} tiles (national)")

    # Filter to NC bounding box
    minx, miny, maxx, maxy = NC_BBOX
    mask = (
        df["tile_x"].between(minx, maxx)
        & df["tile_y"].between(miny, maxy)
        & df["avg_lat_ms"].notna()
    )
    df_nc = df.loc[mask].copy().reset_index(drop=True)
    print(f"  Retained {len(df_nc):,} tiles in NC bounding box")

    gdf = gpd.GeoDataFrame(
        df_nc,
        geometry=gpd.points_from_xy(df_nc["tile_x"], df_nc["tile_y"]),
        crs=CRS_WGS84,
    )

    gdf.to_file(out_path, driver="GPKG")
    print(f"  Saved NC tiles to {out_path}")
    return out_path


# ── Tract aggregation ─────────────────────────────────────────────────────────

def aggregate_to_tracts(
    tiles_gdf: gpd.GeoDataFrame,
    tracts_gdf: gpd.GeoDataFrame,
    tag: str,
) -> gpd.GeoDataFrame:
    """Spatially join Ookla tiles to census tracts and compute weighted averages."""
    tiles = ensure_crs(tiles_gdf, CRS_PROJECT)
    tracts = ensure_crs(tracts_gdf, CRS_PROJECT)

    joined = gpd.sjoin(tiles, tracts[["GEOID", "geometry"]], how="inner", predicate="within")

    def weighted_avg(group: pd.DataFrame) -> pd.Series:
        w = group["tests"].fillna(0).astype(float)
        valid = w.gt(0) & group["avg_lat_ms"].notna()
        if not valid.any():
            return pd.Series({
                f"avg_latency_ms_{tag}": np.nan,
                f"avg_download_mbps_{tag}": np.nan,
                f"avg_upload_mbps_{tag}": np.nan,
                f"total_tests_{tag}": int(w.sum()),
                f"tile_count_{tag}": len(group),
            })
        wv = w[valid]
        return pd.Series({
            f"avg_latency_ms_{tag}": float(np.average(group.loc[valid, "avg_lat_ms"], weights=wv)),
            f"avg_download_mbps_{tag}": float(np.average(group.loc[valid, "avg_d_kbps"] / 1000.0, weights=wv)),
            f"avg_upload_mbps_{tag}": float(np.average(group.loc[valid, "avg_u_kbps"] / 1000.0, weights=wv)),
            f"total_tests_{tag}": int(w.sum()),
            f"tile_count_{tag}": len(group),
        })

    tract_stats = joined.groupby("GEOID").apply(weighted_avg, include_groups=False).reset_index()
    result = tracts_gdf[["GEOID", "geometry"]].merge(tract_stats, on="GEOID", how="left")

    # Normalize latency
    lat_col = f"avg_latency_ms_{tag}"
    norm_col = f"latency_norm_{tag}"
    result[norm_col] = np.nan
    observed = result[lat_col].notna()
    if observed.any():
        result.loc[observed, norm_col] = z_score_normalize(result.loc[observed, lat_col])
    result[f"{norm_col}_imputed"] = result[norm_col]
    result, _ = impute_with_median(result, f"{norm_col}_imputed", f"Latency norm {tag}")

    return result


# ── HABRI recompute ───────────────────────────────────────────────────────────

def recompute_habri(tag: str, tract_stats: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Merge new latency into baseline I_F and recompute HABRI.

    Uses adaptive per-tract I_F weights if fcc_bdc_wired_fraction.csv is present,
    otherwise falls back to uniform weights from src/config.py.
    """
    lat_norm_col = f"latency_norm_{tag}"
    lat_norm_imputed_col = f"{lat_norm_col}_imputed"

    # Load baseline infrastructure (tower density, road fragility, power grid stay fixed)
    infra_baseline = gpd.read_file(DATA_PROCESSED / "infra_fragility.gpkg")
    infra_baseline["GEOID"] = infra_baseline["GEOID"].astype(str).str.zfill(11)

    # Carry p_wired and per-tract weights if already computed in infra_fragility.gpkg
    fixed_cols = ["GEOID", "tower_density_norm", "road_fragility", "geometry"]
    if "power_grid_norm" in infra_baseline.columns:
        fixed_cols.append("power_grid_norm")
    if "p_wired" in infra_baseline.columns:
        fixed_cols.append("p_wired")

    infra = infra_baseline[fixed_cols].merge(
        tract_stats[["GEOID", lat_norm_col, lat_norm_imputed_col,
                      f"avg_latency_ms_{tag}", f"total_tests_{tag}"]],
        on="GEOID",
        how="left",
    )
    infra["latency_norm"] = infra[lat_norm_col].fillna(infra[lat_norm_imputed_col])
    infra, _ = impute_with_median(infra, "latency_norm", f"Latency (normalized) [{tag}]")

    # Determine whether to use adaptive or uniform weights
    use_adaptive = "p_wired" in infra.columns and infra["p_wired"].notna().any()

    if "power_grid_norm" in infra.columns:
        if use_adaptive:
            weights = compute_adaptive_if_weights(infra["p_wired"])
            infra["I_F"] = (
                weights["w_tower"].values  * infra["tower_density_norm"]
                + W_IF_LATENCY             * infra["latency_norm"]
                + weights["w_road"].values * infra["road_fragility"]
                + W_IF_POWER_GRID          * infra["power_grid_norm"]
            )
        else:
            infra["I_F"] = (
                W_IF_TOWER_DENSITY    * infra["tower_density_norm"]
                + W_IF_LATENCY        * infra["latency_norm"]
                + W_IF_ROAD_CENTRALITY * infra["road_fragility"]
                + W_IF_POWER_GRID     * infra["power_grid_norm"]
            )
    else:
        # Fallback: 3-component model (pre-integration baseline)
        infra["I_F"] = (
            W_IF_TOWER_DENSITY    * infra["tower_density_norm"]
            + W_IF_LATENCY        * infra["latency_norm"]
            + W_IF_ROAD_CENTRALITY * infra["road_fragility"]
        )

    infra_out = DATA_PROCESSED / f"infra_fragility_current_{tag}.gpkg"
    infra.to_file(infra_out, driver="GPKG")
    print(f"  Saved infrastructure fragility ({tag}) → {infra_out}")

    # Load baseline composite and substitute new I_F
    habri_baseline = gpd.read_file(DATA_PROCESSED / "habri_composite.gpkg")
    if "geometry" in habri_baseline.columns:
        habri_baseline = habri_baseline.drop(columns="geometry")
    habri_baseline["GEOID"] = habri_baseline["GEOID"].astype(str).str.zfill(11)

    habri = habri_baseline.merge(
        infra[["GEOID", "I_F", "latency_norm", f"avg_latency_ms_{tag}"]],
        on="GEOID",
        how="left",
        suffixes=("", "_new"),
    )
    for col in ["I_F", "latency_norm"]:
        new_col = f"{col}_new"
        if new_col in habri.columns:
            habri[col] = habri[new_col]
            habri.drop(columns=[new_col], inplace=True)

    habri["HABRI"] = (
        W_HAZARD_EXPOSURE * habri["H_E"]
        + W_INFRA_FRAGILITY * habri["I_F"]
        + W_COPING_CAPACITY * habri["C_C"]
    )

    # Assign quintiles
    non_null = habri["HABRI"].dropna()
    if len(non_null) > 0:
        bins = min(5, non_null.nunique())
        for b in range(bins, 1, -1):
            try:
                habri["HABRI_quintile"] = pd.qcut(
                    habri["HABRI"], q=b, labels=HABRI_QUINTILE_LABELS[:b], duplicates="drop"
                )
                break
            except ValueError:
                continue

    return habri


# ── Main ──────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Quarterly Ookla broadband refresh for HABRI.")
    parser.add_argument("--year", type=int, default=None, help="Ookla data year (default: auto-detect)")
    parser.add_argument("--quarter", type=int, choices=[1, 2, 3, 4], default=None, help="Ookla quarter (default: auto-detect)")
    parser.add_argument("--force", action="store_true", help="Re-download even if local file exists")
    parser.add_argument("--skip-download", action="store_true", help="Skip S3 download, use existing local gpkg")
    return parser.parse_args()


def main() -> None:
    DATA_RAW.mkdir(parents=True, exist_ok=True)
    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)

    args = parse_args()

    if args.year and args.quarter:
        year, quarter = args.year, args.quarter
    else:
        year, quarter = current_quarter()
        print(f"Auto-detected latest available quarter: Q{quarter} {year}")

    tag = version_tag(year, quarter)
    print(f"\n{'='*60}")
    print(f"HABRI Quarterly Update — {tag}")
    print(f"{'='*60}\n")

    # Check prerequisite baselines exist
    for prereq in ["habri_composite.gpkg", "infra_fragility.gpkg", "study_tracts.gpkg"]:
        if not (DATA_PROCESSED / prereq).exists():
            print(f"ERROR: {prereq} not found. Run the HABRI notebooks first.")
            sys.exit(1)

    # Step 1: Download or load Ookla tiles
    print(f"[1/4] Ookla tile data (Q{quarter} {year})")
    gpkg_path = DATA_RAW / f"ookla_fixed_{tag}.gpkg"
    if args.skip_download and gpkg_path.exists():
        print(f"  Skipping download, loading {gpkg_path}")
        tiles_gdf = gpd.read_file(gpkg_path)
    else:
        gpkg_path = download_ookla_parquet(year, quarter, force=args.force)
        tiles_gdf = gpd.read_file(gpkg_path)

    print(f"  Loaded {len(tiles_gdf):,} NC tiles")

    # Step 2: Aggregate to tracts
    print(f"\n[2/4] Aggregating to census tracts")
    tracts = load_study_tracts()
    tracts["GEOID"] = tracts["GEOID"].astype(str).str.zfill(11)

    tract_stats = aggregate_to_tracts(tiles_gdf, tracts, tag)
    covered = tract_stats[f"avg_latency_ms_{tag}"].notna().sum()
    print(f"  {covered:,} / {len(tract_stats):,} tracts have Ookla coverage")

    csv_path = DATA_PROCESSED / f"ookla_tract_{tag}.csv"
    gpkg_path2 = DATA_PROCESSED / f"ookla_tract_{tag}.gpkg"
    tract_stats.drop(columns="geometry").to_csv(csv_path, index=False)
    tract_stats.to_file(gpkg_path2, driver="GPKG")
    print(f"  Saved tract aggregates → {csv_path}")

    # Step 3: Recompute HABRI
    print(f"\n[3/4] Recomputing HABRI with updated latency")
    habri = recompute_habri(tag, tract_stats)
    print(f"  HABRI range: [{habri['HABRI'].min():.3f}, {habri['HABRI'].max():.3f}]  "
          f"mean={habri['HABRI'].mean():.3f}")

    # Step 4: Save outputs
    print(f"\n[4/4] Saving outputs")
    out_csv = DATA_PROCESSED / f"habri_current_{tag}.csv"
    out_gpkg = DATA_PROCESSED / f"habri_current_{tag}.gpkg"

    habri.to_csv(out_csv, index=False)
    tracts_geom = tracts[["GEOID", "geometry"]]
    habri_geo = tracts_geom.merge(habri, on="GEOID", how="inner")
    habri_geo.to_file(out_gpkg, driver="GPKG")

    print(f"  {out_csv}")
    print(f"  {out_gpkg}")
    print(f"\nDone. Run the dashboard to compare: streamlit run app.py")


if __name__ == "__main__":
    main()
