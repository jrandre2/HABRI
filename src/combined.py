"""Helpers for joint NC/TN HABRI layers on a shared standardized scale."""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import pandas as pd

from src.config import (
    COUNTY_FIPS,
    CRS_WGS84,
    DATA_PROCESSED,
    W_COPING_CAPACITY,
    W_HAZARD_EXPOSURE,
    W_INFRA_FRAGILITY,
)
from src.region import TN_CONFIG
from src.utils import z_score_normalize

HABRI_QUINTILE_LABELS = ["Very Low", "Low", "Moderate", "High", "Very High"]
STATE_ABBR = {"37": "NC", "47": "TN"}
STATE_NAME = {"37": "North Carolina", "47": "Tennessee"}
COUNTY_NAME_BY_FIPS = {
    **{f"37{county_fips}": county for county, county_fips in COUNTY_FIPS.items()},
    **{f"47{county_fips}": county for county, county_fips in TN_CONFIG.county_fips.items()},
}


def assign_habri_quintiles(values: pd.Series) -> pd.Series:
    """Assign robust quintile labels, even for degenerate inputs."""
    non_null = values.dropna()
    if non_null.empty:
        return pd.Series([pd.NA] * len(values), index=values.index, dtype="category")

    requested_bins = min(5, non_null.nunique())
    requested_bins = max(2, requested_bins)

    for bins in range(requested_bins, 1, -1):
        try:
            return pd.qcut(
                values,
                q=bins,
                labels=HABRI_QUINTILE_LABELS[:bins],
                duplicates="drop",
            )
        except ValueError:
            continue

    # Degenerate constant series: keep the output categorical and neutral.
    return pd.Series(
        pd.Categorical(
            [HABRI_QUINTILE_LABELS[2]] * len(values),
            categories=[HABRI_QUINTILE_LABELS[2]],
            ordered=True,
        ),
        index=values.index,
    )


def load_state_habri(path: Path) -> gpd.GeoDataFrame:
    """Load a HABRI GeoPackage and normalize the key identifiers."""
    gdf = gpd.read_file(path)
    gdf["GEOID"] = gdf["GEOID"].astype(str).str.zfill(11)
    return gdf


def _normalize_county_fips(value: object, geoid: str, state_fips: str) -> str:
    digits = "".join(ch for ch in str(value) if ch.isdigit())
    if len(digits) >= 5:
        return digits[-5:]
    if len(digits) == 3:
        return f"{state_fips}{digits}"
    return geoid[:5]


def harmonize_habri_schema(gdf: gpd.GeoDataFrame, *, state_fips: str | None = None) -> gpd.GeoDataFrame:
    """Add consistent state/county metadata to a state HABRI layer."""
    out = gdf.copy()
    out["GEOID"] = out["GEOID"].astype(str).str.zfill(11)
    inferred_state_fips = out["GEOID"].str[:2]
    if state_fips is None:
        state_fips = inferred_state_fips.mode().iloc[0]
    if not inferred_state_fips.eq(state_fips).all():
        raise ValueError(f"State FIPS mismatch while harmonizing layer: expected {state_fips}")

    if "county_fips" in out.columns:
        out["county_fips"] = [
            _normalize_county_fips(raw, geoid, state_fips)
            for raw, geoid in zip(out["county_fips"], out["GEOID"], strict=False)
        ]
    else:
        out["county_fips"] = out["GEOID"].str[:5]

    out["state_fips"] = state_fips
    out["state_abbr"] = STATE_ABBR.get(state_fips, state_fips)
    out["state_name"] = STATE_NAME.get(state_fips, "Unknown")
    out["county_name"] = out["county_fips"].map(COUNTY_NAME_BY_FIPS).fillna("Unknown")

    if isinstance(out, gpd.GeoDataFrame) and out.geometry.name in out.columns:
        if out.crs is None:
            raise ValueError("Input GeoDataFrame has no CRS.")
        out = out.to_crs(CRS_WGS84)

    return out


def build_joint_standardized_habri(
    nc: gpd.GeoDataFrame,
    tn: gpd.GeoDataFrame,
) -> gpd.GeoDataFrame:
    """Merge NC and TN HABRI layers and place them on one shared scale.

    This is a second-pass standardization across the two completed state outputs.
    The original state-local scores are preserved with a ``_state`` suffix.
    """
    nc_h = harmonize_habri_schema(nc, state_fips="37")
    tn_h = harmonize_habri_schema(tn, state_fips="47")
    combined = gpd.GeoDataFrame(
        pd.concat([nc_h, tn_h], ignore_index=True, sort=False),
        geometry="geometry",
        crs=CRS_WGS84,
    )

    for col in ["H_E", "I_F", "C_C", "HABRI"]:
        combined[f"{col}_state"] = combined[col]
    if "HABRI_quintile" in combined.columns:
        combined["HABRI_quintile_state"] = combined["HABRI_quintile"]

    for col in ["H_E", "I_F", "C_C"]:
        combined[col] = z_score_normalize(combined[f"{col}_state"])

    combined["HABRI"] = (
        W_HAZARD_EXPOSURE * combined["H_E"]
        + W_INFRA_FRAGILITY * combined["I_F"]
        + W_COPING_CAPACITY * combined["C_C"]
    )
    combined["HABRI_quintile"] = assign_habri_quintiles(combined["HABRI"])
    combined["HABRI_delta_vs_state"] = combined["HABRI"] - combined["HABRI_state"]
    combined["standardization_scope"] = "nc_tn_joint"
    combined["standardization_method"] = "joint_subindex_zscore_cdf"

    first_columns = [
        "GEOID",
        "state_fips",
        "state_abbr",
        "state_name",
        "county_fips",
        "county_name",
        "H_E",
        "I_F",
        "C_C",
        "HABRI",
        "HABRI_quintile",
        "risk_profile",
        "H_E_state",
        "I_F_state",
        "C_C_state",
        "HABRI_state",
        "HABRI_quintile_state",
        "HABRI_delta_vs_state",
        "standardization_scope",
        "standardization_method",
    ]
    ordered = [col for col in first_columns if col in combined.columns]
    ordered.extend(col for col in combined.columns if col not in ordered)
    return combined[ordered]


def load_joint_standardized_habri(processed_dir: Path = DATA_PROCESSED) -> gpd.GeoDataFrame:
    """Load the NC and TN baselines and return a shared-scale combined layer."""
    nc = load_state_habri(processed_dir / "habri_composite.gpkg")
    tn = load_state_habri(processed_dir / "habri_tn_composite.gpkg")
    return build_joint_standardized_habri(nc, tn)
