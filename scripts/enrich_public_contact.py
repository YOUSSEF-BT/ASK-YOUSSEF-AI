"""Enrich generated portfolio knowledge with public contact details.

The portfolio repository remains the source of truth. This script reads the
public Contact.jsx source after the normal sync/build steps, extracts only email
addresses explicitly exposed through mailto: links, and mirrors them into the
Markdown evidence corpus and structured profile used by Ask Youssef AI.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

MAILTO_RE = re.compile(
    r"mailto:([A-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Z0-9.-]+\.[A-Z]{2,})",
    re.IGNORECASE,
)


def extract_public_emails(source_root: Path) -> list[str]:
    """Return unique emails that the portfolio explicitly publishes as mailto links."""
    candidates = [source_root / "src/sections/Contact.jsx"]
    emails: set[str] = set()
    for path in candidates:
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        emails.update(match.group(1).lower() for match in MAILTO_RE.finditer(text))
    return sorted(emails)


def enrich(source_root: Path, site_root: Path, profile_path: Path) -> dict[str, int]:
    emails = extract_public_emails(source_root)
    if not emails:
        raise RuntimeError("No explicitly public mailto email found in portfolio Contact.jsx")

    public_links_path = site_root / "public-links.md"
    manifest_path = site_root / "manifest.json"
    if not public_links_path.is_file() or not profile_path.is_file() or not manifest_path.is_file():
        raise RuntimeError("Run sync_portfolio.py and build_structured_profile.py before contact enrichment")

    markdown = public_links_path.read_text(encoding="utf-8").rstrip() + "\n"
    for email in emails:
        line = f"- Email: {email} — mailto:{email}"
        if line not in markdown:
            markdown += line + "\n"
    public_links_path.write_text(markdown + "\n", encoding="utf-8")

    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    links = list(profile.get("public_links") or [])
    known = {
        str(row.get("url") or "").lower()
        for row in links
        if isinstance(row, dict)
    }
    for email in emails:
        mailto = f"mailto:{email}"
        if mailto.lower() not in known:
            links.append(
                {
                    "type": "public_link",
                    "label": "Email",
                    "value": email,
                    "url": mailto,
                }
            )
            known.add(mailto.lower())
    profile["public_links"] = links
    profile_path.write_text(json.dumps(profile, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["public_links"] = len(links)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    return {"emails": len(emails), "public_links": len(links)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, help="Path to the portfolio source repository")
    parser.add_argument("--site", default="backend/data/site")
    parser.add_argument("--profile", default="backend/data/profile.json")
    args = parser.parse_args()

    result = enrich(Path(args.source), Path(args.site), Path(args.profile))
    print(
        "Public contact enrichment complete: "
        f"{result['emails']} public email(s), {result['public_links']} public link/contact records."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
