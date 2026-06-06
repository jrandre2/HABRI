#!/usr/bin/env python3
"""Fetch and process FCC BDC fixed-broadband availability into tract-level p_wired.

This script now supports multiple states and uses the public FCC National
Broadband Map download API to retrieve the statewide fixed-broadband
technology files for a given filing. It computes per-tract wired availability
fraction (`p_wired`): the share of residential or mixed-use locations in each
tract where at least one wired fixed-broadband technology is available.

`p_wired` is the adaptive-weighting signal for HABRI Infrastructure Fragility
(`I_F`). Tracts with higher wired availability weight road fragility more
heavily; tracts with lower wired availability weight tower density more
heavily.

Wired technologies counted in `p_wired`
---------------------------------------
    0   Other wired
    10  Copper / DSL
    40  Cable / HFC
    50  Fiber to the premises

Other fixed technologies remain part of the denominator but not the wired
numerator:
    60  GSO Satellite
    61  NGSO Satellite
    70  Unlicensed Fixed Wireless
    71  Licensed Fixed Wireless
    72  LBR Fixed Wireless

Outputs
-------
data/processed/fcc_bdc_wired_fraction_<state>.csv
    Columns: GEOID, p_wired, n_blocks_total, n_blocks_wired,
             n_locations_total, n_locations_wired, state_fips, state_abbr,
             process_uuid, bdc_filing_note

For North Carolina, the script also writes the legacy path:
data/processed/fcc_bdc_wired_fraction.csv

Usage
-----
    python scripts/fetch_fcc_bdc.py --state NC
    python scripts/fetch_fcc_bdc.py --state TN
    python scripts/fetch_fcc_bdc.py --state TN --process-uuid <uuid>
    python scripts/fetch_fcc_bdc.py --state NC --input data/raw/bdc_nc*.csv
"""

from __future__ import annotations

import argparse
import io
import sys
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import requests

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import DATA_PROCESSED, DATA_RAW

# ── Constants ─────────────────────────────────────────────────────────────────

STATE_INFO = {
    "NC": {"abbr": "NC", "fips": "37", "name": "North Carolina"},
    "37": {"abbr": "NC", "fips": "37", "name": "North Carolina"},
    "TN": {"abbr": "TN", "fips": "47", "name": "Tennessee"},
    "47": {"abbr": "TN", "fips": "47", "name": "Tennessee"},
}

WIRED_TECH_CODES = {0, 10, 40, 50}

BDC_REQUIRED_COLS = {
    "location_id",
    "technology",
    "business_residential_code",
    "block_geoid",
}

FCC_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://broadbandmap.fcc.gov/data-download/nationwide-data",
    "Origin": "https://broadbandmap.fcc.gov",
}

FCC_API_BASE = "https://broadbandmap.fcc.gov/nbm/map/api"
FCC_PROCESS_BASE = "https://broadbandmap.fcc.gov/api/reference"


# ── Helpers ───────────────────────────────────────────────────────────────────

def resolve_state(spec: str) -> dict[str, str]:
    key = spec.strip().upper()
    if key not in STATE_INFO:
        valid = ", ".join(sorted({"NC", "TN", "37", "47"}))
        raise ValueError(f"Unsupported state '{spec}'. Expected one of: {valid}")
    return STATE_INFO[key]


def _request_json(url: str) -> dict:
    resp = requests.get(url, headers=FCC_HEADERS, timeout=120)
    resp.raise_for_status()
    return resp.json()


def latest_process() -> dict:
    data = _request_json(f"{FCC_API_BASE}/published/downloads").get("data", [])
    if not data:
        raise RuntimeError("FCC published/downloads API returned no filings.")
    return data[0]


def process_metadata(process_uuid: str) -> dict:
    data = _request_json(f"{FCC_PROCESS_BASE}/map_processing_updates/{process_uuid}").get("data", [])
    if not data:
        raise RuntimeError(f"No FCC processing metadata found for process_uuid={process_uuid}")
    return data[0]


def list_statewide_fixed_downloads(process_uuid: str, state_fips: str) -> list[dict]:
    rows = _request_json(
        f"{FCC_API_BASE}/national_map_process/nbm_get_data_download/{process_uuid}/"
    ).get("data", [])

    statewide = [
        row
        for row in rows
        if row.get("state_fips") == state_fips
        and (row.get("data_type") or "").lower() == "fixed broadband"
        and (row.get("data_category") or "").lower() == "nationwide"
        and row.get("download_available") == "Yes"
        and row.get("provider_id") in (None, "")
    ]

    statewide.sort(key=lambda row: int(str(row.get("technology_code", "999")).split(",")[0]))
    if not statewide:
        raise RuntimeError(
            f"No statewide fixed-broadband downloads found for state_fips={state_fips} "
            f"and process_uuid={process_uuid}."
        )
    return statewide


def expand_inputs(patterns: list[str] | None) -> list[Path]:
    if not patterns:
        return []

    paths: list[Path] = []
    for pattern in patterns:
        has_glob = any(ch in pattern for ch in "*?[]")
        if Path(pattern).is_absolute():
            abs_pattern = Path(pattern)
            if has_glob:
                matches = sorted(abs_pattern.parent.glob(abs_pattern.name))
            else:
                matches = [abs_pattern] if abs_pattern.exists() else []
        elif any(ch in pattern for ch in "*?[]"):
            matches = sorted(PROJECT_ROOT.glob(pattern))
        else:
            candidate = PROJECT_ROOT / pattern
            matches = [candidate] if candidate.exists() else []
        paths.extend(matches)

    deduped = []
    seen: set[Path] = set()
    for path in paths:
        resolved = path.resolve()
        if resolved not in seen:
            deduped.append(resolved)
            seen.add(resolved)
    return deduped


def download_state_files(
    downloads: list[dict],
    *,
    state_abbr: str,
    process_uuid: str,
    refresh: bool,
) -> list[Path]:
    out_dir = DATA_RAW / "fcc_bdc" / state_abbr.lower() / process_uuid
    out_dir.mkdir(parents=True, exist_ok=True)

    paths: list[Path] = []
    total = len(downloads)
    for idx, row in enumerate(downloads, start=1):
        file_name = f"{row['file_name']}.csv.zip"
        out_path = out_dir / file_name
        if out_path.exists() and not refresh:
            print(f"  [{idx}/{total}] Cached: {out_path.name}")
            paths.append(out_path)
            continue

        url = f"{FCC_API_BASE}/getNBMDataDownloadFile/{row['id']}/1"
        print(
            f"  [{idx}/{total}] Downloading {row['technology_code_desc']} "
            f"({row['technology_code']}) → {out_path.name}"
        )
        with requests.get(url, headers=FCC_HEADERS, timeout=300, stream=True) as resp:
            resp.raise_for_status()
            with out_path.open("wb") as fh:
                for chunk in resp.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        fh.write(chunk)
        paths.append(out_path)
    return paths


def _infer_filing_note(metadata: dict) -> str:
    as_of = metadata.get("data_as_of_date", "unknown")
    updated = metadata.get("last_updated_date", "unknown")
    process_uuid = metadata.get("process_uuid", "unknown")
    return f"BDC filing {as_of} (last updated {updated}; process {process_uuid})"


def _iter_csv_chunks(path: Path, chunk_size: int):
    if path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as zf:
            names = [name for name in zf.namelist() if name.lower().endswith(".csv")]
            if not names:
                raise ValueError(f"ZIP file contains no CSV: {path}")
            with zf.open(names[0]) as fh:
                text = io.TextIOWrapper(fh, encoding="utf-8", newline="")
                yield from pd.read_csv(text, dtype=str, chunksize=chunk_size, low_memory=False)
    else:
        yield from pd.read_csv(path, dtype=str, chunksize=chunk_size, low_memory=False)


def process_bdc_files(
    paths: list[Path],
    *,
    state_abbr: str,
    state_fips: str,
    filing_note: str,
    process_uuid: str | None,
    chunk_size: int,
) -> pd.DataFrame:
    print(f"  Processing {len(paths)} BDC source file(s)")
    print(f"  Filing note: {filing_note}")

    block_wired: dict[str, set[str]] = {}
    block_all: dict[str, set[str]] = {}

    total_rows = 0
    validated = False

    for file_idx, path in enumerate(paths, start=1):
        print(f"  Source [{file_idx}/{len(paths)}]: {path.name}")
        for chunk_idx, chunk in enumerate(_iter_csv_chunks(path, chunk_size), start=1):
            chunk.columns = [c.strip().lower() for c in chunk.columns]

            if not validated:
                missing = BDC_REQUIRED_COLS - set(chunk.columns)
                if missing:
                    raise ValueError(
                        f"BDC source is missing expected columns: {missing}\n"
                        f"Found: {list(chunk.columns[:12])}..."
                    )
                print(f"  Columns detected: {list(chunk.columns[:8])}...")
                validated = True

            if "state_usps" in chunk.columns:
                chunk = chunk[chunk["state_usps"].str.strip().str.upper() == state_abbr]
            else:
                chunk = chunk[chunk["block_geoid"].str.startswith(state_fips, na=False)]

            if "business_residential_code" in chunk.columns:
                chunk = chunk[
                    chunk["business_residential_code"]
                    .str.strip()
                    .str.upper()
                    .isin({"X", "R"})
                ]

            if chunk.empty:
                continue

            chunk = chunk[chunk["block_geoid"].notna() & chunk["location_id"].notna()].copy()
            if chunk.empty:
                continue

            chunk["tech_int"] = (
                pd.to_numeric(chunk["technology"], errors="coerce").fillna(-1).astype(int)
            )
            chunk["is_wired"] = chunk["tech_int"].isin(WIRED_TECH_CODES)

            block_geoids = chunk["block_geoid"].astype(str).to_numpy()
            location_ids = chunk["location_id"].astype(str).to_numpy()
            wired_flags = chunk["is_wired"].to_numpy()
            for block_geoid, location_id, is_wired in zip(block_geoids, location_ids, wired_flags):
                block_all.setdefault(block_geoid, set()).add(location_id)
                if is_wired:
                    block_wired.setdefault(block_geoid, set()).add(location_id)

            total_rows += len(chunk)
            if chunk_idx % 5 == 0:
                print(
                    f"    {path.name}: processed {chunk_idx} chunk(s), "
                    f"{total_rows:,} filtered rows overall"
                )

    if not block_all:
        raise ValueError(
            f"No BDC blocks found after filtering for {state_abbr}. "
            "Check the state selection and input files."
        )

    rows = []
    for block_geoid, all_locs in block_all.items():
        wired_locs = block_wired.get(block_geoid, set())
        rows.append(
            {
                "block_geoid": block_geoid,
                "n_locations": len(all_locs),
                "n_wired_locations": len(wired_locs),
                "has_wired": len(wired_locs) > 0,
            }
        )

    blocks_df = pd.DataFrame(rows)
    blocks_df["tract_geoid"] = blocks_df["block_geoid"].str[:11].str.zfill(11)

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

    tracts["p_wired"] = np.where(
        tracts["n_locations_total"] > 0,
        tracts["n_locations_wired"] / tracts["n_locations_total"],
        np.nan,
    )
    tracts["state_fips"] = state_fips
    tracts["state_abbr"] = state_abbr
    tracts["process_uuid"] = process_uuid
    tracts["bdc_filing_note"] = filing_note
    return tracts


def print_summary(df: pd.DataFrame) -> None:
    valid = df["p_wired"].dropna()
    print(f"\n  Tracts with BDC data:   {len(df):,}")
    print(f"  Tracts with p_wired:    {valid.notna().sum():,}")
    print(f"  p_wired distribution:")
    print(f"    mean  = {valid.mean():.4f}")
    print(f"    median= {valid.median():.4f}")
    print(f"    SD    = {valid.std():.4f}")
    print(f"    range = [{valid.min():.4f}, {valid.max():.4f}]")

    labels = ["0–20%", "20–40%", "40–60%", "60–80%", "80–100%"]
    cuts = pd.cut(
        valid,
        bins=[0, 0.2, 0.4, 0.6, 0.8, 1.001],
        labels=labels,
        include_lowest=True,
    )
    print("  Wired availability quintiles:")
    for label, count in cuts.value_counts(sort=False).items():
        pct = count / len(valid) * 100
        print(f"    {label}: {count:,} tracts ({pct:.1f}%)")

    n_zero = (valid == 0).sum()
    print(
        f"\n  Tracts with zero wired availability: {n_zero:,} "
        f"({n_zero / len(valid) * 100:.1f}%)"
    )


# ── CLI ───────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Fetch/process FCC BDC availability data → per-tract p_wired."
    )
    p.add_argument(
        "--state",
        default="NC",
        help="State abbreviation or FIPS (supported: NC/37, TN/47).",
    )
    p.add_argument(
        "--input",
        nargs="*",
        default=None,
        help="Optional local CSV/ZIP file(s) or glob(s). If omitted, files are downloaded from the FCC API.",
    )
    p.add_argument(
        "--process-uuid",
        default=None,
        help="FCC published download process UUID. Defaults to the latest published filing.",
    )
    p.add_argument(
        "--output",
        default=None,
        help="Optional explicit output CSV path. Defaults to data/processed/fcc_bdc_wired_fraction_<state>.csv",
    )
    p.add_argument(
        "--refresh-downloads",
        action="store_true",
        help="Re-download FCC ZIP files even if cached locally.",
    )
    p.add_argument(
        "--chunk-size",
        type=int,
        default=500_000,
        help="Rows per pandas chunk while processing source CSVs.",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
    state = resolve_state(args.state)
    state_abbr = state["abbr"]
    state_fips = state["fips"]

    print(f"\n{'=' * 60}")
    print(f"HABRI — FCC BDC Wired Availability Processing ({state_abbr})")
    print(f"{'=' * 60}\n")

    paths = expand_inputs(args.input)
    if args.input and not paths:
        raise FileNotFoundError(
            f"No local input files matched: {', '.join(args.input)}"
        )
    process_uuid = args.process_uuid
    filing_note: str

    if paths:
        print(f"[1/2] Using local BDC inputs for {state['name']}")
        print(f"  Files: {len(paths)}")
        for path in paths:
            print(f"    - {path}")
        filing_note = "BDC filing date unknown (local input)"
        process_uuid = process_uuid or None
    else:
        print(f"[1/3] Discovering FCC BDC downloads for {state['name']}")
        latest = latest_process() if process_uuid is None else {"process_uuid": process_uuid}
        process_uuid = latest["process_uuid"]
        metadata = process_metadata(process_uuid)
        filing_note = _infer_filing_note(metadata)
        print(f"  Latest process UUID: {process_uuid}")
        print(f"  Filing: {metadata.get('data_as_of_date')}  last updated {metadata.get('last_updated_date')}")

        downloads = list_statewide_fixed_downloads(process_uuid, state_fips)
        print(f"  Statewide fixed-broadband technology files: {len(downloads)}")
        for row in downloads:
            print(f"    - {row['technology_code']:>2}  {row['technology_code_desc']}")

        print(f"\n[2/3] Downloading FCC BDC ZIP files")
        paths = download_state_files(
            downloads,
            state_abbr=state_abbr,
            process_uuid=process_uuid,
            refresh=args.refresh_downloads,
        )

    step_label = "[2/2]" if args.input else "[3/3]"
    print(f"\n{step_label} Processing BDC availability data")
    df = process_bdc_files(
        paths,
        state_abbr=state_abbr,
        state_fips=state_fips,
        filing_note=filing_note,
        process_uuid=process_uuid,
        chunk_size=args.chunk_size,
    )

    out_csv = Path(args.output) if args.output else DATA_PROCESSED / f"fcc_bdc_wired_fraction_{state_abbr.lower()}.csv"
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_csv, index=False)
    print(f"\n  Saved → {out_csv}")

    if state_abbr == "NC":
        legacy_out = DATA_PROCESSED / "fcc_bdc_wired_fraction.csv"
        if legacy_out != out_csv:
            df.to_csv(legacy_out, index=False)
            print(f"  Synced legacy NC path → {legacy_out}")

    print_summary(df)

    if state_abbr == "NC":
        print("\nNext step: run scripts/integrate_power_grid.py to rebuild NC I_F with adaptive weights.")
    else:
        print(f"\nNext step: run scripts/build_habri_{state_abbr.lower()}.py to rebuild {state_abbr} with adaptive weights.")


if __name__ == "__main__":
    main()
