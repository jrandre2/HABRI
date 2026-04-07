#!/usr/bin/env python3
"""Fixed vs. mobile Ookla latency degradation — road proxy validation.

Tests whether road_fragility predicts wired broadband outages (type=fixed)
more than cellular outages (type=mobile) after Hurricane Helene (Q3→Q4 2024).

If road_fragility correlates with fixed latency degradation but not mobile,
that supports the road right-of-way colocation assumption. If both correlate
equally, the signal is geographic confounding (remote = bad everything).

Outputs
-------
data/processed/road_proxy_validation.csv    per-tract fixed/mobile delta + components
data/processed/road_proxy_validation.png    correlation comparison figure

Usage
-----
    python scripts/validate_road_proxy_mobile.py
    python scripts/validate_road_proxy_mobile.py --skip-download
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from scipy import stats

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import (
    CRS_PROJECT,
    CRS_WGS84,
    DATA_PROCESSED,
    DATA_RAW,
    OOKLA_COLUMNS,
)
from src.utils import ensure_crs, impute_with_median, load_study_tracts, z_score_normalize

NC_BBOX = (-84.5, 33.7, -75.2, 36.7)

OOKLA_MOBILE_S3_BASE = "s3://ookla-open-data/parquet/performance/type=mobile"

WNC_FIPS = {"37021", "37087", "37089", "37115", "37121", "37199"}


# ── S3 helpers ────────────────────────────────────────────────────────────────

def mobile_s3_path(year: int, quarter: int) -> str:
    month = quarter * 3 - 2  # Q1→1, Q2→4, Q3→7, Q4→10
    date_str = f"{year}-{month:02d}-01"
    return (
        f"{OOKLA_MOBILE_S3_BASE}/year={year}/quarter={quarter}/"
        f"{date_str}_performance_mobile_tiles.parquet"
    )


def download_mobile_parquet(year: int, quarter: int, force: bool = False) -> Path:
    tag = f"{year}_q{quarter}"
    out_path = DATA_RAW / f"ookla_mobile_{tag}.gpkg"

    if out_path.exists() and not force:
        print(f"  Already exists: {out_path}")
        return out_path

    s3_path = mobile_s3_path(year, quarter)
    print(f"  Reading from S3: {s3_path}")
    print("  (mobile parquet is typically 1–2 GB nationally — may take a few minutes)")

    import s3fs
    fs = s3fs.S3FileSystem(anon=True)
    table = pq.read_table(
        s3_path.replace("s3://", ""),
        filesystem=fs,
        columns=["tile_x", "tile_y", "avg_d_kbps", "avg_u_kbps",
                 "avg_lat_ms", "tests", "devices"],
    )

    df = pd.DataFrame()
    for col in table.schema.names:
        df[col] = table.column(col).to_pylist()

    print(f"  Downloaded {len(df):,} tiles (national)")

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
    print(f"  Saved → {out_path}")
    return out_path


# ── Tract aggregation ─────────────────────────────────────────────────────────

def aggregate_to_tracts(tiles_gdf: gpd.GeoDataFrame, tracts_gdf: gpd.GeoDataFrame,
                        tag: str) -> pd.DataFrame:
    tiles = ensure_crs(tiles_gdf, CRS_PROJECT)
    tracts = ensure_crs(tracts_gdf, CRS_PROJECT)

    joined = gpd.sjoin(tiles, tracts[["GEOID", "geometry"]], how="inner", predicate="within")

    def weighted_avg(group: pd.DataFrame) -> pd.Series:
        w = group["tests"].fillna(0).astype(float)
        valid = w.gt(0) & group["avg_lat_ms"].notna()
        if not valid.any():
            return pd.Series({f"avg_lat_ms_{tag}": np.nan, f"n_tests_{tag}": 0})
        return pd.Series({
            f"avg_lat_ms_{tag}": float(np.average(group.loc[valid, "avg_lat_ms"],
                                                    weights=w[valid])),
            f"n_tests_{tag}": int(w.sum()),
        })

    stats_df = joined.groupby("GEOID").apply(weighted_avg, include_groups=False).reset_index()

    # Normalize latency (z-score → CDF)
    lat_col = f"avg_lat_ms_{tag}"
    norm_col = f"latency_norm_{tag}"
    stats_df[norm_col] = np.nan
    obs = stats_df[lat_col].notna()
    if obs.any():
        stats_df.loc[obs, norm_col] = z_score_normalize(stats_df.loc[obs, lat_col])

    covered = stats_df[lat_col].notna().sum()
    print(f"  {covered:,} tracts have coverage (tag={tag})")
    return stats_df


# ── Correlation helpers ───────────────────────────────────────────────────────

def spearman(x: pd.Series, y: pd.Series, label: str, subset_mask=None) -> dict:
    if subset_mask is not None:
        x, y = x[subset_mask], y[subset_mask]
    mask = x.notna() & y.notna()
    n = mask.sum()
    if n < 30:
        return {"label": label, "rho": np.nan, "p": np.nan, "n": n}
    rho, p = stats.spearmanr(x[mask], y[mask])
    return {"label": label, "rho": rho, "p": p, "n": n}


# ── Main analysis ─────────────────────────────────────────────────────────────

def run(skip_download: bool = False) -> None:
    print(f"\n{'='*60}")
    print("HABRI — Road Proxy Validation: Fixed vs. Mobile")
    print(f"{'='*60}\n")

    tracts = load_study_tracts()
    tracts["GEOID"] = tracts["GEOID"].astype(str).str.zfill(11)

    # ── Download mobile tiles ──────────────────────────────────────────────────
    print("[1/4] Mobile Ookla tiles (Q3 2024 — pre-Helene)")
    if skip_download and (DATA_RAW / "ookla_mobile_2024_q3.gpkg").exists():
        print(f"  Loading existing file")
        mob_q3_tiles = gpd.read_file(DATA_RAW / "ookla_mobile_2024_q3.gpkg")
    else:
        download_mobile_parquet(2024, 3)
        mob_q3_tiles = gpd.read_file(DATA_RAW / "ookla_mobile_2024_q3.gpkg")

    print("[1/4] Mobile Ookla tiles (Q4 2024 — post-Helene)")
    if skip_download and (DATA_RAW / "ookla_mobile_2024_q4.gpkg").exists():
        print(f"  Loading existing file")
        mob_q4_tiles = gpd.read_file(DATA_RAW / "ookla_mobile_2024_q4.gpkg")
    else:
        download_mobile_parquet(2024, 4)
        mob_q4_tiles = gpd.read_file(DATA_RAW / "ookla_mobile_2024_q4.gpkg")

    # ── Aggregate to tracts ────────────────────────────────────────────────────
    print("\n[2/4] Aggregating to census tracts")
    mob_q3 = aggregate_to_tracts(mob_q3_tiles, tracts, "mob_q3_2024")
    mob_q4 = aggregate_to_tracts(mob_q4_tiles, tracts, "mob_q4_2024")

    # ── Build comparison dataframe ─────────────────────────────────────────────
    print("\n[3/4] Building comparison dataset")

    # Fixed latency data (already processed)
    fix_q3 = pd.read_csv(DATA_PROCESSED / "habri_composite.csv", dtype={"GEOID": str})
    fix_q3["GEOID"] = fix_q3["GEOID"].str.zfill(11)

    fix_q4 = pd.read_csv(DATA_PROCESSED / "ookla_tract_2024_q4.csv", dtype={"GEOID": str})
    fix_q4["GEOID"] = fix_q4["GEOID"].str.zfill(11)

    # Infrastructure components
    infra = gpd.read_file(DATA_PROCESSED / "infra_fragility.gpkg")
    infra["GEOID"] = infra["GEOID"].astype(str).str.zfill(11)

    df = infra[["GEOID", "road_fragility", "max_betweenness", "edge_count",
                "tower_density_norm", "power_grid_norm", "latency_norm"]].copy()

    # Fixed latency delta
    df = df.merge(fix_q4[["GEOID", "latency_norm_2024_q4"]], on="GEOID", how="left")
    df["fixed_delta"] = df["latency_norm_2024_q4"] - df["latency_norm"]

    # Mobile latency delta
    df = df.merge(mob_q3[["GEOID", "latency_norm_mob_q3_2024"]], on="GEOID", how="left")
    df = df.merge(mob_q4[["GEOID", "latency_norm_mob_q4_2024"]], on="GEOID", how="left")
    df["mobile_delta"] = df["latency_norm_mob_q4_2024"] - df["latency_norm_mob_q3_2024"]

    df["county5"] = df["GEOID"].str[:5]
    wnc_mask = df["county5"].isin(WNC_FIPS)

    # Road density norm
    from scipy.stats import norm as norm_dist
    edge_z = (df["edge_count"] - df["edge_count"].mean()) / df["edge_count"].std()
    df["road_density_norm"] = 1 - norm_dist.cdf(edge_z)

    coverage_fixed = df["fixed_delta"].notna().sum()
    coverage_mobile = df["mobile_delta"].notna().sum()
    coverage_wnc_fixed = df.loc[wnc_mask, "fixed_delta"].notna().sum()
    coverage_wnc_mobile = df.loc[wnc_mask, "mobile_delta"].notna().sum()
    print(f"  Fixed delta coverage:  {coverage_fixed:,} tracts statewide, "
          f"{coverage_wnc_fixed} WNC")
    print(f"  Mobile delta coverage: {coverage_mobile:,} tracts statewide, "
          f"{coverage_wnc_mobile} WNC")

    # Save comparison dataset
    out_csv = DATA_PROCESSED / "road_proxy_validation.csv"
    df.drop(columns="geometry", errors="ignore").to_csv(out_csv, index=False)
    print(f"  Saved → {out_csv}")

    # ── Correlations ──────────────────────────────────────────────────────────
    print("\n[4/4] Correlation results")
    print()

    predictors = [
        ("road_fragility",    df["road_fragility"],    "road_fragility (0.60·betweenness + 0.40·density)"),
        ("max_betweenness",   df["max_betweenness"],   "max_betweenness only"),
        ("road_density_norm", df["road_density_norm"], "road density only"),
        ("tower_density_norm",df["tower_density_norm"],"tower_density_norm"),
        ("power_grid_norm",   df["power_grid_norm"],   "power_grid_norm"),
    ]

    rows = []
    for key, vals, label in predictors:
        for scope, mask in [("Statewide", None), ("WNC only", wnc_mask)]:
            for conn, delta_col in [("Fixed", "fixed_delta"), ("Mobile", "mobile_delta")]:
                y = df[delta_col]
                r = spearman(vals, y, f"{label} | {conn} | {scope}", mask)
                r.update({"predictor": key, "connection": conn, "scope": scope})
                rows.append(r)

    results = pd.DataFrame(rows)

    def stars(p):
        if pd.isna(p): return ""
        if p < 0.001: return "***"
        if p < 0.01: return "**"
        if p < 0.05: return "*"
        return ""

    for scope in ["Statewide", "WNC only"]:
        print(f"  ── {scope} ──")
        sub = results[results["scope"] == scope]
        print(f"  {'Predictor':40s} {'Fixed rho':>10} {'Mobile rho':>10}  {'Diff':>8}")
        for key, _, label in predictors:
            row_f = sub[(sub["predictor"] == key) & (sub["connection"] == "Fixed")].iloc[0]
            row_m = sub[(sub["predictor"] == key) & (sub["connection"] == "Mobile")].iloc[0]
            rho_f = row_f["rho"]
            rho_m = row_m["rho"]
            diff = (rho_f - rho_m) if not pd.isna(rho_f) and not pd.isna(rho_m) else np.nan
            f_str = f"{rho_f:+.4f}{stars(row_f['p'])}" if not pd.isna(rho_f) else "    N/A"
            m_str = f"{rho_m:+.4f}{stars(row_m['p'])}" if not pd.isna(rho_m) else "    N/A"
            d_str = f"{diff:+.4f}" if not pd.isna(diff) else "    N/A"
            print(f"  {label:40s} {f_str:>13} {m_str:>13}  {d_str:>8}")
        print()

    # ── Figure ────────────────────────────────────────────────────────────────
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))

    for ax, scope in zip(axes, ["Statewide", "WNC only"]):
        sub = results[results["scope"] == scope]
        keys = [k for k, _, _ in predictors]
        labels_short = ["road_fragility", "betweenness", "road_density",
                        "tower_density", "power_grid"]
        x = np.arange(len(keys))
        width = 0.35

        rhos_f = [sub[(sub["predictor"]==k) & (sub["connection"]=="Fixed")]["rho"].values[0]
                  for k in keys]
        rhos_m = [sub[(sub["predictor"]==k) & (sub["connection"]=="Mobile")]["rho"].values[0]
                  for k in keys]

        bars_f = ax.bar(x - width/2, rhos_f, width, label="Fixed broadband", color="#2C3E50", alpha=0.85)
        bars_m = ax.bar(x + width/2, rhos_m, width, label="Mobile (cellular)", color="#E74C3C", alpha=0.85)
        ax.axhline(0, color="black", lw=0.8)
        ax.set_xticks(x)
        ax.set_xticklabels(labels_short, rotation=30, ha="right", fontsize=9)
        ax.set_ylabel("Spearman ρ with latency delta (Q3→Q4 2024)")
        ax.set_title(f"{scope}")
        ax.legend(frameon=False, fontsize=9)
        ax.grid(axis="y", alpha=0.3)
        ax.set_ylim(-0.6, 0.6)

    fig.suptitle("Road Proxy Validation: Fixed vs. Mobile Latency Degradation after Hurricane Helene",
                 fontsize=11, y=1.01)
    fig.tight_layout()

    out_png = DATA_PROCESSED / "road_proxy_validation.png"
    fig.savefig(out_png, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Figure saved → {out_png}")

    # ── Interpretation ────────────────────────────────────────────────────────
    print("\n── Interpretation ──")
    wnc_f = results[(results["scope"]=="WNC only") & (results["predictor"]=="road_fragility")
                    & (results["connection"]=="Fixed")]["rho"].values[0]
    wnc_m = results[(results["scope"]=="WNC only") & (results["predictor"]=="road_fragility")
                    & (results["connection"]=="Mobile")]["rho"].values[0]
    if not pd.isna(wnc_f) and not pd.isna(wnc_m):
        ratio = abs(wnc_f) / max(abs(wnc_m), 1e-6)
        print(f"  road_fragility | WNC fixed rho = {wnc_f:+.4f}, mobile rho = {wnc_m:+.4f}")
        print(f"  Fixed/mobile ratio: {ratio:.2f}x")
        if ratio > 1.5 and abs(wnc_f) > 0.15:
            print("  RESULT: road_fragility predicts fixed outages substantially more than mobile.")
            print("  This SUPPORTS the road right-of-way colocation assumption.")
        elif ratio < 1.1:
            print("  RESULT: road_fragility predicts fixed and mobile equally.")
            print("  This SUGGESTS geographic confounding, not road ROW mechanism.")
        else:
            print("  RESULT: Moderate separation — partial support for road ROW mechanism.")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Validate road proxy: fixed vs mobile degradation.")
    p.add_argument("--skip-download", action="store_true",
                   help="Skip S3 download if local mobile gpkg files already exist")
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run(skip_download=args.skip_download)
