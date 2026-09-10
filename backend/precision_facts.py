"""Deterministic precision lane for portfolio facts that should not be guessed.

Hybrid RAG is excellent for open-ended questions, but some portfolio questions
are better treated as structured database operations: exact counts, complete
lists, issuer inventories, filtered project inventories, current role checks,
employer verification, and a few high-value capability/profile questions.

Everything about Youssef is derived from the synchronized profile except the
Ask Youssef AI self-description, which is product metadata for this application.
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


def _citations(*sources: str) -> str:
    unique: list[str] = []
    for source in sources:
        if source and source not in unique:
            unique.append(source)
    return " ".join(f"[{source}]" for source in unique)


_CERT_TERMS = {
    "certification", "certifications", "certificate", "certificates", "certificat",
    "certificats", "credential", "credentials", "شهادة", "شهادات", "الشهادات",
}
_PROJECT_TERMS = {"project", "projects", "projet", "projets", "مشروع", "مشاريع", "المشاريع"}

_COUNT_PATTERNS = (
    r"\bhow many\b", r"\bnumber of\b", r"\btotal\b", r"\bcount\b",
    r"\bcombien\b", r"\bnombre (?:de|des|d')", r"\bau total\b",
    r"(?:^|\s)كم(?:\s|$)", r"(?:^|\s)عدد(?:\s|$)",
)
_LIST_ALL_PATTERNS = (
    r"\blist all\b", r"\bshow all\b", r"\bcomplete list\b", r"\bevery\b",
    r"\bliste (?:de )?(?:tous|toutes)\b", r"\bmontre (?:tous|toutes)\b",
    r"\btous les\b", r"\btoutes les\b", r"جميع", r"كل", r"قائمة",
)
_BROAD_CERT_PATTERNS = (
    r"^\s*(?:which|what) (?:certifications?|certificates?|credentials?) (?:does )?(?:he|youssef) (?:have|hold)\??\s*$",
    r"^\s*what are (?:his|youssef'?s) (?:certifications?|certificates?|credentials?)\??\s*$",
    r"^\s*quell?es? (?:certifications?|certificats?) (?:a|possede) (?:youssef|il).*$",
    r"^\s*quell?es? sont (?:ses|les) (?:certifications?|certificats?).*$",
    r"ما هي.*شهاد", r"ماهي.*شهاد",
)
_ISSUER_FOLLOWUP_PATTERNS = (
    r"^\s*(?:what|how) about\b", r"^\s*(?:and|also)\b",
    r"^\s*(?:et|sinon|aussi)\b", r"^\s*(?:qu'en est-il de|et pour)\b",
    r"^\s*(?:وماذا عن|ماذا عن|و)\b",
)
_ORDINALS = (
    (0, (r"\bfirst\b", r"\b1st\b", r"\bpremier\b", r"\bpremiere\b", r"\b1er\b", r"الأول", r"الاول")),
    (1, (r"\bsecond\b", r"\b2nd\b", r"\bdeuxieme\b", r"\bseconde?\b", r"الثاني")),
    (2, (r"\bthird\b", r"\b3rd\b", r"\btroisieme\b", r"الثالث")),
)

_COMMON = {
    "how", "many", "number", "of", "the", "total", "count", "what", "which", "are", "is",
    "does", "do", "has", "have", "hold", "holds", "he", "his", "him", "youssef", "list", "lists",
    "listed", "show", "all", "every", "complete", "current", "currently", "public", "professional",
    "profile", "portfolio", "exact", "exactly", "entries", "categories", "category", "work", "with",
    "combien", "nombre", "de", "des", "du", "au", "quel", "quels", "quelle", "quelles", "est", "sont",
    "il", "ses", "son", "sa", "youssef", "liste", "lister", "montre", "tous", "toutes", "complet",
    "complete", "actuel", "actuels", "actuelle", "actuelles", "public", "publique", "professionnel",
    "professionnelle", "profil", "portfolio", "categories", "categorie", "entrees", "travail",
    "كم", "عدد", "ما", "هي", "هو", "يوسف", "لديه", "عنده", "كل", "جميع", "قائمة", "اعرض", "من",
}
_SPECIFIC_STOP = _COMMON | {
    *{_normalize(x) for x in _CERT_TERMS},
    "from", "by", "and", "or", "about", "certified", "associate", "foundation", "foundations", "ai",
    "lui", "le", "la", "les", "et", "sur", "pour", "عن", "له",
}
_ISSUER_GENERIC = {"learning", "community", "university", "cognitive", "class", "academy", "institute"}

_COLLECTIONS: dict[str, dict[str, Any]] = {
    "projects": {
        "profile_key": "projects",
        "terms": _PROJECT_TERMS,
        "source": "structured-profile",
        "label": {"en": "projects", "fr": "projets", "ar": "مشاريع"},
    },
    "experience": {
        "profile_key": "work_experiences",
        "terms": {"experience", "experiences", "employment", "jobs", "roles", "emplois", "emploi", "postes", "poste", "خبرة", "خبرات", "وظائف"},
        "source": "experience-education",
        "label": {"en": "professional experiences", "fr": "expériences professionnelles", "ar": "خبرات مهنية"},
    },
    "education": {
        "profile_key": "education",
        "terms": {"education", "studies", "degrees", "degree", "etudes", "diplomes", "diplome", "formation", "تعليم", "دراسة", "دراسات"},
        "source": "experience-education",
        "label": {"en": "education entries", "fr": "entrées de formation", "ar": "مسارات تعليمية"},
    },
    "skills": {
        "profile_key": "skill_categories",
        "terms": {"skill", "skills", "competence", "competences", "مهارة", "مهارات", "المهارات"},
        "source": "skills",
        "label": {"en": "skill categories", "fr": "catégories de compétences", "ar": "فئات مهارات"},
    },
    "contacts": {
        "profile_key": "public_links",
        "terms": {"contact", "contacts", "links", "liens", "coordonnees", "تواصل", "روابط", "اتصال"},
        "source": "public-links",
        "label": {"en": "public professional contact options", "fr": "moyens de contact professionnels publics", "ar": "وسائل تواصل مهنية عامة"},
    },
}

_PROJECT_FILTERS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Computer Vision", ("computer vision", "vision par ordinateur")),
    ("RAG", ("rag", "retrieval augmented generation", "retrieval-augmented generation", "controlled rag")),
    ("Python", ("python",)),
    ("MLOps", ("mlops",)),
    ("Machine Learning", ("machine learning",)),
    ("Deep Learning", ("deep learning",)),
    ("NLP", ("nlp", "natural language processing")),
    ("Data Engineering", ("data engineering",)),
    ("TypeScript", ("typescript",)),
    ("React", ("react",)),
    ("Streamlit", ("streamlit",)),
)

_CURRENT_PATTERNS = (
    r"\bwhat (?:is|does) (?:youssef|he) (?:doing|do) (?:now|currently)\b",
    r"\bwhat is (?:youssef'?s|his) current (?:role|job|work)\b",
    r"\byoussef .*fait quoi maintenant\b", r"\bque fait (?:youssef|il) (?:maintenant|actuellement)\b",
    r"\bquel est (?:son|le) (?:poste|travail|role) actuel\b",
    r"ماذا يفعل يوسف الآن", r"ما هو عمل يوسف الحالي",
)
_GOAL_TERMS = {"goal", "goals", "objective", "objectives", "aim", "aims", "ambition", "ambitions", "objectif", "objectifs", "but", "buts", "butes", "طموح", "اهداف", "أهداف"}
_AGENTIC_TERMS = ("agentic ai", "ia agentique", "agentic", "ai agents", "agents ia")
_COPILOT_TERMS = ("copilot", "assistant ai", "ai assistant", "assistant ia", "portfolio copilot")

_EMPLOYER_PATTERNS = (
    re.compile(r"\b(?:did|has)\s+(?:youssef|he)\s+(?:ever\s+)?(?:work|worked)\s+(?:at|for|with)\s+([^?.!]+)", re.I),
    re.compile(r"\bdoes\s+(?:youssef|he)\s+work\s+(?:at|for|with)\s+([^?.!]+)", re.I),
    re.compile(r"\b(?:youssef|il)\s+(?:a(?:-t-il)?\s+)?(?:deja\s+)?travaille\s+(?:chez|pour)\s+([^?.!]+)", re.I),
)


@dataclass(frozen=True)
class StructuredFactAnswer:
    answer: str
    source: str = "structured-profile"
    tool: str = "structured_profile"
    evidence: str = "Resolved from the complete synchronized structured profile."


class StructuredFactResolver:
    """Resolve high-confidence portfolio facts deterministically when possible."""

    def __init__(self, profile: dict[str, Any] | None = None) -> None:
        self.profile = profile or {}
        self.projects = [x for x in self.profile.get("projects", []) if isinstance(x, dict)]
        self.certifications = [
            x for x in self.profile.get("certifications", [])
            if isinstance(x, dict) and x.get("title") and x.get("issuer")
        ]
        self.experiences = [x for x in self.profile.get("work_experiences", []) if isinstance(x, dict)]
        self.skills = [x for x in self.profile.get("skill_categories", []) if isinstance(x, dict)]
        self.education = [x for x in self.profile.get("education", []) if isinstance(x, dict)]
        self.links = [x for x in self.profile.get("public_links", []) if isinstance(x, dict)]
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
    def _contains_term(text: str, terms: set[str]) -> bool:
        tokens, normalized = _tokens(text), _normalize(text)
        return any((" " in _normalize(term) and _normalize(term) in normalized) or _normalize(term) in tokens for term in terms)

    @staticmethod
    def _unqualified(question: str, domain_terms: set[str]) -> bool:
        allowed = set(_COMMON)
        for term in domain_terms:
            allowed |= _tokens(term)
        return not (_tokens(question) - allowed)

    @staticmethod
    def _ordinal(question: str) -> int | None:
        normalized = _normalize(question)
        for index, patterns in _ORDINALS:
            if any(re.search(pattern, normalized, re.I) for pattern in patterns):
                return index
        return None

    @staticmethod
    def _claimed_cert_count(question: str) -> int | None:
        normalized = _normalize(question)
        patterns = (
            r"\b(\d+)\s+(?:oracle\s+)?(?:certifications?|certificates?|certificats?)\b",
            r"\b(?:has|have|a|possede)\s+(\d+)\s+(?:certifications?|certificates?|certificats?)\b",
        )
        for pattern in patterns:
            match = re.search(pattern, normalized, re.I)
            if match:
                return int(match.group(1))
        return None

    def _issuer_matches(self, text: str) -> list[str]:
        normalized, tokens = _normalize(text), _tokens(text)
        matches: list[str] = []
        for issuer in self._issuers:
            issuer_norm = _normalize(issuer)
            distinctive = {t for t in _tokens(issuer) if t not in _ISSUER_GENERIC and len(t) >= 3}
            if (issuer_norm and issuer_norm in normalized) or bool(tokens & distinctive):
                matches.append(issuer)
        return matches

    def _history_cert_context(self, history: list[Any]) -> bool:
        recent = " ".join(_turn_content(turn) for turn in history[-6:])
        return bool(_tokens(recent) & {_normalize(x) for x in _CERT_TERMS}) or bool(self._issuer_matches(recent))

    def _history_issuer_matches(self, history: list[Any]) -> list[str]:
        for turn in reversed(history[-6:]):
            matches = self._issuer_matches(_turn_content(turn))
            if matches:
                return matches
        return []

    def _cert_context(self, question: str, history: list[Any]) -> bool:
        if _tokens(question) & {_normalize(x) for x in _CERT_TERMS}:
            return True
        if self._ordinal(question) is not None and self._history_cert_context(history):
            return True
        if self._issuer_matches(question):
            return bool(
                len(_tokens(question)) <= 8
                and self._matches(_ISSUER_FOLLOWUP_PATTERNS, question)
                and self._history_cert_context(history)
            )
        if len(_tokens(question)) <= 6 and self._matches(_COUNT_PATTERNS, question):
            return self._history_cert_context(history)
        return False

    @staticmethod
    def _specific_cert_candidates(question: str, rows: list[dict[str, Any]], issuers: list[str]) -> list[dict[str, Any]]:
        issuer_tokens: set[str] = set()
        for issuer in issuers:
            issuer_tokens |= _tokens(issuer)
        query_terms = _tokens(question) - _SPECIFIC_STOP - issuer_tokens
        if not query_terms:
            return []
        scored = [(len(query_terms & _tokens(str(row.get("title") or ""))), row) for row in rows]
        scored = [(score, row) for score, row in scored if score]
        if not scored:
            return []
        best = max(score for score, _ in scored)
        return [row for score, row in scored if score == best]

    @staticmethod
    def _format_cert_details(row: dict[str, Any], language: str) -> StructuredFactAnswer:
        title = str(row.get("title") or "Certification")
        issuer = str(row.get("issuer") or "")
        date = str(row.get("date") or "").strip()
        description = str(row.get("description") or "").strip()
        verification = str(row.get("verification_url") or "").strip()
        if language == "fr":
            parts = [f"{title} est une certification délivrée par {issuer}."]
            if date:
                parts.append(f"Date : {date}.")
            if description:
                parts.append(f"Elle couvre : {description}")
            if verification:
                parts.append(f"Vérification : {verification}")
        elif language == "ar":
            parts = [f"{title} هي شهادة صادرة عن {issuer}."]
            if date:
                parts.append(f"التاريخ: {date}.")
            if description:
                parts.append(f"المحتوى: {description}")
            if verification:
                parts.append(f"رابط التحقق: {verification}")
        else:
            parts = [f"{title} is a certification issued by {issuer}."]
            if date:
                parts.append(f"Date: {date}.")
            if description:
                parts.append(f"It covers: {description}")
            if verification:
                parts.append(f"Verification: {verification}")
        return StructuredFactAnswer(" ".join(parts) + " [certifications]", source="certifications")

    @staticmethod
    def _issuer_inventory(rows: list[dict[str, Any]], issuers: list[str], language: str, claimed: int | None = None, count_only: bool = False) -> StructuredFactAnswer:
        count, label = len(rows), " / ".join(issuers)
        if claimed is not None:
            if language == "fr":
                prefix = (f"Oui, c'est exact : le portfolio public en répertorie {count}." if claimed == count
                          else f"Pas exactement : le portfolio public en répertorie {count}, pas {claimed}.")
            elif language == "ar":
                prefix = (f"نعم، هذا صحيح: الملف العام يعرض {count} شهادات." if claimed == count
                          else f"ليس تماماً: الملف العام يعرض {count} شهادات، وليس {claimed}.")
            else:
                prefix = (f"Yes, that's correct: the public portfolio lists {count}." if claimed == count
                          else f"Not quite: the public portfolio lists {count}, not {claimed}.")
        elif count_only:
            if language == "fr":
                return StructuredFactAnswer(f"Le portfolio public de Youssef répertorie exactement {count} certification(s) {label}. [certifications]", source="certifications")
            if language == "ar":
                return StructuredFactAnswer(f"يعرض ملف يوسف المهني العام بالضبط {count} شهادة من {label}. [certifications]", source="certifications")
            return StructuredFactAnswer(f"Youssef's public portfolio lists exactly {count} {label} certification(s). [certifications]", source="certifications")
        else:
            prefix = ({"fr": f"Le portfolio public de Youssef répertorie {count} certification(s) {label} :",
                       "ar": f"يعرض ملف يوسف المهني العام {count} شهادة من {label}:",
                       "en": f"Youssef's public portfolio lists {count} {label} certification(s):"})[language if language in {"fr", "ar"} else "en"]
        items = "\n".join(f"{i}. {row['title']}" for i, row in enumerate(rows, 1))
        return StructuredFactAnswer(f"{prefix}\n{items} [certifications]", source="certifications")

    def _resolve_certifications(self, question: str, history: list[Any], language: str) -> StructuredFactAnswer | None:
        if not self.certifications or not self._cert_context(question, history):
            return None

        ordinal = self._ordinal(question)
        if ordinal is not None and self._history_cert_context(history):
            history_issuers = self._history_issuer_matches(history)
            rows = [row for row in self.certifications if str(row.get("issuer")) in history_issuers] if history_issuers else self.certifications
            if 0 <= ordinal < len(rows):
                return self._format_cert_details(rows[ordinal], language)

        issuers = self._issuer_matches(question)
        count_requested = self._matches(_COUNT_PATTERNS, question)
        claimed = self._claimed_cert_count(question)
        if issuers:
            rows = [row for row in self.certifications if str(row.get("issuer")) in issuers]
            specific = self._specific_cert_candidates(question, rows, issuers)
            if len(specific) == 1 and not count_requested and claimed is None:
                return self._format_cert_details(specific[0], language)
            return self._issuer_inventory(rows, issuers, language, claimed=claimed, count_only=count_requested)

        cert_terms = {_normalize(x) for x in _CERT_TERMS}
        if count_requested and self._unqualified(question, cert_terms):
            count = len(self.certifications)
            if language == "fr":
                text = f"Le portfolio public de Youssef répertorie actuellement {count} certifications/certificats au total."
            elif language == "ar":
                text = f"يعرض ملف يوسف المهني العام حالياً {count} شهادة/اعتماداً بالمجموع."
            else:
                text = f"Youssef's public portfolio currently lists {count} certifications/certificates in total."
            return StructuredFactAnswer(text + " [certifications]", source="certifications")

        if self._matches(_LIST_ALL_PATTERNS, question) and self._unqualified(question, cert_terms):
            grouped: dict[str, list[dict[str, Any]]] = {}
            for row in self.certifications:
                grouped.setdefault(str(row["issuer"]), []).append(row)
            blocks = []
            for issuer in sorted(grouped, key=str.lower):
                blocks.append(f"{issuer} ({len(grouped[issuer])})\n" + "\n".join(f"• {row['title']}" for row in grouped[issuer]))
            intro = ({"fr": f"Voici les {len(self.certifications)} certifications/certificats actuellement répertoriés :",
                      "ar": f"هذه هي {len(self.certifications)} شهادة/اعتماداً المدرجة حالياً:",
                      "en": f"Here are the {len(self.certifications)} certifications/certificates currently listed:"})[language if language in {"fr", "ar"} else "en"]
            return StructuredFactAnswer(intro + "\n\n" + "\n\n".join(blocks) + " [certifications]", source="certifications")

        if self._matches(_BROAD_CERT_PATTERNS, question) and self._unqualified(question, cert_terms):
            counts = Counter(str(row["issuer"]) for row in self.certifications)
            breakdown = "; ".join(f"{issuer} — {count}" for issuer, count in sorted(counts.items(), key=lambda x: (-x[1], x[0].lower())))
            if language == "fr":
                text = f"Le portfolio public de Youssef répertorie actuellement {len(self.certifications)} certifications/certificats provenant de {len(counts)} organismes. Répartition : {breakdown}."
            elif language == "ar":
                text = f"يعرض ملف يوسف المهني العام حالياً {len(self.certifications)} شهادة/اعتماداً من {len(counts)} جهات مُصدرة. التوزيع: {breakdown}."
            else:
                text = f"Youssef's public portfolio currently lists {len(self.certifications)} certifications/certificates across {len(counts)} issuing organizations. Breakdown: {breakdown}."
            return StructuredFactAnswer(text + " [certifications]", source="certifications")
        return None

    @staticmethod
    def _project_haystack(row: dict[str, Any]) -> str:
        values = [row.get("title"), row.get("description"), row.get("role")]
        values.extend(row.get("tags", []) or [])
        values.extend(row.get("tech_stack", []) or [])
        return _normalize(" ".join(str(v) for v in values if v))

    @staticmethod
    def _alias_in_text(alias: str, text: str) -> bool:
        alias = _normalize(alias)
        if " " in alias:
            return alias in text
        return alias in _tokens(text)

    def _project_filter(self, question: str) -> tuple[str, tuple[str, ...]] | None:
        normalized = _normalize(question)
        for label, aliases in _PROJECT_FILTERS:
            if any(self._alias_in_text(alias, normalized) for alias in aliases):
                return label, aliases
        return None

    def _resolve_filtered_projects(self, question: str, language: str) -> StructuredFactAnswer | None:
        project_filter = self._project_filter(question)
        if not project_filter:
            return None
        count_requested = self._matches(_COUNT_PATTERNS, question)
        list_requested = self._matches(_LIST_ALL_PATTERNS, question)
        has_project_word = self._contains_term(question, _PROJECT_TERMS)
        built_pattern = re.search(r"\b(?:built|build|created|developed|construit|construis|cree|developpe)\b", _normalize(question))
        if not ((count_requested or list_requested) and (has_project_word or built_pattern)):
            return None

        label, aliases = project_filter
        rows = [row for row in self.projects if any(self._alias_in_text(alias, self._project_haystack(row)) for alias in aliases)]
        if not rows:
            return None

        citations = _citations(*(str(row.get("slug") or "") for row in rows))
        items = "\n".join(f"{i}. {row.get('title')} [{row.get('slug')}]" for i, row in enumerate(rows, 1))
        if language == "fr":
            intro = f"Le portfolio public documente exactement {len(rows)} projet(s) correspondant explicitement à {label} :"
        elif language == "ar":
            intro = f"يوثق ملف يوسف المهني العام بالضبط {len(rows)} مشروعاً مرتبطاً صراحةً بـ {label}:"
        else:
            intro = f"Youssef's public portfolio explicitly documents exactly {len(rows)} {label} project(s):"

        extra = ""
        if label == "RAG":
            if language == "fr":
                extra = "\nRemarque : son expérience freelance actuelle mentionne aussi des systèmes RAG, mais le portfolio ne donne pas un nombre séparé de projets clients RAG. [experience-education]"
            elif language == "ar":
                extra = "\nملاحظة: خبرته الحالية في العمل الحر تذكر أيضاً أنظمة RAG، لكن الملف لا يعطي عدداً منفصلاً لمشاريع العملاء من هذا النوع. [experience-education]"
            else:
                extra = "\nNote: his current freelance experience also mentions RAG systems, but the portfolio does not provide a separate count of client RAG projects. [experience-education]"
        return StructuredFactAnswer(f"{intro}\n{items}{extra}", source=str(rows[0].get("slug") or "structured-profile"), evidence=f"Exact filtered project inventory: {label}; {len(rows)} matching structured project records. {citations}")

    def _resolve_current_work(self, question: str, language: str) -> StructuredFactAnswer | None:
        if not self._matches(_CURRENT_PATTERNS, question):
            return None
        current = [row for row in self.experiences if "present" in _normalize(str(row.get("period") or ""))]
        if not current:
            return None
        row = current[0]
        role, company, period = str(row.get("role") or ""), str(row.get("company") or ""), str(row.get("period") or "")
        description = str(row.get("description") or "").strip()
        highlights = [str(x) for x in row.get("highlights", []) if str(x).strip()]
        if language == "fr":
            text = f"Actuellement, le rôle professionnel public de Youssef est {role} chez {company} ({period}). {description}"
            if highlights:
                text += " Ses activités documentées comprennent : " + "; ".join(highlights) + "."
        elif language == "ar":
            text = f"حالياً، دوره المهني العام هو {role} لدى {company} ({period}). {description}"
            if highlights:
                text += " وتشمل أنشطته الموثقة: " + "؛ ".join(highlights) + "."
        else:
            text = f"Youssef's current public professional role is {role} at {company} ({period}). {description}"
            if highlights:
                text += " His documented current work includes: " + "; ".join(highlights) + "."
        return StructuredFactAnswer(text + " [experience-education]", source="experience-education")

    def _resolve_goals(self, question: str, language: str) -> StructuredFactAnswer | None:
        if not (_tokens(question) & {_normalize(x) for x in _GOAL_TERMS}):
            return None
        names = [str(row.get("name") or row.get("category") or "").strip() for row in self.skills]
        names = [name for name in names if name]
        focus = "; ".join(names)
        if language == "fr":
            text = ("Le portfolio public ne contient pas de rubrique déclarant explicitement les objectifs futurs ou ambitions personnelles de Youssef. "
                    f"Ce qu'il documente explicitement, ce sont ses axes professionnels actuels : {focus}. Je ne présenterai donc pas ces axes comme des objectifs futurs non déclarés.")
        elif language == "ar":
            text = ("لا يحتوي الملف المهني العام على قسم يصرح بشكل مباشر بأهداف يوسف المستقبلية أو طموحاته الشخصية. "
                    f"ما يوثقه صراحة هو مجالات تركيزه المهنية الحالية: {focus}. لذلك لن أقدم هذه المجالات كأهداف مستقبلية غير معلنة.")
        else:
            text = ("The public portfolio does not contain a section explicitly stating Youssef's future goals or personal ambitions. "
                    f"What it does explicitly document is his current professional focus: {focus}. I therefore won't present those focus areas as undeclared future goals.")
        return StructuredFactAnswer(text + " [skills]", source="skills")

    def _resolve_agentic_capability(self, question: str, language: str) -> StructuredFactAnswer | None:
        normalized = _normalize(question)
        if not any(term in normalized for term in _AGENTIC_TERMS):
            return None
        relevant_skill = next((row for row in self.skills if row.get("id") == "agentic-ai" or "agentic" in _normalize(str(row.get("name") or ""))), None)
        if not relevant_skill:
            return None
        skills = ", ".join(str(x) for x in relevant_skill.get("skills", []) if str(x).strip())
        certs = [row for row in self.certifications if "agentic ai" in _normalize(str(row.get("title") or ""))]
        cert_text = "; ".join(str(row.get("title")) for row in certs[:3])
        if language == "fr":
            text = (f"Oui. D'après le portfolio public, Youssef possède des compétences explicitement documentées en Agentic AI & LLM Orchestration : {skills}. "
                    "Son expérience freelance actuelle mentionne également les AI agents et les workflows d'intelligence documentaire.")
            if cert_text:
                text += f" Il possède aussi une formation/certification pertinente : {cert_text}."
            text += " Le portfolio ne présente toutefois pas encore un projet autonome explicitement étiqueté « Agentic AI » ; il faut donc distinguer compétences documentées et projet public livré."
        elif language == "ar":
            text = (f"نعم. وفقاً للملف المهني العام، لدى يوسف مهارات موثقة صراحة في Agentic AI & LLM Orchestration: {skills}. "
                    "وتذكر خبرته الحالية في العمل الحر أيضاً AI agents ومسارات document intelligence.")
            if cert_text:
                text += f" كما لديه شهادة/تدريب ذي صلة: {cert_text}."
            text += " لكن الملف لا يعرض بعد مشروعاً مستقلاً منشوراً وموسوماً صراحة باسم Agentic AI، لذلك يجب التمييز بين المهارات الموثقة والمشروع العام المنشور."
        else:
            text = (f"Yes. Based on the public portfolio, Youssef has explicitly documented Agentic AI & LLM Orchestration skills: {skills}. "
                    "His current freelance experience also mentions AI agents and document-intelligence workflows.")
            if cert_text:
                text += f" He also has relevant training/certification evidence: {cert_text}."
            text += " The portfolio does not yet list a standalone public project explicitly labeled 'Agentic AI', so documented capability should be distinguished from a shipped public project."
        return StructuredFactAnswer(text + " [skills] [experience-education] [certifications]", source="skills")

    @staticmethod
    def _resolve_copilot(question: str, language: str) -> StructuredFactAnswer | None:
        normalized = _normalize(question)
        if not any(term in normalized for term in _COPILOT_TERMS):
            return None
        if not any(term in normalized for term in ("built", "build", "made", "created", "fait", "cree", "deja", "have", "has", "a-t-il", "already")):
            return None
        repo = "https://github.com/YOUSSEF-BT/ASK-YOUSSEF-AI"
        if language == "fr":
            text = ("Oui. Ask Youssef AI — l'assistant que vous utilisez actuellement — est lui-même un copilot de portfolio professionnel conçu pour le portfolio de Youssef. "
                    "Il combine retrieval hybride, profil structuré, réponses fondées sur des sources, citations, garde-fous, contexte conversationnel et évaluation de production. "
                    f"Dépôt public : {repo}")
        elif language == "ar":
            text = ("نعم. Ask Youssef AI — المساعد الذي تستخدمه الآن — هو نفسه copilot مهني لمحفظة يوسف. "
                    "يجمع بين الاسترجاع الهجين والملف المنظم والإجابات المستندة إلى المصادر والاستشهادات والحواجز والسياق الحواري وتقييم الإنتاج. "
                    f"المستودع العام: {repo}")
        else:
            text = ("Yes. Ask Youssef AI — the assistant you're using now — is itself a professional portfolio copilot built for Youssef's portfolio. "
                    "It combines hybrid retrieval, a structured profile, source-grounded answers, citations, guardrails, conversation context, and production evaluation. "
                    f"Public repository: {repo}")
        return StructuredFactAnswer(text, source="ask-youssef-ai", evidence="Product self-description backed by the public ASK-YOUSSEF-AI repository and runtime capabilities.")

    def _extract_employer_target(self, question: str) -> str | None:
        normalized = _normalize(question)
        for pattern in _EMPLOYER_PATTERNS:
            match = pattern.search(normalized)
            if match:
                return match.group(1).strip(" ?.!")
        return None

    def _resolve_employer(self, question: str, language: str) -> StructuredFactAnswer | None:
        target = self._extract_employer_target(question)
        if not target:
            return None
        target_norm = _normalize(target)
        matches = [row for row in self.experiences if target_norm in _normalize(str(row.get("company") or "")) or _normalize(str(row.get("company") or "")) in target_norm]
        if matches:
            row = matches[0]
            company, role, period = str(row.get("company") or target), str(row.get("role") or ""), str(row.get("period") or "")
            if language == "fr":
                text = f"Oui. Le portfolio public répertorie une expérience chez {company} : {role} ({period})."
            elif language == "ar":
                text = f"نعم. يعرض الملف المهني العام خبرة لدى {company}: {role} ({period})."
            else:
                text = f"Yes. The public portfolio lists work experience at {company}: {role} ({period})."
            return StructuredFactAnswer(text + " [experience-education]", source="experience-education")

        issuer_matches = self._issuer_matches(target)
        display = issuer_matches[0] if issuer_matches else target.title()
        if language == "fr":
            text = f"Non. Aucune expérience professionnelle synchronisée ne répertorie {display} comme employeur."
            if issuer_matches:
                text += f" {display} apparaît dans le portfolio comme organisme de certification, pas comme employeur. [certifications]"
        elif language == "ar":
            text = f"لا. لا توجد خبرة مهنية متزامنة تذكر {display} كجهة عمل."
            if issuer_matches:
                text += f" يظهر {display} في الملف كجهة إصدار شهادات، وليس كصاحب عمل. [certifications]"
        else:
            text = f"No. No synchronized work-experience entry lists {display} as Youssef's employer."
            if issuer_matches:
                text += f" {display} appears in the portfolio as a certification issuer, not as an employer. [certifications]"
        return StructuredFactAnswer(text + " [experience-education]", source="experience-education")

    @staticmethod
    def _format_collection_row(name: str, row: dict[str, Any]) -> str:
        if name == "projects":
            return str(row.get("title") or row.get("slug") or "Project")
        if name == "experience":
            parts = [str(row.get("role") or "Role"), str(row.get("company") or ""), str(row.get("period") or "")]
            return " — ".join(x for x in parts if x)
        if name == "education":
            parts = [str(row.get("degree") or "Education"), str(row.get("school") or ""), str(row.get("period") or "")]
            return " — ".join(x for x in parts if x)
        if name == "skills":
            return f"{row.get('name') or row.get('category') or 'Skills'}: " + ", ".join(str(x) for x in row.get("skills", []) if str(x).strip())
        if name == "contacts":
            url = str(row.get("url") or "")
            if row.get("label"):
                return f"{row.get('label')}: {row.get('value') or url}"
            if "github.com" in url:
                return f"GitHub: {url}"
            if "linkedin.com" in url:
                return f"LinkedIn: {url}"
            if "fiverr.com" in url:
                return f"Fiverr: {url}"
            return url
        return str(row)

    def _resolve_collection(self, question: str, history: list[Any], language: str) -> StructuredFactAnswer | None:
        found: tuple[str, dict[str, Any]] | None = None
        for name, config in _COLLECTIONS.items():
            if self._contains_term(question, set(config["terms"])):
                found = (name, config)
                break
        if found is None and len(_tokens(question)) <= 6 and self._matches(_COUNT_PATTERNS, question):
            recent = " ".join(_turn_content(turn) for turn in history[-4:])
            matches = [(name, cfg) for name, cfg in _COLLECTIONS.items() if self._contains_term(recent, set(cfg["terms"]))]
            if len(matches) == 1:
                found = matches[0]
        if found is None:
            return None
        name, config = found
        domain_terms = set(config["terms"])
        count_requested = self._matches(_COUNT_PATTERNS, question)
        list_requested = self._matches(_LIST_ALL_PATTERNS, question)
        if not (count_requested or list_requested) or not self._unqualified(question, domain_terms):
            return None
        rows = [row for row in self.profile.get(config["profile_key"], []) if isinstance(row, dict)]
        count, source = len(rows), str(config["source"])
        label = str(config["label"].get(language) or config["label"]["en"])
        if count_requested:
            if language == "fr":
                text = f"Le profil public synchronisé de Youssef répertorie exactement {count} {label}."
            elif language == "ar":
                text = f"يعرض ملف يوسف المهني العام المتزامن بالضبط {count} {label}."
            else:
                text = f"Youssef's synchronized public profile lists exactly {count} {label}."
            return StructuredFactAnswer(text + f" [{source}]", source=source)
        items = "\n".join(f"{i}. {self._format_collection_row(name, row)}" for i, row in enumerate(rows, 1)) or "(none)"
        if language == "fr":
            intro = f"Voici la liste complète des {count} {label} actuellement synchronisés :"
        elif language == "ar":
            intro = f"هذه هي القائمة الكاملة لـ {count} {label} المتزامنة حالياً:"
        else:
            intro = f"Here is the complete list of the {count} {label} currently synchronized:"
        return StructuredFactAnswer(f"{intro}\n{items} [{source}]", source=source)

    def resolve(self, question: str, history: list[Any] | None = None) -> StructuredFactAnswer | None:
        history = history or []
        language = detect_language(question)

        # Order matters: employer wording must win over issuer matching; high-value
        # conversational facts win before broad collection aggregation.
        for resolver in (
            lambda: self._resolve_employer(question, language),
            lambda: self._resolve_current_work(question, language),
            lambda: self._resolve_goals(question, language),
            lambda: self._resolve_agentic_capability(question, language),
            lambda: self._resolve_copilot(question, language),
            lambda: self._resolve_certifications(question, history, language),
            lambda: self._resolve_filtered_projects(question, language),
            lambda: self._resolve_collection(question, history, language),
        ):
            result = resolver()
            if result is not None:
                return result
        return None
