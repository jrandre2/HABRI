#!/usr/bin/env python3
"""Build a January 2026 current-conditions HABRI index without altering the baseline."""

from __future__ import annotations

import argparse
import os
import math
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
    CRS_PROJECT,
    CRS_WGS84,
    DATA_PROCESSED,
    DATA_RAW,
    W_COPING_CAPACITY,
    W_HAZARD_EXPOSURE,
    W_IF_LATENCY,
    W_IF_ROAD_CENTRALITY,
    W_IF_TOWER_DENSITY,
    W_INFRA_FRAGILITY,
)
from src.utils import ensure_crs, impute_with_median, load_study_tracts, z_score_normalize

PERIOD_START = pd.Timestamp("2026-01-01T00:00:00Z")
PERIOD_END = pd.Timestamp("2026-02-01T00:00:00Z")
VERSION_TAG = "2026_01"
TILE_ZOOM = 16
HABRI_QUINTILE_LABELS = ["Very Low", "Low", "Moderate", "High", "Very High"]


def parse_bool(series: pd.Series) -> pd.Series:
    values = series.astype(str).str.strip().str.lower()
    return values.isin({"true", "1", "t", "yes", "y"})


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
    parser = argparse.ArgumentParser(description="Build a current-conditions HABRI layer for Jan 2026.")
    parser.add_argument(
        "--input-csv",
        help="Path to FixedNetworkPerformance January 2026 CSV",
        default=None,
    )
    parser.add_argument(
        "--version-tag",
        default=VERSION_TAG,
        help="Version tag for generated outputs",
    )
    parser.add_argument(
        "--max-location-accuracy-m",
        type=float,
        default=None,
        help="Drop rows with attr_location_accuracy_m greater than this threshold (meters).",
    )
    return parser.parse_args()


def latlon_to_tile_indices(
    latitudes: pd.Series,
    longitudes: pd.Series,
    zoom: int,
) -> tuple[np.ndarray, np.ndarray]:
    n = 2 ** zoom
    lat = np.clip(latitudes.to_numpy(dtype=float), -85.05112878, 85.05112878)
    lon = np.clip(longitudes.to_numpy(dtype=float), -180.0, 180.0)

    x_float = (lon + 180.0) / 360.0 * n
    lat_rad = np.radians(lat)
    y_float = (1.0 - np.arcsinh(np.tan(lat_rad)) / math.pi) / 2.0 * n

    tile_x = np.clip(x_float.astype(int), 0, n - 1)
    tile_y = np.clip(y_float.astype(int), 0, n - 1)
    return tile_x, tile_y


def tile_indices_to_centroid(
    tile_x: pd.Series,
    tile_y: pd.Series,
    zoom: int,
) -> tuple[np.ndarray, np.ndarray]:
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
    available = [col for col in column_schema["required"] if col in header.columns]
    missing = [col for col in column_schema["required"] if col not in header.columns]
    if missing:
        raise ValueError(f"Missing required columns in input CSV: {missing}")
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


def assign_habri_quintiles(values: pd.Series) -> pd.Series:
    non_null = values.dropna()
    if non_null.empty:
        return pd.Series([pd.NA] * len(values), index=values.index, dtype="category")

    requested_bins = min(5, non_null.nunique())
    requested_bins = max(2, requested_bins)

    for bins in range(requested_bins, 1, -1):
        try:
            return pd.qcut(values, q=bins, labels=HABRI_QUINTILE_LABELS[:bins], duplicates="drop")
        except ValueError:
            continue

    # Degenerate case: all values identical. Use a neutral category so this never fails.
    return pd.Series(
        pd.Categorical([HABRI_QUINTILE_LABELS[2]] * len(values), categories=[HABRI_QUINTILE_LABELS[2]], ordered=True),
        index=values.index,
    )


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
        jitter_val = np.nan
        if valid.any() and group.loc[valid, "avg_jitter_ms"].notna().any():
            jitter_val = float(np.average(group.loc[valid, "avg_jitter_ms"].fillna(0), weights=weights[valid]))

        if not valid.any():
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
        return pd.Series(
            {
                f"avg_latency_ms_{suffix}": float(np.average(group.loc[valid, "avg_lat_ms"], weights=valid_weights)),
                f"avg_download_mbps_{suffix}": float(
                    np.average(group.loc[valid, "avg_d_kbps"] / 1000.0, weights=valid_weights)
                ),
                f"avg_upload_mbps_{suffix}": float(
                    np.average(group.loc[valid, "avg_u_kbps"] / 1000.0, weights=valid_weights)
                ),
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


def assign_risk_profiles(habri: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    profile_features = habri[
        [
            "no_vehicle_vuln",
            "disability_vuln",
            "mobile_only_vuln",
            "tower_density_norm",
            "road_fragility",
            "latency_norm",
        ]
    ].copy()
    profile_features = profile_features.fillna(0.5)

    scaler = StandardScaler()
    features_scaled = scaler.fit_transform(profile_features)

    kmeans = KMeans(n_clusters=3, random_state=42, n_init=10)
    habri["cluster"] = kmeans.fit_predict(features_scaled)

    centroids_z = pd.DataFrame(
        kmeans.cluster_centers_,
        columns=profile_features.columns,
    )
    power_cols = ["no_vehicle_vuln", "disability_vuln", "mobile_only_vuln", "tower_density_norm"]
    transport_cols = ["road_fragility", "latency_norm"]
    centroids_z["power_z"] = centroids_z[power_cols].mean(axis=1)
    centroids_z["transport_z"] = centroids_z[transport_cols].mean(axis=1)

    profile_labels = {}
    for i, row in centroids_z.iterrows():
        if row["power_z"] > 0.5 and row["transport_z"] > 0.5:
            profile_labels[i] = "Dual-Risk"
        elif row["power_z"] > row["transport_z"]:
            profile_labels[i] = "Power-Dependent"
        else:
            profile_labels[i] = "Transport-Fragile"

    if len(set(profile_labels.values())) < 3:
        combined = centroids_z["power_z"] + centroids_z["transport_z"]
        sorted_clusters = combined.sort_values().index.tolist()
        profile_labels = {
            sorted_clusters[0]: "Transport-Fragile",
            sorted_clusters[1]: "Power-Dependent",
            sorted_clusters[2]: "Dual-Risk",
        }

    habri["risk_profile"] = habri["cluster"].map(profile_labels)
    return habri


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

    infra_baseline = gpd.read_file(DATA_PROCESSED / "infra_fragility.gpkg")
    infra_baseline["GEOID"] = infra_baseline["GEOID"].astype(str).str.zfill(11)
    lat_ms_col = f"avg_latency_ms_{version_tag}"
    lat_norm_col = f"latency_norm_{version_tag}"
    lat_norm_imputed_col = f"{lat_norm_col}_imputed"
    infra = infra_baseline[["GEOID", "tower_density_norm", "road_fragility", "geometry"]].merge(
        jan_tract[
            [
                "GEOID",
                lat_ms_col,
                lat_norm_col,
                lat_norm_imputed_col,
            ]
        ],
        on="GEOID",
        how="left",
    )

    # Update Jan 2026 latency to replace frozen baseline latency.
    infra["latency_norm"] = infra[lat_norm_col].fillna(infra[lat_norm_imputed_col])
    infra, _ = impute_with_median(infra, "latency_norm", "Ookla Latency (normalized) [2026-01]")
    infra["I_F"] = (
        W_IF_TOWER_DENSITY * infra["tower_density_norm"]
        + W_IF_LATENCY * infra["latency_norm"]
        + W_IF_ROAD_CENTRALITY * infra["road_fragility"]
    )

    infra_out = DATA_PROCESSED / f"infra_fragility_current_{version_tag}.gpkg"
    infra.to_file(infra_out, driver="GPKG")
    print(f"Saved versioned infrastructure fragility layer to {infra_out}")

    habri_baseline = gpd.read_file(DATA_PROCESSED / "habri_composite.gpkg")
    if "geometry" in habri_baseline.columns:
        habri_baseline = habri_baseline.drop(columns="geometry")
    habri_baseline["GEOID"] = habri_baseline["GEOID"].astype(str).str.zfill(11)
    habri = habri_baseline.merge(
        infra[
            [
                "GEOID",
                "latency_norm",
                lat_ms_col,
                "I_F",
                "tower_density_norm",
                "road_fragility",
            ]
        ],
        on="GEOID",
        how="left",
        suffixes=("", "_current"),
    )
    if "latency_norm_current" in habri.columns:
        habri["latency_norm"] = habri["latency_norm_current"]
        habri = habri.drop(columns=["latency_norm_current"])
    if "I_F_current" in habri.columns:
        habri["I_F"] = habri["I_F_current"]
        habri = habri.drop(columns=["I_F_current"])
    if "tower_density_norm_current" in habri.columns:
        habri["tower_density_norm"] = habri["tower_density_norm_current"]
        habri = habri.drop(columns=["tower_density_norm_current"])
    if "road_fragility_current" in habri.columns:
        habri["road_fragility"] = habri["road_fragility_current"]
        habri = habri.drop(columns=["road_fragility_current"])

    # Keep baseline H_E and C_C fixed by construction; only I_F changes with current latency.
    habri["HABRI"] = (
        W_HAZARD_EXPOSURE * habri["H_E"]
        + W_INFRA_FRAGILITY * habri["I_F"]
        + W_COPING_CAPACITY * habri["C_C"]
    )

    habri["HABRI_quintile"] = assign_habri_quintiles(habri["HABRI"])
    habri = assign_risk_profiles(habri)

    out_csv = DATA_PROCESSED / f"habri_current_{version_tag}.csv"
    out_gpkg = DATA_PROCESSED / f"habri_current_{version_tag}.gpkg"
    habri.drop(columns="geometry").to_csv(out_csv, index=False)
    habri.to_file(out_gpkg, driver="GPKG")
    print(f"Saved current-conditions HABRI layer to {out_csv}")
    print(f"Saved current-conditions HABRI GeoPackage to {out_gpkg}")


if __name__ == "__main__":
    main()
