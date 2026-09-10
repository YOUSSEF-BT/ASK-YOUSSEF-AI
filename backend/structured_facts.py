"""Exact whole-dataset facts from the synchronized structured portfolio.

A top-k RAG result is evidence, not a database aggregate. This resolver is a
small deterministic lane for questions whose answer requires the COMPLETE
collection: totals, broad inventories, certification issuer filters, and
explicit complete-list requests. Specific/filtered questions stay in hybrid RAG.
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
        token.strip(".-")
        for token in _TOKEN.findall(_normalize(value))
        if len(token.strip(".-")) > 1
    }


def _turn_content(turn: Any) -> str:
    if isinstance(turn, dict):
        return str(turn.get("content") or "")
    return str(getattr(turn, "content", "") or "")


_CERT_TERMS = {
    "certification", "certifications", "certificate", "certificates", "certificat",
    "certificats", "credential", "credentials", "شهادة", "شهادات", "الشهادات",
}

_COUNT_PATTERNS = (
    r"\bhow many\b", r"\bnumber of\b", r"\btotal\b", r"\bcount\b",
    r"\bcombien\b", r"\bnombre (?:de|des|d')", r"\bau total\b",
    r"(?:^|\s)كم(?:\s|$)", r"(?:^|\s)عدد(?:\s|$)",
)

_LIST_ALL_PATTERNS = (
    r"\blist all\b", r"\bshow all\b", r"\bcomplete list\b", r"\bevery\b",
    r"\ball (?:the |his |her )?\w+", r"\bliste (?:de )?(?:tous|toutes)\b",
    r"\bmontre (?:tous|toutes)\b", r"\btous les\b", r"\btoutes les\b",
    r"جميع", r"كل", r"قائمة",
)

_BROAD_CERT_PATTERNS = (
    r"^\s*(?:which|what) (?:certifications?|certificates?|credentials?) (?:does )?(?:he|youssef) (?:have|hold)\??\s*$",
    r"^\s*what are (?:his|youssef'?s) (?:certifications?|certificates?|credentials?)\??\s*$",
    r"^\s*quell?es? (?:certifications?|certificats?) (?:a|possede|possède) (?:youssef|il).*$",
    r"^\s*quell?es? sont (?:ses|les) (?:certifications?|certificats?).*$",
    r"ما هي.*شهاد", r"ماهي.*شهاد",
)

_BROAD_COLLECTION_PATTERNS = (
    r"^\s*(?:which|what) .*(?:does )?(?:he|youssef) (?:have|list)\??\s*$",
    r"^\s*what are (?:his|youssef'?s) .+\??\s*$",
    r"^\s*quels? sont (?:ses|les) .+\??\s*$",
    r"^\s*quell?es? sont (?:ses|les) .+\??\s*$",
    r"ما هي", r"ماهي",
)

_ISSUER_FOLLOWUP_PATTERNS = (
    r"^\s*(?:what|how) about\b", r"^\s*(?:and|also)\b",
    r"^\s*(?:et|sinon|aussi)\b", r"^\s*(?:qu'en est-il de|et pour)\b",
    r"^\s*(?:وماذا عن|ماذا عن|و)\b",
)

_COMMON_AGGREGATE_TOKENS = {
    # English
    "how", "many", "number", "of", "the", "total", "count", "what", "which", "are", "is",
    "does", "do", "has", "have", "hold", "holds", "he", "his", "youssef", "list", "lists",
    "listed", "show", "all", "every", "complete", "current", "currently", "public", "professional",
    "profile", "portfolio", "synchronized", "synchronised", "exact", "exactly", "entries", "categories",
    "category", "options", "work",
    # French (accents are stripped by _normalize)
    "combien", "nombre", "de", "des", "du", "au", "total", "quel", "quels", "quelle", "quelles",
    "est", "sont", "a", "il", "ses", "son", "youssef", "liste", "listes", "lister", "montre", "tous",
    "toutes", "complet", "complete", "actuel", "actuels", "actuelle", "actuelles", "public", "publique",
    "publiques", "professionnel", "professionnels", "professionnelle", "professionnelles", "profil",
    "portfolio", "categories", "categorie", "entrees", "options",
    # Arabic
    "كم", "عدد", "ما", "هي", "هو", "يوسف", "لديه", "عنده", "كل", "جميع", "قائمة", "اعرض", "عرض",
    "الحالي", "الحالية", "العام", "المهني", "من",
}

_SPECIFIC_STOP = _COMMON_AGGREGATE_TOKENS | {
    *{_normalize(x) for x in _CERT_TERMS},
    "him", "from", "by", "and", "or", "with", "about", "certified", "associate", "foundation",
    "foundations", "lui", "sa", "le", "la", "les", "et", "sur", "pour", "عن", "له", "ai",
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
        "terms": {"experience", "experiences", "employment", "jobs", "roles", "emplois", "emploi", "postes", "poste", "خبرة", "خبرات", "الخبرات", "وظائف", "وظيفة"},
        "source": "experience-education",
        "label": {"en": "professional experiences", "fr": "expériences professionnelles", "ar": "خبرات مهنية"},
    },
    "education": {
        "profile_key": "education",
        "terms": {"education", "studies", "degrees", "degree", "etudes", "études", "diplomes", "diplômes", "diplome", "diplôme", "formation", "تعليم", "دراسة", "دراسات"},
        "source": "experience-education",
        "label": {"en": "education entries", "fr": "entrées de formation", "ar": "مسارات تعليمية"},
    },
    "skills": {
        "profile_key": "skill_categories",
        "terms": {"skill", "skills", "competence", "competences", "compétence", "compétences", "مهارة", "مهارات", "المهارات"},
        "source": "skills",
        "label": {"en": "skill categories", "fr": "catégories de compétences", "ar": "فئات مهارات"},
    },
    "contacts": {
        "profile_key": "public_links",
        "terms": {"contact", "contacts", "links", "liens", "coordonnees", "coordonnées", "تواصل", "روابط", "اتصال"},
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
    """Resolve only facts that are safer as deterministic whole-set operations."""

    def __init__(self, profile: dict[str, Any] | None = None) -> None:
        self.profile = profile or {}
        self.certifications = [
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
        tokens = _tokens(text)
        normalized = _normalize(text)
        for term in terms:
            term = _normalize(term)
            if (" " in term and term in normalized) or (" " not in term and term in tokens):
                return True
        return False

    @staticmethod
    def _unqualified(question: str, domain_terms: set[str]) -> bool:
        allowed = set(_COMMON_AGGREGATE_TOKENS)
        for term in domain_terms:
            allowed |= _tokens(term)
        return not (_tokens(question) - allowed)

    def _issuer_matches(self, question: str) -> list[str]:
        q_norm, q_tokens = _normalize(question), _tokens(question)
        matches: list[str] = []
        for issuer in self._issuers:
            issuer_norm = _normalize(issuer)
            distinctive = {
                token for token in _tokens(issuer)
                if token not in _ISSUER_GENERIC_TOKENS and len(token) >= 3
            }
            if (issuer_norm and issuer_norm in q_norm) or bool(q_tokens & distinctive):
                matches.append(issuer)
        return matches

    @staticmethod
    def _history_has_certification_context(history: list[Any]) -> bool:
        recent = " ".join(_turn_content(turn) for turn in history[-4:])
        return bool(_tokens(recent) & {_normalize(x) for x in _CERT_TERMS})

    def _cert_context(self, question: str, history: list[Any]) -> bool:
        if _tokens(question) & {_normalize(x) for x in _CERT_TERMS}:
            return True
        if self._issuer_matches(question):
            return bool(
                len(_tokens(question)) <= 7
                and self._matches(_ISSUER_FOLLOWUP_PATTERNS, question)
                and self._history_has_certification_context(history)
            )
        if len(_tokens(question)) <= 6 and self._matches(_COUNT_PATTERNS, question):
            return self._history_has_certification_context(history)
        return False

    @staticmethod
    def _citation(answer: str, source: str = "certifications") -> StructuredFactAnswer:
        return StructuredFactAnswer(answer=answer.rstrip() + f" [{source}]", source=source)

    def _specific_cert_candidates(self, question: str, rows: list[dict[str, Any]], issuers: list[str]) -> list[dict[str, Any]]:
        issuer_tokens: set[str] = set()
        for issuer in issuers:
            issuer_tokens |= _tokens(issuer)
        query_terms = _tokens(question) - _SPECIFIC_STOP - issuer_tokens
        if not query_terms:
            return []
        scored = [
            (len(query_terms & _tokens(str(row.get("title") or ""))), row)
            for row in rows
        ]
        scored = [(score, row) for score, row in scored if score]
        if not scored:
            return []
        best = max(score for score, _ in scored)
        return [row for score, row in scored if score == best]

    def _format_specific_cert(self, row: dict[str, Any], language: str) -> StructuredFactAnswer:
        title, issuer = str(row.get("title")), str(row.get("issuer"))
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
        return self._citation(answer + ".")

    def _format_issuer(self, rows: list[dict[str, Any]], issuers: list[str], language: str, count_only: bool) -> StructuredFactAnswer:
        label, count = " / ".join(issuers), len(rows)
        if count_only:
            if language == "fr":
                answer = f"Le portfolio public de Youssef répertorie **{count} certification{'s' if count != 1 else ''} {label}**."
            elif language == "ar":
                answer = f"يعرض ملف يوسف المهني العام **{count} شهادة من {label}**."
            else:
                answer = f"Youssef's public portfolio lists **{count} {label} certification{'s' if count != 1 else ''}**."
            return self._citation(answer)
        items = "\n".join(f"{i}. **{row['title']}**" for i, row in enumerate(rows, 1))
        if language == "fr":
            answer = f"Oui. Le portfolio public de Youssef répertorie **{count} certification{'s' if count != 1 else ''} {label}** :\n\n{items}"
        elif language == "ar":
            answer = f"نعم. يعرض ملف يوسف المهني العام **{count} شهادة من {label}**:\n\n{items}"
        else:
            answer = f"Yes. Youssef's public portfolio lists **{count} {label} certification{'s' if count != 1 else ''}**:\n\n{items}"
        return self._citation(answer)

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
        counts = Counter(str(row["issuer"]) for row in self.certifications)
        breakdown = "; ".join(
            f"**{issuer} — {count}**"
            for issuer, count in sorted(counts.items(), key=lambda item: (-item[1], item[0].lower()))
        )
        if language == "fr":
            answer = f"Le portfolio public de Youssef répertorie actuellement **{total} certifications/certificats** provenant de **{len(counts)} organismes**. Répartition : {breakdown}."
        elif language == "ar":
            answer = f"يعرض ملف يوسف المهني العام حالياً **{total} شهادة/اعتماداً** من **{len(counts)} جهات مُصدرة**. التوزيع: {breakdown}."
        else:
            answer = f"Youssef's public portfolio currently lists **{total} certifications/certificates** across **{len(counts)} issuing organizations**. Breakdown: {breakdown}."
        return self._citation(answer)

    def _format_all_certs(self, language: str) -> StructuredFactAnswer:
        grouped: dict[str, list[dict[str, Any]]] = {}
        for row in self.certifications:
            grouped.setdefault(str(row["issuer"]), []).append(row)
        blocks = []
        for issuer in sorted(grouped, key=str.lower):
            rows = grouped[issuer]
            blocks.append(f"**{issuer} ({len(rows)})**\n" + "\n".join(f"- {row['title']}" for row in rows))
        body, total = "\n\n".join(blocks), len(self.certifications)
        if language == "fr":
            answer = f"Voici les **{total} certifications/certificats** actuellement répertoriés :\n\n{body}"
        elif language == "ar":
            answer = f"هذه هي **{total} شهادة/اعتماداً** المدرجة حالياً:\n\n{body}"
        else:
            answer = f"Here are the **{total} certifications/certificates** currently listed:\n\n{body}"
        return self._citation(answer)

    def _resolve_certifications(self, question: str, history: list[Any], language: str) -> StructuredFactAnswer | None:
        if not self.certifications or not self._cert_context(question, history):
            return None
        issuers = self._issuer_matches(question)
        count_requested = self._matches(_COUNT_PATTERNS, question)
        if issuers:
            rows = [row for row in self.certifications if str(row["issuer"]) in issuers]
            specific = self._specific_cert_candidates(question, rows, issuers)
            if len(specific) == 1 and not count_requested:
                return self._format_specific_cert(specific[0], language)
            return self._format_issuer(rows, issuers, language, count_requested)

        cert_terms = {_normalize(x) for x in _CERT_TERMS}
        if count_requested:
            return self._format_cert_total(language) if self._unqualified(question, cert_terms) else None
        if self._matches(_LIST_ALL_PATTERNS, question):
            return self._format_all_certs(language) if self._unqualified(question, cert_terms) else None
        if self._matches(_BROAD_CERT_PATTERNS, question) and self._unqualified(question, cert_terms):
            return self._format_cert_overview(language)
        # Specific or filtered non-issuer certification questions belong to RAG.
        return None

    @staticmethod
    def _format_collection_row(name: str, row: dict[str, Any]) -> str:
        if name == "projects":
            title, period = str(row.get("title") or row.get("slug") or "Project"), str(row.get("period") or "").strip()
            return f"**{title}**" + (f" — {period}" if period else "")
        if name == "experience":
            role = str(row.get("role") or row.get("title") or "Role")
            company, period = str(row.get("company") or "").strip(), str(row.get("period") or "").strip()
            suffix = " — ".join(part for part in (company, period) if part)
            return f"**{role}**" + (f" — {suffix}" if suffix else "")
        if name == "education":
            degree = str(row.get("degree") or "Education")
            school, period = str(row.get("school") or "").strip(), str(row.get("period") or "").strip()
            suffix = " — ".join(part for part in (school, period) if part)
            return f"**{degree}**" + (f" — {suffix}" if suffix else "")
        if name == "skills":
            return f"**{row.get('category') or 'Skills'}**: " + ", ".join(str(x) for x in row.get("skills", []) if str(x).strip())
        if name == "contacts":
            return f"**{row.get('label') or 'Link'}**: {row.get('url') or ''}".rstrip()
        return str(row)

    def _resolve_collection(self, question: str, history: list[Any], language: str) -> StructuredFactAnswer | None:
        found: tuple[str, dict[str, Any]] | None = None
        for name, config in _COLLECTIONS.items():
            if self._contains_any_term(question, set(config["terms"])):
                found = (name, config)
                break
        if found is None and len(_tokens(question)) <= 6 and self._matches(_COUNT_PATTERNS, question):
            recent = " ".join(_turn_content(turn) for turn in history[-4:])
            matches = [
                (name, config) for name, config in _COLLECTIONS.items()
                if self._contains_any_term(recent, set(config["terms"]))
            ]
            if len(matches) == 1:
                found = matches[0]
        if found is None:
            return None

        name, config = found
        domain_terms = set(config["terms"])
        count_requested = self._matches(_COUNT_PATTERNS, question)
        list_requested = self._matches(_LIST_ALL_PATTERNS, question) or self._matches(_BROAD_COLLECTION_PATTERNS, question)
        if not (count_requested or list_requested) or not self._unqualified(question, domain_terms):
            return None

        rows = [row for row in self.profile.get(config["profile_key"], []) if isinstance(row, dict)]
        count, source = len(rows), str(config["source"])
        label = str(config["label"].get(language) or config["label"]["en"])
        if count_requested:
            if language == "fr":
                answer = f"Le profil public synchronisé de Youssef répertorie exactement **{count} {label}**."
            elif language == "ar":
                answer = f"يعرض ملف يوسف المهني العام المتزامن بالضبط **{count} {label}**."
            else:
                answer = f"Youssef's synchronized public profile lists exactly **{count} {label}**."
            return self._citation(answer, source)

        items = "\n".join(f"{i}. {self._format_collection_row(name, row)}" for i, row in enumerate(rows, 1)) or "(none)"
        if language == "fr":
            answer = f"Voici la liste complète des **{count} {label}** actuellement synchronisés :\n\n{items}"
        elif language == "ar":
            answer = f"هذه هي القائمة الكاملة لـ **{count} {label}** المتزامنة حالياً:\n\n{items}"
        else:
            answer = f"Here is the complete list of the **{count} {label}** currently synchronized:\n\n{items}"
        return self._citation(answer, source)

    def resolve(self, question: str, history: list[Any] | None = None) -> StructuredFactAnswer | None:
        history = history or []
        language = detect_language(question)
        certification = self._resolve_certifications(question, history, language)
        if certification is not None:
            return certification
        return self._resolve_collection(question, history, language)
