"""Build a machine-readable professional profile from the portfolio source.

The generated JSON is a deterministic, public-data-only companion to the Markdown
RAG corpus. It gives retrieval exact entities and fields for projects, skills,
certifications, experience, education, and professional links without executing
any JavaScript from the source repository.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from sync_portfolio import (
    _field_block,
    _named_array,
    _nested_english,
    _nested_english_array,
    _prepare_source,
    _simple_object_pairs,
    _string,
    _string_array,
    _top_level_objects,
)

DEFAULT_OUTPUT = Path("backend/data/profile.json")
PORTFOLIO_URL = "https://youssef-bt.github.io"
PORTFOLIO_REPO = "https://github.com/YOUSSEF-BT/YOUSSEF-BT.github.io"


def _full_portfolio_url(value: str | None) -> str | None:
    if not value:
        return None
    return f"{PORTFOLIO_URL}{value}" if value.startswith("/") else value


def _projects(source_root: Path) -> list[dict]:
    rows: list[dict] = []
    for path in sorted((source_root / "src/data/projects").glob("*.js")):
        if path.name == "index.js":
            continue
        text = path.read_text(encoding="utf-8")
        slug = _string(text, "slug")
        title = _string(text, "title")
        if not slug or not title:
            continue
        rows.append(
            {
                "type": "project",
                "slug": slug,
                "title": title,
                "url": f"{PORTFOLIO_URL}/projects/{slug}",
                "description": _string(text, "description"),
                "role": _string(text, "role"),
                "company": _string(text, "company"),
                "period": _string(text, "period"),
                "location": _string(text, "location"),
                "status": _string(text, "status"),
                "github": _string(text, "github"),
                "tags": _string_array(text, "tags"),
                "key_achievements": _string_array(text, "keyAchievements"),
                "tech_stack": _string_array(text, "techStack"),
                "results": dict(_simple_object_pairs(text, "results")),
                "results_note": _string(text, "resultsNote"),
                "disclaimer": _string(text, "disclaimer"),
                "limitations": _string_array(text, "limitations"),
                "source_file": str(path.relative_to(source_root)),
            }
        )
    return rows


def _skills(source_root: Path) -> list[dict]:
    path = source_root / "src/pages/Skills.jsx"
    text = path.read_text(encoding="utf-8")
    body = _named_array(text, "skillCategories")
    if body is None:
        raise RuntimeError("skillCategories array not found")
    rows: list[dict] = []
    for obj in _top_level_objects(body):
        ident = _string(obj, "id")
        name = _string(obj, "name")
        if not ident or not name:
            continue
        evidence: list[dict] = []
        ebody = _field_block(obj, "evidence", "[", "]") or ""
        for eobj in _top_level_objects(ebody):
            label = _string(eobj, "label")
            if not label:
                continue
            evidence.append(
                {
                    "label": label,
                    "url": _full_portfolio_url(_string(eobj, "to") or _string(eobj, "href")),
                    "meta": _string(eobj, "meta"),
                }
            )
        rows.append(
            {
                "type": "skill_category",
                "id": ident,
                "name": name,
                "description": _string(obj, "description"),
                "skills": _string_array(obj, "skills"),
                "evidence": evidence,
                "url": f"{PORTFOLIO_URL}/skills",
                "source_file": str(path.relative_to(source_root)),
            }
        )
    return rows


def _certifications(source_root: Path) -> list[dict]:
    path = source_root / "src/pages/CertificationsPage.jsx"
    text = path.read_text(encoding="utf-8")
    body = _named_array(text, "certifications")
    if body is None:
        raise RuntimeError("certifications array not found")
    rows: list[dict] = []
    for obj in _top_level_objects(body):
        title = _string(obj, "title")
        issuer = _string(obj, "issuer")
        if not title or not issuer:
            continue
        rows.append(
            {
                "type": "certification",
                "title": title,
                "issuer": issuer,
                "date": _string(obj, "date"),
                "description": _string(obj, "description"),
                "category": _string(obj, "category"),
                "verification_url": _string(obj, "link"),
                "url": f"{PORTFOLIO_URL}/certifications",
                "source_file": str(path.relative_to(source_root)),
            }
        )
    return rows


def _experience_and_education(source_root: Path) -> tuple[list[dict], list[dict]]:
    path = source_root / "src/sections/Experience.jsx"
    text = path.read_text(encoding="utf-8")
    work_body = _named_array(text, "workExperiences")
    education_body = _named_array(text, "education")
    if work_body is None or education_body is None:
        raise RuntimeError("experience source arrays not found")

    work: list[dict] = []
    for obj in _top_level_objects(work_body):
        work.append(
            {
                "type": "work_experience",
                "period": _nested_english(obj, "period"),
                "role": _nested_english(obj, "role"),
                "company": _nested_english(obj, "company"),
                "context": _nested_english(obj, "companyDetail"),
                "description": _nested_english(obj, "description"),
                "highlights": _nested_english_array(obj, "highlights"),
                "technologies": _string_array(obj, "technologies"),
                "company_url": _string(obj, "companyLink"),
                "url": f"{PORTFOLIO_URL}/#experience",
                "source_file": str(path.relative_to(source_root)),
            }
        )

    education: list[dict] = []
    for obj in _top_level_objects(education_body):
        education.append(
            {
                "type": "education",
                "period": _nested_english(obj, "period"),
                "degree": _nested_english(obj, "degree"),
                "school": _string(obj, "school"),
                "program": _nested_english(obj, "detail"),
                "description": _nested_english(obj, "description"),
                "focus": _string_array(obj, "technologies"),
                "school_url": _string(obj, "schoolLink"),
                "url": f"{PORTFOLIO_URL}/#experience",
                "source_file": str(path.relative_to(source_root)),
            }
        )
    return work, education


def _links(source_root: Path) -> list[dict]:
    paths = [
        source_root / "src/sections/Hero.jsx",
        source_root / "src/sections/Contact.jsx",
        source_root / "src/components/FiverrLogo.jsx",
    ]
    found: set[str] = set()
    pattern = re.compile(r"https://[^\"'`\s)<>]+")
    allowed = ("github.com/YOUSSEF-BT", "linkedin.com/in/", "fiverr.com/", "upwork.com/", "youssef-bt.github.io")
    for path in paths:
        if not path.exists():
            continue
        for url in pattern.findall(path.read_text(encoding="utf-8")):
            if any(host in url for host in allowed):
                found.add(url.rstrip(";,"))
    return [{"type": "public_link", "url": url} for url in sorted(found)]


def build(source_root: Path) -> dict:
    work, education = _experience_and_education(source_root)
    profile = {
        "schema_version": 1,
        "identity": {
            "name": "Youssef Bouzit",
            "portfolio_url": PORTFOLIO_URL,
            "source_repository": PORTFOLIO_REPO,
        },
        "projects": _projects(source_root),
        "skill_categories": _skills(source_root),
        "certifications": _certifications(source_root),
        "work_experiences": work,
        "education": education,
        "public_links": _links(source_root),
    }
    if not profile["projects"] or not profile["skill_categories"] or not profile["certifications"]:
        raise RuntimeError("Structured profile extraction is incomplete")
    return profile


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", help="Path to an already-cloned portfolio repository")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()

    source_root, temp = _prepare_source(args.source)
    try:
        profile = build(source_root)
    finally:
        if temp is not None:
            temp.cleanup()

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(profile, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(
        "Structured profile built: "
        f"{len(profile['projects'])} projects, "
        f"{len(profile['skill_categories'])} skill categories, "
        f"{len(profile['certifications'])} certifications, "
        f"{len(profile['work_experiences'])} work experiences, "
        f"{len(profile['education'])} education entries."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
