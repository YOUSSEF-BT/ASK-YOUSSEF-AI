"""Generate a citable aggregate source from the synchronized public profile.

Exact collection totals are resolved from ``backend/data/profile.json`` rather
than inferred from top-k retrieval. This companion Markdown document lets the
public widget and deployed evaluator treat those deterministic totals as a real,
linkable portfolio source while keeping the portfolio repository authoritative.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def build(profile_path: Path, site_dir: Path) -> Path:
    profile = json.loads(profile_path.read_text(encoding="utf-8"))

    counts = {
        "Projects": len(profile.get("projects", [])),
        "Skill categories": len(profile.get("skill_categories", [])),
        "Certifications / certificates": len(profile.get("certifications", [])),
        "Professional experiences": len(profile.get("work_experiences", [])),
        "Education entries": len(profile.get("education", [])),
        "Public professional links": len(profile.get("public_links", [])),
    }

    site_dir.mkdir(parents=True, exist_ok=True)
    output = site_dir / "structured-profile.md"
    lines = [
        "---",
        'title: "Structured Portfolio Profile"',
        "url: https://youssef-bt.github.io/#/projects",
        "---",
        "",
        "# Structured Portfolio Profile",
        "",
        "This document exposes aggregate facts derived deterministically from the synchronized public portfolio profile so exact collection counts can be cited like the other portfolio sources.",
        "",
        "## Current synchronized aggregates",
        "",
    ]
    lines.extend(f"- {label}: {value}" for label, value in counts.items())
    lines.extend(
        [
            "",
            "## Provenance",
            "",
            "These counts are derived from `backend/data/profile.json`, which is generated from the public portfolio repository by the synchronization pipeline. The portfolio source remains authoritative.",
            "",
        ]
    )
    output.write_text("\n".join(lines), encoding="utf-8")
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", default="backend/data/profile.json")
    parser.add_argument("--site", default="backend/data/site")
    args = parser.parse_args()

    output = build(Path(args.profile), Path(args.site))
    print(f"Generated structured aggregate source: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
