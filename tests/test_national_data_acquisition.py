from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = PROJECT_ROOT / "docs" / "national_data_sources.json"


def test_manifest_contains_core_national_sources() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    source_ids = {row["id"] for row in manifest["sources"]}

    assert manifest["schema_version"] == 1
    assert "fcc_dirs_public_reports" in source_ids
    assert "ioda_localized_connectivity" in source_ids
    assert "openfema_disaster_declarations" in source_ids
    assert "noaa_storm_events" in source_ids


def test_phase_1_checklist_renders() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/print_national_data_acquisition.py",
            "--phase",
            "1",
            "--format",
            "markdown",
        ],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    output = result.stdout
    assert "| Priority | Phase | Dataset |" in output
    assert "FCC DIRS public communications status reports" in output
    assert "OpenFEMA Disaster Declarations Summaries v2" in output
