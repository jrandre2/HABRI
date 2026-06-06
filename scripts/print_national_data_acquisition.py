#!/usr/bin/env python3
"""Render the HABRI-GRID national data acquisition checklist."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MANIFEST = PROJECT_ROOT / "docs" / "national_data_sources.json"


def load_manifest(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_csv_arg(value: str | None) -> set[str]:
    if not value:
        return set()
    return {item.strip() for item in value.split(",") if item.strip()}


def filter_sources(
    sources: list[dict[str, Any]],
    *,
    priorities: set[str],
    categories: set[str],
    phase: int | None,
) -> list[dict[str, Any]]:
    filtered: list[dict[str, Any]] = []
    for source in sources:
        if priorities and source["priority"] not in priorities:
            continue
        if categories and source["category"] not in categories:
            continue
        if phase is not None and int(source["phase"]) != phase:
            continue
        filtered.append(source)
    filtered.sort(key=lambda row: (row["phase"], row["priority"], row["id"]))
    return filtered


def script_display(script_path: str) -> str:
    exists = (PROJECT_ROOT / script_path).exists()
    status = "exists" if exists else "planned"
    return f"{script_path} ({status})"


def render_text(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "No sources matched the selected filters."

    lines = [f"{len(rows)} acquisition source(s)\n"]
    for row in rows:
        lines.extend(
            [
                f"[{row['priority']} / phase {row['phase']}] {row['name']}",
                f"  id: {row['id']}",
                f"  category: {row['category']}",
                f"  access: {row['access_mode']}",
                f"  raw: {row['raw_path']}",
                f"  processed: {row['processed_path']}",
                f"  next script: {script_display(row['next_script'])}",
                f"  why: {row['why_it_matters']}",
                f"  notes: {row['notes']}",
                "",
            ]
        )
    return "\n".join(lines).rstrip()


def render_markdown(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "No sources matched the selected filters."

    lines = [
        "| Priority | Phase | Dataset | Category | Access | Next script | Raw path | Processed path |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            "| {priority} | {phase} | {name} | {category} | {access} | `{script}` | `{raw}` | `{processed}` |".format(
                priority=row["priority"],
                phase=row["phase"],
                name=row["name"],
                category=row["category"],
                access=row["access_mode"],
                script=script_display(row["next_script"]),
                raw=row["raw_path"],
                processed=row["processed_path"],
            )
        )
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST,
        help="Path to the national data acquisition manifest JSON.",
    )
    parser.add_argument(
        "--priority",
        default="",
        help="Comma-separated priorities to include, for example 'P0,P1'.",
    )
    parser.add_argument(
        "--category",
        default="",
        help="Comma-separated categories to include, for example 'outage_label,hazard_catalog'.",
    )
    parser.add_argument(
        "--phase",
        type=int,
        choices=[1, 2, 3],
        help="Optional implementation phase filter.",
    )
    parser.add_argument(
        "--format",
        choices=["text", "markdown", "json"],
        default="text",
        help="Output format.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    manifest = load_manifest(args.manifest)
    sources = filter_sources(
        manifest["sources"],
        priorities=parse_csv_arg(args.priority),
        categories=parse_csv_arg(args.category),
        phase=args.phase,
    )

    if args.format == "json":
        print(json.dumps(sources, indent=2))
    elif args.format == "markdown":
        print(render_markdown(sources))
    else:
        print(render_text(sources))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
