#!/usr/bin/env python3
"""Cross-state HABRI comparison: Western NC vs. Eastern Tennessee — Hurricane Helene.

Loads the completed NC and TN HABRI baselines and produces comparison figures
showing that both states' pre-storm vulnerability scores predicted observed
Helene connectivity damage.

Requires both pipelines to have been run:
  - NC: notebooks 01-04 + scripts/integrate_power_grid.py
  - TN: scripts/build_habri_tn.py

Outputs (all in data/processed/)
---------------------------------
habri_wnc_etn_map.png
    Side-by-side choropleth: WNC counties vs. Eastern TN counties,
    scaled to each state's own distribution.

habri_wnc_etn_recovery.png
    Overlaid quarterly latency trend: WNC focal counties vs. ETN focal counties
    (requires quarterly Ookla outputs for both states).

habri_helene_validation_combined.png
    Two-panel scatter: pre-storm HABRI vs. Q3→Q4 latency change,
    left panel = WNC, right panel = ETN.  Titles show ρ / p-value.

habri_wnc_etn_profiles.png
    Stacked bar: risk profile distribution comparison (WNC vs. ETN).

Usage
-----
    python scripts/compare_helene_nc_tn.py
    python scripts/compare_helene_nc_tn.py --no-save  # display only
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib.lines as mlines
import numpy as np
import pandas as pd
from scipy.stats import spearmanr

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.combined import harmonize_habri_schema
from src.config import DATA_PROCESSED, DATA_RAW
from src.region import ETN_HELENE_COUNTY_FIPS, NC_CONFIG, WNC_COUNTY_FIPS

# ── Constants ─────────────────────────────────────────────────────────────────

PROFILE_COLORS = {
    "Power-Dependent":  "#88CCEE",
    "Transport-Fragile": "#CC6677",
    "Dual-Risk":        "#DDCC77",
}

WNC_COLORS = {
    "Buncombe":  "#1f77b4",
    "Haywood":   "#ff7f0e",
    "Henderson": "#d62728",
    "Madison":   "#9467bd",
    "Mitchell":  "#8c564b",
    "Yancey":    "#e377c2",
}

ETN_COLORS = {
    "Unicoi":     "#d62728",
    "Carter":     "#1f77b4",
    "Johnson":    "#9467bd",
    "Sullivan":   "#ff7f0e",
    "Washington": "#2ca02c",
    "Greene":     "#8c564b",
    "Cocke":      "#e377c2",
    "Hamblen":    "#bcbd22",
}

WNC_FIPS_5 = {f"{NC_CONFIG.state_fips}{county_fips}" for county_fips in WNC_COUNTY_FIPS.values()}
ETN_FIPS_5 = set(ETN_HELENE_COUNTY_FIPS.values())


# ── Data loaders ──────────────────────────────────────────────────────────────

def load_nc() -> gpd.GeoDataFrame:
    path = DATA_PROCESSED / "habri_composite.gpkg"
    if not path.exists():
        raise FileNotFoundError(f"NC composite not found: {path}\nRun the NC pipeline first.")
    return harmonize_habri_schema(gpd.read_file(path), state_fips="37")


def load_tn() -> gpd.GeoDataFrame:
    path = DATA_PROCESSED / "habri_tn_composite.gpkg"
    if not path.exists():
        raise FileNotFoundError(
            f"TN composite not found: {path}\nRun: python scripts/build_habri_tn.py")
    return harmonize_habri_schema(gpd.read_file(path), state_fips="47")


def _ookla_tract_latency(gpkg_path: Path, tracts_gdf: gpd.GeoDataFrame,
                          crs_project: str) -> pd.Series:
    """Aggregate Ookla tile gpkg to tract-level weighted mean latency."""
    tiles = gpd.read_file(gpkg_path).to_crs(crs_project)
    joined = gpd.sjoin(tiles, tracts_gdf[["GEOID", "geometry"]].to_crs(crs_project),
                        how="left", predicate="within")
    joined = joined.dropna(subset=["GEOID", "avg_lat_ms"])
    joined["weighted"] = joined["avg_lat_ms"] * joined["tests"]
    grp = joined.groupby("GEOID").agg(w=("weighted", "sum"), t=("tests", "sum"))
    return (grp["w"] / grp["t"]).rename("avg_latency_ms")


def load_helene_latency_nc(nc: gpd.GeoDataFrame) -> tuple[pd.Series, pd.Series]:
    """Q3 and Q4 2024 average latency for NC tracts."""
    q3 = DATA_RAW / "ookla_fixed_pre_helene.gpkg"
    q4 = DATA_RAW / "ookla_fixed_post_helene.gpkg"
    if not q3.exists() or not q4.exists():
        return pd.Series(dtype=float), pd.Series(dtype=float)
    l3 = _ookla_tract_latency(q3, nc, "EPSG:2264")
    l4 = _ookla_tract_latency(q4, nc, "EPSG:2264")
    return l3, l4


def load_helene_latency_tn(tn: gpd.GeoDataFrame) -> tuple[pd.Series, pd.Series]:
    """Q3 and Q4 2024 average latency for TN tracts."""
    q3 = DATA_RAW / "ookla_tn_fixed_q3_2024.gpkg"
    q4 = DATA_RAW / "ookla_tn_fixed_q4_2024.gpkg"
    if not q3.exists() or not q4.exists():
        return pd.Series(dtype=float), pd.Series(dtype=float)
    l3 = _ookla_tract_latency(q3, tn, "EPSG:2274")
    l4 = _ookla_tract_latency(q4, tn, "EPSG:2274")
    return l3, l4


# ── Figures ───────────────────────────────────────────────────────────────────

def plot_side_by_side_map(nc: gpd.GeoDataFrame, tn: gpd.GeoDataFrame,
                           save_path: Path | None) -> None:
    """Side-by-side HABRI choropleth: WNC vs. Eastern TN."""
    wnc = nc[nc["county_fips"].isin(WNC_FIPS_5)].to_crs("EPSG:4326")
    etn = tn[tn["county_fips"].isin(ETN_FIPS_5)].to_crs("EPSG:4326")

    fig, axes = plt.subplots(1, 2, figsize=(18, 8))

    for ax, gdf, title, boundary_color in [
        (axes[0], wnc, "Western NC (WNC)\nHurricane Helene Focal Counties", "#2C3E50"),
        (axes[1], etn, "Eastern TN (ETN)\nHurricane Helene Focal Counties", "#2C3E50"),
    ]:
        try:
            import contextily as cx
            cx.add_basemap(ax, crs=gdf.crs, source=cx.providers.CartoDB.Positron,
                           alpha=0.30)
        except Exception:
            pass
        gdf.plot(column="HABRI", ax=ax, legend=True, cmap="cividis_r",
                 scheme="NaturalBreaks", k=5, edgecolor="none", alpha=0.90,
                 legend_kwds={"loc": "lower left", "fontsize": 9, "frameon": True,
                               "title": "HABRI\n(within-state)"},
                 zorder=3)
        gdf.dissolve(by="county_fips").boundary.plot(
            ax=ax, color=boundary_color, linewidth=1.6, zorder=6)
        ax.set_title(title, fontsize=13, fontweight="bold")
        ax.set_axis_off()

    plt.suptitle("Pre-Disaster HABRI Scores — Hurricane Helene Impact Areas\n"
                 "(Scores normalized within each state independently)",
                 fontsize=13, fontweight="bold")
    fig.tight_layout()
    if save_path:
        fig.savefig(save_path, dpi=300, bbox_inches="tight")
        print(f"  Saved: {save_path}")
    else:
        plt.show()
    plt.close(fig)


def plot_helene_validation(nc: gpd.GeoDataFrame, tn: gpd.GeoDataFrame,
                            nc_l3: pd.Series, nc_l4: pd.Series,
                            tn_l3: pd.Series, tn_l4: pd.Series,
                            save_path: Path | None) -> None:
    """Two-panel scatter: HABRI vs. Q3→Q4 latency delta for WNC and ETN."""
    if nc_l3.empty or nc_l4.empty or tn_l3.empty or tn_l4.empty:
        print("  Skipping Helene validation scatter (Ookla data missing for one or both states)")
        return

    def _prep(gdf, fips_set, l3, l4):
        sub = gdf[gdf["county_fips"].isin(fips_set)].set_index("GEOID")
        df = sub[["HABRI", "I_F", "risk_profile"]].join(
            l3.rename("lat_q3")).join(l4.rename("lat_q4")).dropna()
        df["lat_delta"] = df["lat_q4"] - df["lat_q3"]
        return df

    wnc_df = _prep(nc, WNC_FIPS_5, nc_l3, nc_l4)
    etn_df = _prep(tn, ETN_FIPS_5, tn_l3, tn_l4)

    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    for ax, df, region_name in [(axes[0], wnc_df, "WNC"), (axes[1], etn_df, "ETN")]:
        for profile, color in PROFILE_COLORS.items():
            sub = df[df["risk_profile"] == profile]
            ax.scatter(sub["HABRI"], sub["lat_delta"], color=color, alpha=0.65,
                       s=30, label=profile, zorder=3)
        rho, pval = spearmanr(df["HABRI"], df["lat_delta"])
        ax.axhline(0, color="grey", lw=1, ls="--")
        ax.set_xlabel("Pre-Storm HABRI Score")
        ax.set_ylabel("Latency Δ Q4 − Q3 2024 (ms)")
        ax.set_title(f"{region_name}  ρ = {rho:.3f}  p = {pval:.3e}  n = {len(df)}")
        ax.legend(frameon=False, fontsize=9)
        ax.grid(alpha=0.3)
    plt.suptitle("HABRI vs. Helene-Induced Latency Degradation — WNC and ETN",
                 fontweight="bold")
    fig.tight_layout()
    if save_path:
        fig.savefig(save_path, dpi=200, bbox_inches="tight")
        print(f"  Saved: {save_path}")
    else:
        plt.show()
    plt.close(fig)

    rho_wnc, pv_wnc = spearmanr(wnc_df["HABRI"], wnc_df["lat_delta"])
    rho_etn, pv_etn = spearmanr(etn_df["HABRI"], etn_df["lat_delta"])
    print(f"  WNC: HABRI ρ={rho_wnc:.3f} p={pv_wnc:.3e}  n={len(wnc_df)}")
    print(f"  ETN: HABRI ρ={rho_etn:.3f} p={pv_etn:.3e}  n={len(etn_df)}")


def plot_profile_comparison(nc: gpd.GeoDataFrame, tn: gpd.GeoDataFrame,
                             save_path: Path | None) -> None:
    """Grouped bar: risk profile distribution in WNC vs. ETN vs. statewide NC vs. TN."""
    datasets = {
        "NC statewide": nc,
        "WNC counties": nc[nc["county_fips"].isin(WNC_FIPS_5)],
        "TN statewide": tn,
        "ETN counties": tn[tn["county_fips"].isin(ETN_FIPS_5)],
    }
    profiles = list(PROFILE_COLORS.keys())
    fractions = {name: [(df["risk_profile"] == p).sum() / len(df)
                        for p in profiles]
                 for name, df in datasets.items()}

    fig, ax = plt.subplots(figsize=(10, 5))
    x = np.arange(len(profiles))
    width = 0.20
    offsets = np.array([-1.5, -0.5, 0.5, 1.5]) * width

    for (name, fracs), offset, color in zip(fractions.items(), offsets,
                                             ["#2C3E50", "#C0392B", "#27AE60", "#8E44AD"]):
        bars = ax.bar(x + offset, fracs, width, label=name, color=color, alpha=0.85)
        for bar, val in zip(bars, fracs):
            if val > 0.05:
                ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.01,
                        f"{val:.0%}", ha="center", va="bottom", fontsize=8)

    ax.set_xticks(x)
    ax.set_xticklabels(profiles)
    ax.set_ylabel("Fraction of Tracts")
    ax.set_ylim(0, 1.1)
    ax.set_title("Risk Profile Distribution: NC vs. TN (Statewide and Helene-Affected Counties)")
    ax.legend(frameon=False)
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    if save_path:
        fig.savefig(save_path, dpi=200, bbox_inches="tight")
        print(f"  Saved: {save_path}")
    else:
        plt.show()
    plt.close(fig)


def plot_quarterly_recovery(nc_quarters_path: Path, tn_quarters_path: Path,
                             save_path: Path | None) -> None:
    """Overlaid quarterly latency trend — WNC vs. ETN focal counties."""
    nc_files = sorted(DATA_PROCESSED.glob("habri_current_*.csv"))
    tn_files = sorted(DATA_PROCESSED.glob("habri_tn_current_*.csv"))

    if not nc_files and not tn_files:
        print("  Skipping recovery trend (no quarterly files found)")
        return

    def _mean_latency(csv_files, fips_set, state_prefix):
        rows = []
        for f in csv_files:
            tag = f.stem.replace(f"habri_{state_prefix}_current_", "").replace(
                "habri_current_", "")
            if "_q" not in tag:
                continue
            parts = tag.split("_q")
            if len(parts) != 2:
                continue
            try:
                year, q = int(parts[0]), int(parts[1])
            except ValueError:
                continue
            df = pd.read_csv(f, dtype={"GEOID": str})
            df["county_fips"] = df["GEOID"].str[:5]
            sub = df[df["county_fips"].isin(fips_set)]
            if "HABRI" in sub.columns and len(sub) > 0:
                rows.append({"year": year, "quarter": q,
                             "HABRI_mean": sub["HABRI"].mean(),
                             "label": f"Q{q} {year}"})
        if not rows:
            return pd.DataFrame(columns=["year", "quarter", "HABRI_mean", "label"])
        return pd.DataFrame(rows).sort_values(["year", "quarter"])

    wnc_trend = _mean_latency(nc_files, WNC_FIPS_5, "")
    etn_trend = _mean_latency(tn_files, ETN_FIPS_5, "tn")

    if wnc_trend.empty and etn_trend.empty:
        print("  Skipping recovery trend (no usable quarterly data)")
        return

    fig, ax = plt.subplots(figsize=(11, 5))
    if not wnc_trend.empty:
        ax.plot(wnc_trend["label"], wnc_trend["HABRI_mean"],
                color="#C0392B", lw=2.2, marker="o", ms=6, label="WNC focal counties")
    if not etn_trend.empty:
        ax.plot(etn_trend["label"], etn_trend["HABRI_mean"],
                color="#27AE60", lw=2.2, marker="s", ms=6, label="ETN focal counties")

    ax.set_ylabel("Mean HABRI Score")
    ax.set_title("Post-Helene Recovery: WNC vs. ETN Quarterly HABRI Trend")
    ax.legend(frameon=False)
    ax.grid(axis="y", alpha=0.3)
    plt.xticks(rotation=45, ha="right")
    fig.tight_layout()
    if save_path:
        fig.savefig(save_path, dpi=200, bbox_inches="tight")
        print(f"  Saved: {save_path}")
    else:
        plt.show()
    plt.close(fig)


# ── Summary stats ─────────────────────────────────────────────────────────────

def print_summary(nc: gpd.GeoDataFrame, tn: gpd.GeoDataFrame) -> None:
    print(f"\n{'='*60}")
    print("Cross-state summary")
    print(f"{'='*60}")
    for label, gdf, fips_set in [
        ("NC statewide",  nc, None),
        ("WNC counties",  nc, WNC_FIPS_5),
        ("TN statewide",  tn, None),
        ("ETN counties",  tn, ETN_FIPS_5),
    ]:
        sub = gdf if fips_set is None else gdf[gdf["county_fips"].isin(fips_set)]
        h = sub["HABRI"]
        print(f"\n{label} ({len(sub)} tracts):")
        print(f"  HABRI  mean={h.mean():.4f}  SD={h.std():.4f}  "
              f"range=[{h.min():.4f}, {h.max():.4f}]")
        if "risk_profile" in sub.columns:
            for p, n in sub["risk_profile"].value_counts().items():
                print(f"  {p:20s} {n:4d}  ({n/len(sub)*100:.1f}%)")


# ── Main ──────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Cross-state WNC vs. ETN Helene comparison figures.")
    p.add_argument("--no-save", action="store_true",
                   help="Display figures instead of saving")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    save = not args.no_save

    print(f"\n{'='*60}")
    print("HABRI — Cross-State NC/TN Helene Comparison")
    print(f"{'='*60}\n")

    nc = load_nc()
    tn = load_tn()
    print(f"NC: {len(nc)} tracts | TN: {len(tn)} tracts")

    nc_l3, nc_l4 = load_helene_latency_nc(nc)
    tn_l3, tn_l4 = load_helene_latency_tn(tn)

    print_summary(nc, tn)

    print("\nGenerating figures…")
    plot_side_by_side_map(
        nc, tn,
        DATA_PROCESSED / "habri_wnc_etn_map.png" if save else None,
    )
    plot_helene_validation(
        nc, tn, nc_l3, nc_l4, tn_l3, tn_l4,
        DATA_PROCESSED / "habri_helene_validation_combined.png" if save else None,
    )
    plot_profile_comparison(
        nc, tn,
        DATA_PROCESSED / "habri_wnc_etn_profiles.png" if save else None,
    )
    plot_quarterly_recovery(
        DATA_PROCESSED, DATA_PROCESSED,
        DATA_PROCESSED / "habri_wnc_etn_recovery.png" if save else None,
    )
    print("\nDone.")


if __name__ == "__main__":
    main()
