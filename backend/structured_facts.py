"""Deterministic answers for exact aggregate facts in the synchronized profile.

Hybrid RAG is ideal for evidence passages, but top-k retrieval must never be used
as a proxy for set cardinality or a complete inventory. This module handles
questions whose correct answer depends on the *whole* structured dataset:

- certification totals, issuer filters and complete certification inventories;
- exact counts and explicit "list all" requests for projects, experience,
  education, skill categories and public professional contact links.

All answers are derived from ``backend/data/profile.json`` at runtime. Counts are
never hard-coded, so the next successful portfolio sync updates them automatically.
Specific evidence questions (for example "Which project uses BoT-SORT?") are not
intercepted and continue through the normal hybrid RAG + grounding path.
"""
from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from router import detect_language

_TOKEN = re.compile(r"[\w+#.-]+", re.UNICODE)


def _normalize(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    return value.lower().strip()


def _tokens(value: str) -> set[str]:
    return {
        raw.strip(".-")
        for raw in _TOKEN.findall(_normalize(value))
        if len(raw.strip(".-")) > 1
    }


def _turn_content(turn: Any) -> str:
    if isinstance(turn, dict):
        return str(turn.get("content") or "")
    return str(getattr(turn, "content", "") or "")


_CERT_TERMS = {
    "certification", "certifications", "certificate", "certificates", "certificat",
    "certificats", "credential", "credentials", "certifie", "certifiee", "certifies",
    "شهادة", "شهادات", "الشهادات",
}

_COUNT_PATTERNS = (
    r"\bhow many\b", r"\bnumber of\b", r"\btotal\b", r"\bcount\b",
    r"\bcombien\b", r"\bnombre (?:de|des|d')\b", r"\bau total\b",
    r"(?:^|\s)كم(?:\s|$)", r"(?:^|\s)عدد(?:\s|$)",
)

_LIST_ALL_PATTERNS = (
    r"\blist all\b", r"\bshow all\b", r"\bcomplete list\b", r"\bevery\b",
    r"\ball (?:the |his |her )?\w+", r"\bliste (?:de )?(?:tous|toutes)\b",
    r"\bmontre (?:tous|toutes)\b", r"\btous les\b", r"\btoutes les\b",
    r"جميع", r"كل", r"قائمة",
)

_ISSUER_FOLLOWUP_PATTERNS = (
    r"^\s*(?:what|how) about\b",
    r"^\s*(?:and|also)\b",
    r"^\s*(?:et|sinon|aussi)\b",
    r"^\s*(?:qu'en est-il de|et pour)\b",
    r"^\s*(?:وماذا عن|ماذا عن|و)\b",
)

_SPECIFIC_STOP = {
    *{_normalize(x) for x in _CERT_TERMS},
    "youssef", "his", "he", "him", "have", "has", "holds", "which", "what", "about",
    "the", "a", "an", "of", "from", "by", "does", "is", "are", "and", "or", "with",
    "il", "lui", "ses", "son", "sa", "de", "des", "du", "la", "le", "les", "quel",
    "quelle", "quelles", "quels", "a", "est", "et", "sur", "pour", "يوسف", "ما", "هي",
    "عن", "له", "لديه", "عنده", "ai", "certified", "associate", "foundation", "foundations",
}

_ISSUER_GENERIC_TOKENS = {
    "learning", "community", "university", "cognitive", "class", "academy", "institute",
}

_COLLECTIONS: dict[str, dict[str, Any]] = {
    "projects": {
        "profile_key": "projects",
        "terms": {"project", "projects", "projet", "projets", "مشروع", "مشاريع", "المشاريع"},
        "source": "structured-profile",
        "label": {"en": "projects", "fr": "projets", "ar": "مشاريع"},
    },
    "experience": {
        "profile_key": "work_experiences",
        "terms": {
            "experience", "experiences", "employment", "jobs", "roles", "emplois", "emploi",
            "postes", "poste", "خبرة", "خبرات", "الخبرات", "وظائف", "وظيفة",
        },
        "source": "experience-education",
        "label": {"en": "professional experiences", "fr": "expériences professionnelles", "ar": "خبرات مهنية"},
    },
    "education": {
        "profile_key": "education",
        "terms": {
            "education", "studies", "degrees", "degree", "etudes", "études", "diplomes", "diplômes",
            "diplome", "diplôme", "formation", "تعليم", "دراسة", "دراسات",
        },
        "source": "experience-education",
        "label": {"en": "education entries", "fr": "entrées de formation", "ar": "مسارات تعليمية"},
    },
    "skills": {
        "profile_key": "skill_categories",
        "terms": {
            "skill", "skills", "competence", "competences", "compétence", "compétences",
            "مهارة", "مهارات", "المهارات",
        },
        "source": "skills",
        "label": {"en": "skill categories", "fr": "catégories de compétences", "ar": "فئات مهارات"},
    },
    "contacts": {
        "profile_key": "public_links",
        "terms": {
            "contact", "contacts", "links", "liens", "coordonnees", "coordonnées",
            "تواصل", "روابط", "اتصال",
        },
        "source": "public-links",
        "label": {"en": "public professional contact options", "fr": "moyens de contact professionnels publics", "ar": "وسائل تواصل مهنية عامة"},
    },
}


@dataclass(frozen=True)
class StructuredFactAnswer:
    answer: str
    source: str = "certifications"
    tool: str = "structured_profile"
    evidence: str = "Resolved from the complete synchronized structured profile."


class StructuredFactResolver:
    """Resolve whole-dataset facts without asking an LLM to count a top-k slice."""

    def __init__(self, profile: dict[str, Any] | None = None) -> None:
        self.profile = profile or {}
        self.certifications: list[dict[str, Any]] = [
            row for row in self.profile.get("certifications", [])
            if isinstance(row, dict) and row.get("title") and row.get("issuer")
        ]
        self._issuers: list[str] = []
        for row in self.certifications:
            issuer = str(row.get("issuer") or "").strip()
            if issuer and issuer not in self._issuers:
                self._issuers.append(issuer)

    @classmethod
    def from_path(cls, path: str | Path) -> "StructuredFactResolver":
        path = Path(path)
        if not path.is_file():
            return cls({})
        try:
            return cls(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError, TypeError):
            return cls({})

    @property
    def certification_count(self) -> int:
        return len(self.certifications)

    @staticmethod
    def _matches(patterns: Iterable[str], text: str) -> bool:
        normalized = _normalize(text)
        return any(re.search(pattern, normalized, re.I) for pattern in patterns)

    @staticmethod
    def _contains_any_term(text: str, terms: set[str]) -> bool:
        normalized_tokens = _tokens(text)
        normalized_text = _normalize(text)
        for term in terms:
            nterm = _normalize(term)
            if " " in nterm:
                if nterm in normalized_text:
                    return True
            elif nterm in normalized_tokens:
                return True
        return False

    def _issuer_matches(self, question: str) -> list[str]:
        q_norm = _normalize(question)
        q_tokens = _tokens(question)
        matches: list[str] = []
        for issuer in self._issuers:
            issuer_norm = _normalize(issuer)
            issuer_tokens = _tokens(issuer)
            distinctive = {
                token for token in issuer_tokens
                if token not in _ISSUER_GENERIC_TOKENS and len(token) >= 3
            }
            if (issuer_norm and issuer_norm in q_norm) or bool(q_tokens & distinctive):
                matches.append(issuer)
        return matches

    @staticmethod
    def _history_has_certification_context(history: list[Any]) -> bool:
        recent = " ".join(_turn_content(turn) for turn in history[-4:])
        return bool(_tokens(recent) & {_normalize(x) for x in _CERT_TERMS})

    def _has_certification_context(self, question: str, history: list[Any]) -> bool:
        q_tokens = _tokens(question)
        if q_tokens & {_normalize(x) for x in _CERT_TERMS}:
            return True
        if len(q_tokens) <= 6 and self._matches(_COUNT_PATTERNS, question):
            return self._history_has_certification_context(history)
        if self._issuer_matches(question):
            is_short = len(q_tokens) <= 7
            looks_like_followup = self._matches(_ISSUER_FOLLOWUP_PATTERNS, question)
            return bool(is_short and looks_like_followup and self._history_has_certification_context(history))
        return False

    @staticmethod
    def _issuer_label(issuers: list[str]) -> str:
        return " / ".join(issuers)

    @staticmethod
    def _citation(answer: str, source: str = "certifications") -> StructuredFactAnswer:
        return StructuredFactAnswer(answer=answer.rstrip() + f" [{source}]", source=source)

    def _specific_candidates(self, question: str, rows: list[dict[str, Any]], issuers: list[str]) -> list[dict[str, Any]]:
        if not rows:
            return []
        issuer_tokens: set[str] = set()
        for issuer in issuers:
            issuer_tokens |= _tokens(issuer)
        query_terms = _tokens(question) - _SPECIFIC_STOP - issuer_tokens
        if not query_terms:
            return []
        scored: list[tuple[int, dict[str, Any]]] = []
        for row in rows:
            overlap = len(query_terms & _tokens(str(row.get("title") or "")))
            if overlap:
                scored.append((overlap, row))
        if not scored:
            return []
        best = max(score for score, _ in scored)
        return [row for score, row in scored if score == best]

    @staticmethod
    def _format_specific(row: dict[str, Any], language: str) -> StructuredFactAnswer:
        title = str(row.get("title") or "Certification")
        issuer = str(row.get("issuer") or "")
        date = str(row.get("date") or "").strip()
        verification = str(row.get("verification_url") or "").strip()
        if language == "fr":
            answer = f"Oui. Youssef possède **{title}**, délivrée par **{issuer}**"
            if date:
                answer += f" ({date})"
            if verification:
                answer += f". Vérification : {verification}"
        elif language == "ar":
            answer = f"نعم. يوسف حاصل على **{title}** من **{issuer}**"
            if date:
                answer += f" ({date})"
            if verification:
                answer += f". رابط التحقق: {verification}"
        else:
            answer = f"Yes. Youssef holds **{title}**, issued by **{issuer}**"
            if date:
                answer += f" ({date})"
            if verification:
                answer += f". Verification: {verification}"
        return StructuredFactResolver._citation(answer + ".")

    @staticmethod
    def _format_issuer_rows(rows: list[dict[str, Any]], issuers: list[str], language: str, count_only: bool) -> StructuredFactAnswer:
        label = StructuredFactResolver._issuer_label(issuers)
        count = len(rows)
        if count_only:
            if language == "fr":
                answer = f"Le portfolio public de Youssef répertorie **{count} certification{'s' if count != 1 else ''} {label}**."
            elif language == "ar":
                answer = f"يعرض ملف يوسف المهني العام **{count} شهادة من {label}**."
            else:
                answer = f"Youssef's public portfolio lists **{count} {label} certification{'s' if count != 1 else ''}**."
            return StructuredFactResolver._citation(answer)

        lines = "\n".join(f"{idx}. **{row.get('title')}**" for idx, row in enumerate(rows, 1))
        if language == "fr":
            answer = f"Oui. Le portfolio public de Youssef répertorie **{count} certification{'s' if count != 1 else ''} {label}** :\n\n{lines}"
        elif language == "ar":
            answer = f"نعم. يعرض ملف يوسف المهني العام **{count} شهادة من {label}**:\n\n{lines}"
        else:
            answer = f"Yes. Youssef's public portfolio lists **{count} {label} certification{'s' if count != 1 else ''}**:\n\n{lines}"
        return StructuredFactResolver._citation(answer)

    def _format_cert_total(self, language: str) -> StructuredFactAnswer:
        count = len(self.certifications)
        if language == "fr":
            answer = f"Le portfolio public de Youssef répertorie actuellement **{count} certifications/certificats au total**."
        elif language == "ar":
            answer = f"يعرض ملف يوسف المهني العام حالياً **{count} شهادة/اعتماداً بالمجموع**."
        else:
            answer = f"Youssef's public portfolio currently lists **{count} certifications/certificates in total**."
        return self._citation(answer)

    def _format_cert_overview(self, language: str) -> StructuredFactAnswer:
        total = len(self.certifications)
        counts = Counter(str(row.get("issuer") or "Unknown") for row in self.certifications)
        breakdown = "; ".join(
            f"**{issuer} — {count}**"
            for issuer, count in sorted(counts.items(), key=lambda item: (-item[1], item[0].lower()))
        )
        if language == "fr":
            answer = (
                f"Le portfolio public de Youssef répertorie actuellement **{total} certifications/certificats** "
                f"provenant de **{len(counts)} organismes**. Répartition : {breakdown}.\n\n"
                "Si vous voulez tous les intitulés, demandez **« liste toutes ses certifications »**."
            )
        elif language == "ar":
            answer = (
                f"يعرض ملف يوسف المهني العام حالياً **{total} شهادة/اعتماداً** من **{len(counts)} جهات مُصدرة**. "
                f"التوزيع: {breakdown}.\n\nإذا أردت جميع العناوين، اطلب **« اعرض جميع شهاداته »**."
            )
        else:
            answer = (
                f"Youssef's public portfolio currently lists **{total} certifications/certificates** "
                f"across **{len(counts)} issuing organizations**. Breakdown: {breakdown}.\n\n"
                "If you want every title, ask **\"list all certifications\"**."
            )
        return self._citation(answer)

    def _format_all_certifications(self, language: str) -> StructuredFactAnswer:
        grouped: dict[str, list[dict[str, Any]]] = {}
        for row in self.certifications:
            grouped.setdefault(str(row.get("issuer") or "Unknown"), []).append(row)
        blocks: list[str] = []
        for issuer in sorted(grouped, key=str.lower):
            rows = grouped[issuer]
            titles = "\n".join(f"- {row.get('title')}" for row in rows)
            blocks.append(f"**{issuer} ({len(rows)})**\n{titles}")
        body = "\n\n".join(blocks)
        total = len(self.certifications)
        if language == "fr":
            answer = f"Voici les **{total} certifications/certificats** actuellement répertoriés :\n\n{body}"
        elif language == "ar":
            answer = f"هذه هي **{total} شهادة/اعتماداً** المدرجة حالياً:\n\n{body}"
        else:
            answer = f"Here are the **{total} certifications/certificates** currently listed:\n\n{body}"
        return self._citation(answer)

    def _collection_for_question(self, question: str) -> tuple[str, dict[str, Any]] | None:
        for name, config in _COLLECTIONS.items():
            if self._contains_any_term(question, set(config["terms"])):
                return name, config
        return None

    @staticmethod
    def _format_collection_row(name: str, row: dict[str, Any]) -> str:
        if name == "projects":
            title = str(row.get("title") or row.get("slug") or "Project")
            period = str(row.get("period") or "").strip()
            return f"**{title}**" + (f" — {period}" if period else "")
        if name == "experience":
            role = str(row.get("role") or row.get("title") or "Role")
            company = str(row.get("company") or "").strip()
            period = str(row.get("period") or "").strip()
            suffix = " — ".join(part for part in (company, period) if part)
            return f"**{role}**" + (f" — {suffix}" if suffix else "")
        if name == "education":
            degree = str(row.get("degree") or "Education")
            school = str(row.get("school") or "").strip()
            period = str(row.get("period") or "").strip()
            suffix = " — ".join(part for part in (school, period) if part)
            return f"**{degree}**" + (f" — {suffix}" if suffix else "")
        if name == "skills":
            category = str(row.get("category") or "Skills")
            skills = [str(item) for item in (row.get("skills") or []) if str(item).strip()]
            return f"**{category}**: " + ", ".join(skills)
        if name == "contacts":
            label = str(row.get("label") or "Link")
            url = str(row.get("url") or "").strip()
            return f"**{label}**: {url}" if url else f"**{label}**"
        return str(row)

    def _resolve_other_collection(self, question: str, history: list[Any], language: str) -> StructuredFactAnswer | None:
        found = self._collection_for_question(question)
        if found is None and len(_tokens(question)) <= 6 and self._matches(_COUNT_PATTERNS, question):
            recent = " ".join(_turn_content(turn) for turn in history[-4:])
            matches = [
                (name, cfg) for name, cfg in _COLLECTIONS.items()
                if self._contains_any_term(recent, set(cfg["terms"]))
            ]
            if len(matches) == 1:
                found = matches[0]
        if found is None:
            return None

        name, config = found
        count_requested = self._matches(_COUNT_PATTERNS, question)
        list_all_requested = self._matches(_LIST_ALL_PATTERNS, question)
        if not count_requested and not list_all_requested:
            return None

        rows = [row for row in self.profile.get(config["profile_key"], []) if isinstance(row, dict)]
        count = len(rows)
        source = str(config["source"])
        label = str(config["label"].get(language) or config["label"]["en"])

        if count_requested:
            if language == "fr":
                answer = f"Le profil public synchronisé de Youssef répertorie exactement **{count} {label}**."
            elif language == "ar":
                answer = f"يعرض ملف يوسف المهني العام المتزامن بالضبط **{count} {label}**."
            else:
                answer = f"Youssef's synchronized public profile lists exactly **{count} {label}**."
            return self._citation(answer, source)

        lines = "\n".join(
            f"{idx}. {self._format_collection_row(name, row)}"
            for idx, row in enumerate(rows, 1)
        ) or "(none)"
        if language == "fr":
            answer = f"Voici la liste complète des **{count} {label}** actuellement synchronisés :\n\n{lines}"
        elif language == "ar":
            answer = f"هذه هي القائمة الكاملة لـ **{count} {label}** المتزامنة حالياً:\n\n{lines}"
        else:
            answer = f"Here is the complete list of the **{count} {label}** currently synchronized:\n\n{lines}"
        return self._citation(answer, source)

    def resolve(self, question: str, history: list[Any] | None = None) -> StructuredFactAnswer | None:
        """Return a deterministic answer only when whole-set semantics require it."""
        history = history or []
        language = detect_language(question)

        if self.certifications and self._has_certification_context(question, history):
            issuers = self._issuer_matches(question)
            count_only = self._matches(_COUNT_PATTERNS, question)
            if issuers:
                rows = [row for row in self.certifications if str(row.get("issuer") or "") in issuers]
                specific = self._specific_candidates(question, rows, issuers)
                if len(specific) == 1 and not count_only:
                    return self._format_specific(specific[0], language)
                return self._format_issuer_rows(rows, issuers, language, count_only)
            if count_only:
                return self._format_cert_total(language)
            if self._matches(_LIST_ALL_PATTERNS, question):
                return self._format_all_certifications(language)
            return self._format_cert_overview(language)

        return self._resolve_other_collection(question, history, language)
