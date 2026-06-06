"""Unit tests for the HABRI-GRID public-data pilot."""

import geopandas as gpd
import pandas as pd
from shapely.geometry import box

from src.habri_grid import (
    INTERVENTIONS,
    apply_intervention,
    build_proxy_asset_graph,
    compute_risk_forecast,
    rank_interventions,
)


def _sample_pilot_tracts() -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(
        {
            "GEOID": ["37001000100", "37001000200", "47179000100"],
            "state_fips": ["37", "37", "47"],
            "state_abbr": ["NC", "NC", "TN"],
            "county_fips": ["37001", "37001", "47179"],
            "county_name": ["Alpha", "Alpha", "Beta"],
            "county_label": ["Alpha, NC", "Alpha, NC", "Beta, TN"],
            "pilot_region": ["WNC", "WNC", "ETN"],
            "risk_profile": ["Power-Dependent", "Transport-Fragile", "Dual-Risk"],
            "H_E": [0.70, 0.45, 0.60],
            "I_F": [0.65, 0.50, 0.58],
            "C_C": [0.55, 0.35, 0.48],
            "HABRI": [0.64, 0.44, 0.56],
            "ifld_norm": [0.80, 0.45, 0.62],
            "hrcn_norm": [0.40, 0.30, 0.35],
            "lnds_norm": [0.72, 0.25, 0.48],
            "tower_density_norm": [0.60, 0.30, 0.52],
            "latency_norm": [0.55, 0.42, 0.50],
            "road_fragility": [0.62, 0.78, 0.56],
            "power_grid_norm": [0.70, 0.44, 0.60],
            "p_wired": [0.45, 0.80, 0.52],
            "w_tower": [0.28, 0.20, 0.25],
            "w_road": [0.27, 0.35, 0.30],
            "mobile_only_vuln": [0.52, 0.20, 0.33],
            "no_vehicle_vuln": [0.35, 0.15, 0.25],
            "disability_vuln": [0.40, 0.22, 0.28],
            "income_vuln": [0.46, 0.21, 0.30],
            "poverty_vuln": [0.44, 0.18, 0.29],
            "graph_exposure_score": [0.55, 0.40, 0.48],
            "graph_degree_centrality": [0.12, 0.10, 0.11],
            "substation_pagerank": [0.02, 0.02, 0.03],
            "wireless_reliance": [0.55, 0.20, 0.48],
            "longitude": [-82.5, -82.3, -82.4],
            "latitude": [35.6, 35.6, 36.2],
        },
        geometry=[
            box(-82.60, 35.50, -82.45, 35.68),
            box(-82.45, 35.50, -82.25, 35.68),
            box(-82.52, 36.10, -82.28, 36.32),
        ],
        crs="EPSG:4326",
    )


def test_build_proxy_asset_graph_includes_expected_node_types():
    tracts = _sample_pilot_tracts()
    nodes, edges = build_proxy_asset_graph(tracts)

    assert {"tract", "substation", "transmission_segment", "feeder", "backhaul_anchor", "cell_site"} <= set(
        nodes["node_type"]
    )
    assert edges["source"].notna().all()
    assert edges["target"].notna().all()
    assert (nodes["graph_pagerank"] > 0).all()


def test_compute_risk_forecast_bounds_outputs():
    forecast = compute_risk_forecast(_sample_pilot_tracts(), scenario_key="helene_replay")

    assert forecast["outage_probability"].between(0, 1).all()
    assert (forecast["expected_outage_hours"] >= 0).all()
    assert (forecast["restoration_lag_hours"] >= 0).all()
    assert (forecast["outage_probability_low"] <= forecast["outage_probability"]).all()
    assert (forecast["outage_probability_high"] >= forecast["outage_probability"]).all()


def test_apply_intervention_reduces_power_fragility_for_targets():
    tracts = _sample_pilot_tracts()
    treated = apply_intervention(
        tracts,
        intervention=INTERVENTIONS["generator_placement"],
        target_geoids=["37001000100"],
    )

    original = tracts.set_index("GEOID").loc["37001000100", "power_grid_norm"]
    updated = treated.set_index("GEOID").loc["37001000100", "power_grid_norm"]
    assert updated < original


def test_rank_interventions_returns_ranked_reductions():
    tracts = _sample_pilot_tracts()
    baseline = compute_risk_forecast(tracts, scenario_key="helene_replay")
    runs = rank_interventions(tracts, scenario_key="helene_replay", budget_musd=12.0, baseline_forecast=baseline)

    assert not runs.empty
    assert runs["scenario_rank"].tolist() == sorted(runs["scenario_rank"].tolist())
    assert (runs["outage_minutes_saved"] >= 0).all()
    assert (runs["target_tract_count"] >= 1).all()
