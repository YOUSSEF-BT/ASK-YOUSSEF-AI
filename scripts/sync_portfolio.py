"""Build Ask Youssef AI's retrieval corpus from the portfolio source repository.

The portfolio code remains the source of truth. This script clones (or reads) the
public portfolio repository, extracts stable professional facts from its project,
skills, certifications, experience, and profile source files, and writes concise
Markdown documents that the RAG pipeline can index.

It intentionally parses data as text instead of executing JavaScript/JSX from the
portfolio repository. That keeps synchronization deterministic and reduces the
risk of treating source code as executable instructions.
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Iterable

DEFAULT_REPO = "https://github.com/YOUSSEF-BT/YOUSSEF-BT.github.io.git"
DEFAULT_OUTPUT = Path("backend/data/site")

_STRING = r'("(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\')'


def _decode(value: str) -> str:
    value = value.strip()
    try:
        if value.startswith('"'):
            return json.loads(value)
        return ast.literal_eval(value)
    except Exception:
        return value.strip('"\'')


def _string(text: str, key: str) -> str | None:
    match = re.search(rf"\b{re.escape(key)}\s*:\s*{_STRING}", text, re.S)
    return _decode(match.group(1)) if match else None


def _balanced(text: str, start: int, opening: str, closing: str) -> tuple[str, int]:
    if start >= len(text) or text[start] != opening:
        raise ValueError(f"Expected {opening!r} at offset {start}")
    depth = 0
    quote: str | None = None
    escaped = False
    for i in range(start, len(text)):
        ch = text[i]
        if quote:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == quote:
                quote = None
            continue
        if ch in ('"', "'", "`"):
            quote = ch
            continue
        if ch == opening:
            depth += 1
        elif ch == closing:
            depth -= 1
            if depth == 0:
                return text[start + 1 : i], i + 1
    raise ValueError(f"Unbalanced {opening}{closing} block")


def _field_block(text: str, key: str, opening: str, closing: str) -> str | None:
    match = re.search(rf"\b{re.escape(key)}\s*:\s*{re.escape(opening)}", text)
    if not match:
        return None
    start = text.find(opening, match.start())
    return _balanced(text, start, opening, closing)[0]


def _named_array(text: str, variable: str) -> str | None:
    match = re.search(rf"\b{re.escape(variable)}\s*=\s*\[", text)
    if not match:
        return None
    start = text.find("[", match.start())
    return _balanced(text, start, "[", "]")[0]


def _string_array(text: str, key: str) -> list[str]:
    block = _field_block(text, key, "[", "]")
    if block is None:
        return []
    return [_decode(m.group(1)) for m in re.finditer(_STRING, block, re.S)]


def _top_level_objects(array_body: str) -> list[str]:
    objects: list[str] = []
    i = 0
    while i < len(array_body):
        if array_body[i] == "{":
            body, end = _balanced(array_body, i, "{", "}")
            objects.append(body)
            i = end
        else:
            i += 1
    return objects


def _nested_english(text: str, key: str) -> str | None:
    block = _field_block(text, key, "{", "}")
    return _string(block, "en") if block else None


def _nested_english_array(text: str, key: str) -> list[str]:
    block = _field_block(text, key, "{", "}")
    return _string_array(block, "en") if block else []


def _simple_object_pairs(text: str, key: str) -> list[tuple[str, str]]:
    block = _field_block(text, key, "{", "}")
    if not block:
        return []
    pairs = []
    pattern = re.compile(rf"\b([A-Za-z][A-Za-z0-9_]*)\s*:\s*{_STRING}", re.S)
    for match in pattern.finditer(block):
        pairs.append((match.group(1), _decode(match.group(2))))
    return pairs


def _frontmatter(title: str, url: str) -> str:
    clean_title = " ".join(title.replace("\n", " ").split())
    return f'---\ntitle: "{clean_title.replace(chr(34), chr(39))}"\nurl: {url}\n---\n\n'


def _section(title: str, value: str | None) -> str:
    return f"## {title}\n\n{value.strip()}\n\n" if value and value.strip() else ""


def _bullets(title: str, values: Iterable[str]) -> str:
    values = [v.strip() for v in values if v and v.strip()]
    if not values:
        return ""
    return f"## {title}\n\n" + "\n".join(f"- {v}" for v in values) + "\n\n"


def _write_project(source: Path, output: Path) -> bool:
    text = source.read_text(encoding="utf-8")
    slug = _string(text, "slug")
    title = _string(text, "title")
    if not slug or not title:
        return False

    url = f"https://youssef-bt.github.io/projects/{slug}"
    body = _frontmatter(title, url)
    body += f"# {title}\n\n"
    body += _section("Description", _string(text, "description"))

    identity_fields = [
        ("Role", _string(text, "role")),
        ("Company", _string(text, "company")),
        ("Period", _string(text, "period")),
        ("Location", _string(text, "location")),
        ("Status", _string(text, "status")),
        ("GitHub", _string(text, "github")),
    ]
    facts = [f"**{label}:** {value}" for label, value in identity_fields if value]
    if facts:
        body += "## Project facts\n\n" + "\n\n".join(facts) + "\n\n"

    body += _bullets("Tags", _string_array(text, "tags"))
    body += _section("Solution", _string(text, "solution"))
    body += _bullets("Key achievements", _string_array(text, "keyAchievements"))
    body += _bullets("Technology stack", _string_array(text, "techStack"))

    results = _simple_object_pairs(text, "results")
    if results:
        body += "## Results\n\n" + "\n".join(f"- **{key}:** {value}" for key, value in results) + "\n\n"
    body += _section("Results note", _string(text, "resultsNote"))
    body += _section("Disclaimer", _string(text, "disclaimer"))
    body += _bullets("Limitations", _string_array(text, "limitations"))
    body += _bullets("Future improvements", _string_array(text, "futureImprovements"))
    body += _section(
        "Source provenance",
        f"Generated from `{source.relative_to(source.parents[3])}` in the public portfolio repository. "
        "The portfolio source is authoritative for this generated document.",
    )

    (output / f"project-{slug}.md").write_text(body, encoding="utf-8")
    return True


def _write_skills(source: Path, output: Path) -> int:
    text = source.read_text(encoding="utf-8")
    body = _named_array(text, "skillCategories")
    if body is None:
        raise RuntimeError("skillCategories array not found")
    categories = []
    for obj in _top_level_objects(body):
        ident = _string(obj, "id")
        name = _string(obj, "name")
        description = _string(obj, "description")
        skills = _string_array(obj, "skills")
        evidence_body = _field_block(obj, "evidence", "[", "]") or ""
        evidence = []
        for eobj in _top_level_objects(evidence_body):
            label = _string(eobj, "label")
            link = _string(eobj, "to") or _string(eobj, "href")
            if label:
                evidence.append((label, link))
        if ident and name:
            categories.append((ident, name, description, skills, evidence))

    md = _frontmatter("AI Engineering Skills", "https://youssef-bt.github.io/skills")
    md += "# AI Engineering Skills\n\n"
    for ident, name, description, skills, evidence in categories:
        md += f"## {name}\n\n"
        if description:
            md += f"{description}\n\n"
        if skills:
            md += "**Skills:** " + ", ".join(skills) + "\n\n"
        if evidence:
            md += "**Evidence:**\n\n"
            for label, link in evidence:
                full = f"https://youssef-bt.github.io{link}" if link and link.startswith("/") else link
                md += f"- {label}" + (f" — {full}" if full else "") + "\n"
            md += "\n"
    (output / "skills.md").write_text(md, encoding="utf-8")
    return len(categories)


def _write_certifications(source: Path, output: Path) -> int:
    text = source.read_text(encoding="utf-8")
    body = _named_array(text, "certifications")
    if body is None:
        raise RuntimeError("certifications array not found")
    certs = []
    for obj in _top_level_objects(body):
        title = _string(obj, "title")
        issuer = _string(obj, "issuer")
        date = _string(obj, "date")
        description = _string(obj, "description")
        category = _string(obj, "category")
        link = _string(obj, "link")
        if title and issuer:
            certs.append((title, issuer, date, description, category, link))

    md = _frontmatter("Certifications", "https://youssef-bt.github.io/certifications")
    md += "# Certifications\n\n"
    for title, issuer, date, description, category, link in certs:
        md += f"## {title}\n\n"
        md += f"- **Issuer:** {issuer}\n"
        if date:
            md += f"- **Date:** {date}\n"
        if category:
            md += f"- **Category:** {category}\n"
        if link:
            md += f"- **Verification / certificate:** {link}\n"
        if description:
            md += f"\n{description}\n"
        md += "\n"
    (output / "certifications.md").write_text(md, encoding="utf-8")
    return len(certs)


def _write_experience(source: Path, output: Path) -> tuple[int, int]:
    text = source.read_text(encoding="utf-8")
    work_body = _named_array(text, "workExperiences")
    education_body = _named_array(text, "education")
    if work_body is None or education_body is None:
        raise RuntimeError("experience source arrays not found")

    md = _frontmatter("Experience & Education", "https://youssef-bt.github.io/#experience")
    md += "# Professional Experience & Education\n\n"

    work_objects = _top_level_objects(work_body)
    md += "## Professional Experience\n\n"
    for obj in work_objects:
        period = _nested_english(obj, "period")
        role = _nested_english(obj, "role")
        company = _nested_english(obj, "company")
        detail = _nested_english(obj, "companyDetail")
        description = _nested_english(obj, "description")
        highlights = _nested_english_array(obj, "highlights")
        technologies = _string_array(obj, "technologies")
        md += f"### {role or 'Role'} — {company or 'Organization'}\n\n"
        if period:
            md += f"**Period:** {period}\n\n"
        if detail:
            md += f"**Context:** {detail}\n\n"
        if description:
            md += f"{description}\n\n"
        if highlights:
            md += "**Highlights:**\n" + "\n".join(f"- {x}" for x in highlights) + "\n\n"
        if technologies:
            md += "**Technologies:** " + ", ".join(technologies) + "\n\n"

    edu_objects = _top_level_objects(education_body)
    md += "## Education\n\n"
    for obj in edu_objects:
        period = _nested_english(obj, "period")
        degree = _nested_english(obj, "degree")
        school = _string(obj, "school")
        detail = _nested_english(obj, "detail")
        description = _nested_english(obj, "description")
        technologies = _string_array(obj, "technologies")
        md += f"### {degree or 'Education'} — {school or 'Institution'}\n\n"
        if period:
            md += f"**Period:** {period}\n\n"
        if detail:
            md += f"**Program:** {detail}\n\n"
        if description:
            md += f"{description}\n\n"
        if technologies:
            md += "**Focus:** " + ", ".join(technologies) + "\n\n"

    (output / "experience-education.md").write_text(md, encoding="utf-8")
    return len(work_objects), len(edu_objects)


def _write_public_links(source_root: Path, output: Path) -> int:
    candidates = [
        source_root / "src/sections/Hero.jsx",
        source_root / "src/sections/Contact.jsx",
        source_root / "src/components/FiverrLogo.jsx",
    ]
    urls: set[str] = set()
    url_re = re.compile(r"https://[^\"'`\s)<>]+")
    for path in candidates:
        if not path.exists():
            continue
        for url in url_re.findall(path.read_text(encoding="utf-8")):
            if any(host in url for host in ("github.com/YOUSSEF-BT", "linkedin.com/in/", "fiverr.com/", "upwork.com/", "youssef-bt.github.io")):
                urls.add(url.rstrip(";,"))

    md = _frontmatter("Public Professional Links", "https://youssef-bt.github.io")
    md += "# Public Professional Links\n\n"
    md += "These links are extracted from the public portfolio source.\n\n"
    for url in sorted(urls):
        md += f"- {url}\n"
    md += "\n"
    (output / "public-links.md").write_text(md, encoding="utf-8")
    return len(urls)


def _prepare_source(source: str | None) -> tuple[Path, tempfile.TemporaryDirectory[str] | None]:
    if source:
        path = Path(source).resolve()
        if not path.exists():
            raise FileNotFoundError(path)
        return path, None

    temp = tempfile.TemporaryDirectory(prefix="ask-youssef-portfolio-")
    root = Path(temp.name) / "portfolio"
    subprocess.run(["git", "clone", "--depth", "1", DEFAULT_REPO, str(root)], check=True)
    return root, temp


def build(source_root: Path, output: Path) -> dict[str, int]:
    output.mkdir(parents=True, exist_ok=True)
    for path in output.glob("*.md"):
        path.unlink()

    projects_dir = source_root / "src/data/projects"
    if not projects_dir.is_dir():
        raise RuntimeError(f"Missing project data directory: {projects_dir}")

    project_count = 0
    for source in sorted(projects_dir.glob("*.js")):
        if source.name == "index.js":
            continue
        project_count += int(_write_project(source, output))

    skill_count = _write_skills(source_root / "src/pages/Skills.jsx", output)
    cert_count = _write_certifications(source_root / "src/pages/CertificationsPage.jsx", output)
    work_count, edu_count = _write_experience(source_root / "src/sections/Experience.jsx", output)
    link_count = _write_public_links(source_root, output)

    manifest = {
        "projects": project_count,
        "skill_categories": skill_count,
        "certifications": cert_count,
        "work_experiences": work_count,
        "education_entries": edu_count,
        "public_links": link_count,
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", help="Path to an already-cloned portfolio repository")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()

    source_root, temp = _prepare_source(args.source)
    try:
        manifest = build(source_root, Path(args.output))
    finally:
        if temp is not None:
            temp.cleanup()

    print("Portfolio knowledge synchronized:")
    for key, value in manifest.items():
        print(f"  {key}: {value}")
    if manifest["projects"] < 1 or manifest["skill_categories"] < 1 or manifest["certifications"] < 1:
        raise RuntimeError("Knowledge synchronization produced an incomplete corpus")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
