"""Compatibility layer for deterministic portfolio precision facts.

The implementation lives in ``precision_facts.py`` so the precision lane can
evolve independently from hybrid retrieval. This module keeps backward-compatible
aggregate vocabulary, canonicalizes project citations, and owns a small set of
high-risk career-state answers that must come from explicit synchronized fields
rather than LLM inference.
"""
from dataclasses import replace
import re

import precision_facts as _precision

# Natural aggregate phrasing such as "public contact options" is semantically
# equivalent to "public contacts". Keep these generic nouns neutral so they do
# not turn a complete-set request into a filtered query.
_precision._COMMON.update({"option", "options"})

StructuredFactAnswer = _precision.StructuredFactAnswer


_JOB_SEARCH_PATTERNS = (
    r"\b(?:is|does) (?:youssef|he) (?:currently )?(?:looking|searching) for (?:a )?(?:job|work|position|role)\b",
    r"\b(?:is|does) (?:youssef|he) (?:seeking|looking for) (?:a )?(?:full-time|full time)\b",
    r"\b(?:is|does) (?:youssef|he) (?:open|available) (?:to|for) (?:full-time|full time|work|opportunities)\b",
    r"\b(?:est ce que |est-ce que )?(?:youssef|il) .*\b(?:recherche|cherche)\b.*\b(?:emploi|travail|poste|job|cdi|opportunite)\b",
    r"\b(?:youssef\s+)?(?:recherche|cherche)(?:-t-il)?\b.*\b(?:emploi|travail|poste|job|cdi|opportunite)\b",
    r"\b(?:youssef|il) (?:recherche|cherche) (?:un |une |des )?(?:emploi|travail|poste|job|cdi|opportunite)\b",
    r"\b(?:youssef|il) .*\b(?:ouvert|disponible)\b.*\b(?:cdi|emploi|travail|opportunite|temps plein)\b",
    r"\b(?:est-il|il est|youssef est)\b.*\b(?:ouvert|disponible)\b.*\b(?:cdi|emploi|travail|opportunite|temps plein)\b",
    r"هل .*يوسف.*(?:يبحث|يبحث حاليا).*(?:عمل|وظيفة|فرصة)",
)


class StructuredFactResolver(_precision.StructuredFactResolver):
    """Precision resolver with canonical source IDs and explicit career state."""

    @staticmethod
    def _job_search_question(question: str) -> bool:
        normalized = _precision._normalize(question)
        return any(re.search(pattern, normalized, re.I) for pattern in _JOB_SEARCH_PATTERNS)

    def _resolve_job_search(self, question: str, language: str):
        if not self._job_search_question(question):
            return None
        status = self.profile.get("career_status") or {}
        if not isinstance(status, dict) or "seeking_full_time" not in status:
            return None

        seeking = status.get("seeking_full_time") is True
        roles = [str(role).strip() for role in status.get("target_roles", []) if str(role).strip()]
        role_text = ", ".join(roles)
        freelance = status.get("freelance_parallel") is True

        if language == "fr":
            if seeking:
                text = "Oui. Le portfolio public indique explicitement que Youssef recherche actuellement une opportunité en CDI à temps plein"
                if role_text:
                    text += f" comme {role_text}"
                text += "."
                if freelance:
                    text += " En parallèle, il exerce comme Ingénieur IA/ML Freelance ; cette activité freelance ne remplace pas sa recherche de CDI."
            else:
                text = "Non. Le statut professionnel public synchronisé n’indique pas actuellement une recherche de CDI à temps plein."
        elif language == "ar":
            if seeking:
                text = "نعم. يذكر ملف يوسف المهني العام صراحةً أنه يبحث حالياً عن فرصة عمل بدوام كامل"
                if role_text:
                    text += f" في أدوار مثل: {role_text}"
                text += "."
                if freelance:
                    text += " وفي الوقت نفسه يعمل كمهندس AI/ML مستقل؛ العمل الحر لا يعني أنه أوقف بحثه عن وظيفة بدوام كامل."
            else:
                text = "لا. الحالة المهنية العامة المتزامنة لا تشير حالياً إلى أنه يبحث عن وظيفة بدوام كامل."
        else:
            if seeking:
                text = "Yes. Youssef's public portfolio explicitly states that he is currently seeking a full-time opportunity"
                if role_text:
                    text += f" as {role_text}"
                text += "."
                if freelance:
                    text += " He is freelancing in parallel; the freelance role does not replace his full-time job search."
            else:
                text = "No. The synchronized public career status does not currently indicate a full-time job search."

        return StructuredFactAnswer(
            text + " [career-status] [experience-education]",
            source="career-status",
            evidence="Resolved from explicit public career-availability statements synchronized from the portfolio About/Contact copy.",
        )

    def _resolve_current_work(self, question: str, language: str):
        """Use localized structured fields and include parallel CDI availability."""
        if not self._matches(_precision._CURRENT_PATTERNS, question):
            return None
        current = [
            row for row in self.experiences
            if "present" in _precision._normalize(str(row.get("period") or ""))
        ]
        if not current:
            return None
        row = current[0]
        career = self.profile.get("career_status") or {}

        if language == "fr":
            role = str(row.get("role_fr") or row.get("role") or "")
            company = str(row.get("company_fr") or row.get("company") or "")
            period = str(row.get("period_fr") or row.get("period") or "")
            description = str(row.get("description_fr") or row.get("description") or "").strip()
            highlights = [str(x) for x in (row.get("highlights_fr") or row.get("highlights") or []) if str(x).strip()]
            text = f"Actuellement, Youssef exerce comme {role} chez {company} ({period}). {description}"
            if highlights:
                text += " Ses activités documentées comprennent : " + "; ".join(highlights) + "."
            if isinstance(career, dict) and career.get("seeking_full_time") is True:
                text += " En parallèle, son portfolio indique explicitement qu’il recherche une opportunité en CDI à temps plein."
        elif language == "ar":
            role = str(row.get("role") or "")
            company = str(row.get("company") or "")
            period = str(row.get("period") or "")
            description = str(row.get("description") or "").strip()
            highlights = [str(x) for x in row.get("highlights", []) if str(x).strip()]
            text = f"حالياً، يعمل يوسف كـ {role} لدى {company} ({period}). {description}"
            if highlights:
                text += " وتشمل أنشطته الموثقة: " + "؛ ".join(highlights) + "."
            if isinstance(career, dict) and career.get("seeking_full_time") is True:
                text += " وبالتوازي مع ذلك، يذكر ملفه العام صراحةً أنه يبحث عن فرصة عمل بدوام كامل."
        else:
            role = str(row.get("role") or "")
            company = str(row.get("company") or "")
            period = str(row.get("period") or "")
            description = str(row.get("description") or "").strip()
            highlights = [str(x) for x in row.get("highlights", []) if str(x).strip()]
            text = f"Youssef's current public professional role is {role} at {company} ({period}). {description}"
            if highlights:
                text += " His documented current work includes: " + "; ".join(highlights) + "."
            if isinstance(career, dict) and career.get("seeking_full_time") is True:
                text += " In parallel, his public portfolio explicitly states that he is seeking a full-time opportunity."

        citations = " [experience-education]"
        if isinstance(career, dict) and career.get("seeking_full_time") is True:
            citations += " [career-status]"
        return StructuredFactAnswer(text + citations, source="experience-education")

    def _canonicalize_project_sources(self, result):
        answer = result.answer
        source = result.source
        for row in self.projects:
            slug = str(row.get("slug") or "").strip()
            if not slug:
                continue
            canonical = f"project-{slug}"
            answer = answer.replace(f"[{slug}]", f"[{canonical}]")
            if source == slug:
                source = canonical

        if answer == result.answer and source == result.source:
            return result
        return replace(result, answer=answer, source=source)

    def resolve(self, question, history=None):
        history = history or []
        language = _precision.detect_language(question)

        # Highest-risk career state is explicit, never inferred from freelance.
        result = self._resolve_job_search(question, language)

        # Certification wording must be handled before generic "Agentic AI"
        # capability matching. Otherwise a question such as "Which Oracle Agentic
        # AI certification does he have?" can be semantically hijacked by the
        # capability resolver merely because its title contains "Agentic AI".
        if result is None:
            result = self._resolve_certifications(question, history, language)

        if result is None:
            result = super().resolve(question, history)
        if result is None:
            return None
        return self._canonicalize_project_sources(result)


__all__ = ["StructuredFactAnswer", "StructuredFactResolver"]
