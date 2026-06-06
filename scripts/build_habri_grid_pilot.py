#!/usr/bin/env python3
"""Build the public-data HABRI-GRID pilot bundle."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import DATA_PROCESSED
from src.habri_grid import build_habri_grid_bundle


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the HABRI-GRID public-data pilot outputs.")
    parser.add_argument(
        "--scenario",
        default="helene_replay",
        help="Scenario key for the default risk forecast bundle.",
    )
    parser.add_argument(
        "--budget",
        type=float,
        default=20.0,
        help="Budget in millions of USD for the ranked mitigation scenario run.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)

    bundle = build_habri_grid_bundle(
        processed_dir=DATA_PROCESSED,
        scenario_key=args.scenario,
        budget_musd=args.budget,
    )

    risk_path = DATA_PROCESSED / "habri_grid_risk_forecast.gpkg"
    nodes_path = DATA_PROCESSED / "habri_grid_asset_nodes.gpkg"
    edges_path = DATA_PROCESSED / "habri_grid_asset_edges.csv"
    scenarios_path = DATA_PROCESSED / "habri_grid_scenario_runs.csv"

    bundle.risk_forecast.to_file(risk_path, driver="GPKG")
    bundle.asset_graph_nodes.to_file(nodes_path, driver="GPKG")
    bundle.asset_graph_edges.to_csv(edges_path, index=False)
    bundle.scenario_runs.to_csv(scenarios_path, index=False)

    print("Built HABRI-GRID pilot outputs:")
    print(f"  {risk_path}")
    print(f"  {nodes_path}")
    print(f"  {edges_path}")
    print(f"  {scenarios_path}")


if __name__ == "__main__":
    main()
