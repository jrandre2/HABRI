"""Unit tests for shared NC/TN HABRI helpers."""

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import Point

from src.combined import build_joint_standardized_habri, harmonize_habri_schema
from src.config import W_COPING_CAPACITY, W_HAZARD_EXPOSURE, W_INFRA_FRAGILITY


def test_harmonize_habri_schema_prefixes_three_digit_county_fips():
    gdf = gpd.GeoDataFrame(
        {
            "GEOID": ["37021000100"],
            "county_fips": ["021"],
            "H_E": [0.60],
            "I_F": [0.50],
            "C_C": [0.40],
            "HABRI": [0.52],
        },
        geometry=[Point(-82.5, 35.6)],
        crs="EPSG:4326",
    )

    result = harmonize_habri_schema(gdf, state_fips="37")

    assert result.loc[0, "county_fips"] == "37021"
    assert result.loc[0, "county_name"] == "Buncombe"
    assert result.loc[0, "state_abbr"] == "NC"
    assert result.loc[0, "state_name"] == "North Carolina"


def test_harmonize_habri_schema_derives_county_fips_when_missing():
    gdf = gpd.GeoDataFrame(
        {
            "GEOID": ["47019000100"],
            "H_E": [0.55],
            "I_F": [0.45],
            "C_C": [0.35],
            "HABRI": [0.47],
        },
        geometry=[Point(-82.1, 36.3)],
        crs="EPSG:4326",
    )

    result = harmonize_habri_schema(gdf, state_fips="47")

    assert result.loc[0, "county_fips"] == "47019"
    assert result.loc[0, "county_name"] == "Carter"
    assert result.loc[0, "state_abbr"] == "TN"


@pytest.fixture
def nc_small():
    return gpd.GeoDataFrame(
        {
            "GEOID": ["37021000100", "37087000100"],
            "county_fips": ["37021", "37087"],
            "H_E": [0.20, 0.80],
            "I_F": [0.30, 0.70],
            "C_C": [0.40, 0.60],
            "HABRI": [0.285, 0.725],
            "HABRI_quintile": ["Very Low", "Very High"],
            "risk_profile": ["Power-Dependent", "Dual-Risk"],
        },
        geometry=[Point(-82.5, 35.6), Point(-82.9, 35.4)],
        crs="EPSG:4326",
    )


@pytest.fixture
def tn_small():
    return gpd.GeoDataFrame(
        {
            "GEOID": ["47019000100", "47171000100"],
            "H_E": [0.35, 0.65],
            "I_F": [0.45, 0.55],
            "C_C": [0.25, 0.75],
            "HABRI": [0.3625, 0.6375],
            "HABRI_quintile": ["Low", "High"],
            "risk_profile": ["Transport-Fragile", "Power-Dependent"],
        },
        geometry=[Point(-82.1, 36.3), Point(-82.4, 36.1)],
        crs="EPSG:4326",
    )


def test_build_joint_standardized_habri_recomputes_shared_scale(nc_small, tn_small):
    combined = build_joint_standardized_habri(nc_small, tn_small)

    assert len(combined) == 4
    assert set(combined["state_abbr"]) == {"NC", "TN"}
    assert {"H_E_state", "I_F_state", "C_C_state", "HABRI_state", "HABRI_quintile_state"} <= set(combined.columns)
    assert combined["HABRI"].between(0, 1).all()

    expected = (
        W_HAZARD_EXPOSURE * combined["H_E"]
        + W_INFRA_FRAGILITY * combined["I_F"]
        + W_COPING_CAPACITY * combined["C_C"]
    )
    pd.testing.assert_series_equal(
        combined["HABRI"].reset_index(drop=True),
        expected.reset_index(drop=True),
        check_names=False,
    )

    assert combined["HABRI_quintile"].notna().all()
