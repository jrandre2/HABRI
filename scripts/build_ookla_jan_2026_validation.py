#!/usr/bin/env python3
"""Build January 2026 Ookla-derived validation artifacts without touching the baseline."""

from __future__ import annotations

import argparse
import os
import math
import sys
from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import spearmanr

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import CRS_PROJECT, CRS_WGS84, DATA_PROCESSED, DATA_RAW
from src.utils import ensure_crs, impute_with_median, load_study_tracts, z_score_normalize


PERIOD_START = pd.Timestamp("2026-01-01T00:00:00Z")
PERIOD_END = pd.Timestamp("2026-02-01T00:00:00Z")
VERSION_TAG = "2026_01"
TILE_ZOOM = 16


def resolve_input_csv(path_arg: str | None) -> Path:
    candidates: list[Path] = []
    if path_arg:
        candidates.append(Path(path_arg).expanduser())
    env_path = os.getenv("OOKLA_JAN2026_CSV")
    if env_path:
        candidates.append(Path(env_path).expanduser())
    candidates.extend(
        [
            Path.home().expanduser() / "Downloads" / "FixedNetworkPerformance_54196_2026-01-01.csv",
            DATA_RAW / "FixedNetworkPerformance_54196_2026-01-01.csv",
        ]
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Jan 2026 Ookla validation artifacts.")
    parser.add_argument(
        "--input-csv",
        default=None,
        help="Path to FixedNetworkPerformance January 2026 CSV.",
    )
    parser.add_argument(
        "--version-tag",
        default=VERSION_TAG,
        help="Version tag for generated outputs.",
    )
    parser.add_argument(
        "--max-location-accuracy-m",
        type=float,
        default=None,
        help="Drop rows with attr_location_accuracy_m greater than this threshold (meters).",
    )
    return parser.parse_args()


def parse_bool(series: pd.Series) -> pd.Series:
    values = series.astype(str).str.strip().str.lower()
    return values.isin({"true", "1", "t", "yes", "y"})


def latlon_to_tile_indices(latitudes: pd.Series, longitudes: pd.Series, zoom: int) -> tuple[np.ndarray, np.ndarray]:
    n = 2 ** zoom
    lat = np.clip(latitudes.to_numpy(dtype=float), -85.05112878, 85.05112878)
    lon = np.clip(longitudes.to_numpy(dtype=float), -180.0, 180.0)

    x_float = (lon + 180.0) / 360.0 * n
    lat_rad = np.radians(lat)
    y_float = (1.0 - np.arcsinh(np.tan(lat_rad)) / math.pi) / 2.0 * n

    tile_x = np.clip(x_float.astype(int), 0, n - 1)
    tile_y = np.clip(y_float.astype(int), 0, n - 1)
    return tile_x, tile_y


def tile_indices_to_centroid(tile_x: pd.Series, tile_y: pd.Series, zoom: int) -> tuple[np.ndarray, np.ndarray]:
    n = 2 ** zoom
    x = tile_x.to_numpy(dtype=float) + 0.5
    y = tile_y.to_numpy(dtype=float) + 0.5

    lon = x / n * 360.0 - 180.0
    lat_rad = np.arctan(np.sinh(math.pi * (1.0 - 2.0 * y / n)))
    lat = np.degrees(lat_rad)
    return lon, lat


def tile_indices_to_quadkey(tile_x: int, tile_y: int, zoom: int) -> str:
    digits: list[str] = []
    for level in range(zoom, 0, -1):
        digit = 0
        mask = 1 << (level - 1)
        if tile_x & mask:
            digit += 1
        if tile_y & mask:
            digit += 2
        digits.append(str(digit))
    return "".join(digits)


def load_jan_2026_tests(
    input_csv: Path,
    max_location_accuracy_m: float | None = None,
) -> pd.DataFrame:
    column_schema = {
        "required": [
            "ts_result",
            "attr_location_latitude",
            "attr_location_longitude",
            "attr_location_accuracy_m",
            "val_download_mbps",
            "val_upload_mbps",
            "val_latency_iqm_ms",
            "val_download_latency_iqm_ms",
            "val_upload_latency_iqm_ms",
            "id_device",
            "attr_provider_name_common",
            "is_network_vpn",
        ],
        "optional": [
            "val_jitter_ms",
        ],
    }

    if not input_csv.exists():
        raise FileNotFoundError(f"Input CSV not found: {input_csv}")

    header = pd.read_csv(input_csv, nrows=0)
    missing = [col for col in column_schema["required"] if col not in header.columns]
    if missing:
        raise ValueError(f"Missing required columns in input CSV: {missing}")
    available = list(column_schema["required"])
    available.extend(col for col in column_schema["optional"] if col in header.columns)

    df = pd.read_csv(input_csv, usecols=available, low_memory=False)
    df["ts_result"] = pd.to_datetime(df["ts_result"], errors="coerce", utc=True)

    numeric_columns = [
        "attr_location_latitude",
        "attr_location_longitude",
        "attr_location_accuracy_m",
        "val_download_mbps",
        "val_upload_mbps",
        "val_latency_iqm_ms",
        "val_download_latency_iqm_ms",
        "val_upload_latency_iqm_ms",
    ]
    if "val_jitter_ms" in df.columns:
        numeric_columns.append("val_jitter_ms")
    for column in numeric_columns:
        df[column] = pd.to_numeric(df[column], errors="coerce")
    if "val_jitter_ms" not in df.columns:
        df["val_jitter_ms"] = np.nan

    mask = (
        df["ts_result"].ge(PERIOD_START)
        & df["ts_result"].lt(PERIOD_END)
        & df["attr_location_latitude"].between(-90, 90)
        & df["attr_location_longitude"].between(-180, 180)
        & df["val_latency_iqm_ms"].notna()
        & df["val_download_mbps"].notna()
        & df["val_upload_mbps"].notna()
    )
    if max_location_accuracy_m is not None:
        mask &= df["attr_location_accuracy_m"].notna()
        mask &= df["attr_location_accuracy_m"] <= max_location_accuracy_m

    if "is_network_vpn" in df.columns:
        mask &= ~parse_bool(df["is_network_vpn"])

    filtered = df.loc[mask].copy()
    filtered["provider_name"] = filtered["attr_provider_name_common"].fillna("Unknown")
    return filtered


def build_tile_gdf(tests: pd.DataFrame) -> gpd.GeoDataFrame:
    tile_x_int, tile_y_int = latlon_to_tile_indices(
        tests["attr_location_latitude"],
        tests["attr_location_longitude"],
        TILE_ZOOM,
    )
    tests = tests.copy()
    tests["tile_x_int"] = tile_x_int
    tests["tile_y_int"] = tile_y_int

    tiles = (
        tests.groupby(["tile_x_int", "tile_y_int"], dropna=False)
        .agg(
            avg_d_kbps=("val_download_mbps", lambda s: int(round(s.mean() * 1000.0))),
            avg_u_kbps=("val_upload_mbps", lambda s: int(round(s.mean() * 1000.0))),
            avg_lat_ms=("val_latency_iqm_ms", "mean"),
            avg_lat_down_ms=("val_download_latency_iqm_ms", "mean"),
            avg_lat_up_ms=("val_upload_latency_iqm_ms", "mean"),
            avg_jitter_ms=("val_jitter_ms", "mean"),
            tests=("val_latency_iqm_ms", "size"),
            devices=("id_device", pd.Series.nunique),
            provider_count=("provider_name", pd.Series.nunique),
        )
        .reset_index()
    )

    lon, lat = tile_indices_to_centroid(tiles["tile_x_int"], tiles["tile_y_int"], TILE_ZOOM)
    tiles["tile_x"] = lon
    tiles["tile_y"] = lat
    tiles["quadkey"] = [
        tile_indices_to_quadkey(int(x), int(y), TILE_ZOOM)
        for x, y in zip(tiles["tile_x_int"], tiles["tile_y_int"])
    ]

    geometry = gpd.points_from_xy(tiles["tile_x"], tiles["tile_y"])
    gdf = gpd.GeoDataFrame(
        tiles[
            [
                "tile_x",
                "tile_y",
                "avg_d_kbps",
                "avg_u_kbps",
                "avg_lat_ms",
                "avg_lat_down_ms",
                "avg_lat_up_ms",
                "avg_jitter_ms",
                "tests",
                "devices",
                "provider_count",
                "quadkey",
            ]
        ],
        geometry=geometry,
        crs=CRS_WGS84,
    )
    return gdf


def aggregate_tiles_to_tracts(
    tiles_gdf: gpd.GeoDataFrame,
    tracts_gdf: gpd.GeoDataFrame,
    suffix: str,
) -> gpd.GeoDataFrame:
    joined = gpd.sjoin(
        ensure_crs(tiles_gdf, CRS_PROJECT),
        ensure_crs(tracts_gdf, CRS_PROJECT)[["GEOID", "geometry"]],
        how="inner",
        predicate="within",
    )

    def weighted_stats(group: pd.DataFrame) -> pd.Series:
        weights = group["tests"].fillna(0).astype(float)
        valid = weights.gt(0) & group["avg_lat_ms"].notna()
        has_jitter = "avg_jitter_ms" in group.columns

        if not valid.any():
            jitter_val = np.nan
            return pd.Series(
                {
                    f"avg_latency_ms_{suffix}": np.nan,
                    f"avg_download_mbps_{suffix}": np.nan,
                    f"avg_upload_mbps_{suffix}": np.nan,
                    f"avg_jitter_ms_{suffix}": jitter_val,
                    f"total_tests_{suffix}": int(weights.sum()),
                    f"total_devices_{suffix}": int(group["devices"].fillna(0).sum()),
                    f"tile_count_{suffix}": int(len(group)),
                }
            )

        valid_weights = weights[valid]
        jitter_val = np.nan
        if has_jitter and group.loc[valid, "avg_jitter_ms"].notna().any():
            jitter_vals = group.loc[valid, "avg_jitter_ms"].fillna(0).to_numpy(dtype=float)
            jitter_val = float(np.average(jitter_vals, weights=valid_weights))

        return pd.Series(
            {
                f"avg_latency_ms_{suffix}": float(np.average(group.loc[valid, "avg_lat_ms"], weights=valid_weights)),
                f"avg_download_mbps_{suffix}": float(np.average(group.loc[valid, "avg_d_kbps"] / 1000.0, weights=valid_weights)),
                f"avg_upload_mbps_{suffix}": float(np.average(group.loc[valid, "avg_u_kbps"] / 1000.0, weights=valid_weights)),
                f"avg_jitter_ms_{suffix}": jitter_val,
                f"total_tests_{suffix}": int(weights.sum()),
                f"total_devices_{suffix}": int(group["devices"].fillna(0).sum()),
                f"tile_count_{suffix}": int(len(group)),
            }
        )

    tract_stats = joined.groupby("GEOID").apply(weighted_stats, include_groups=False).reset_index()
    result = tracts_gdf[["GEOID", "geometry"]].merge(tract_stats, on="GEOID", how="left")

    latency_col = f"avg_latency_ms_{suffix}"
    norm_col = f"latency_norm_{suffix}"
    result[norm_col] = np.nan
    observed = result[latency_col].notna()
    if observed.any():
        result.loc[observed, norm_col] = z_score_normalize(result.loc[observed, latency_col])
    result[f"{norm_col}_imputed"] = result[norm_col]
    result, _ = impute_with_median(result, f"{norm_col}_imputed", f"Latency norm {suffix}")
    return result


def load_baseline_scores() -> pd.DataFrame:
    baseline = gpd.read_file(DATA_PROCESSED / "habri_composite.gpkg")
    if "geometry" in baseline.columns:
        baseline = baseline.drop(columns="geometry")
    baseline["GEOID"] = baseline["GEOID"].astype(str).str.zfill(11)
    return baseline


def compute_summary(validation: pd.DataFrame, version_tag: str) -> pd.DataFrame:
    latency_col = f"avg_latency_ms_{version_tag}"
    metric_pairs = [
        ("HABRI", "latency_delta_ms_vs_q3_2024"),
        ("HABRI", "latency_abs_delta_ms_vs_q3_2024"),
        ("I_F", "latency_delta_ms_vs_q3_2024"),
        ("I_F", "latency_abs_delta_ms_vs_q3_2024"),
        ("latency_norm", latency_col),
    ]

    rows: list[dict[str, float | int | str]] = []
    for left, right in metric_pairs:
        subset = validation[[left, right]].dropna()
        if len(subset) < 3:
            rho = np.nan
            p_value = np.nan
        else:
            rho, p_value = spearmanr(subset[left], subset[right])
        rows.append(
            {
                "left_metric": left,
                "right_metric": right,
                "n": int(len(subset)),
                "spearman_rho": rho,
                "p_value": p_value,
            }
        )

    overall = {
        "left_metric": "overall",
        "right_metric": "overall",
        "n": int(validation[latency_col].notna().sum()),
        "spearman_rho": np.nan,
        "p_value": np.nan,
        "median_latency_q3_2024_ms": float(validation["avg_latency_ms_q3_2024"].median()),
        f"median_latency_{version_tag}_ms": float(validation[latency_col].median()),
        "median_delta_ms": float(validation["latency_delta_ms_vs_q3_2024"].median()),
        "median_abs_delta_ms": float(validation["latency_abs_delta_ms_vs_q3_2024"].median()),
    }
    rows.append(overall)
    return pd.DataFrame(rows)


def add_fit_line(ax: plt.Axes, x: pd.Series, y: pd.Series) -> None:
    subset = pd.DataFrame({"x": x, "y": y}).dropna()
    if len(subset) < 2:
        return
    coeffs = np.polyfit(subset["x"], subset["y"], 1)
    xs = np.linspace(subset["x"].min(), subset["x"].max(), 100)
    ys = coeffs[0] * xs + coeffs[1]
    ax.plot(xs, ys, color="#9a3412", linewidth=2)


def make_validation_plot(validation: pd.DataFrame, output_path: Path) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(14, 6), constrained_layout=True)
    fig.patch.set_facecolor("#f4f1e8")

    left = validation[["HABRI", "latency_abs_delta_ms_vs_q3_2024"]].dropna()
    rho_left, _ = spearmanr(left["HABRI"], left["latency_abs_delta_ms_vs_q3_2024"])
    axes[0].scatter(
        left["HABRI"],
        left["latency_abs_delta_ms_vs_q3_2024"],
        s=14,
        alpha=0.45,
        color="#1f5f8b",
        edgecolors="none",
    )
    add_fit_line(axes[0], left["HABRI"], left["latency_abs_delta_ms_vs_q3_2024"])
    axes[0].set_title(f"Baseline HABRI vs absolute latency shift\nSpearman rho = {rho_left:.3f}, n = {len(left)}")
    axes[0].set_xlabel("HABRI (baseline Q3 2024)")
    axes[0].set_ylabel("Absolute latency change (ms)\nJanuary 2026 vs Q3 2024")
    axes[0].grid(alpha=0.2)

    right = validation[["I_F", "latency_abs_delta_ms_vs_q3_2024"]].dropna()
    rho_right, _ = spearmanr(right["I_F"], right["latency_abs_delta_ms_vs_q3_2024"])
    axes[1].scatter(
        right["I_F"],
        right["latency_abs_delta_ms_vs_q3_2024"],
        s=14,
        alpha=0.45,
        color="#b45309",
        edgecolors="none",
    )
    add_fit_line(axes[1], right["I_F"], right["latency_abs_delta_ms_vs_q3_2024"])
    axes[1].set_title(f"Baseline I_F vs absolute latency shift\nSpearman rho = {rho_right:.3f}, n = {len(right)}")
    axes[1].set_xlabel("Infrastructure Fragility (baseline Q3 2024)")
    axes[1].set_ylabel("Absolute latency change (ms)\nJanuary 2026 vs Q3 2024")
    axes[1].grid(alpha=0.2)

    fig.suptitle("HABRI validation against January 2026 fixed-network performance", fontsize=14, y=1.03)
    fig.savefig(output_path, dpi=200, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    DATA_RAW.mkdir(parents=True, exist_ok=True)
    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)

    args = parse_args()
    input_csv = resolve_input_csv(args.input_csv)
    version_tag = args.version_tag
    print(f"Reading raw fixed-network CSV from {input_csv}")
    tests = load_jan_2026_tests(
        input_csv=input_csv,
        max_location_accuracy_m=args.max_location_accuracy_m,
    )
    print(f"Retained {len(tests):,} January 2026 tests after filtering")

    jan_tiles = build_tile_gdf(tests)
    jan_tile_path = DATA_RAW / f"ookla_fixed_{version_tag}.gpkg"
    jan_tiles.to_file(jan_tile_path, driver="GPKG")
    print(f"Saved {len(jan_tiles):,} aggregated tiles to {jan_tile_path}")

    tracts = load_study_tracts()
    tracts["GEOID"] = tracts["GEOID"].astype(str).str.zfill(11)

    jan_tract = aggregate_tiles_to_tracts(jan_tiles, tracts, version_tag)
    jan_tract = jan_tract.sort_values("GEOID").reset_index(drop=True)

    jan_tract_csv_path = DATA_PROCESSED / f"ookla_tract_{version_tag}.csv"
    jan_tract_gpkg_path = DATA_PROCESSED / f"ookla_tract_{version_tag}.gpkg"
    jan_tract.drop(columns="geometry").to_csv(jan_tract_csv_path, index=False)
    jan_tract.to_file(jan_tract_gpkg_path, driver="GPKG")
    print(f"Saved tract-level January 2026 metrics to {jan_tract_csv_path}")
    print(f"Saved tract-level January 2026 GeoPackage to {jan_tract_gpkg_path}")

    baseline_tiles = gpd.read_file(DATA_RAW / "ookla_fixed_pre_helene.gpkg")
    baseline_tract = aggregate_tiles_to_tracts(baseline_tiles, tracts, "q3_2024")
    baseline_latency = baseline_tract[["GEOID", "avg_latency_ms_q3_2024"]]

    baseline_scores = load_baseline_scores()
    validation = baseline_scores.merge(jan_tract.drop(columns="geometry"), on="GEOID", how="left")
    validation = validation.merge(baseline_latency, on="GEOID", how="left")
    validation["latency_delta_ms_vs_q3_2024"] = (
        validation[f"avg_latency_ms_{version_tag}"] - validation["avg_latency_ms_q3_2024"]
    )
    validation["latency_abs_delta_ms_vs_q3_2024"] = validation["latency_delta_ms_vs_q3_2024"].abs()
    validation["latency_pct_change_vs_q3_2024"] = np.where(
        validation["avg_latency_ms_q3_2024"].gt(0),
        validation["latency_delta_ms_vs_q3_2024"] / validation["avg_latency_ms_q3_2024"],
        np.nan,
    )

    validation_csv_path = DATA_PROCESSED / f"habri_validation_{version_tag}.csv"
    validation.to_csv(validation_csv_path, index=False)
    print(f"Saved validation table to {validation_csv_path}")

    summary = compute_summary(validation, version_tag)
    summary_csv_path = DATA_PROCESSED / f"habri_validation_{version_tag}_summary.csv"
    summary.to_csv(summary_csv_path, index=False)
    print(f"Saved validation summary to {summary_csv_path}")

    plot_path = DATA_PROCESSED / f"habri_validation_{version_tag}.png"
    make_validation_plot(validation, plot_path)
    print(f"Saved validation plot to {plot_path}")


if __name__ == "__main__":
    main()
