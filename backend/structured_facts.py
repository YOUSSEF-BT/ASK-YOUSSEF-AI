"""Deterministic answers for exact aggregate facts in the synchronized profile.

Hybrid RAG is ideal for evidence passages, but top-k retrieval must never be used
as a proxy for set cardinality. This module handles questions whose correct
answer depends on the *whole* structured dataset (currently certifications):
counts, issuer filters, broad inventory summaries, and issuer follow-ups.

All answers are derived from ``backend/data/profile.json`` at runtime. Nothing in
this module hard-codes a certification count, so a future portfolio sync updates
answers automatically.
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
    r"\bcombien\b", r"\bnombre (?:de|des)\b", r"\bau total\b",
    r"(?:^|\s)كم(?:\s|$)", r"(?:^|\s)عدد(?:\s|$)",
)

_LIST_ALL_PATTERNS = (
    r"\blist all\b", r"\ball (?:the )?cert", r"\bcomplete list\b", r"\bevery cert",
    r"\bliste (?:de )?(?:tous|toutes)\b", r"\btous les certific", r"\btoutes les certific",
    r"جميع.*شهاد", r"كل.*شهاد", r"قائمة.*شهاد",
)

_BROAD_LIST_PATTERNS = (
    r"\bwhich certifications?\b", r"\bwhat certifications?\b", r"\bwhat certificates?\b",
    r"\bcertifications? does (?:he|youssef) have\b", r"\bcertificates? does (?:he|youssef) have\b",
    r"\bquell?es? certifications?\b", r"\bquels? certificats?\b",
    r"ما هي.*شهاد", r"ماهي.*شهاد",
)

# Only issuer-only turns with this short follow-up shape may inherit the
# certification topic from history. This prevents e.g. "Did he work at IBM?"
# from being hijacked merely because IBM also appears as a certificate issuer.
_ISSUER_FOLLOWUP_PATTERNS = (
    r"^\s*(?:what|how) about\b",
    r"^\s*(?:and|also)\b",
    r"^\s*(?:et|sinon|aussi)\b",
    r"^\s*(?:qu'en est-il de|et pour)\b",
    r"^\s*(?:وماذا عن|ماذا عن|و)\b",
)

# Tokens that identify sentence structure rather than a particular certification.
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


@dataclass(frozen=True)
class StructuredFactAnswer:
    answer: str
    source: str = "certifications"
    tool: str = "structured_profile"
    evidence: str = "Resolved from the complete synchronized structured profile."


class StructuredFactResolver:
    """Resolve whole-dataset certification facts without asking an LLM to count."""

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

    def _issuer_matches(self, question: str) -> list[str]:
        """Match issuer names dynamically, including useful short aliases.

        Shared aliases intentionally return multiple issuers. For example,
        ``LinkedIn`` can represent both ``LinkedIn`` and
        ``LinkedIn Learning Community`` rather than silently dropping one group.
        """
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
            exact_phrase = bool(issuer_norm and issuer_norm in q_norm)
            short_alias = bool(q_tokens & distinctive)
            if exact_phrase or short_alias:
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

        # A short aggregate follow-up such as "how many?" inherits the topic from
        # the recent transcript. Do not use history to reinterpret arbitrary turns.
        if len(q_tokens) <= 6 and self._matches(_COUNT_PATTERNS, question):
            return self._history_has_certification_context(history)

        # Issuer names alone are ambiguous: IBM/Oracle/LinkedIn could be an
        # employer, technology, company, etc. Treat them as certification filters
        # only for a concise follow-up after a certification discussion.
        if self._issuer_matches(question):
            is_short = len(q_tokens) <= 7
            looks_like_followup = self._matches(_ISSUER_FOLLOWUP_PATTERNS, question)
            return bool(is_short and looks_like_followup and self._history_has_certification_context(history))
        return False

    @staticmethod
    def _issuer_label(issuers: list[str]) -> str:
        return " / ".join(issuers)

    @staticmethod
    def _citation(answer: str) -> StructuredFactAnswer:
        return StructuredFactAnswer(answer=answer.rstrip() + " [certifications]")

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
            title_terms = _tokens(str(row.get("title") or ""))
            overlap = len(query_terms & title_terms)
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
            return StructuredFactResolver._citation(answer + ".")
        if language == "ar":
            answer = f"نعم. يوسف حاصل على **{title}** من **{issuer}**"
            if date:
                answer += f" ({date})"
            if verification:
                answer += f". رابط التحقق: {verification}"
            return StructuredFactResolver._citation(answer + ".")
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
                return StructuredFactResolver._citation(
                    f"Le portfolio public de Youssef répertorie **{count} certification{'s' if count != 1 else ''} {label}**."
                )
            if language == "ar":
                return StructuredFactResolver._citation(
                    f"يعرض ملف يوسف المهني العام **{count} شهادة من {label}**."
                )
            return StructuredFactResolver._citation(
                f"Youssef's public portfolio lists **{count} {label} certification{'s' if count != 1 else ''}**."
            )

        lines = [f"{idx}. **{row.get('title')}**" for idx, row in enumerate(rows, 1)]
        joined = "\n".join(lines)
        if language == "fr":
            answer = (
                f"Oui. Le portfolio public de Youssef répertorie **{count} certification{'s' if count != 1 else ''} {label}** :\n\n"
                f"{joined}"
            )
        elif language == "ar":
            answer = (
                f"نعم. يعرض ملف يوسف المهني العام **{count} شهادة من {label}**:\n\n"
                f"{joined}"
            )
        else:
            answer = (
                f"Yes. Youssef's public portfolio lists **{count} {label} certification{'s' if count != 1 else ''}**:\n\n"
                f"{joined}"
            )
        return StructuredFactResolver._citation(answer)

    def _format_total(self, language: str) -> StructuredFactAnswer:
        count = len(self.certifications)
        if language == "fr":
            return self._citation(
                f"Le portfolio public de Youssef répertorie actuellement **{count} certifications/certificats au total**."
            )
        if language == "ar":
            return self._citation(
                f"يعرض ملف يوسف المهني العام حالياً **{count} شهادة/اعتماداً بالمجموع**."
            )
        return self._citation(
            f"Youssef's public portfolio currently lists **{count} certifications/certificates in total**."
        )

    def _format_overview(self, language: str) -> StructuredFactAnswer:
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
                f"التوزيع: {breakdown}.\n\n"
                "إذا أردت جميع العناوين، اطلب **« اعرض جميع شهاداته »**."
            )
        else:
            answer = (
                f"Youssef's public portfolio currently lists **{total} certifications/certificates** "
                f"across **{len(counts)} issuing organizations**. Breakdown: {breakdown}.\n\n"
                "If you want every title, ask **\"list all certifications\"**."
            )
        return self._citation(answer)

    def _format_all(self, language: str) -> StructuredFactAnswer:
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

    def resolve(self, question: str, history: list[Any] | None = None) -> StructuredFactAnswer | None:
        """Return a deterministic answer when the question requires whole-set facts."""
        history = history or []
        if not self.certifications or not self._has_certification_context(question, history):
            return None

        language = detect_language(question)
        issuers = self._issuer_matches(question)
        count_only = self._matches(_COUNT_PATTERNS, question)

        if issuers:
            rows = [
                row for row in self.certifications
                if str(row.get("issuer") or "") in issuers
            ]
            specific = self._specific_candidates(question, rows, issuers)
            if len(specific) == 1 and not count_only:
                return self._format_specific(specific[0], language)
            return self._format_issuer_rows(rows, issuers, language, count_only)

        if count_only:
            return self._format_total(language)
        if self._matches(_LIST_ALL_PATTERNS, question):
            return self._format_all(language)
        return self._format_overview(language)
