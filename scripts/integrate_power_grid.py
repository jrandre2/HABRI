#!/usr/bin/env python3
"""Integrate power_grid_norm into the HABRI Infrastructure Fragility sub-index.

This script updates the canonical baseline files to incorporate transmission-line
density as a fourth I_F component:

    I_F = 0.25 * tower_density_norm   (was 0.30)
        + 0.25 * latency_norm          (was 0.30)
        + 0.30 * road_fragility        (was 0.40)
        + 0.20 * power_grid_norm       (new)

The script also re-runs k-means vulnerability profiling (adding power_grid_norm
to the power-dependence feature set), regenerates the 4-panel static map, and
optionally re-runs all quarterly HABRI outputs with the new weights.

Prerequisites
-------------
- data/processed/infra_fragility.gpkg       (from notebook 03)
- data/processed/power_grid_fragility.gpkg  (from scripts/fetch_power_grid.py)
- data/processed/habri_composite.gpkg       (from notebook 04)
- data/processed/hazard_scores.gpkg         (from notebook 02)

Usage
-----
    python scripts/integrate_power_grid.py
    python scripts/integrate_power_grid.py --regen-quarterly   # also redo Q1-Q4 2025
    python scripts/integrate_power_grid.py --dry-run           # print stats, no writes
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import (
    CRS_WGS84,
    DATA_PROCESSED,
    W_COPING_CAPACITY,
    W_HAZARD_EXPOSURE,
    W_IF_LATENCY,
    W_IF_POWER_GRID,
    W_IF_ROAD_CENTRALITY,
    W_IF_TOWER_DENSITY,
    W_INFRA_FRAGILITY,
)
from src.utils import compute_adaptive_if_weights, impute_with_median

HABRI_QUINTILE_LABELS = ["Very Low", "Low", "Moderate", "High", "Very High"]

# Clustering features — identical to notebook 04; power_grid_norm is NOT added here.
# power_grid_norm changes the I_F score but doesn't define a new vulnerability archetype,
# so it does not belong in the profiling feature set.
POWER_COLS = [
    "no_vehicle_vuln", "disability_vuln", "mobile_only_vuln",
    "tower_density_norm",
]
TRANSPORT_COLS = ["road_fragility", "latency_norm"]
ALL_PROFILE_FEATURES = POWER_COLS + TRANSPORT_COLS

PROFILE_COLORS = {
    "Power-Dependent": "#88CCEE",
    "Transport-Fragile": "#CC6677",
    "Dual-Risk": "#DDCC77",
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _check_prereqs() -> None:
    required = [
        "infra_fragility.gpkg",
        "power_grid_fragility.gpkg",
        "habri_composite.gpkg",
    ]
    missing = [f for f in required if not (DATA_PROCESSED / f).exists()]
    if missing:
        print("ERROR: Missing prerequisite files:")
        for f in missing:
            print(f"  {DATA_PROCESSED / f}")
        sys.exit(1)


def _assign_profiles(habri: pd.DataFrame, kmeans: KMeans) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Assign cluster labels deterministically based on centroid positions.

    Assignment rules (match notebook 04 semantics):
    1. Dual-Risk         — cluster with highest combined (power_z + transport_z)
    2. Transport-Fragile — among the remaining two, the one with highest (transport_z − power_z)
    3. Power-Dependent   — the remaining cluster

    This is deterministic and handles the typical case where both non-Dual clusters
    initially test as Transport-Fragile in the strict threshold logic.
    """
    centroids_z = pd.DataFrame(kmeans.cluster_centers_, columns=ALL_PROFILE_FEATURES)
    centroids_z["power_z"] = centroids_z[POWER_COLS].mean(axis=1)
    centroids_z["transport_z"] = centroids_z[TRANSPORT_COLS].mean(axis=1)
    centroids_z["combined"] = centroids_z["power_z"] + centroids_z["transport_z"]
    centroids_z["transport_excess"] = centroids_z["transport_z"] - centroids_z["power_z"]

    profile_labels: dict[int, str] = {}

    # 1. Dual-Risk: highest combined fragility signal
    dual_idx = int(centroids_z["combined"].idxmax())
    profile_labels[dual_idx] = "Dual-Risk"

    remaining = [i for i in centroids_z.index if i != dual_idx]

    # 2. Transport-Fragile: most transport-dominated of the remaining two
    transport_idx = int(centroids_z.loc[remaining, "transport_excess"].idxmax())
    profile_labels[transport_idx] = "Transport-Fragile"

    # 3. Power-Dependent: the last cluster
    power_idx = [i for i in remaining if i != transport_idx][0]
    profile_labels[power_idx] = "Power-Dependent"

    habri["risk_profile"] = habri["cluster"].map(profile_labels)
    return habri, centroids_z


# ── Core integration ──────────────────────────────────────────────────────────

def integrate(dry_run: bool = False) -> pd.DataFrame:
    """Merge power_grid_norm, recompute I_F and HABRI, re-run k-means profiling.

    If data/processed/fcc_bdc_wired_fraction.csv is present, adaptive per-tract
    I_F weights are used (road weight scales with wired availability, tower weight
    scales inversely). Otherwise, uniform weights from src/config.py are used.
    Run scripts/fetch_fcc_bdc.py first to generate the BDC wired fraction file.
    """

    print(f"\n{'='*60}")
    print("HABRI — Power Grid Integration (v3 Baseline)")
    print(f"{'='*60}\n")

    # ── Step 1: load source files ─────────────────────────────────────────────
    print("[1/5] Loading baseline files")
    infra = gpd.read_file(DATA_PROCESSED / "infra_fragility.gpkg")
    infra["GEOID"] = infra["GEOID"].astype(str).str.zfill(11)

    pg = gpd.read_file(DATA_PROCESSED / "power_grid_fragility.gpkg")
    pg["GEOID"] = pg["GEOID"].astype(str).str.zfill(11)

    habri_orig = gpd.read_file(DATA_PROCESSED / "habri_composite.gpkg")
    habri_orig["GEOID"] = habri_orig["GEOID"].astype(str).str.zfill(11)

    print(f"  infra_fragility: {len(infra):,} tracts")
    print(f"  power_grid:      {len(pg):,} tracts  "
          f"(power_grid_norm range: [{pg.power_grid_norm.min():.4f}, {pg.power_grid_norm.max():.4f}])")
    print(f"  habri_composite: {len(habri_orig):,} tracts")

    # ── Load FCC BDC wired fraction (optional) ────────────────────────────────
    bdc_path = DATA_PROCESSED / "fcc_bdc_wired_fraction.csv"
    if bdc_path.exists():
        bdc = pd.read_csv(bdc_path, dtype={"GEOID": str})
        bdc["GEOID"] = bdc["GEOID"].str.zfill(11)
        # Drop stale p_wired column if already present from a prior run
        if "p_wired" in infra.columns:
            infra = infra.drop(columns=["p_wired"])
        infra = infra.merge(bdc[["GEOID", "p_wired"]], on="GEOID", how="left")
        n_with_bdc = infra["p_wired"].notna().sum()
        print(f"  FCC BDC p_wired: {n_with_bdc:,} tracts matched "
              f"(mean={infra['p_wired'].mean():.3f}, "
              f"filing: {bdc['bdc_filing_note'].iloc[0]})")
        use_adaptive = True
    else:
        print(f"  FCC BDC not found — using uniform I_F weights")
        print(f"  (Run scripts/fetch_fcc_bdc.py to enable adaptive weighting)")
        infra["p_wired"] = float("nan")
        use_adaptive = False

    # ── Step 2: merge and recompute I_F ──────────────────────────────────────
    print("\n[2/5] Recomputing Infrastructure Fragility (I_F)")

    # Drop columns that pg will overwrite (may already exist from a prior run)
    pg_cols = ["power_grid_norm", "transmission_line_km", "transmission_density", "max_voltage_kv"]
    infra = infra.drop(columns=[c for c in pg_cols if c in infra.columns])

    infra = infra.merge(
        pg[["GEOID"] + pg_cols],
        on="GEOID",
        how="left",
    )
    infra, n_imputed = impute_with_median(infra, "power_grid_norm", "Power grid norm")
    if n_imputed:
        print(f"  Imputed {n_imputed} tracts missing power_grid_norm")

    if use_adaptive:
        weights = compute_adaptive_if_weights(infra["p_wired"])
        infra["w_tower"]   = weights["w_tower"].values
        infra["w_road"]    = weights["w_road"].values
        infra["I_F"] = (
            infra["w_tower"]          * infra["tower_density_norm"]
            + W_IF_LATENCY            * infra["latency_norm"]
            + infra["w_road"]         * infra["road_fragility"]
            + W_IF_POWER_GRID         * infra["power_grid_norm"]
        )
        print(f"  Adaptive weights: road=[{infra['w_road'].min():.3f}, {infra['w_road'].max():.3f}], "
              f"tower=[{infra['w_tower'].min():.3f}, {infra['w_tower'].max():.3f}]")
    else:
        infra["w_tower"] = W_IF_TOWER_DENSITY
        infra["w_road"]  = W_IF_ROAD_CENTRALITY
        infra["I_F"] = (
            W_IF_TOWER_DENSITY    * infra["tower_density_norm"]
            + W_IF_LATENCY        * infra["latency_norm"]
            + W_IF_ROAD_CENTRALITY * infra["road_fragility"]
            + W_IF_POWER_GRID     * infra["power_grid_norm"]
        )
        print(f"  Uniform weights: tower={W_IF_TOWER_DENSITY}, latency={W_IF_LATENCY}, "
              f"road={W_IF_ROAD_CENTRALITY}, power={W_IF_POWER_GRID}")

    print(f"  I_F range: [{infra['I_F'].min():.4f}, {infra['I_F'].max():.4f}]  "
          f"mean={infra['I_F'].mean():.4f}")

    # ── Step 3: rebuild HABRI composite ──────────────────────────────────────
    print("\n[3/5] Rebuilding HABRI composite")

    # Start from habri_orig to keep H_E, C_C, and all sub-component columns
    habri = habri_orig.copy()
    if "geometry" in habri.columns:
        geometry = habri[["GEOID", "geometry"]].copy()
        habri = habri.drop(columns="geometry")
    else:
        geometry = None

    # Merge updated I_F and power_grid_norm into composite
    habri = habri.merge(
        infra[["GEOID", "I_F", "tower_density_norm", "latency_norm",
               "road_fragility", "power_grid_norm"]],
        on="GEOID",
        how="left",
        suffixes=("_old", ""),
    )
    # Drop old versions of overwritten columns
    for col in ["I_F", "tower_density_norm", "latency_norm", "road_fragility"]:
        old_col = f"{col}_old"
        if old_col in habri.columns:
            habri.drop(columns=[old_col], inplace=True)

    habri["HABRI"] = (
        W_HAZARD_EXPOSURE * habri["H_E"]
        + W_INFRA_FRAGILITY * habri["I_F"]
        + W_COPING_CAPACITY * habri["C_C"]
    )

    print(f"  HABRI range: [{habri['HABRI'].min():.4f}, {habri['HABRI'].max():.4f}]  "
          f"mean={habri['HABRI'].mean():.4f}  SD={habri['HABRI'].std():.4f}")

    # ── Step 4: re-run k-means profiling ─────────────────────────────────────
    print("\n[4/5] Re-running k-means vulnerability profiling (k=3)")

    features_df = habri[ALL_PROFILE_FEATURES].fillna(0.5)
    scaler = StandardScaler()
    features_scaled = scaler.fit_transform(features_df)

    kmeans = KMeans(n_clusters=3, random_state=42, n_init=10)
    habri["cluster"] = kmeans.fit_predict(features_scaled)
    habri, centroids_z = _assign_profiles(habri, kmeans)
    print(f"  Cluster centroids (power_z / transport_z / combined):")
    for i, row in centroids_z.iterrows():
        profile = habri.loc[habri["cluster"] == i, "risk_profile"].iloc[0]
        print(f"    Cluster {i} → {profile:20s}  "
              f"power_z={row['power_z']:+.3f}  transport_z={row['transport_z']:+.3f}  "
              f"combined={row['combined']:+.3f}")

    # Reassign quintiles
    non_null = habri["HABRI"].dropna()
    for b in range(5, 1, -1):
        try:
            habri["HABRI_quintile"] = pd.qcut(
                habri["HABRI"], q=b, labels=HABRI_QUINTILE_LABELS[:b], duplicates="drop"
            )
            break
        except ValueError:
            continue

    for profile in ["Dual-Risk", "Power-Dependent", "Transport-Fragile"]:
        n = (habri["risk_profile"] == profile).sum()
        mean_score = habri.loc[habri["risk_profile"] == profile, "HABRI"].mean()
        print(f"  {profile:20s}: {n:,} tracts ({n/len(habri)*100:.1f}%)  mean HABRI={mean_score:.3f}")

    if dry_run:
        print("\n[DRY RUN] No files written.")
        return habri

    # ── Step 5: save updated baseline files ───────────────────────────────────
    print("\n[5/5] Saving updated baseline files")

    # Updated infra_fragility (adds power_grid_norm, updates I_F)
    infra_out = DATA_PROCESSED / "infra_fragility.gpkg"
    infra.to_file(infra_out, driver="GPKG")
    print(f"  {infra_out}")

    # Updated habri_composite (CSV + GeoPackage)
    csv_out = DATA_PROCESSED / "habri_composite.csv"
    habri.to_csv(csv_out, index=False)
    print(f"  {csv_out}")

    if geometry is not None:
        habri_geo = geometry.merge(habri, on="GEOID", how="inner")
        gpkg_out = DATA_PROCESSED / "habri_composite.gpkg"
        habri_geo.to_file(gpkg_out, driver="GPKG")
        print(f"  {gpkg_out}")

    print("\nIntegration complete.")
    print("IMPORTANT: Update CLAUDE.md baseline stats and run validation to confirm results.")
    return habri


# ── Quarterly regeneration ────────────────────────────────────────────────────

def regen_quarterly() -> None:
    """Re-run quarterly HABRI outputs using the updated baseline and script."""
    # Find all existing Ookla tile gpkg files (already downloaded)
    ookla_files = sorted((DATA_PROCESSED.parent / "raw").glob("ookla_fixed_20*.gpkg"))
    # Skip the pre/post-Helene baseline files — only quarterly versioned files
    quarterly = [f for f in ookla_files if "_q" in f.stem and "pre_helene" not in f.stem
                 and "post_helene" not in f.stem]

    if not quarterly:
        print("No quarterly Ookla tile files found. Run update_ookla_quarterly.py first.")
        return

    print(f"\nRegenerating {len(quarterly)} quarterly HABRI outputs with updated weights...")
    script = PROJECT_ROOT / "scripts" / "update_ookla_quarterly.py"

    for qfile in quarterly:
        # Parse tag from filename, e.g. ookla_fixed_2025_q1.gpkg → year=2025 quarter=1
        parts = qfile.stem.replace("ookla_fixed_", "").split("_q")
        if len(parts) != 2:
            print(f"  Skipping unrecognised filename: {qfile.name}")
            continue
        year, quarter = int(parts[0]), int(parts[1])
        print(f"  Recomputing Q{quarter} {year}...")
        result = subprocess.run(
            [sys.executable, str(script),
             "--year", str(year), "--quarter", str(quarter), "--skip-download"],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            print(f"  ERROR: {result.stderr[-500:]}")
        else:
            print(f"  Done: habri_current_{year}_q{quarter}.csv")


# ── CLI ───────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Integrate power_grid_norm into HABRI I_F sub-index."
    )
    p.add_argument("--dry-run", action="store_true",
                   help="Print statistics only; do not write any files")
    p.add_argument("--regen-quarterly", action="store_true",
                   help="After integration, re-run all quarterly HABRI outputs")
    return p.parse_args()


def main() -> None:
    _check_prereqs()
    args = parse_args()
    integrate(dry_run=args.dry_run)
    if args.regen_quarterly and not args.dry_run:
        regen_quarterly()


if __name__ == "__main__":
    main()
