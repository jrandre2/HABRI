#!/usr/bin/env python3
"""Build a joint North Carolina and Tennessee HABRI layer on one standardized scale.

This script preserves the existing state baselines and writes a separate
cross-state product that standardizes the completed North Carolina and
Tennessee outputs onto a shared distribution.

Outputs
-------
data/processed/habri_nc_tn_standardized.csv / .gpkg
    Combined tract layer for North Carolina and Tennessee with shared-scale
    H_E, I_F, C_C, and HABRI scores.

data/processed/habri_nc_tn_standardized.png
    Single-panel standardized HABRI choropleth for both states.

data/processed/habri_nc_tn_standardized_4panel.png
    Four-panel map for H_E, I_F, C_C, and HABRI on the shared North Carolina
    and Tennessee scale.

data/processed/habri_nc_tn_standardized.html
    Interactive Folium map of the combined standardized layer.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.combined import build_joint_standardized_habri, load_state_habri
from src.config import CRS_WGS84, DATA_PROCESSED

PANEL_COLS = [
    ("H_E", "Hazard Exposure (joint scale)"),
    ("I_F", "Infrastructure Fragility (joint scale)"),
    ("C_C", "Coping Capacity Deficit (joint scale)"),
    ("HABRI", "HABRI Composite (joint scale)"),
]


def _add_basemap(ax, gdf: gpd.GeoDataFrame) -> None:
    try:
        import contextily as cx

        cx.add_basemap(ax, crs=gdf.crs, source=cx.providers.CartoDB.Positron, alpha=0.32)
    except Exception:
        pass


def _save_figure(fig: plt.Figure, path: Path | None, *, dpi: int = 300) -> None:
    if path is None:
        plt.show()
        return
    fig.savefig(path, dpi=dpi, bbox_inches="tight")
    print(f"  Saved: {path}")


def _outside_legend_kwds(
    side: str,
    *,
    fontsize: int = 9,
    title: str = "Score",
    title_fontsize: int = 9,
) -> dict:
    if side == "left":
        loc = "upper right"
        anchor = (-0.04, 1.0)
    else:
        loc = "upper left"
        anchor = (1.04, 1.0)
    return {
        "loc": loc,
        "bbox_to_anchor": anchor,
        "borderaxespad": 0.0,
        "fontsize": fontsize,
        "frameon": True,
        "title": title,
        "title_fontsize": title_fontsize,
    }


def _plot_frame(
    ax: plt.Axes,
    gdf: gpd.GeoDataFrame,
    column: str,
    title: str,
    *,
    legend_kwds: dict | None = None,
) -> None:
    gdf.plot(
        column=column,
        ax=ax,
        legend=True,
        cmap="cividis_r",
        scheme="NaturalBreaks",
        k=5,
        edgecolor="none",
        linewidth=0,
        alpha=0.90,
        legend_kwds=legend_kwds or _outside_legend_kwds("right"),
        missing_kwds={"color": "#cccccc"},
        zorder=3,
    )

    states = gdf.dissolve(by="state_abbr").boundary
    states.plot(ax=ax, color="#16324f", linewidth=2.1, alpha=0.95, zorder=6)

    labels = gdf.dissolve(by="state_abbr").reset_index()
    labels["geometry"] = labels.representative_point()
    for _, row in labels.iterrows():
        ax.text(
            row.geometry.x,
            row.geometry.y,
            row["state_abbr"],
            fontsize=13,
            fontweight="bold",
            color="#111111",
            ha="center",
            va="center",
            bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.70, "pad": 0.25},
            zorder=7,
        )

    ax.set_title(title, fontsize=13, fontweight="bold")
    ax.set_axis_off()


def plot_joint_composite_map(combined: gpd.GeoDataFrame, save_path: Path | None) -> None:
    """Single-panel HABRI map for the combined standardized layer."""
    plot_gdf = combined.to_crs("EPSG:3857")
    fig, ax = plt.subplots(figsize=(14, 11))
    _add_basemap(ax, plot_gdf)
    _plot_frame(
        ax,
        plot_gdf,
        "HABRI",
        "NC and TN HABRI (shared standardized scale)",
        legend_kwds={
            "loc": "upper left",
            "bbox_to_anchor": (1.01, 1.0),
            "borderaxespad": 0.0,
            "fontsize": 9,
            "frameon": True,
            "title": "Score",
            "title_fontsize": 9,
        },
    )
    plt.suptitle(
        "Hazard-Adjusted Broadband Reliability Index\nNorth Carolina and Tennessee",
        fontsize=16,
        fontweight="bold",
    )
    fig.subplots_adjust(left=0.03, right=0.82, top=0.90, bottom=0.03)
    _save_figure(fig, save_path)
    plt.close(fig)


def plot_joint_4panel(combined: gpd.GeoDataFrame, save_path: Path | None) -> None:
    """Four-panel combined map for the standardized sub-indices and composite."""
    plot_gdf = combined.to_crs("EPSG:3857")
    fig, axes = plt.subplots(2, 2, figsize=(22, 16))

    xmin, ymin, xmax, ymax = plot_gdf.total_bounds
    xpad = (xmax - xmin) * 0.02
    ypad = (ymax - ymin) * 0.02

    for idx, (ax, (column, title)) in enumerate(zip(axes.flat, PANEL_COLS)):
        ax.set_xlim(xmin - xpad, xmax + xpad)
        ax.set_ylim(ymin - ypad, ymax + ypad)
        _add_basemap(ax, plot_gdf)
        _plot_frame(
            ax,
            plot_gdf,
            column,
            title,
            legend_kwds=_outside_legend_kwds("left" if idx % 2 == 0 else "right"),
        )

    plt.suptitle(
        "HABRI shared-scale sub-indices across North Carolina and Tennessee",
        fontsize=15,
        fontweight="bold",
    )
    fig.subplots_adjust(left=0.12, right=0.88, top=0.92, bottom=0.02, wspace=0.26, hspace=0.10)
    _save_figure(fig, save_path)
    plt.close(fig)


def plot_folium_map(combined: gpd.GeoDataFrame, save_path: Path | None) -> None:
    """Interactive Folium map for the combined standardized layer."""
    try:
        import folium
    except ImportError:
        print("  folium not installed; skipping interactive map")
        return

    combined_wgs = combined.to_crs(CRS_WGS84)
    minx, miny, maxx, maxy = combined_wgs.total_bounds
    center = [float((miny + maxy) / 2), float((minx + maxx) / 2)]

    m = folium.Map(location=center, zoom_start=6, tiles="cartodbpositron")

    folium.Choropleth(
        geo_data=combined_wgs.__geo_interface__,
        data=combined_wgs,
        columns=["GEOID", "HABRI"],
        key_on="feature.properties.GEOID",
        fill_color="BuPu",
        fill_opacity=0.72,
        line_opacity=0.10,
        legend_name="HABRI Score (shared North Carolina and Tennessee standardized scale)",
        name="HABRI",
    ).add_to(m)

    folium.GeoJson(
        combined_wgs.__geo_interface__,
        name="Tract details",
        style_function=lambda _: {"fillColor": "transparent", "color": "transparent", "weight": 0},
        tooltip=folium.GeoJsonTooltip(
            fields=["state_name", "county_name", "GEOID", "HABRI", "risk_profile"],
            aliases=["State", "County", "Tract", "HABRI", "Risk profile"],
            localize=True,
        ),
    ).add_to(m)

    state_bounds = combined_wgs.dissolve(by="state_abbr").reset_index()
    folium.GeoJson(
        state_bounds.__geo_interface__,
        name="State boundaries",
        style_function=lambda _: {
            "fillColor": "transparent",
            "fillOpacity": 0,
            "color": "#16324f",
            "weight": 2.0,
        },
        show=True,
    ).add_to(m)

    folium.LayerControl().add_to(m)

    if save_path is None:
        print("  (--no-save: skipping HTML export)")
        return

    m.save(str(save_path))
    print(f"  Saved: {save_path}")


def print_summary(combined: gpd.GeoDataFrame) -> None:
    print("\nCombined shared-scale summary")
    print("-" * 60)
    for state_abbr, sub in combined.groupby("state_abbr"):
        print(
            f"{state_abbr}: {len(sub):,} tracts | "
            f"HABRI mean={sub['HABRI'].mean():.4f} "
            f"range=[{sub['HABRI'].min():.4f}, {sub['HABRI'].max():.4f}]"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a joint North Carolina and Tennessee HABRI layer."
    )
    parser.add_argument(
        "--nc-gpkg",
        default=str(DATA_PROCESSED / "habri_composite.gpkg"),
        help="Path to the North Carolina HABRI GeoPackage.",
    )
    parser.add_argument(
        "--tn-gpkg",
        default=str(DATA_PROCESSED / "habri_tn_composite.gpkg"),
        help="Path to the Tennessee HABRI GeoPackage.",
    )
    parser.add_argument(
        "--output-prefix",
        default="habri_nc_tn_standardized",
        help="Prefix for output artifacts in data/processed.",
    )
    parser.add_argument("--no-save", action="store_true", help="Display figures instead of writing files.")
    parser.add_argument("--skip-folium", action="store_true", help="Skip the interactive HTML export.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    save = not args.no_save

    print(f"\n{'=' * 60}")
    print("HABRI — Joint NC/TN Standardized Layer")
    print(f"{'=' * 60}")
    print("Method: second-pass shared standardization across the completed NC and TN outputs.")

    nc = load_state_habri(Path(args.nc_gpkg))
    tn = load_state_habri(Path(args.tn_gpkg))
    combined = build_joint_standardized_habri(nc, tn)
    print_summary(combined)

    if save:
        out_csv = DATA_PROCESSED / f"{args.output_prefix}.csv"
        out_gpkg = DATA_PROCESSED / f"{args.output_prefix}.gpkg"
        combined.drop(columns="geometry").to_csv(out_csv, index=False)
        combined.to_file(out_gpkg, driver="GPKG")
        print(f"\nSaved data products:\n  {out_csv}\n  {out_gpkg}")

    print("\nGenerating maps...")
    plot_joint_composite_map(
        combined,
        DATA_PROCESSED / f"{args.output_prefix}.png" if save else None,
    )
    plot_joint_4panel(
        combined,
        DATA_PROCESSED / f"{args.output_prefix}_4panel.png" if save else None,
    )
    if args.skip_folium:
        print("  Folium export skipped (--skip-folium)")
    else:
        plot_folium_map(
            combined,
            DATA_PROCESSED / f"{args.output_prefix}.html" if save else None,
        )

    print("\nDone.")


if __name__ == "__main__":
    main()
