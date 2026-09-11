"""QA hardening layer for deterministic portfolio facts.

The previous production resolver is kept verbatim in ``structured_facts_base``.
This module subclasses it and closes conversational edge cases discovered by
live production audits: French slang language detection, unemployment wording,
Arabic current-role localization, Arabic Oracle counts, noisy employer suffixes,
explicit false-claim requests, and exact accident-stack questions.
"""
from __future__ import annotations

import re

import precision_facts as _precision
import structured_facts_base as _base

StructuredFactAnswer = _base.StructuredFactAnswer


_FRENCH_HINTS = (
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
    "certificat",
    "projet",
    "emploi",
    "travail ou nn",
)

_UNEMPLOYMENT_PATTERNS = (
    r"\bchomage\b",
    r"\bchomeur\b",
    r"\bunemployed\b",
    r"\bjobless\b",
    r"عاطل",
    r"البطالة",
)

_FALSE_CLAIM_PATTERNS = (
    r"\bmeme si (?:c['’ ]?est )?faux\b",
    r"\beven if (?:it['’ ]?s|it is|that is)?\s*false\b",
    r"\beven though (?:it['’ ]?s|it is|that is)?\s*false\b",
    r"حتى لو.*(?:خطأ|غير صحيح|كاذب)",
)

_ARABIC_ORACLE = re.compile(r"(?:أوراكل|اوراكل|أوركل|اوركل)")


class StructuredFactResolver(_base.StructuredFactResolver):
    """Production resolver with live-audit edge cases handled deterministically."""

    @staticmethod
    def _effective_language(question: str) -> str:
        """Keep short/slang French and Arabic prompts in the visitor's language."""
        raw = question or ""
        if re.search(r"[\u0600-\u06FF]", raw):
            return "ar"
        normalized = _precision._normalize(raw)
        if any(hint in normalized for hint in _FRENCH_HINTS):
            return "fr"
        return _precision.detect_language(raw)

    def _current_row(self):
        return next(
            (
                row
                for row in self.experiences
                if "present" in _precision._normalize(str(row.get("period") or ""))
            ),
            None,
        )

    def _resolve_unemployment(self, question: str, language: str):
        normalized = _precision._normalize(question)
        if not any(re.search(pattern, normalized, re.I) for pattern in _UNEMPLOYMENT_PATTERNS):
            return None

        row = self._current_row()
        if row is None:
            return None
        career = self.profile.get("career_status") or {}
        seeking = isinstance(career, dict) and career.get("seeking_full_time") is True

        if language == "fr":
            role = str(row.get("role_fr") or row.get("role") or "Ingénieur IA/ML Freelance")
            company = str(row.get("company_fr") or row.get("company") or "Fiverr")
            period = str(row.get("period_fr") or row.get("period") or "")
            text = f"Non. Youssef n’est pas au chômage selon son profil professionnel public : il exerce actuellement comme {role} chez {company}"
            if period:
                text += f" ({period})"
            text += "."
            if seeking:
                text += " En parallèle, il recherche une opportunité en CDI à temps plein."
        elif language == "ar":
            text = "لا. وفق ملفه المهني العام، يوسف ليس عاطلاً عن العمل؛ فهو يعمل حالياً كمهندس ذكاء اصطناعي وتعلّم آلي مستقل عبر Fiverr."
            if seeking:
                text += " وبالتوازي مع ذلك، يبحث عن فرصة عمل بدوام كامل."
        else:
            role = str(row.get("role") or "Freelance AI/ML Engineer")
            company = str(row.get("company") or "Fiverr")
            period = str(row.get("period") or "")
            text = f"No. According to his public professional profile, Youssef is not unemployed; he currently works as a {role} at {company}"
            if period:
                text += f" ({period})"
            text += "."
            if seeking:
                text += " In parallel, he is seeking a full-time opportunity."

        citations = " [experience-education]"
        if seeking:
            citations += " [career-status]"
        return StructuredFactAnswer(text + citations, source="experience-education")

    @staticmethod
    def _resolve_explicit_false_claim(question: str, language: str):
        normalized = _precision._normalize(question)
        if not any(re.search(pattern, normalized, re.I) for pattern in _FALSE_CLAIM_PATTERNS):
            return None

        if language == "fr":
            text = (
                "Je ne vais pas présenter comme un fait une affirmation que vous indiquez être fausse. "
                "Je peux uniquement décrire l’expérience professionnelle publique et vérifiable de Youssef."
            )
        elif language == "ar":
            text = (
                "لن أقدّم ادعاءً تشير أنت إلى أنه غير صحيح على أنه حقيقة. "
                "يمكنني فقط وصف الخبرة المهنية العامة والموثقة ليوسف."
            )
        else:
            text = (
                "I won't present a claim that you explicitly say is false as a fact. "
                "I can only describe Youssef's public, verifiable professional experience."
            )
        return StructuredFactAnswer(
            text + " [experience-education] [career-status]",
            source="experience-education",
            evidence="Explicitly false claims are not converted into portfolio facts.",
        )

    def _resolve_arabic_oracle(self, question: str, language: str):
        if language != "ar" or not _ARABIC_ORACLE.search(question or ""):
            return None
        normalized = _precision._normalize(question)
        if not any(term in normalized for term in ("شهادة", "شهادات", "الشهادات", "كم", "عدد")):
            return None

        rows = [
            row
            for row in self.certifications
            if "oracle" in _precision._normalize(str(row.get("issuer") or ""))
        ]
        if not rows:
            return None
        lines = "\n".join(
            f"{index}. {str(row.get('title') or '').strip()}"
            for index, row in enumerate(rows, 1)
        )
        text = f"لدى يوسف {len(rows)} شهادات Oracle موثقة في ملفه المهني العام:\n{lines}"
        return StructuredFactAnswer(text + " [certifications]", source="certifications")

    def _resolve_accident_stack(self, question: str, language: str):
        normalized = _precision._normalize(question)
        if "accident" not in normalized:
            return None
        if not any(term in normalized for term in ("model", "modele", "tracker", "tracking", "yolo", "botsort", "bot-sort", "suivi")):
            return None

        project = next(
            (
                row
                for row in self.projects
                if _precision._normalize(str(row.get("slug") or ""))
                == "real-time-road-accident-detection"
            ),
            None,
        )
        if project is None:
            return None

        source = "project-real-time-road-accident-detection"
        if language == "fr":
            text = (
                "Pour le projet de détection d’accidents routiers en temps réel, Youssef a utilisé "
                "YOLOv11s fine-tuné pour la détection/classification des accidents, YOLOv11n pour "
                "la détection des véhicules, et BoT-SORT pour le suivi multi-objet."
            )
        elif language == "ar":
            text = (
                "في مشروع اكتشاف حوادث الطرق في الزمن الحقيقي، استخدم يوسف YOLOv11s بعد ضبطه "
                "لاكتشاف/تصنيف الحوادث، وYOLOv11n لاكتشاف المركبات، وBoT-SORT لتتبع الأجسام."
            )
        else:
            text = (
                "For the real-time road accident detection project, Youssef used a fine-tuned "
                "YOLOv11s for accident detection/classification, YOLOv11n for vehicle detection, "
                "and BoT-SORT for multi-object tracking."
            )
        return StructuredFactAnswer(f"{text} [{source}]", source=source)

    def _resolve_current_work(self, question: str, language: str):
        """Keep the Arabic current-work answer Arabic instead of mixing raw EN fields."""
        if language != "ar":
            return _base.StructuredFactResolver._resolve_current_work(self, question, language)
        if not self._matches(_precision._CURRENT_PATTERNS, question):
            return None

        row = self._current_row()
        if row is None:
            return None
        career = self.profile.get("career_status") or {}
        text = (
            "حالياً، يعمل يوسف كمهندس ذكاء اصطناعي وتعلّم آلي مستقل عبر Fiverr منذ سبتمبر 2026. "
            "يركز عمله الموثق على أنظمة RAG وتطبيقات LLM، ووكلاء الذكاء الاصطناعي وذكاء الوثائق، "
            "وحلول تعلم الآلة والرؤية الحاسوبية."
        )
        if isinstance(career, dict) and career.get("seeking_full_time") is True:
            text += " وبالتوازي مع ذلك، يذكر ملفه العام صراحةً أنه يبحث عن فرصة عمل بدوام كامل."
        citations = " [experience-education]"
        if isinstance(career, dict) and career.get("seeking_full_time") is True:
            citations += " [career-status]"
        return StructuredFactAnswer(text + citations, source="experience-education")

    def _extract_employer_target_clean(self, question: str):
        target = self._extract_employer_target(question)
        if not target:
            match = re.search(
                r"(?:هل\s+)?(?:عمل|يعمل)\s+يوسف\s+(?:في|لدى|مع)\s+([^؟?!.]+)",
                question or "",
                re.I,
            )
            target = match.group(1) if match else None
        if not target:
            return None
        target = re.sub(
            r"\b(?:maintenant|actuellement|en ce moment|now|currently|today)\b.*$",
            "",
            str(target),
            flags=re.I,
        ).strip(" \t.,;:!?؟-")
        return target or None

    def _resolve_employer(self, question: str, language: str):
        target = self._extract_employer_target_clean(question)
        if not target:
            return None
        target_norm = _precision._normalize(target)
        matches = [
            row
            for row in self.experiences
            if target_norm in _precision._normalize(str(row.get("company") or ""))
            or _precision._normalize(str(row.get("company") or "")) in target_norm
        ]

        if matches:
            row = matches[0]
            if language == "fr":
                company = str(row.get("company_fr") or row.get("company") or target)
                role = str(row.get("role_fr") or row.get("role") or "")
                period = str(row.get("period_fr") or row.get("period") or "")
                text = f"Oui. Le portfolio public répertorie une expérience chez {company} : {role} ({period})."
            elif language == "ar":
                company = str(row.get("company") or target)
                role = str(row.get("role") or "")
                period = str(row.get("period") or "")
                text = f"نعم. يعرض الملف المهني العام خبرة لدى {company}: {role} ({period})."
            else:
                company = str(row.get("company") or target)
                role = str(row.get("role") or "")
                period = str(row.get("period") or "")
                text = f"Yes. The public portfolio lists work experience at {company}: {role} ({period})."
        else:
            display = target[:1].upper() + target[1:]
            if language == "fr":
                text = f"Non. Aucune expérience professionnelle synchronisée ne répertorie {display} comme employeur de Youssef."
            elif language == "ar":
                text = f"لا. لا يعرض الملف المهني العام المتزامن أي خبرة عمل لدى {display}."
            else:
                text = f"No. The synchronized public professional profile does not list {display} as one of Youssef's employers."
        return StructuredFactAnswer(text + " [experience-education]", source="experience-education")

    def resolve(self, question, history=None):
        history = history or []
        language = self._effective_language(question)

        result = self._resolve_private_relationship(question, language)
        if result is None:
            result = self._resolve_explicit_false_claim(question, language)
        if result is None:
            result = self._resolve_contact_details(question, language)
        if result is None:
            result = self._resolve_professional_overview(question, language)
        if result is None:
            result = self._resolve_unemployment(question, language)
        if result is None:
            result = self._resolve_job_search(question, language)
        if result is None:
            result = self._resolve_arabic_oracle(question, language)
        if result is None:
            result = self._resolve_certifications(question, history, language)
        if result is None:
            result = self._resolve_accident_stack(question, language)
        if result is None:
            result = self._resolve_openlegama_rag(question, language)

        # Skip the previous compatibility-layer resolve method here because it
        # re-detects language. The precision parent still dispatches overridden
        # current-work/employer methods dynamically.
        if result is None:
            result = _precision.StructuredFactResolver.resolve(self, question, history)
        if result is None:
            return None
        return self._canonicalize_project_sources(result)


def __getattr__(name):
    """Delegate private compatibility symbols to the preserved base module."""
    return getattr(_base, name)


__all__ = ["StructuredFactAnswer", "StructuredFactResolver"]
