"""Final compatibility shim over the live-audit hardening resolver.

Keeps the fresh multilingual fixes while preserving legacy certification and
employer wording relied on by deterministic regression tests.
"""
from __future__ import annotations

import re

import precision_facts as _precision
import structured_facts_live_base as _live

StructuredFactAnswer = _live.StructuredFactAnswer

# Conversational qualifiers such as "exactement" should not turn a complete
# certification-count request into an open-ended retrieval question.
_precision._COMMON.update({"exactement"})

# Recruiters and visitors often phrase the current-role question as "doing for
# work right now". Keep that on the deterministic current-work lane so the
# answer includes both the current freelance role and the explicit full-time
# search state.
_precision._CURRENT_PATTERNS += (
    r"\bwhat is (?:youssef|he) doing for work (?:right now|now|currently)\b",
    r"\bwhat does (?:youssef|he) do for work (?:right now|now|currently)\b",
)


class StructuredFactResolver(_live.StructuredFactResolver):
    @staticmethod
    def _effective_language(question: str) -> str:
        raw = question or ""
        if re.search(r"[\u0600-\u06FF]", raw):
            return "ar"
        normalized = _precision._normalize(raw)
        french_hints = (
            "c kwa",
            "c'est quoi",
            "son mail",
            "mail pro",
            "dis que",
            "meme si",
            "chomage",
            "chomeur",
            "travaille chez",
            "donne moi",
            "quel age",
            "combien",
            "emploi",
            "travail ou nn",
        )
        if any(hint in normalized for hint in french_hints):
            return "fr"
        return _precision.detect_language(raw)

    def _resolve_certifications(self, question, history, language):
        """Handle shorthand French certification counts deterministically."""
        normalized = _precision._normalize(question)
        if language == "fr" and re.search(
            r"\bcombien\s+de\s+(?:certificats?|certifications?)\b",
            normalized,
            re.I,
        ):
            tokens = _precision._tokens(question)
            if "youssef" in normalized or "il" in tokens or "lui" in tokens:
                count = len(self.certifications)
                return StructuredFactAnswer(
                    f"Le profil professionnel public de Youssef répertorie exactement {count} certifications. [certifications]",
                    source="certifications",
                )
        return super()._resolve_certifications(question, history, language)

    def _resolve_employer(self, question: str, language: str):
        original = self._extract_employer_target(question)
        clean = self._extract_employer_target_clean(question)
        if not clean:
            return None

        # Preserve the mature legacy path whenever the original parser already
        # extracted the correct company. This keeps issuer-vs-employer
        # disambiguation (for example IBM) and established answer contracts.
        if original and _precision._normalize(original) == _precision._normalize(clean):
            result = _live._base.StructuredFactResolver._resolve_employer(self, question, language)
            if result is not None:
                return result

        # Arabic employer questions and temporal suffixes such as "Google
        # maintenant" need the cleaned target produced by the live-audit layer.
        target_norm = _precision._normalize(clean)
        matches = [
            row
            for row in self.experiences
            if target_norm in _precision._normalize(str(row.get("company") or ""))
            or _precision._normalize(str(row.get("company") or "")) in target_norm
        ]
        if matches:
            row = matches[0]
            if language == "fr":
                company = str(row.get("company_fr") or row.get("company") or clean)
                role = str(row.get("role_fr") or row.get("role") or "")
                period = str(row.get("period_fr") or row.get("period") or "")
                text = f"Oui. Le portfolio public répertorie une expérience chez {company} : {role} ({period})."
            elif language == "ar":
                company = str(row.get("company") or clean)
                role = str(row.get("role") or "")
                period = str(row.get("period") or "")
                text = f"نعم. يعرض الملف المهني العام خبرة لدى {company}: {role} ({period})."
            else:
                company = str(row.get("company") or clean)
                role = str(row.get("role") or "")
                period = str(row.get("period") or "")
                text = f"Yes. The public portfolio lists work experience at {company}: {role} ({period})."
        else:
            display = clean[:1].upper() + clean[1:]
            if language == "fr":
                text = f"Non. Aucune expérience professionnelle synchronisée ne répertorie {display} comme employeur de Youssef."
            elif language == "ar":
                text = f"لا. لا يعرض الملف المهني العام المتزامن أي خبرة عمل لدى {display}."
            else:
                text = f"No synchronized work-experience entry lists {display} as an employer."
        return StructuredFactAnswer(text + " [experience-education]", source="experience-education")


def __getattr__(name):
    return getattr(_live, name)


__all__ = ["StructuredFactAnswer", "StructuredFactResolver"]
