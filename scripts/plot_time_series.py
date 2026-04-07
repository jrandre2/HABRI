#!/usr/bin/env python3
"""Multi-quarter HABRI time series visualization.

Combines all versioned HABRI quarterly outputs into publication-quality figures
showing statewide trends and WNC recovery trajectories following Hurricane Helene.

Figures produced
----------------
data/processed/habri_timeseries_statewide.png
    Line chart of mean HABRI score and sub-index means (H_E, I_F, C_C) across
    all available quarters. Helene event marked as a vertical band.

data/processed/habri_timeseries_wnc.png
    Mean HABRI score for each WNC county (Henderson, Haywood, Madison, Mitchell,
    Yancey, Buncombe) vs. NC statewide mean, by quarter.

data/processed/habri_timeseries_profiles.png
    Stacked bar chart showing fraction of tracts in each risk profile per quarter
    (Transport-Fragile / Dual-Risk / Power-Dependent).

data/processed/habri_recovery_scatter.png
    Scatter plot of baseline HABRI (Q3 2024) vs. Q4 2025 HABRI for WNC tracts,
    coloured by risk profile — shows which high-risk tracts recovered.

Usage
-----
    python scripts/plot_time_series.py
    python scripts/plot_time_series.py --no-save   # display only, do not write files
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.lines as mlines
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import DATA_PROCESSED, DATA_RAW, STATE_FIPS

# ── Style ─────────────────────────────────────────────────────────────────────

PROFILE_COLORS = {
    "Power-Dependent": "#88CCEE",
    "Transport-Fragile": "#CC6677",
    "Dual-Risk": "#DDCC77",
}

SUBINDEX_COLORS = {
    "HABRI": "#2C3E50",
    "H_E": "#C0392B",
    "I_F": "#8E44AD",
    "C_C": "#27AE60",
}

WNC_COUNTY_FIPS = {
    "Buncombe": "37021",
    "Haywood": "37087",
    "Henderson": "37089",
    "Madison": "37115",
    "Mitchell": "37121",
    "Yancey": "37199",
}

WNC_COLORS = {
    "Buncombe":  "#1f77b4",
    "Haywood":   "#ff7f0e",
    "Henderson": "#d62728",   # hardest hit
    "Madison":   "#9467bd",
    "Mitchell":  "#8c564b",
    "Yancey":    "#e377c2",
}

# Hurricane Helene: landfall 2024-09-26; Q3 2024 ends 2024-09-30
# So Helene fell in the last days of Q3 2024 and the full impact shows in Q4 2024
HELENE_LABEL = "Hurricane\nHelene"


# ── Data loading ──────────────────────────────────────────────────────────────

def _quarter_label(year: int, quarter: int) -> str:
    return f"Q{quarter} {year}"


def load_all_quarters() -> dict[str, pd.DataFrame]:
    """Load all available HABRI quarterly CSV files in chronological order.

    Returns a dict keyed by quarter label (e.g. 'Q3 2024'), value is the DataFrame.
    """
    quarters: dict[tuple[int, int], pd.DataFrame] = {}

    # Baseline: Q3 2024 (pre-Helene) — from habri_composite.csv
    baseline = DATA_PROCESSED / "habri_composite.csv"
    if baseline.exists():
        df = pd.read_csv(baseline, dtype={"GEOID": str})
        df["GEOID"] = df["GEOID"].str.zfill(11)
        quarters[(2024, 3)] = df

    # Quarterly versioned files
    for csv in sorted(DATA_PROCESSED.glob("habri_current_*.csv")):
        stem = csv.stem.replace("habri_current_", "")
        # Expected format: YYYY_qN  (e.g. 2024_q4, 2025_q1)
        if "_q" not in stem:
            continue
        parts = stem.split("_q")
        if len(parts) != 2:
            continue
        try:
            year, quarter = int(parts[0]), int(parts[1])
        except ValueError:
            continue
        if (year, quarter) == (2024, 3):
            continue  # already loaded as baseline
        df = pd.read_csv(csv, dtype={"GEOID": str})
        df["GEOID"] = df["GEOID"].str.zfill(11)
        quarters[(year, quarter)] = df

    # Sort chronologically
    return {
        _quarter_label(y, q): quarters[(y, q)]
        for y, q in sorted(quarters.keys())
    }


def build_statewide_stats(quarters: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Compute statewide mean of HABRI and sub-indices for each quarter."""
    rows = []
    for label, df in quarters.items():
        row: dict = {"quarter": label}
        for col in ["HABRI", "H_E", "I_F", "C_C"]:
            if col in df.columns:
                row[col] = df[col].mean()
        rows.append(row)
    return pd.DataFrame(rows)


def build_county_stats(quarters: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Compute mean HABRI per WNC county (and statewide) for each quarter."""
    rows = []
    for label, df in quarters.items():
        df["county_fips5"] = df["GEOID"].str[:5]
        row: dict = {"quarter": label}
        row["NC_mean"] = df["HABRI"].mean()
        for county, fips in WNC_COUNTY_FIPS.items():
            sub = df[df["county_fips5"] == fips]
            row[county] = sub["HABRI"].mean() if len(sub) > 0 else np.nan
        rows.append(row)
    return pd.DataFrame(rows)


def build_profile_counts(quarters: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Count tracts per risk profile per quarter (as fractions)."""
    rows = []
    for label, df in quarters.items():
        if "risk_profile" not in df.columns:
            continue
        total = len(df)
        row: dict = {"quarter": label}
        for profile in PROFILE_COLORS:
            row[profile] = (df["risk_profile"] == profile).sum() / total
        rows.append(row)
    return pd.DataFrame(rows)


# ── Plots ─────────────────────────────────────────────────────────────────────

def _helene_xrange(labels: list[str]) -> tuple[float, float] | None:
    """Return (xmin, xmax) for the Helene impact band, or None if not applicable."""
    # Helene hit in Q3 2024; impact visible Q3→Q4 2024 transition
    q3 = "Q3 2024"
    q4 = "Q4 2024"
    if q3 in labels and q4 in labels:
        xi = labels.index(q3)
        return (xi + 0.5, xi + 1.0)
    return None


def plot_statewide(stats: pd.DataFrame, save_path: Path | None) -> None:
    """Line chart of mean sub-index scores across quarters."""
    fig, ax = plt.subplots(figsize=(11, 5))

    labels = stats["quarter"].tolist()
    x = np.arange(len(labels))

    for col, color in SUBINDEX_COLORS.items():
        if col not in stats.columns:
            continue
        lw = 2.5 if col == "HABRI" else 1.6
        ls = "-" if col == "HABRI" else "--"
        ax.plot(x, stats[col], color=color, lw=lw, ls=ls, marker="o", ms=5, label=col)

    # Helene band
    hr = _helene_xrange(labels)
    if hr:
        ax.axvspan(hr[0], hr[1], color="#C0392B", alpha=0.12, zorder=0)
        ax.text((hr[0] + hr[1]) / 2, ax.get_ylim()[1] * 0.97,
                HELENE_LABEL, ha="center", va="top", color="#C0392B",
                fontsize=8, style="italic")

    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=45, ha="right")
    ax.set_ylabel("Mean Score (0–1, 1 = highest risk)")
    ax.set_title("HABRI Statewide Quarterly Trend — All NC Tracts (n=2,660)")
    ax.legend(frameon=False, ncol=2)
    ax.set_ylim(0, 0.75)
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()

    if save_path:
        fig.savefig(save_path, dpi=300, bbox_inches="tight")
        print(f"  Saved: {save_path}")
    else:
        plt.show()
    plt.close(fig)


def plot_wnc_counties(county_stats: pd.DataFrame, save_path: Path | None) -> None:
    """Mean HABRI by WNC county vs. NC statewide mean."""
    fig, ax = plt.subplots(figsize=(11, 5))

    labels = county_stats["quarter"].tolist()
    x = np.arange(len(labels))

    # NC statewide (dashed grey)
    ax.plot(x, county_stats["NC_mean"], color="grey", lw=1.5, ls="--",
            label="NC statewide mean", zorder=2)

    for county, color in WNC_COLORS.items():
        if county in county_stats.columns:
            ax.plot(x, county_stats[county], color=color, lw=2.2,
                    marker="o", ms=5, label=county, zorder=3)

    # Helene band
    hr = _helene_xrange(labels)
    if hr:
        ax.axvspan(hr[0], hr[1], color="#C0392B", alpha=0.12, zorder=0)
        ax.text((hr[0] + hr[1]) / 2, ax.get_ylim()[1] * 0.97,
                HELENE_LABEL, ha="center", va="top", color="#C0392B",
                fontsize=8, style="italic")

    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=45, ha="right")
    ax.set_ylabel("Mean HABRI Score")
    ax.set_title("Western NC County HABRI Trends — Hurricane Helene Impact and Recovery")
    ax.legend(frameon=False, ncol=3, fontsize=9)
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()

    if save_path:
        fig.savefig(save_path, dpi=300, bbox_inches="tight")
        print(f"  Saved: {save_path}")
    else:
        plt.show()
    plt.close(fig)


def plot_profile_stack(profile_counts: pd.DataFrame, save_path: Path | None) -> None:
    """Stacked bar showing risk profile fraction per quarter."""
    if profile_counts.empty:
        print("  No risk_profile data found — skipping profile time series.")
        return

    fig, ax = plt.subplots(figsize=(11, 4))
    labels = profile_counts["quarter"].tolist()
    x = np.arange(len(labels))
    width = 0.6

    bottom = np.zeros(len(labels))
    for profile, color in PROFILE_COLORS.items():
        if profile not in profile_counts.columns:
            continue
        vals = profile_counts[profile].fillna(0).values
        ax.bar(x, vals, width, bottom=bottom, color=color, label=profile,
               edgecolor="white", linewidth=0.5)
        bottom += vals

    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=45, ha="right")
    ax.set_ylabel("Fraction of Tracts")
    ax.set_title("Risk Profile Distribution by Quarter — All NC Tracts")
    ax.set_ylim(0, 1.05)
    ax.legend(frameon=False, loc="upper right")
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()

    if save_path:
        fig.savefig(save_path, dpi=300, bbox_inches="tight")
        print(f"  Saved: {save_path}")
    else:
        plt.show()
    plt.close(fig)


def plot_wnc_recovery_scatter(
    quarters: dict[str, pd.DataFrame],
    save_path: Path | None,
) -> None:
    """Scatter of baseline HABRI vs. latest quarterly HABRI for WNC tracts."""
    baseline_label = "Q3 2024"
    latest_label = sorted(quarters.keys())[-1]

    if baseline_label not in quarters or latest_label == baseline_label:
        print("  Skipping recovery scatter — insufficient quarters.")
        return

    baseline = quarters[baseline_label].copy()
    latest = quarters[latest_label].copy()
    baseline["county5"] = baseline["GEOID"].str[:5]

    wnc_fips = set(WNC_COUNTY_FIPS.values())
    wnc_base = baseline[baseline["county5"].isin(wnc_fips)][["GEOID", "HABRI", "risk_profile"]].copy()
    wnc_base.columns = ["GEOID", "HABRI_base", "risk_profile"]

    wnc_latest = latest[["GEOID", "HABRI"]].rename(columns={"HABRI": "HABRI_latest"})
    merged = wnc_base.merge(wnc_latest, on="GEOID", how="inner").dropna()

    fig, ax = plt.subplots(figsize=(6, 6))

    for profile, color in PROFILE_COLORS.items():
        sub = merged[merged["risk_profile"] == profile]
        ax.scatter(sub["HABRI_base"], sub["HABRI_latest"],
                   color=color, alpha=0.7, s=25, label=profile, zorder=3)

    # 1:1 line
    lims = [min(merged["HABRI_base"].min(), merged["HABRI_latest"].min()) - 0.02,
            max(merged["HABRI_base"].max(), merged["HABRI_latest"].max()) + 0.02]
    ax.plot(lims, lims, color="grey", lw=1.5, ls="--", zorder=2, label="No change")
    ax.set_xlim(lims)
    ax.set_ylim(lims)

    ax.set_xlabel(f"HABRI Score ({baseline_label} — pre-Helene)")
    ax.set_ylabel(f"HABRI Score ({latest_label})")
    ax.set_title(f"Western NC Recovery: {baseline_label} → {latest_label}")
    ax.legend(frameon=False, fontsize=9)
    ax.grid(alpha=0.3)
    fig.tight_layout()

    if save_path:
        fig.savefig(save_path, dpi=300, bbox_inches="tight")
        print(f"  Saved: {save_path}")
    else:
        plt.show()
    plt.close(fig)


# ── Main ──────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Generate HABRI multi-quarter time series figures.")
    p.add_argument("--no-save", action="store_true",
                   help="Display figures interactively instead of saving")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    save = not args.no_save

    print(f"\n{'='*60}")
    print("HABRI — Time Series Visualization")
    print(f"{'='*60}\n")

    print("[1/2] Loading quarterly data")
    quarters = load_all_quarters()
    if not quarters:
        print("ERROR: No quarterly CSV files found in data/processed/")
        sys.exit(1)
    print(f"  Found {len(quarters)} quarters: {list(quarters.keys())}")

    statewide = build_statewide_stats(quarters)
    county_stats = build_county_stats(quarters)
    profile_counts = build_profile_counts(quarters)

    print("\n[2/2] Generating figures")
    plot_statewide(
        statewide,
        DATA_PROCESSED / "habri_timeseries_statewide.png" if save else None,
    )
    plot_wnc_counties(
        county_stats,
        DATA_PROCESSED / "habri_timeseries_wnc.png" if save else None,
    )
    plot_profile_stack(
        profile_counts,
        DATA_PROCESSED / "habri_timeseries_profiles.png" if save else None,
    )
    plot_wnc_recovery_scatter(
        quarters,
        DATA_PROCESSED / "habri_recovery_scatter.png" if save else None,
    )

    print("\nDone.")
    print("\nQuarterly summary (statewide mean HABRI):")
    for _, row in statewide.iterrows():
        habri_val = f"{row['HABRI']:.4f}" if "HABRI" in row else "N/A"
        print(f"  {row['quarter']:12s}  {habri_val}")


if __name__ == "__main__":
    main()
