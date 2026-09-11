"""Normalize generated RAG Markdown without hand-editing synchronized evidence.

The knowledge documents under ``backend/data/site`` are generated artifacts. This
post-processing step keeps their presentation consistent while preserving factual
content produced by the synchronization pipeline.

It also enforces a repository-specific publication rule: generated evidence may
link to Youssef Bouzit's own GitHub repositories, but lines containing GitHub
links owned by other accounts are omitted from the generated corpus.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path


_HEADING_REPLACEMENTS = {
    "## Project facts": "## Project Facts",
    "## Key achievements": "## Key Achievements",
    "## Technology stack": "## Technology Stack",
    "## Results note": "## Results Context",
    "## Future improvements": "## Future Improvements",
    "## Source provenance": "## Evidence Provenance",
    "## Current synchronized aggregates": "## Current Synchronized Aggregates",
}

_GITHUB_OWNER = re.compile(r"https://github\.com/([^/\s)\]>]+)", re.I)
_ALLOWED_GITHUB_OWNER = "youssef-bt"


def _contains_external_github(line: str) -> bool:
    for match in _GITHUB_OWNER.finditer(line):
        if match.group(1).strip().lower() != _ALLOWED_GITHUB_OWNER:
            return True
    return False


def polish_text(text: str) -> str:
    lines: list[str] = []
    for raw in text.splitlines():
        line = _HEADING_REPLACEMENTS.get(raw, raw.rstrip())
        if _contains_external_github(line):
            continue
        lines.append(line)

    # Keep Markdown compact and deterministic without changing factual content.
    compact: list[str] = []
    blank = False
    for line in lines:
        if line.strip():
            compact.append(line)
            blank = False
        elif not blank:
            compact.append("")
            blank = True

    return "\n".join(compact).strip() + "\n"


def polish_directory(site_dir: Path) -> int:
    changed = 0
    for path in sorted(site_dir.glob("*.md")):
        original = path.read_text(encoding="utf-8")
        polished = polish_text(original)
        if polished != original:
            path.write_text(polished, encoding="utf-8")
            changed += 1
    return changed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", default="backend/data/site")
    args = parser.parse_args()

    site_dir = Path(args.site)
    if not site_dir.is_dir():
        raise SystemExit(f"Knowledge directory not found: {site_dir}")

    changed = polish_directory(site_dir)
    print(f"Polished generated Markdown documents: {changed} changed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
