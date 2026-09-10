"""Deterministic structured retrieval over Youssef's synchronized public profile.

The vector/BM25 corpus is excellent for passages. This index complements it with
field-aware retrieval over machine-readable projects, skills, certifications,
experience, education, and links. It is intentionally lightweight and local: no
model call, no network request, and no private data.
"""
from __future__ import annotations

import json
import math
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_TOKEN = re.compile(r"[\w+#.-]+", re.UNICODE)


def _normalize(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    return value.lower().strip()


def _tokens(value: str) -> list[str]:
    return [t for t in _TOKEN.findall(_normalize(value)) if len(t) > 1]


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, dict):
        return " ".join(f"{k} {_stringify(v)}" for k, v in value.items())
    if isinstance(value, list):
        return " ".join(_stringify(v) for v in value)
    return str(value)


@dataclass
class StructuredHit:
    score: float
    meta: dict[str, Any]


@dataclass
class _Document:
    entity_type: str
    primary: str
    secondary: str
    text: str
    meta: dict[str, Any]
    tokens: list[str]
    primary_tokens: set[str]
    secondary_tokens: set[str]


_INTENT_ALIASES = {
    "project": {
        "project", "projects", "projet", "projets", "portfolio", "github",
        "مشروع", "مشاريع", "المشاريع",
    },
    "skill_category": {
        "skill", "skills", "competence", "competences", "technologie", "technologies",
        "stack", "مهارة", "مهارات", "تقنيات", "المهارات",
    },
    "certification": {
        "certification", "certifications", "certificate", "certificates", "certificat",
        "certificats", "oracle", "anthropic", "شهادة", "شهادات", "الشهادات",
    },
    "work_experience": {
        "experience", "experiences", "work", "job", "internship", "intern", "stage",
        "emploi", "travail", "fiverr", "nextronic", "aba", "خبرة", "تجربة", "عمل",
    },
    "education": {
        "education", "degree", "university", "school", "diploma", "diplome", "formation",
        "etudes", "supmti", "دراسة", "تعليم", "شهادة", "جامعة",
    },
    "public_link": {
        "contact", "email", "mail", "adresse", "linkedin", "github", "fiverr", "link", "links",
        "contacte", "contacter", "joindre", "رابط", "تواصل", "اتصال", "بريد", "ايميل",
    },
}


class StructuredProfileRetriever:
    """Field-weighted search over a generated `backend/data/profile.json`."""

    def __init__(self, profile: dict[str, Any] | None = None) -> None:
        self.profile = profile or {}
        self.docs = self._build_documents(self.profile)
        df: Counter[str] = Counter()
        for doc in self.docs:
            df.update(set(doc.tokens))
        self._df = df
        self._n = len(self.docs)

    @classmethod
    def from_path(cls, path: str | Path) -> "StructuredProfileRetriever":
        path = Path(path)
        if not path.is_file():
            return cls({})
        try:
            return cls(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError, TypeError):
            return cls({})

    @property
    def count(self) -> int:
        return len(self.docs)

    @staticmethod
    def _doc(
        entity_type: str,
        primary: str,
        secondary: str,
        text: str,
        *,
        source: str,
        idx: int,
        title: str,
        heading: str,
        url: str,
        raw: dict[str, Any],
    ) -> _Document:
        searchable = " ".join(x for x in (primary, secondary, text) if x)
        meta = {
            "text": text,
            "source": source,
            "heading": heading,
            "idx": 1_000_000 + idx,
            "url": url,
            "title": title,
            "entity_type": entity_type,
            "structured": raw,
        }
        return _Document(
            entity_type=entity_type,
            primary=primary,
            secondary=secondary,
            text=text,
            meta=meta,
            tokens=_tokens(searchable),
            primary_tokens=set(_tokens(primary)),
            secondary_tokens=set(_tokens(secondary)),
        )

    def _build_documents(self, profile: dict[str, Any]) -> list[_Document]:
        docs: list[_Document] = []
        idx = 0

        identity = profile.get("identity") or {}
        if identity:
            name = str(identity.get("name") or "Youssef Bouzit")
            text = (
                f"Name: {name}. Portfolio: {identity.get('portfolio_url', '')}. "
                f"Public source repository: {identity.get('source_repository', '')}."
            )
            docs.append(self._doc(
                "identity", name, "portfolio profile", text,
                source="public-links", idx=idx, title="Public Professional Profile",
                heading=name, url=str(identity.get("portfolio_url") or ""), raw=identity,
            ))
            idx += 1

        for row in profile.get("projects", []):
            slug = str(row.get("slug") or "project")
            title = str(row.get("title") or slug)
            secondary = " ".join(
                _stringify(row.get(k))
                for k in ("role", "company", "tags", "tech_stack", "results")
            )
            text = " ".join(
                part for part in [
                    f"Project: {title}.",
                    f"Description: {_stringify(row.get('description'))}.",
                    f"Role: {_stringify(row.get('role'))}.",
                    f"Company: {_stringify(row.get('company'))}.",
                    f"Period: {_stringify(row.get('period'))}.",
                    f"Location: {_stringify(row.get('location'))}.",
                    f"Status: {_stringify(row.get('status'))}.",
                    f"Technologies: {_stringify(row.get('tech_stack'))}.",
                    f"Tags: {_stringify(row.get('tags'))}.",
                    f"Achievements: {_stringify(row.get('key_achievements'))}.",
                    f"Results: {_stringify(row.get('results'))}.",
                    f"Limitations: {_stringify(row.get('limitations'))}.",
                ] if part
            )
            docs.append(self._doc(
                "project", title, secondary, text,
                source=f"project-{slug}", idx=idx, title=title,
                heading="Structured project profile", url=str(row.get("url") or ""), raw=row,
            ))
            idx += 1

        for row in profile.get("skill_categories", []):
            name = str(row.get("name") or row.get("id") or "Skills")
            evidence = _stringify(row.get("evidence"))
            text = (
                f"Skill category: {name}. Description: {_stringify(row.get('description'))}. "
                f"Skills: {_stringify(row.get('skills'))}. Evidence: {evidence}."
            )
            docs.append(self._doc(
                "skill_category", name, _stringify(row.get("skills")), text,
                source="skills", idx=idx, title="AI Engineering Skills",
                heading=name, url=str(row.get("url") or ""), raw=row,
            ))
            idx += 1

        for row in profile.get("certifications", []):
            title = str(row.get("title") or "Certification")
            issuer = str(row.get("issuer") or "")
            text = (
                f"Certification: {title}. Issuer: {issuer}. Date: {_stringify(row.get('date'))}. "
                f"Category: {_stringify(row.get('category'))}. "
                f"Description: {_stringify(row.get('description'))}. "
                f"Verification: {_stringify(row.get('verification_url'))}."
            )
            docs.append(self._doc(
                "certification", title, issuer, text,
                source="certifications", idx=idx, title="Certifications",
                heading=title, url=str(row.get("url") or ""), raw=row,
            ))
            idx += 1

        for row in profile.get("work_experiences", []):
            role = str(row.get("role") or "Professional Experience")
            company = str(row.get("company") or "")
            text = (
                f"Professional experience: {role} at {company}. Period: {_stringify(row.get('period'))}. "
                f"Context: {_stringify(row.get('context'))}. Description: {_stringify(row.get('description'))}. "
                f"Highlights: {_stringify(row.get('highlights'))}. "
                f"Technologies: {_stringify(row.get('technologies'))}."
            )
            docs.append(self._doc(
                "work_experience", role, company, text,
                source="experience-education", idx=idx, title="Experience & Education",
                heading=f"{role} — {company}".strip(" —"), url=str(row.get("url") or ""), raw=row,
            ))
            idx += 1

        for row in profile.get("education", []):
            degree = str(row.get("degree") or "Education")
            school = str(row.get("school") or "")
            text = (
                f"Education: {degree} at {school}. Period: {_stringify(row.get('period'))}. "
                f"Program: {_stringify(row.get('program'))}. Description: {_stringify(row.get('description'))}. "
                f"Focus: {_stringify(row.get('focus'))}."
            )
            docs.append(self._doc(
                "education", degree, school, text,
                source="experience-education", idx=idx, title="Experience & Education",
                heading=f"{degree} — {school}".strip(" —"), url=str(row.get("url") or ""), raw=row,
            ))
            idx += 1

        for row in profile.get("public_links", []):
            url = str(row.get("url") or "")
            if not url:
                continue
            label = str(row.get("label") or "Professional link")
            value = str(row.get("value") or "")
            visible_value = value or url
            primary = " ".join(part for part in (label, visible_value) if part)
            is_email = label.strip().lower() == "email" or url.lower().startswith("mailto:")
            email_terms = "email mail adresse contacter joindre بريد ايميل تواصل اتصال" if is_email else ""
            secondary = " ".join(
                part for part in ("professional contact", email_terms, label, value) if part
            )
            text = f"Public professional contact. {label}: {visible_value}. Link: {url}."
            docs.append(self._doc(
                "public_link", primary, secondary, text,
                source="public-links", idx=idx, title="Public Professional Links",
                heading=label, url=url, raw=row,
            ))
            idx += 1

        return docs

    def _idf(self, token: str) -> float:
        df = self._df.get(token, 0)
        return math.log(1.0 + (self._n + 1.0) / (df + 1.0)) if self._n else 0.0

    @staticmethod
    def _intent_types(query_tokens: set[str]) -> set[str]:
        matched: set[str] = set()
        for entity_type, aliases in _INTENT_ALIASES.items():
            if query_tokens & {_normalize(a) for a in aliases}:
                matched.add(entity_type)
        return matched

    def search(self, query: str, k: int = 12) -> list[StructuredHit]:
        terms = _tokens(query)
        if not terms or not self.docs or k <= 0:
            return []
        term_set = set(terms)
        intents = self._intent_types(term_set)
        normalized_query = _normalize(query)
        scored: list[StructuredHit] = []

        for doc in self.docs:
            doc_set = set(doc.tokens)
            overlap = term_set & doc_set
            if not overlap:
                continue

            weighted_overlap = sum(self._idf(t) for t in overlap)
            possible = sum(self._idf(t) for t in term_set) or 1.0
            coverage = weighted_overlap / possible
            primary = len(term_set & doc.primary_tokens) / max(1, len(term_set))
            secondary = len(term_set & doc.secondary_tokens) / max(1, len(term_set))

            phrase = 0.0
            primary_norm = _normalize(doc.primary)
            secondary_norm = _normalize(doc.secondary)
            if len(normalized_query) >= 3 and normalized_query in primary_norm:
                phrase += 0.32
            elif primary_norm and primary_norm in normalized_query:
                phrase += 0.18
            if len(normalized_query) >= 3 and normalized_query in secondary_norm:
                phrase += 0.12

            intent_boost = 0.10 if intents and doc.entity_type in intents else 0.0
            score = min(1.0, 0.56 * coverage + 0.22 * primary + 0.10 * secondary + phrase + intent_boost)
            meta = dict(doc.meta)
            meta["structured_match"] = {
                "coverage": round(coverage, 6),
                "primary_overlap": round(primary, 6),
                "secondary_overlap": round(secondary, 6),
                "intent_boost": round(intent_boost, 6),
            }
            scored.append(StructuredHit(score=score, meta=meta))

        scored.sort(key=lambda hit: hit.score, reverse=True)
        return scored[:k]
