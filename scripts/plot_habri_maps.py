#!/usr/bin/env python3
"""Regenerate all HABRI static and interactive map figures.

Reads ``data/processed/habri_composite.gpkg`` (the current baseline) and
produces four publication-ready outputs:

Outputs
-------
data/processed/habri_statewide_4panel.png / .pdf
    Statewide 4-panel choropleth: H_E, I_F, C_C, HABRI (all 2,660 NC tracts).

data/processed/habri_4panel.png / .pdf
    Zoomed 4-panel for Land of the Sky counties
    (Buncombe, Henderson, Madison, Transylvania).

data/processed/habri_profiles.png / .pdf
    Risk-profile map for Land of the Sky counties.

data/processed/habri_map.html
    Interactive Folium choropleth (statewide, ~21 MB).

Usage
-----
    python scripts/plot_habri_maps.py
    python scripts/plot_habri_maps.py --no-save   # display only
    python scripts/plot_habri_maps.py --skip-folium  # skip the slow HTML export
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib.lines as mlines
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import DATA_PROCESSED, DATA_RAW, CRS_WGS84

# ── Style constants ───────────────────────────────────────────────────────────

PROFILE_COLORS = {
    "Power-Dependent":  "#88CCEE",
    "Transport-Fragile": "#CC6677",
    "Dual-Risk":        "#DDCC77",
}

LOTS_FIPS = ["37021", "37089", "37115", "37175"]
LOTS_NAMES = {
    "37021": "Buncombe",
    "37089": "Henderson",
    "37115": "Madison",
    "37175": "Transylvania",
}

WNC_FIPS = ["37021", "37087", "37089", "37115", "37121", "37199"]

PANEL_COLS = [
    ("H_E",    "Hazard Exposure (H_E)"),
    ("I_F",    "Infrastructure Fragility (I_F)"),
    ("C_C",    "Coping Capacity Deficit (C_C)"),
    ("HABRI",  "HABRI Composite Score"),
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _add_basemap(ax, gdf):
    try:
        import contextily as cx
        cx.add_basemap(ax, crs=gdf.crs, source=cx.providers.CartoDB.Positron,
                       alpha=0.30)
    except Exception:
        pass


def _save(fig, path_stem: Path | None, suffix: str, dpi: int = 300) -> None:
    if path_stem is None:
        plt.show()
        return
    png = path_stem.parent / (path_stem.name + suffix + ".png")
    pdf = path_stem.parent / (path_stem.name + suffix + ".pdf")
    fig.savefig(png, dpi=dpi, bbox_inches="tight")
    fig.savefig(pdf, bbox_inches="tight")
    print(f"  Saved: {png}")
    print(f"  Saved: {pdf}")


# ── Plot 1: statewide 4-panel ─────────────────────────────────────────────────

def plot_statewide_4panel(habri: gpd.GeoDataFrame, save_stem: Path | None) -> None:
    """Statewide 4-panel choropleth for all 2,660 NC tracts."""
    fig, axes = plt.subplots(2, 2, figsize=(24, 16))

    xmin, ymin, xmax, ymax = habri.total_bounds
    xpad = (xmax - xmin) * 0.01
    ypad = (ymax - ymin) * 0.01

    # WNC county boundary overlay
    wnc_boundary = habri[habri["county_fips"].isin(WNC_FIPS)].dissolve().boundary

    for ax, (col, title) in zip(axes.flat, PANEL_COLS):
        ax.set_xlim(xmin - xpad, xmax + xpad)
        ax.set_ylim(ymin - ypad, ymax + ypad)
        _add_basemap(ax, habri)

        habri.plot(
            column=col,
            ax=ax,
            legend=True,
            cmap="cividis_r",
            scheme="NaturalBreaks",
            k=5,
            edgecolor="none",
            linewidth=0,
            alpha=0.88,
            legend_kwds={
                "loc": "lower left",
                "fontsize": 9,
                "frameon": True,
                "title": "Score",
                "title_fontsize": 9,
            },
            missing_kwds={"color": "#cccccc"},
            zorder=3,
        )

        # Highlight WNC counties
        wnc_boundary.plot(ax=ax, color="#CC6677", linewidth=1.8, alpha=0.9, zorder=6)

        ax.set_title(title, fontsize=13, fontweight="bold")
        ax.set_axis_off()

    plt.suptitle(
        "Hazard-Adjusted Broadband Reliability Index (HABRI) — North Carolina\n"
        "All 2,660 Census Tracts | WNC counties outlined",
        fontsize=14,
        fontweight="bold",
    )
    fig.subplots_adjust(left=0.02, right=0.98, top=0.91, bottom=0.02,
                        wspace=0.06, hspace=0.10)
    _save(fig, save_stem, "", dpi=300)
    plt.close(fig)


# ── Plot 2: LOTS 4-panel ──────────────────────────────────────────────────────

def plot_lots_4panel(habri: gpd.GeoDataFrame, save_stem: Path | None) -> None:
    """4-panel choropleth zoomed to Land of the Sky counties."""
    lots_habri = habri[habri["county_fips"].isin(LOTS_FIPS)].copy()

    lots_county_boundaries = lots_habri.dissolve(by="county_fips").boundary
    lots_boundary = lots_habri.dissolve().boundary
    lots_counties = lots_habri.dissolve(by="county_fips").reset_index()
    lots_counties["county_name"] = lots_counties["county_fips"].map(LOTS_NAMES)
    lots_label_pts = lots_counties.copy()
    lots_label_pts["geometry"] = lots_counties.representative_point()

    xmin, ymin, xmax, ymax = lots_habri.total_bounds
    xpad = (xmax - xmin) * 0.04
    ypad = (ymax - ymin) * 0.03

    fig, axes = plt.subplots(2, 2, figsize=(30, 24))

    for ax, (col, title) in zip(axes.flat, PANEL_COLS):
        ax.set_xlim(xmin - xpad, xmax + xpad)
        ax.set_ylim(ymin - ypad, ymax + ypad)
        _add_basemap(ax, lots_habri)

        lots_habri.plot(
            column=col,
            ax=ax,
            legend=True,
            cmap="cividis_r",
            scheme="NaturalBreaks",
            k=5,
            edgecolor="none",
            linewidth=0,
            alpha=0.92,
            legend_kwds={
                "loc": "upper left",
                "bbox_to_anchor": (-0.16, 0.98),
                "fontsize": 13,
                "frameon": True,
                "borderaxespad": 0.0,
            },
            zorder=3,
        )

        lots_county_boundaries.plot(ax=ax, color="white",  linewidth=4.4, zorder=8)
        lots_county_boundaries.plot(ax=ax, color="black",  linewidth=2.3, zorder=9)
        lots_boundary.plot(ax=ax, color="black",  linewidth=7.2, zorder=10)
        lots_boundary.plot(ax=ax, color="#ffd400", linewidth=3.3, zorder=11)

        for _, row in lots_label_pts.iterrows():
            ax.text(
                row.geometry.x, row.geometry.y,
                row["county_name"],
                fontsize=11, fontweight="bold", color="#1f1f1f",
                ha="center", va="center",
                bbox=dict(facecolor="white", edgecolor="none", alpha=0.62, pad=0.20),
                zorder=12,
            )

        ax.set_title(title, fontsize=16)
        ax.set_axis_off()

    plt.suptitle(
        "Hazard-Adjusted Broadband Reliability Index (HABRI) — Land of the Sky Counties",
        fontsize=19, fontweight="bold",
    )
    fig.subplots_adjust(left=0.09, right=0.99, top=0.92, bottom=0.04,
                        wspace=0.18, hspace=0.18)
    _save(fig, save_stem, "", dpi=800)
    plt.close(fig)


# ── Plot 3: LOTS profile map ──────────────────────────────────────────────────

def plot_lots_profiles(habri: gpd.GeoDataFrame, save_stem: Path | None) -> None:
    """Risk-profile map for Land of the Sky counties."""
    lots_habri = habri[habri["county_fips"].isin(LOTS_FIPS)].copy()

    lots_county_boundaries = lots_habri.dissolve(by="county_fips").boundary
    lots_boundary = lots_habri.dissolve().boundary
    lots_counties = lots_habri.dissolve(by="county_fips").reset_index()
    lots_counties["county_name"] = lots_counties["county_fips"].map(LOTS_NAMES)
    lots_label_pts = lots_counties.copy()
    lots_label_pts["geometry"] = lots_counties.representative_point()

    xmin, ymin, xmax, ymax = lots_habri.total_bounds
    xpad = (xmax - xmin) * 0.04
    ypad = (ymax - ymin) * 0.03

    fig, ax = plt.subplots(figsize=(24, 19))
    ax.set_xlim(xmin - xpad, xmax + xpad)
    ax.set_ylim(ymin - ypad, ymax + ypad)
    _add_basemap(ax, lots_habri)

    for profile, color in PROFILE_COLORS.items():
        subset = lots_habri[lots_habri["risk_profile"] == profile]
        subset.plot(ax=ax, color=color, edgecolor="none", linewidth=0,
                    alpha=0.94, zorder=3)

    lots_county_boundaries.plot(ax=ax, color="white", linewidth=4.7, zorder=8)
    lots_county_boundaries.plot(ax=ax, color="black", linewidth=2.5, zorder=9)
    lots_boundary.plot(ax=ax, color="black",   linewidth=7.2, zorder=10)
    lots_boundary.plot(ax=ax, color="#ffd400", linewidth=3.3, zorder=11)

    for _, row in lots_label_pts.iterrows():
        ax.text(
            row.geometry.x, row.geometry.y,
            row["county_name"],
            fontsize=12, fontweight="bold", color="#1f1f1f",
            ha="center", va="center",
            bbox=dict(facecolor="white", edgecolor="none", alpha=0.62, pad=0.24),
            zorder=12,
        )

    legend_handles = [
        mlines.Line2D([0], [0], marker="s", color="w", label=p,
                      markerfacecolor=c, markersize=16)
        for p, c in PROFILE_COLORS.items()
    ] + [
        mlines.Line2D([0], [0], color="black", linewidth=3.0, label="County Boundary"),
        mlines.Line2D([0], [0], color="black", linewidth=7.2,
                      label="Land of the Sky Boundary"),
    ]
    ax.legend(
        handles=legend_handles,
        title="Map Features",
        fontsize=16, title_fontsize=17,
        loc="upper left",
        bbox_to_anchor=(0.02, 0.88),
        bbox_transform=fig.transFigure,
        borderaxespad=0.0,
        frameon=True,
    )
    ax.set_title("HABRI Vulnerability Profiles — Land of the Sky Counties",
                 fontsize=18)
    ax.set_axis_off()
    fig.subplots_adjust(left=0.08, right=0.99, top=0.90, bottom=0.04)
    _save(fig, save_stem, "", dpi=800)
    plt.close(fig)


# ── Plot 4: Folium interactive map ────────────────────────────────────────────

def plot_folium_map(habri: gpd.GeoDataFrame, save_path: Path | None) -> None:
    """Statewide interactive choropleth saved as HTML."""
    try:
        import folium
        from folium.plugins import MarkerCluster
    except ImportError:
        print("  folium not installed — skipping interactive map")
        return

    habri_wgs = habri.to_crs(CRS_WGS84)
    center_lat = float(habri_wgs.geometry.centroid.y.mean())
    center_lon = float(habri_wgs.geometry.centroid.x.mean())

    m = folium.Map(location=[center_lat, center_lon], zoom_start=7,
                   tiles="cartodbpositron")

    folium.Choropleth(
        geo_data=habri_wgs.__geo_interface__,
        data=habri_wgs,
        columns=["GEOID", "HABRI"],
        key_on="feature.properties.GEOID",
        fill_color="BuPu",
        fill_opacity=0.7,
        line_opacity=0.2,
        legend_name="HABRI Score (0 = Low Risk, 1 = High Risk)",
        name="HABRI Score",
    ).add_to(m)

    def style_by_profile(feature):
        profile = feature["properties"].get("risk_profile", "")
        return {
            "fillColor": PROFILE_COLORS.get(profile, "gray"),
            "color": "gray", "weight": 0.3, "fillOpacity": 0.5,
        }

    folium.GeoJson(
        habri_wgs.__geo_interface__,
        name="Risk Profiles",
        style_function=style_by_profile,
        tooltip=folium.GeoJsonTooltip(
            fields=["GEOID", "risk_profile", "HABRI"],
            aliases=["Tract", "Profile", "HABRI Score"],
            localize=True,
        ),
        show=False,
    ).add_to(m)

    lots_wgs = habri_wgs[habri_wgs["county_fips"].isin(LOTS_FIPS)]
    lots_boundary = lots_wgs.dissolve()
    folium.GeoJson(
        lots_boundary.__geo_interface__,
        name="Land of the Sky",
        style_function=lambda x: {
            "fillColor": "transparent", "fillOpacity": 0,
            "color": "black", "weight": 3,
        },
        show=True,
    ).add_to(m)

    tower_path = DATA_RAW / "hifld_cellular_towers.geojson"
    if tower_path.exists():
        towers_wgs = gpd.read_file(tower_path).to_crs(CRS_WGS84)
        tower_cluster = MarkerCluster(name="Cellular Towers", show=False)
        for _, row in towers_wgs.iterrows():
            folium.CircleMarker(
                location=[row.geometry.y, row.geometry.x],
                radius=2, color="blue", fill=True, fill_opacity=0.5,
            ).add_to(tower_cluster)
        tower_cluster.add_to(m)

    folium.LayerControl().add_to(m)

    if save_path:
        m.save(str(save_path))
        print(f"  Saved: {save_path}")
    else:
        print("  (--no-save: skipping HTML export)")


# ── Main ──────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Regenerate HABRI map figures.")
    p.add_argument("--no-save", action="store_true",
                   help="Display figures instead of writing files")
    p.add_argument("--skip-folium", action="store_true",
                   help="Skip slow interactive Folium HTML export")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    save = not args.no_save

    print(f"\n{'='*60}")
    print("HABRI — Map Figure Regeneration")
    print(f"{'='*60}\n")

    gpkg = DATA_PROCESSED / "habri_composite.gpkg"
    if not gpkg.exists():
        print(f"ERROR: {gpkg} not found")
        sys.exit(1)

    print(f"Loading {gpkg} ...")
    habri = gpd.read_file(gpkg)
    # Ensure county_fips exists
    if "county_fips" not in habri.columns and "GEOID" in habri.columns:
        habri["county_fips"] = habri["GEOID"].astype(str).str.zfill(11).str[:5]
    print(f"  {len(habri)} tracts loaded  |  CRS: {habri.crs}")
    print(f"  HABRI range [{habri['HABRI'].min():.4f}, {habri['HABRI'].max():.4f}]  "
          f"mean={habri['HABRI'].mean():.4f}\n")

    # ── 1. Statewide 4-panel ──────────────────────────────────────────────────
    print("[1/4] Statewide 4-panel choropleth")
    plot_statewide_4panel(
        habri,
        DATA_PROCESSED / "habri_statewide_4panel" if save else None,
    )

    # ── 2. LOTS 4-panel ───────────────────────────────────────────────────────
    print("[2/4] Land of the Sky 4-panel choropleth")
    plot_lots_4panel(
        habri,
        DATA_PROCESSED / "habri_4panel" if save else None,
    )

    # ── 3. LOTS profile map ───────────────────────────────────────────────────
    print("[3/4] Land of the Sky risk-profile map")
    plot_lots_profiles(
        habri,
        DATA_PROCESSED / "habri_profiles" if save else None,
    )

    # ── 4. Folium interactive map ─────────────────────────────────────────────
    if args.skip_folium:
        print("[4/4] Folium map skipped (--skip-folium)")
    else:
        print("[4/4] Folium interactive map (statewide)")
        plot_folium_map(
            habri,
            DATA_PROCESSED / "habri_map.html" if save else None,
        )

    print("\nDone.")


if __name__ == "__main__":
    main()
