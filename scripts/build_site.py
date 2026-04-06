#!/usr/bin/env python3
"""Build the static GitHub Pages site for HABRI.

Generates _site/index.html with project summary, key findings,
and links to documentation. Run automatically by the pages.yml CI workflow.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

SITE_DIR = PROJECT_ROOT / "_site"

# ── Helpers ───────────────────────────────────────────────────────────────────

def read_summary_stats() -> dict:
    """Read key stats from habri_composite.csv if available."""
    csv_path = PROJECT_ROOT / "data" / "processed" / "habri_composite.csv"
    if not csv_path.exists():
        return {}
    scores = []
    profiles: dict[str, int] = {}
    try:
        with open(csv_path, newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    scores.append(float(row["HABRI"]))
                except (KeyError, ValueError):
                    pass
                profile = row.get("risk_profile", "")
                if profile:
                    profiles[profile] = profiles.get(profile, 0) + 1
    except Exception:
        return {}

    if not scores:
        return {}
    return {
        "n_tracts": len(scores),
        "mean": sum(scores) / len(scores),
        "min": min(scores),
        "max": max(scores),
        "profiles": profiles,
    }


def build_index(stats: dict) -> str:
    n_tracts = stats.get("n_tracts", 2660)
    mean_score = stats.get("mean", 0.495)
    min_score = stats.get("min", 0.203)
    max_score = stats.get("max", 0.818)
    profiles = stats.get("profiles", {
        "Power-Dependent": 1359,
        "Dual-Risk": 1075,
        "Transport-Fragile": 226,
    })

    profile_rows = "\n".join(
        f"<tr><td>{p}</td><td>{c:,}</td></tr>"
        for p, c in sorted(profiles.items(), key=lambda x: -x[1])
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>HABRI — Hazard-Adjusted Broadband Reliability Index</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
           background: #f8f9fa; color: #212529; line-height: 1.6; }}
    header {{ background: #212529; color: #fff; padding: 2rem; }}
    header h1 {{ font-size: 1.8rem; font-weight: 700; }}
    header p {{ opacity: .75; margin-top: .4rem; }}
    .container {{ max-width: 960px; margin: 2rem auto; padding: 0 1rem; }}
    .kpi-row {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
               gap: 1rem; margin-bottom: 2rem; }}
    .kpi {{ background: #fff; border: 1px solid #dee2e6; border-radius: 8px;
           padding: 1rem; text-align: center; }}
    .kpi .value {{ font-size: 2rem; font-weight: 700; color: #cb181d; }}
    .kpi .label {{ font-size: .8rem; color: #6c757d; margin-top: .2rem; }}
    .section {{ background: #fff; border: 1px solid #dee2e6; border-radius: 8px;
               padding: 1.5rem; margin-bottom: 1.5rem; }}
    .section h2 {{ font-size: 1.1rem; font-weight: 600; margin-bottom: 1rem;
                  border-bottom: 2px solid #cb181d; padding-bottom: .4rem; }}
    table {{ width: 100%; border-collapse: collapse; font-size: .9rem; }}
    th, td {{ padding: .5rem .75rem; text-align: left; border-bottom: 1px solid #dee2e6; }}
    th {{ background: #f1f3f5; font-weight: 600; }}
    .formula {{ background: #f8f9fa; border-left: 4px solid #cb181d;
               padding: .75rem 1rem; font-family: monospace; margin: .75rem 0; }}
    .links a {{ display: inline-block; background: #212529; color: #fff;
               padding: .5rem 1rem; border-radius: 4px; text-decoration: none;
               margin: .25rem .25rem 0 0; font-size: .85rem; }}
    .links a:hover {{ background: #cb181d; }}
    footer {{ text-align: center; padding: 2rem; color: #6c757d; font-size: .85rem; }}
  </style>
</head>
<body>
  <header>
    <h1>HABRI: Hazard-Adjusted Broadband Reliability Index</h1>
    <p>North Carolina — Identifying communities at risk of losing internet connectivity during natural disasters</p>
  </header>

  <div class="container">

    <div class="kpi-row">
      <div class="kpi">
        <div class="value">{n_tracts:,}</div>
        <div class="label">Census tracts</div>
      </div>
      <div class="kpi">
        <div class="value">{mean_score:.3f}</div>
        <div class="label">Mean HABRI score</div>
      </div>
      <div class="kpi">
        <div class="value">{min_score:.3f}–{max_score:.3f}</div>
        <div class="label">Score range</div>
      </div>
      <div class="kpi">
        <div class="value">100</div>
        <div class="label">NC counties</div>
      </div>
    </div>

    <div class="section">
      <h2>Index Formula</h2>
      <div class="formula">HABRI = 0.40 &times; H<sub>E</sub> + 0.35 &times; I<sub>F</sub> + 0.25 &times; C<sub>C</sub></div>
      <table>
        <tr><th>Component</th><th>Weight</th><th>Description</th></tr>
        <tr><td>H<sub>E</sub> — Hazard Exposure</td><td>40%</td><td>FEMA NRI flood, hurricane, and landslide risk scores</td></tr>
        <tr><td>I<sub>F</sub> — Infrastructure Fragility</td><td>35%</td><td>Cellular tower density, broadband latency, road centrality</td></tr>
        <tr><td>C<sub>C</sub> — Community Coping Capacity</td><td>25%</td><td>Vehicle access, mobile-only internet, disability, income, poverty</td></tr>
      </table>
    </div>

    <div class="section">
      <h2>Vulnerability Profiles (K-means, k=3)</h2>
      <table>
        <tr><th>Profile</th><th>Tracts</th></tr>
        {profile_rows}
      </table>
    </div>

    <div class="section">
      <h2>Validation — Hurricane Helene (Sep 2024)</h2>
      <table>
        <tr><th>Validation Dataset</th><th>Result</th></tr>
        <tr><td>Ookla Q3→Q4 latency change (n=2,650 tracts)</td><td>Spearman &rho;=&minus;0.113, p&lt;0.001</td></tr>
        <tr><td>FCC county cell outages (n=100 counties)</td><td>Spearman &rho;=0.236, p=0.018</td></tr>
        <tr><td>IODA Morris Broadband BGP blackout</td><td>80-hour complete outage in Henderson Co. — high-risk prediction confirmed</td></tr>
      </table>
    </div>

    <div class="section">
      <h2>Documentation &amp; Code</h2>
      <div class="links">
        <a href="https://github.com/jesseandrews/habri">GitHub Repository</a>
        <a href="docs/METHODOLOGY.md">Methodology</a>
        <a href="docs/DATA_DICTIONARY.md">Data Dictionary</a>
        <a href="docs/HABRI_EXPLAINED.md">Plain-Language Summary</a>
        <a href="docs/CONTRIBUTING.md">Contributing Guide</a>
      </div>
    </div>

  </div>

  <footer>
    HABRI — Hazard-Adjusted Broadband Reliability Index &middot; North Carolina &middot; Data: FEMA NRI v1.20, Ookla Open Data, Census ACS 2022
  </footer>
</body>
</html>
"""


def main() -> None:
    SITE_DIR.mkdir(parents=True, exist_ok=True)

    print("Reading summary statistics...")
    stats = read_summary_stats()

    print("Building index.html...")
    html = build_index(stats)
    (SITE_DIR / "index.html").write_text(html, encoding="utf-8")

    # Copy docs into _site/docs/
    docs_src = PROJECT_ROOT / "docs"
    if docs_src.exists():
        import shutil
        docs_dst = SITE_DIR / "docs"
        if docs_dst.exists():
            shutil.rmtree(docs_dst)
        shutil.copytree(docs_src, docs_dst)
        print(f"Copied docs/ → {docs_dst}")

    print(f"Site built at {SITE_DIR}/")


if __name__ == "__main__":
    main()
