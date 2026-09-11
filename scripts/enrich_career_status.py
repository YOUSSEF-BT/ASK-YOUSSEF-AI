"""Enrich the synchronized profile with explicit public career availability.

The portfolio already states that Youssef is seeking/open to full-time AI/ML
opportunities while also doing freelance work. The generic structured-profile
builder historically ignored those translated About/Contact strings, which let
an LLM incorrectly infer that a current freelance role meant he was not seeking
a salaried position.

This enrichment keeps the portfolio repository as the source of truth. It:
- extracts the explicit EN/FR career-availability statements from LanguageContext;
- derives the target full-time roles from the English About statement;
- adds localized EN/FR fields to synchronized work-experience rows;
- writes a dedicated career-status.md retrieval document.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from sync_portfolio import (
    _STRING,
    _decode,
    _field_block,
    _named_array,
    _string,
    _string_array,
    _top_level_objects,
)

PORTFOLIO_URL = "https://youssef-bt.github.io"


def _all_strings(text: str, key: str) -> list[str]:
    pattern = re.compile(rf"\b{re.escape(key)}\s*:\s*{_STRING}", re.S)
    return [_decode(match.group(1)) for match in pattern.finditer(text)]


def _nested_lang(text: str, key: str, lang: str) -> str | None:
    block = _field_block(text, key, "{", "}")
    return _string(block, lang) if block else None


def _nested_lang_array(text: str, key: str, lang: str) -> list[str]:
    block = _field_block(text, key, "{", "}")
    return _string_array(block, lang) if block else []


def _target_roles(statement: str) -> list[str]:
    match = re.search(
        r"seeking\s+a\s+full-time\s+opportunity\s+as\s+(.+?)(?:\.|$)",
        statement or "",
        re.I,
    )
    if not match:
        return []
    value = re.sub(r"\s+or\s+", ", ", match.group(1), flags=re.I)
    return [part.strip(" ,") for part in value.split(",") if part.strip(" ,")]


def _career_status(source_root: Path) -> dict:
    path = source_root / "src/context/LanguageContext.jsx"
    text = path.read_text(encoding="utf-8")

    # In LanguageContext the French translation block precedes English.
    about = _all_strings(text, "description3")
    availability = _all_strings(text, "availableDesc")
    if len(about) < 2 or len(availability) < 2:
        raise RuntimeError("Could not extract bilingual career availability from LanguageContext.jsx")

    details_fr, details_en = about[0], about[1]
    summary_fr, summary_en = availability[0], availability[1]
    combined = f"{details_en} {summary_en}".lower()
    seeking = (
        "seeking a full-time opportunity" in combined
        or "open to full-time" in combined
    )
    if not seeking:
        raise RuntimeError("Portfolio no longer explicitly states full-time availability")

    return {
        "type": "career_status",
        "seeking_full_time": True,
        "employment_type": "CDI / full-time",
        "summary": summary_en,
        "summary_fr": summary_fr,
        "details": details_en,
        "details_fr": details_fr,
        "target_roles": _target_roles(details_en),
        "freelance_parallel": True,
        "url": f"{PORTFOLIO_URL}/#contact",
        "source_file": "src/context/LanguageContext.jsx",
    }


def _localize_experiences(source_root: Path, profile: dict) -> None:
    path = source_root / "src/sections/Experience.jsx"
    text = path.read_text(encoding="utf-8")
    body = _named_array(text, "workExperiences")
    if body is None:
        raise RuntimeError("workExperiences array not found")

    source_rows = _top_level_objects(body)
    profile_rows = [row for row in profile.get("work_experiences", []) if isinstance(row, dict)]
    for source_obj in source_rows:
        role_en = _nested_lang(source_obj, "role", "en")
        company_en = _nested_lang(source_obj, "company", "en")
        if not role_en:
            continue
        target = next(
            (
                row for row in profile_rows
                if row.get("role") == role_en
                and (not company_en or row.get("company") == company_en)
            ),
            None,
        )
        if target is None:
            continue
        target.update(
            {
                "period_fr": _nested_lang(source_obj, "period", "fr"),
                "role_fr": _nested_lang(source_obj, "role", "fr"),
                "company_fr": _nested_lang(source_obj, "company", "fr"),
                "context_fr": _nested_lang(source_obj, "companyDetail", "fr"),
                "description_fr": _nested_lang(source_obj, "description", "fr"),
                "highlights_fr": _nested_lang_array(source_obj, "highlights", "fr"),
            }
        )


def _write_career_doc(status: dict, site_dir: Path) -> None:
    site_dir.mkdir(parents=True, exist_ok=True)
    roles = status.get("target_roles") or []
    body = (
        '---\n'
        'title: "Career Availability"\n'
        f'url: {status["url"]}\n'
        '---\n\n'
        '# Career Availability\n\n'
        'This page is synchronized from explicit public portfolio positioning.\n\n'
        '## English\n\n'
        f'- **Status:** {status["summary"]}\n'
        f'- **Details:** {status["details"]}\n'
    )
    if roles:
        body += '- **Target full-time roles:** ' + ', '.join(roles) + '\n'
    body += (
        '- **Freelance:** Current freelance work runs in parallel with the full-time opportunity search; it does not replace it.\n\n'
        '## Français\n\n'
        f'- **Statut :** {status["summary_fr"]}\n'
        f'- **Détails :** {status["details_fr"]}\n'
        '- **Freelance :** L’activité freelance actuelle est menée en parallèle de la recherche d’un CDI ; elle ne la remplace pas.\n'
    )
    (site_dir / "career-status.md").write_text(body, encoding="utf-8")


def enrich(source_root: Path, profile_path: Path, site_dir: Path) -> dict:
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    status = _career_status(source_root)
    profile["career_status"] = status
    _localize_experiences(source_root, profile)
    profile_path.write_text(json.dumps(profile, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_career_doc(status, site_dir)
    return status


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--profile", default="backend/data/profile.json")
    parser.add_argument("--site", default="backend/data/site")
    args = parser.parse_args()

    status = enrich(Path(args.source), Path(args.profile), Path(args.site))
    print("Career availability synchronized:", status["summary"])
    print("Target roles:", status.get("target_roles") or [])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
