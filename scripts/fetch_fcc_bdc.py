#!/usr/bin/env python3
"""Process FCC Broadband Data Collection (BDC) availability data for NC.

Computes per-tract wired broadband availability fraction (p_wired):
the proportion of residential locations in each census tract where at least
one provider offers a wired technology (DSL, cable/HFC, or optical fiber).

p_wired is used as the adaptive-weighting signal in I_F: tracts with high
wired availability have road_fragility weighted upward (wired infrastructure
follows road rights-of-way); tracts with low wired availability have
tower_density_norm weighted upward instead.

Manual Download Required
------------------------
The FCC BDC bulk download interface requires browser authentication and does
not support unauthenticated programmatic access. Download the data manually:

1. Go to: https://broadbandmap.fcc.gov/data-download/bulk-download
2. Select:
     State: North Carolina
     Category: Availability Data
     Data Type: Fixed Broadband
     Filing Date: [most recent available — typically Dec or Jun of prior year]
3. Click Download. You will receive a ZIP file.
4. Extract the CSV and place it at:
     data/raw/bdc_nc_fixed_availability.csv

   (Any filename matching data/raw/bdc_nc_*.csv will also be detected.)

BDC Technology Codes Used
--------------------------
Wired (used to compute p_wired):
    10  — DSL
    40  — Cable/HFC
    50  — Optical Fiber
    0   — Other wired

Fixed Wireless (excluded from p_wired — does not follow road ROW):
    61  — License-Exempt Fixed Wireless
    62  — Non-LTE Licensed Fixed Wireless
    63  — Licensed LTE Fixed Wireless
    64  — Licensed 5G NR Fixed Wireless
    70  — Fixed Wireless (legacy BDC code)
    71–74 — Fixed Wireless (alternate legacy codes)

Mobile (excluded from p_wired):
    300 — LTE
    301 — 5G NR
    302 — Other mobile

Output
------
data/processed/fcc_bdc_wired_fraction.csv
    Columns: GEOID (11-digit tract), p_wired, n_blocks_total, n_blocks_wired,
             n_locations_total, n_locations_wired, bdc_filing_note

Usage
-----
    python scripts/fetch_fcc_bdc.py
    python scripts/fetch_fcc_bdc.py --input data/raw/bdc_nc_fixed_availability.csv
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import DATA_PROCESSED, DATA_RAW, STATE_FIPS

# ── Constants ─────────────────────────────────────────────────────────────────

# Technology codes treated as "wired" for p_wired computation.
# These technologies run physical wire to the premises and are co-located
# with road rights-of-way, making road_fragility a relevant fragility proxy.
WIRED_TECH_CODES = {10, 40, 50, 0}

# Expected columns in the BDC availability CSV (FCC BDC format, 2022+)
# The filing may have additional columns; only these are used.
BDC_REQUIRED_COLS = {
    "location_id",
    "technology",
    "business_residential_code",
    "block_geoid",
}

MANUAL_DOWNLOAD_INSTRUCTIONS = """
  ┌─────────────────────────────────────────────────────────┐
  │  FCC BDC — Manual Download Required                    │
  ├─────────────────────────────────────────────────────────┤
  │  1. Go to:                                             │
  │     https://broadbandmap.fcc.gov/data-download/        │
  │     bulk-download                                       │
  │                                                         │
  │  2. Select:                                            │
  │     • State: North Carolina                            │
  │     • Category: Availability Data                      │
  │     • Data Type: Fixed Broadband                       │
  │     • Filing Date: most recent available               │
  │                                                         │
  │  3. Extract the CSV from the downloaded ZIP and        │
  │     place it at:                                        │
  │     data/raw/bdc_nc_fixed_availability.csv             │
  │                                                         │
  │  4. Re-run this script.                                │
  └─────────────────────────────────────────────────────────┘
"""


# ── File detection ────────────────────────────────────────────────────────────

def find_bdc_csv(explicit_path: str | None) -> Path | None:
    """Return the BDC CSV path, searching common locations."""
    if explicit_path:
        p = Path(explicit_path)
        return p if p.exists() else None

    # Preferred name
    preferred = DATA_RAW / "bdc_nc_fixed_availability.csv"
    if preferred.exists():
        return preferred

    # Any bdc_nc_*.csv in data/raw/
    matches = sorted(DATA_RAW.glob("bdc_nc_*.csv"))
    if matches:
        return matches[-1]  # most recently modified

    # Unzipped with FCC's original naming convention
    fcc_pattern = DATA_RAW.glob("BDC_NC_Fixed_Broadband_*.csv")
    matches = sorted(fcc_pattern)
    if matches:
        return matches[-1]

    return None


# ── Processing ────────────────────────────────────────────────────────────────

def _infer_filing_note(path: Path) -> str:
    """Extract a filing date hint from the filename if present."""
    stem = path.stem.upper()
    for part in stem.split("_"):
        if len(part) == 6 and part.isdigit():
            return f"BDC filing {part[:4]}-{part[4:]}"
        if len(part) == 8 and part.isdigit():
            return f"BDC filing {part[:4]}-{part[4:6]}-{part[6:]}"
    return "BDC filing date unknown (check filename)"


def process_bdc(csv_path: Path, chunk_size: int = 500_000) -> pd.DataFrame:
    """Compute per-tract p_wired from a BDC availability CSV.

    Parameters
    ----------
    csv_path : Path
        Path to the BDC fixed broadband availability CSV.
    chunk_size : int
        Rows per pandas chunk (BDC NC files are typically 3–8 M rows).

    Returns
    -------
    DataFrame with columns: GEOID, p_wired, n_blocks_total, n_blocks_wired,
                            n_locations_total, n_locations_wired, bdc_filing_note
    """
    filing_note = _infer_filing_note(csv_path)
    print(f"  Processing: {csv_path.name}")
    print(f"  Filing note: {filing_note}")

    # Accumulate per-block wired/total location counts across chunks
    # block_geoid → {wired_locs: set, all_locs: set}
    block_wired: dict[str, set] = {}
    block_all: dict[str, set] = {}

    chunk_num = 0
    total_rows = 0
    nc_prefix = STATE_FIPS  # "37"

    for chunk in pd.read_csv(
        csv_path,
        dtype=str,
        chunksize=chunk_size,
        low_memory=False,
    ):
        chunk_num += 1
        chunk.columns = [c.strip().lower() for c in chunk.columns]

        # Validate columns on first chunk
        if chunk_num == 1:
            missing = BDC_REQUIRED_COLS - set(chunk.columns)
            if missing:
                raise ValueError(
                    f"BDC CSV is missing expected columns: {missing}\n"
                    f"Found: {list(chunk.columns[:12])}..."
                )
            print(f"  Columns detected: {list(chunk.columns[:8])}...")

        # Filter to NC blocks
        if "state_usps" in chunk.columns:
            chunk = chunk[chunk["state_usps"].str.strip().str.upper() == "NC"]
        else:
            # Fall back to block_geoid prefix
            chunk = chunk[chunk["block_geoid"].str.startswith(nc_prefix, na=False)]

        if chunk.empty:
            continue

        # Filter to residential + mixed locations only
        if "business_residential_code" in chunk.columns:
            chunk = chunk[
                chunk["business_residential_code"].str.strip().str.upper().isin({"X", "R"})
            ]

        # Parse technology code
        chunk["tech_int"] = pd.to_numeric(chunk["technology"], errors="coerce").fillna(-1).astype(int)
        chunk["is_wired"] = chunk["tech_int"].isin(WIRED_TECH_CODES)

        # Accumulate per block
        for _, row in chunk.iterrows():
            bg = row["block_geoid"]
            loc = row["location_id"]
            block_all.setdefault(bg, set()).add(loc)
            if row["is_wired"]:
                block_wired.setdefault(bg, set()).add(loc)

        total_rows += len(chunk)
        if chunk_num % 5 == 0:
            print(f"  Processed {total_rows:,} rows, {len(block_all):,} NC blocks so far...")

    print(f"  Total NC rows processed: {total_rows:,}")
    print(f"  Total NC blocks found: {len(block_all):,}")

    if not block_all:
        raise ValueError(
            "No NC blocks found after filtering. "
            "Check that the CSV contains NC data (STATE_FIPS='37') and correct column names."
        )

    # Build block-level summary
    rows = []
    for bg, all_locs in block_all.items():
        wired_locs = block_wired.get(bg, set())
        rows.append({
            "block_geoid": bg,
            "n_locations": len(all_locs),
            "n_wired_locations": len(wired_locs),
            "has_wired": len(wired_locs) > 0,
        })
    blocks_df = pd.DataFrame(rows)
    blocks_df["tract_geoid"] = blocks_df["block_geoid"].str[:11].str.zfill(11)

    # Aggregate to tract: location-weighted p_wired
    tracts = (
        blocks_df.groupby("tract_geoid")
        .agg(
            n_blocks_total=("block_geoid", "count"),
            n_blocks_wired=("has_wired", "sum"),
            n_locations_total=("n_locations", "sum"),
            n_locations_wired=("n_wired_locations", "sum"),
        )
        .reset_index()
        .rename(columns={"tract_geoid": "GEOID"})
    )

    # p_wired = location-weighted fraction with wired service available
    tracts["p_wired"] = np.where(
        tracts["n_locations_total"] > 0,
        tracts["n_locations_wired"] / tracts["n_locations_total"],
        np.nan,
    )
    tracts["bdc_filing_note"] = filing_note

    return tracts


# ── Summary ───────────────────────────────────────────────────────────────────

def print_summary(df: pd.DataFrame) -> None:
    """Print a summary of the p_wired distribution."""
    valid = df["p_wired"].dropna()
    print(f"\n  Tracts with BDC data:   {len(df):,}")
    print(f"  Tracts with p_wired:    {valid.notna().sum():,}")
    print(f"  p_wired distribution:")
    print(f"    mean  = {valid.mean():.4f}")
    print(f"    median= {valid.median():.4f}")
    print(f"    SD    = {valid.std():.4f}")
    print(f"    range = [{valid.min():.4f}, {valid.max():.4f}]")

    # Quintile breakdown
    labels = ["0–20%", "20–40%", "40–60%", "60–80%", "80–100%"]
    cuts = pd.cut(valid, bins=[0, 0.2, 0.4, 0.6, 0.8, 1.001],
                  labels=labels, include_lowest=True)
    print(f"  Wired availability quintiles:")
    for label, count in cuts.value_counts(sort=False).items():
        pct = count / len(valid) * 100
        print(f"    {label}: {count:,} tracts ({pct:.1f}%)")

    # Flag tracts with no wired availability at all
    n_zero = (valid == 0).sum()
    print(f"\n  Tracts with zero wired availability: {n_zero:,} "
          f"({n_zero/len(valid)*100:.1f}%) — tower weight maximised")


# ── CLI ───────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Process FCC BDC availability data → per-tract p_wired."
    )
    p.add_argument("--input", type=str, default=None,
                   help="Explicit path to BDC CSV (auto-detected if omitted)")
    return p.parse_args()


def main() -> None:
    args = parse_args()

    print(f"\n{'='*60}")
    print("HABRI — FCC BDC Wired Availability Processing")
    print(f"{'='*60}\n")

    csv_path = find_bdc_csv(args.input)

    if csv_path is None:
        print("ERROR: FCC BDC availability CSV not found.")
        print(MANUAL_DOWNLOAD_INSTRUCTIONS)
        sys.exit(1)

    print(f"[1/2] Processing BDC availability CSV")
    df = process_bdc(csv_path)

    print(f"\n[2/2] Saving output")
    out_csv = DATA_PROCESSED / "fcc_bdc_wired_fraction.csv"
    df.to_csv(out_csv, index=False)
    print(f"  Saved → {out_csv}")

    print_summary(df)

    print("\nNext step: run scripts/integrate_power_grid.py to rebuild I_F with adaptive weights.")


if __name__ == "__main__":
    main()
