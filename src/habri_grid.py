"""Public-data HABRI-GRID pilot for coupled power and communications resilience."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import geopandas as gpd
import networkx as nx
import numpy as np
import pandas as pd

from src.combined import assign_habri_quintiles
from src.config import (
    DATA_PROCESSED,
    W_COPING_CAPACITY,
    W_HAZARD_EXPOSURE,
    W_IF_LATENCY,
    W_IF_POWER_GRID,
    W_INFRA_FRAGILITY,
    WNC_COUNTY_FIPS,
)
from src.region import ETN_HELENE_COUNTY_FIPS
from src.utils import z_score_normalize

WNC_PILOT_COUNTY_FIPS = {f"37{county_fips}" for county_fips in WNC_COUNTY_FIPS.values()}
ETN_PILOT_COUNTY_FIPS = set(ETN_HELENE_COUNTY_FIPS.values())
PILOT_COUNTY_FIPS = WNC_PILOT_COUNTY_FIPS | ETN_PILOT_COUNTY_FIPS


@dataclass(frozen=True)
class ScenarioDefinition:
    key: str
    label: str
    flood_weight: float
    hurricane_weight: float
    landslide_weight: float
    stress_multiplier: float
    recovery_multiplier: float
    spillover_multiplier: float
    description: str


@dataclass(frozen=True)
class InterventionDefinition:
    key: str
    label: str
    cost_musd: float
    tracts_per_10m: int
    target_profiles: tuple[str, ...]
    selection_weights: dict[str, float]
    feature_shifts: dict[str, float]
    probability_multiplier: float = 1.0
    duration_multiplier: float = 1.0
    restoration_multiplier: float = 1.0
    exposure_multiplier: float = 1.0
    graph_shift: float = 0.0
    description: str = ""


@dataclass
class HABRIGridBundle:
    pilot_tracts: gpd.GeoDataFrame
    asset_graph_nodes: gpd.GeoDataFrame
    asset_graph_edges: pd.DataFrame
    risk_forecast: gpd.GeoDataFrame
    scenario_runs: pd.DataFrame


PILOT_SCENARIOS: dict[str, ScenarioDefinition] = {
    "helene_replay": ScenarioDefinition(
        key="helene_replay",
        label="Helene replay",
        flood_weight=0.48,
        hurricane_weight=0.22,
        landslide_weight=0.30,
        stress_multiplier=1.18,
        recovery_multiplier=1.12,
        spillover_multiplier=1.08,
        description="Flood-forward event profile aligned to the WNC and ETN Helene footprint.",
    ),
    "regional_flood": ScenarioDefinition(
        key="regional_flood",
        label="Regional flood",
        flood_weight=0.62,
        hurricane_weight=0.10,
        landslide_weight=0.28,
        stress_multiplier=1.10,
        recovery_multiplier=1.04,
        spillover_multiplier=1.02,
        description="Heavy inland flood with moderate landslide spillover and grid stress.",
    ),
    "winter_ice": ScenarioDefinition(
        key="winter_ice",
        label="Winter ice",
        flood_weight=0.20,
        hurricane_weight=0.08,
        landslide_weight=0.12,
        stress_multiplier=0.92,
        recovery_multiplier=1.20,
        spillover_multiplier=1.05,
        description="Lower hazard intensity but slower restoration due to grid and access constraints.",
    ),
}

INTERVENTIONS: dict[str, InterventionDefinition] = {
    "generator_placement": InterventionDefinition(
        key="generator_placement",
        label="Generator placement",
        cost_musd=6.0,
        tracts_per_10m=8,
        target_profiles=("Power-Dependent", "Dual-Risk"),
        selection_weights={
            "power_grid_norm": 0.45,
            "forecast_priority_score": 0.35,
            "C_C": 0.20,
        },
        feature_shifts={"power_grid_norm": -0.28},
        probability_multiplier=0.94,
        duration_multiplier=0.82,
        restoration_multiplier=0.76,
        exposure_multiplier=0.88,
        graph_shift=-0.05,
        description="Reduces tower and repeater dependence on brittle grid segments.",
    ),
    "sectionalizing": InterventionDefinition(
        key="sectionalizing",
        label="Sectionalizing and isolation",
        cost_musd=8.0,
        tracts_per_10m=6,
        target_profiles=("Power-Dependent", "Dual-Risk"),
        selection_weights={
            "I_F": 0.35,
            "power_grid_norm": 0.35,
            "forecast_priority_score": 0.30,
        },
        feature_shifts={"power_grid_norm": -0.14, "road_fragility": -0.05},
        probability_multiplier=0.88,
        duration_multiplier=0.86,
        restoration_multiplier=0.82,
        exposure_multiplier=0.90,
        graph_shift=-0.06,
        description="Cuts feeder-level outage propagation and isolates damaged segments faster.",
    ),
    "feeder_hardening": InterventionDefinition(
        key="feeder_hardening",
        label="Feeder hardening",
        cost_musd=10.0,
        tracts_per_10m=5,
        target_profiles=("Dual-Risk", "Power-Dependent"),
        selection_weights={
            "I_F": 0.40,
            "power_grid_norm": 0.25,
            "road_fragility": 0.15,
            "forecast_priority_score": 0.20,
        },
        feature_shifts={"power_grid_norm": -0.12, "road_fragility": -0.10},
        probability_multiplier=0.90,
        duration_multiplier=0.78,
        restoration_multiplier=0.80,
        exposure_multiplier=0.87,
        graph_shift=-0.08,
        description="Improves the resilience of the electric path serving at-risk tracts.",
    ),
    "route_redundancy": InterventionDefinition(
        key="route_redundancy",
        label="Route redundancy",
        cost_musd=9.0,
        tracts_per_10m=6,
        target_profiles=("Transport-Fragile", "Dual-Risk"),
        selection_weights={
            "road_fragility": 0.50,
            "p_wired": 0.25,
            "forecast_priority_score": 0.25,
        },
        feature_shifts={"road_fragility": -0.24, "p_wired": 0.12},
        probability_multiplier=0.92,
        duration_multiplier=0.80,
        restoration_multiplier=0.88,
        exposure_multiplier=0.90,
        graph_shift=-0.07,
        description="Adds alternate transport and backhaul paths for wired-heavy communities.",
    ),
    "tower_battery_backup": InterventionDefinition(
        key="tower_battery_backup",
        label="Tower battery backup",
        cost_musd=5.0,
        tracts_per_10m=10,
        target_profiles=("Power-Dependent", "Transport-Fragile", "Dual-Risk"),
        selection_weights={
            "tower_density_norm": 0.45,
            "forecast_priority_score": 0.30,
            "wireless_reliance": 0.25,
        },
        feature_shifts={"tower_density_norm": -0.18},
        probability_multiplier=0.90,
        duration_multiplier=0.88,
        restoration_multiplier=0.90,
        exposure_multiplier=0.85,
        graph_shift=-0.04,
        description="Extends cell-site uptime during localized grid loss.",
    ),
    "cell_on_wheels": InterventionDefinition(
        key="cell_on_wheels",
        label="Cell-on-wheels staging",
        cost_musd=4.0,
        tracts_per_10m=12,
        target_profiles=("Power-Dependent", "Transport-Fragile", "Dual-Risk"),
        selection_weights={
            "forecast_priority_score": 0.45,
            "mobile_only_vuln": 0.35,
            "wireless_reliance": 0.20,
        },
        feature_shifts={},
        probability_multiplier=0.96,
        duration_multiplier=0.84,
        restoration_multiplier=0.94,
        exposure_multiplier=0.72,
        graph_shift=-0.03,
        description="Provides temporary coverage where community dependence on wireless service is highest.",
    ),
}


def _sigmoid(values: pd.Series | np.ndarray) -> pd.Series:
    return pd.Series(1.0 / (1.0 + np.exp(-np.asarray(values))), index=getattr(values, "index", None))


def available_scenarios() -> list[ScenarioDefinition]:
    return list(PILOT_SCENARIOS.values())


def available_interventions() -> list[InterventionDefinition]:
    return list(INTERVENTIONS.values())


def load_habri_grid_pilot_tracts(processed_dir: Path = DATA_PROCESSED) -> gpd.GeoDataFrame:
    """Load the Helene pilot tracts for the Genesis-aligned HABRI-GRID workflow."""
    path = processed_dir / "habri_nc_tn_standardized.gpkg"
    if not path.exists():
        raise FileNotFoundError(f"Combined HABRI layer not found: {path}")

    gdf = gpd.read_file(path)
    gdf["GEOID"] = gdf["GEOID"].astype(str).str.zfill(11)
    gdf["county_fips"] = gdf["county_fips"].astype(str).str.zfill(5)

    pilot = gdf[gdf["county_fips"].isin(PILOT_COUNTY_FIPS)].copy()
    if pilot.empty:
        raise ValueError("No pilot tracts found for the configured WNC + ETN county set.")

    pilot["pilot_region"] = np.where(pilot["state_fips"] == "37", "WNC", "ETN")
    pilot["county_label"] = pilot["county_name"] + ", " + pilot["state_abbr"]
    tract_points = pilot.geometry.representative_point()
    pilot["longitude"] = tract_points.x
    pilot["latitude"] = tract_points.y
    pilot["wireless_reliance"] = 1.0 - pilot["p_wired"].fillna(pilot["p_wired"].median())

    return pilot


def _county_anchor_points(tracts: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    county_shapes = tracts[["county_fips", "county_name", "state_abbr", "pilot_region", "geometry"]].dissolve(
        by=["county_fips", "county_name", "state_abbr", "pilot_region"],
        as_index=False,
    )
    county_shapes["geometry"] = county_shapes.geometry.representative_point()
    return county_shapes


def _tract_adjacency_edges(tracts: gpd.GeoDataFrame) -> pd.DataFrame:
    left = tracts[["GEOID", "HABRI", "geometry"]].copy()
    right = tracts[["GEOID", "HABRI", "geometry"]].copy()

    joined = gpd.sjoin(left, right, how="inner", predicate="touches", lsuffix="left", rsuffix="right")
    joined = joined[joined["GEOID_left"] < joined["GEOID_right"]]
    if joined.empty:
        return pd.DataFrame(columns=["source", "target", "edge_type", "weight", "tract_geoid"])

    similarity = 1.0 - (joined["HABRI_left"] - joined["HABRI_right"]).abs()
    weights = 0.35 + 0.65 * similarity.clip(0.0, 1.0)
    return pd.DataFrame(
        {
            "source": "tract:" + joined["GEOID_left"],
            "target": "tract:" + joined["GEOID_right"],
            "edge_type": "adjacent_tract",
            "weight": weights,
            "tract_geoid": joined["GEOID_left"],
        }
    )


def build_proxy_asset_graph(tracts: gpd.GeoDataFrame) -> tuple[gpd.GeoDataFrame, pd.DataFrame]:
    """Build a public-data asset graph with tract, feeder, grid, and backhaul nodes."""
    tract_points = tracts.geometry.representative_point()
    county_points = _county_anchor_points(tracts)

    node_records: list[dict[str, object]] = []
    edge_records: list[dict[str, object]] = []

    for county in county_points.itertuples():
        county_mask = tracts["county_fips"] == county.county_fips
        county_score = (
            0.45 * tracts.loc[county_mask, "power_grid_norm"].mean()
            + 0.30 * tracts.loc[county_mask, "I_F"].mean()
            + 0.25 * tracts.loc[county_mask, "H_E"].mean()
        )
        node_records.append(
            {
                "node_id": f"substation:{county.county_fips}",
                "node_type": "substation",
                "tract_geoid": pd.NA,
                "county_fips": county.county_fips,
                "county_name": county.county_name,
                "state_abbr": county.state_abbr,
                "pilot_region": county.pilot_region,
                "data_quality": "proxy",
                "node_score": county_score,
                "geometry": county.geometry,
            }
        )

    for tract, point in zip(tracts.itertuples(), tract_points, strict=False):
        tract_node = {
            "tract_geoid": tract.GEOID,
            "county_fips": tract.county_fips,
            "county_name": tract.county_name,
            "state_abbr": tract.state_abbr,
            "pilot_region": tract.pilot_region,
            "geometry": point,
        }
        node_records.extend(
            [
                {
                    "node_id": f"tract:{tract.GEOID}",
                    "node_type": "tract",
                    "data_quality": "public",
                    "node_score": tract.HABRI,
                    **tract_node,
                },
                {
                    "node_id": f"transmission_segment:{tract.GEOID}",
                    "node_type": "transmission_segment",
                    "data_quality": "proxy",
                    "node_score": tract.power_grid_norm,
                    **tract_node,
                },
                {
                    "node_id": f"feeder:{tract.GEOID}",
                    "node_type": "feeder",
                    "data_quality": "proxy",
                    "node_score": 0.55 * tract.power_grid_norm + 0.45 * tract.I_F,
                    **tract_node,
                },
                {
                    "node_id": f"backhaul_anchor:{tract.GEOID}",
                    "node_type": "backhaul_anchor",
                    "data_quality": "proxy",
                    "node_score": 0.60 * tract.road_fragility + 0.40 * tract.p_wired,
                    **tract_node,
                },
                {
                    "node_id": f"cell_site:{tract.GEOID}",
                    "node_type": "cell_site",
                    "data_quality": "proxy",
                    "node_score": 0.70 * tract.tower_density_norm + 0.30 * tract.wireless_reliance,
                    **tract_node,
                },
            ]
        )

        edge_records.extend(
            [
                {
                    "source": f"substation:{tract.county_fips}",
                    "target": f"transmission_segment:{tract.GEOID}",
                    "edge_type": "bulk_power_feeds",
                    "weight": 0.80 + 0.20 * tract.power_grid_norm,
                    "tract_geoid": tract.GEOID,
                },
                {
                    "source": f"transmission_segment:{tract.GEOID}",
                    "target": f"feeder:{tract.GEOID}",
                    "edge_type": "distribution_path",
                    "weight": 0.75 + 0.25 * tract.power_grid_norm,
                    "tract_geoid": tract.GEOID,
                },
                {
                    "source": f"feeder:{tract.GEOID}",
                    "target": f"tract:{tract.GEOID}",
                    "edge_type": "serves_tract",
                    "weight": 0.70 + 0.30 * tract.I_F,
                    "tract_geoid": tract.GEOID,
                },
                {
                    "source": f"tract:{tract.GEOID}",
                    "target": f"backhaul_anchor:{tract.GEOID}",
                    "edge_type": "backhaul_dependency",
                    "weight": 0.65 + 0.35 * tract.road_fragility,
                    "tract_geoid": tract.GEOID,
                },
                {
                    "source": f"tract:{tract.GEOID}",
                    "target": f"cell_site:{tract.GEOID}",
                    "edge_type": "wireless_support",
                    "weight": 0.60 + 0.40 * tract.tower_density_norm,
                    "tract_geoid": tract.GEOID,
                },
            ]
        )

    adjacency_edges = _tract_adjacency_edges(tracts)
    if not adjacency_edges.empty:
        edge_records.extend(adjacency_edges.to_dict("records"))

    nodes = gpd.GeoDataFrame(node_records, geometry="geometry", crs=tracts.crs)
    edges = pd.DataFrame(edge_records)
    node_type_lookup = nodes.set_index("node_id")["node_type"]
    edges["source_type"] = edges["source"].map(node_type_lookup)
    edges["target_type"] = edges["target"].map(node_type_lookup)

    graph = nx.Graph()
    for row in nodes.itertuples():
        graph.add_node(row.node_id, node_type=row.node_type, weight=row.node_score)
    for row in edges.itertuples():
        graph.add_edge(row.source, row.target, weight=row.weight, edge_type=row.edge_type)

    degree = nx.degree_centrality(graph)
    pagerank = nx.pagerank(graph, weight="weight")
    nodes["graph_degree_centrality"] = nodes["node_id"].map(degree).fillna(0.0)
    nodes["graph_pagerank"] = nodes["node_id"].map(pagerank).fillna(0.0)

    return nodes, edges


def attach_graph_features(tracts: gpd.GeoDataFrame, nodes: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Aggregate node centrality back to the tract layer."""
    tract_nodes = nodes[nodes["tract_geoid"].notna()].copy()
    tract_summary = (
        tract_nodes.groupby("tract_geoid")
        .agg(
            graph_degree_centrality=("graph_degree_centrality", "mean"),
            graph_pagerank=("graph_pagerank", "mean"),
        )
        .reset_index()
        .rename(columns={"tract_geoid": "GEOID"})
    )
    substation_scores = (
        nodes[nodes["node_type"] == "substation"][["county_fips", "graph_pagerank"]]
        .rename(columns={"graph_pagerank": "substation_pagerank"})
    )

    out = tracts.merge(tract_summary, on="GEOID", how="left").merge(substation_scores, on="county_fips", how="left")
    out["graph_degree_centrality"] = out["graph_degree_centrality"].fillna(0.0)
    out["graph_pagerank"] = out["graph_pagerank"].fillna(0.0)
    out["substation_pagerank"] = out["substation_pagerank"].fillna(0.0)

    exposure_raw = (
        0.40 * out["graph_pagerank"]
        + 0.25 * out["graph_degree_centrality"]
        + 0.20 * out["substation_pagerank"]
        + 0.15 * out["I_F"]
    )
    out["graph_exposure_score"] = z_score_normalize(exposure_raw).fillna(0.5)
    return out


def _ensure_forecast_columns(tracts: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    out = tracts.copy()
    defaults = {
        "probability_multiplier": 1.0,
        "duration_multiplier": 1.0,
        "restoration_multiplier": 1.0,
        "exposure_multiplier": 1.0,
    }
    for column, value in defaults.items():
        if column not in out.columns:
            out[column] = value
    if "wireless_reliance" not in out.columns:
        out["wireless_reliance"] = 1.0 - out["p_wired"].fillna(out["p_wired"].median())
    return out


def compute_risk_forecast(
    tracts: gpd.GeoDataFrame,
    scenario_key: str = "helene_replay",
) -> gpd.GeoDataFrame:
    """Compute a public-data outage forecast using the HABRI-GRID graph features."""
    if scenario_key not in PILOT_SCENARIOS:
        raise KeyError(f"Unknown scenario: {scenario_key}")

    scenario = PILOT_SCENARIOS[scenario_key]
    forecast = _ensure_forecast_columns(tracts)

    p_wired = forecast["p_wired"].fillna(forecast["p_wired"].median())
    hazard_signal = (
        scenario.flood_weight * forecast["ifld_norm"]
        + scenario.hurricane_weight * forecast["hrcn_norm"]
        + scenario.landslide_weight * forecast["lnds_norm"]
    )
    dependency_signal = (
        0.38 * forecast["power_grid_norm"]
        + 0.22 * forecast["road_fragility"]
        + 0.18 * forecast["tower_density_norm"]
        + 0.22 * forecast["wireless_reliance"]
    )

    neighbor_signal = (
        0.55 * forecast["graph_exposure_score"]
        + 0.25 * forecast["substation_pagerank"].fillna(0.0)
        + 0.20 * forecast["graph_degree_centrality"].fillna(0.0)
    )
    community_signal = 0.60 * forecast["C_C"] + 0.40 * forecast["mobile_only_vuln"]

    outage_probability = _sigmoid(
        -2.05
        + 2.10 * hazard_signal * scenario.stress_multiplier
        + 1.05 * forecast["I_F"]
        + 0.65 * neighbor_signal * scenario.spillover_multiplier
        + 0.45 * community_signal
    )
    outage_probability = (outage_probability * forecast["probability_multiplier"]).clip(0.0, 1.0)

    expected_outage_hours = (
        6.0
        + 34.0 * outage_probability
        + 16.0 * dependency_signal * scenario.stress_multiplier
        + 12.0 * neighbor_signal * scenario.spillover_multiplier
        + 8.0 * community_signal
    ) * forecast["duration_multiplier"]

    restoration_lag_hours = (
        3.0
        + 22.0 * outage_probability
        + 18.0 * forecast["power_grid_norm"] * scenario.recovery_multiplier
        + 11.0 * forecast["road_fragility"] * scenario.recovery_multiplier
        + 10.0 * forecast["C_C"]
    ) * forecast["restoration_multiplier"]

    uncertainty = (
        0.08
        + 0.10 * dependency_signal
        + 0.08 * forecast["wireless_reliance"]
        + 0.06 * (1.0 - p_wired)
    ).clip(0.08, 0.30)

    critical_community_exposure = (
        expected_outage_hours * (0.60 * forecast["C_C"] + 0.40 * forecast["mobile_only_vuln"])
    ) * forecast["exposure_multiplier"]

    expected_outage_hours_low = (expected_outage_hours * (1.0 - uncertainty)).clip(lower=0.0)
    expected_outage_hours_high = expected_outage_hours * (1.0 + uncertainty)
    restoration_lag_hours_low = (restoration_lag_hours * (1.0 - uncertainty)).clip(lower=0.0)
    restoration_lag_hours_high = restoration_lag_hours * (1.0 + uncertainty)

    priority_raw = (
        0.45 * outage_probability
        + 0.30 * z_score_normalize(expected_outage_hours).fillna(0.5)
        + 0.25 * z_score_normalize(critical_community_exposure).fillna(0.5)
    )

    forecast["scenario_key"] = scenario.key
    forecast["scenario_label"] = scenario.label
    forecast["scenario_description"] = scenario.description
    forecast["hazard_signal"] = hazard_signal
    forecast["dependency_signal"] = dependency_signal
    forecast["neighbor_signal"] = neighbor_signal
    forecast["outage_probability"] = outage_probability
    forecast["outage_probability_low"] = (outage_probability - uncertainty).clip(lower=0.0)
    forecast["outage_probability_high"] = (outage_probability + uncertainty).clip(upper=1.0)
    forecast["expected_outage_hours"] = expected_outage_hours
    forecast["expected_outage_hours_low"] = expected_outage_hours_low
    forecast["expected_outage_hours_high"] = expected_outage_hours_high
    forecast["restoration_lag_hours"] = restoration_lag_hours
    forecast["restoration_lag_hours_low"] = restoration_lag_hours_low
    forecast["restoration_lag_hours_high"] = restoration_lag_hours_high
    forecast["critical_community_exposure"] = critical_community_exposure
    forecast["forecast_priority_score"] = priority_raw.clip(0.0, 1.0)
    forecast["forecast_priority_band"] = assign_habri_quintiles(forecast["forecast_priority_score"])
    forecast["habri_rank"] = forecast["HABRI"].rank(ascending=False, method="min").astype(int)
    forecast["forecast_rank"] = forecast["forecast_priority_score"].rank(ascending=False, method="min").astype(int)
    forecast["priority_shift_vs_habri"] = forecast["habri_rank"] - forecast["forecast_rank"]

    ordered = [
        "GEOID",
        "state_abbr",
        "county_name",
        "county_label",
        "pilot_region",
        "scenario_key",
        "scenario_label",
        "risk_profile",
        "H_E",
        "I_F",
        "C_C",
        "HABRI",
        "graph_exposure_score",
        "outage_probability",
        "outage_probability_low",
        "outage_probability_high",
        "expected_outage_hours",
        "expected_outage_hours_low",
        "expected_outage_hours_high",
        "restoration_lag_hours",
        "restoration_lag_hours_low",
        "restoration_lag_hours_high",
        "critical_community_exposure",
        "forecast_priority_score",
        "forecast_priority_band",
        "habri_rank",
        "forecast_rank",
        "priority_shift_vs_habri",
    ]
    remaining = [column for column in forecast.columns if column not in ordered]
    return forecast[ordered + remaining]


def _intervention_target_scores(
    forecast: gpd.GeoDataFrame,
    intervention: InterventionDefinition,
) -> pd.Series:
    score = pd.Series(0.0, index=forecast.index, dtype=float)
    for column, weight in intervention.selection_weights.items():
        if column == "forecast_priority_score":
            score += weight * forecast["forecast_priority_score"]
        elif column == "wireless_reliance":
            score += weight * forecast["wireless_reliance"]
        else:
            score += weight * forecast[column]
    return score


def _target_count(intervention: InterventionDefinition, budget_musd: float, max_count: int) -> int:
    raw = int(round((budget_musd / 10.0) * intervention.tracts_per_10m))
    return min(max_count, max(3, raw))


def apply_intervention(
    tracts: gpd.GeoDataFrame,
    intervention: InterventionDefinition,
    target_geoids: list[str],
) -> gpd.GeoDataFrame:
    """Apply intervention effects to a tract layer while preserving the baseline."""
    out = _ensure_forecast_columns(tracts)
    mask = out["GEOID"].isin(target_geoids)
    if not mask.any():
        return out

    for column, delta in intervention.feature_shifts.items():
        out.loc[mask, column] = (out.loc[mask, column] + delta).clip(0.0, 1.0)

    out.loc[mask, "graph_exposure_score"] = (
        out.loc[mask, "graph_exposure_score"] + intervention.graph_shift
    ).clip(0.0, 1.0)
    out.loc[mask, "probability_multiplier"] *= intervention.probability_multiplier
    out.loc[mask, "duration_multiplier"] *= intervention.duration_multiplier
    out.loc[mask, "restoration_multiplier"] *= intervention.restoration_multiplier
    out.loc[mask, "exposure_multiplier"] *= intervention.exposure_multiplier
    out["wireless_reliance"] = 1.0 - out["p_wired"].fillna(out["p_wired"].median())
    out["I_F"] = (
        out["w_tower"] * out["tower_density_norm"]
        + W_IF_LATENCY * out["latency_norm"]
        + out["w_road"] * out["road_fragility"]
        + W_IF_POWER_GRID * out["power_grid_norm"]
    )
    out["HABRI"] = (
        W_HAZARD_EXPOSURE * out["H_E"]
        + W_INFRA_FRAGILITY * out["I_F"]
        + W_COPING_CAPACITY * out["C_C"]
    )
    return out


def rank_interventions(
    tracts: gpd.GeoDataFrame,
    scenario_key: str = "helene_replay",
    budget_musd: float = 20.0,
    baseline_forecast: gpd.GeoDataFrame | None = None,
) -> pd.DataFrame:
    """Run intervention scenarios and return a ranked mitigation table."""
    baseline = baseline_forecast if baseline_forecast is not None else compute_risk_forecast(tracts, scenario_key)
    rows: list[dict[str, object]] = []

    for intervention in INTERVENTIONS.values():
        eligible = baseline[baseline["risk_profile"].isin(intervention.target_profiles)].copy()
        if eligible.empty:
            eligible = baseline.copy()

        eligible["target_score"] = _intervention_target_scores(eligible, intervention)
        target_count = _target_count(intervention, budget_musd, len(eligible))
        targets = eligible.nlargest(target_count, "target_score")
        target_geoids = targets["GEOID"].tolist()

        treated = apply_intervention(tracts, intervention, target_geoids)
        treated_forecast = compute_risk_forecast(treated, scenario_key)
        compare = baseline.merge(
            treated_forecast[
                [
                    "GEOID",
                    "outage_probability",
                    "expected_outage_hours",
                    "restoration_lag_hours",
                    "critical_community_exposure",
                ]
            ],
            on="GEOID",
            suffixes=("_base", "_treated"),
        )

        outage_hours_saved = (compare["expected_outage_hours_base"] - compare["expected_outage_hours_treated"]).clip(lower=0.0)
        critical_exposure_saved = (
            compare["critical_community_exposure_base"] - compare["critical_community_exposure_treated"]
        ).clip(lower=0.0)
        probability_delta = compare["outage_probability_base"] - compare["outage_probability_treated"]
        restoration_delta = (
            compare["restoration_lag_hours_base"] - compare["restoration_lag_hours_treated"]
        ).clip(lower=0.0)

        rows.append(
            {
                "scenario_key": scenario_key,
                "scenario_label": PILOT_SCENARIOS[scenario_key].label,
                "intervention_key": intervention.key,
                "intervention_label": intervention.label,
                "budget_musd": budget_musd,
                "target_tract_count": len(target_geoids),
                "target_counties": ", ".join(sorted(targets["county_name"].unique())),
                "target_geoids": ", ".join(target_geoids[:12]),
                "outage_minutes_saved": float(outage_hours_saved.sum() * 60.0),
                "critical_exposure_reduction": float(critical_exposure_saved.sum()),
                "mean_probability_delta": float(probability_delta.mean()),
                "mean_restoration_hours_saved": float(restoration_delta.mean()),
                "max_probability_delta": float(probability_delta.max()),
                "description": intervention.description,
            }
        )

    scenario_runs = pd.DataFrame(rows)
    scenario_runs = scenario_runs.sort_values(
        ["outage_minutes_saved", "critical_exposure_reduction"],
        ascending=[False, False],
    ).reset_index(drop=True)
    scenario_runs["scenario_rank"] = np.arange(1, len(scenario_runs) + 1)
    return scenario_runs


def build_habri_grid_bundle(
    processed_dir: Path = DATA_PROCESSED,
    scenario_key: str = "helene_replay",
    budget_musd: float = 20.0,
) -> HABRIGridBundle:
    """Build the HABRI-GRID public-data pilot bundle."""
    pilot = load_habri_grid_pilot_tracts(processed_dir)
    nodes, edges = build_proxy_asset_graph(pilot)
    pilot_with_graph = attach_graph_features(pilot, nodes)
    risk_forecast = compute_risk_forecast(pilot_with_graph, scenario_key=scenario_key)
    scenario_runs = rank_interventions(
        pilot_with_graph,
        scenario_key=scenario_key,
        budget_musd=budget_musd,
        baseline_forecast=risk_forecast,
    )
    return HABRIGridBundle(
        pilot_tracts=pilot_with_graph,
        asset_graph_nodes=nodes,
        asset_graph_edges=edges,
        risk_forecast=risk_forecast,
        scenario_runs=scenario_runs,
    )
