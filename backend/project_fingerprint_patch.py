"""Deterministic answers for high-confidence project fingerprints.

Some portfolio questions identify a unique project from two or more distinctive
technical facts. Those questions do not need an LLM once the synchronized
profile already contains the answer. Resolving them directly makes the public
assistant faster and keeps obvious project-identification questions available
when the generation provider is temporarily unavailable.
"""
from __future__ import annotations

import precision_facts as _precision
import structured_facts as _structured


def _project_by_slug(resolver, slug: str):
    target = _precision._normalize(slug)
    return next(
        (
            row
            for row in resolver.projects
            if _precision._normalize(str(row.get("slug") or "")) == target
        ),
        {},
    )


def _openlegama_fingerprint(normalized: str) -> bool:
    controlled_rag = "controlled rag" in normalized
    legal_scope = any(
        token in normalized
        for token in (
            "moroccan",
            "morocco",
            "marocain",
            "marocaine",
            "maroc",
            "droit",
            "legal",
            "juridique",
            "المغربي",
            "المغرب",
            "قانون",
            "القانون",
        )
    )
    return controlled_rag and legal_scope


def _accident_fingerprint(normalized: str) -> bool:
    tracker = any(token in normalized for token in ("bot-sort", "bot sort", "botsort"))
    return "yolov11s" in normalized and tracker


def _answer_openlegama(resolver, language: str):
    project = _project_by_slug(resolver, "openlegama-moroccan-legal-ai")
    title = str(project.get("title") or "OpenLegaMa — Moroccan Legal AI Assistant")
    if language == "fr":
        answer = (
            f"Le projet est **{title}**. Il utilise un **Controlled RAG** multilingue "
            "pour le droit marocain, avec validation des références, citations fondées "
            "et abstention lorsque les preuves sont insuffisantes. "
            "[project-openlegama-moroccan-legal-ai]"
        )
    elif language == "ar":
        answer = (
            f"المشروع هو **{title}**. يستخدم **Controlled RAG** متعدد اللغات للقانون "
            "المغربي، مع التحقق من المراجع والاستشهادات المبنية على الأدلة والامتناع "
            "عن الإجابة عندما تكون الأدلة غير كافية. "
            "[project-openlegama-moroccan-legal-ai]"
        )
    else:
        answer = (
            f"The project is **{title}**. It uses multilingual **Controlled RAG** for "
            "Moroccan law, with reference validation, grounded citations, and abstention "
            "when the available evidence is insufficient. "
            "[project-openlegama-moroccan-legal-ai]"
        )
    return _precision.StructuredFactAnswer(
        answer,
        source="project-openlegama-moroccan-legal-ai",
        evidence="Unique project fingerprint: Controlled RAG + Moroccan/legal scope.",
    )


def _answer_accident(resolver, language: str):
    project = _project_by_slug(resolver, "real-time-road-accident-detection")
    title = str(project.get("title") or "Real-Time Road Accident Detection — Computer Vision & Deep Learning")
    if language == "fr":
        answer = (
            f"Le projet est **{title}**. Il utilise un **YOLOv11s** fine-tuné pour la "
            "détection/classification des accidents et **BoT-SORT** pour le suivi "
            "multi-objets. [project-real-time-road-accident-detection]"
        )
    elif language == "ar":
        answer = (
            f"المشروع هو **{title}**. يستخدم **YOLOv11s** بعد الضبط الدقيق لاكتشاف/تصنيف "
            "الحوادث و**BoT-SORT** لتتبع عدة أجسام. "
            "[project-real-time-road-accident-detection]"
        )
    else:
        answer = (
            f"The project is **{title}**. It uses a fine-tuned **YOLOv11s** for accident "
            "detection/classification and **BoT-SORT** for multi-object tracking. "
            "[project-real-time-road-accident-detection]"
        )
    return _precision.StructuredFactAnswer(
        answer,
        source="project-real-time-road-accident-detection",
        evidence="Unique project fingerprint: YOLOv11s + BoT-SORT.",
    )


def _resolve_fingerprint(resolver, question: str):
    normalized = _precision._normalize(question)
    language = (
        resolver._effective_language(question)
        if hasattr(resolver, "_effective_language")
        else _precision.detect_language(question)
    )

    if _openlegama_fingerprint(normalized):
        return _answer_openlegama(resolver, language)
    if _accident_fingerprint(normalized):
        return _answer_accident(resolver, language)
    return None


def apply() -> None:
    cls = _structured.StructuredFactResolver
    if getattr(cls, "_project_fingerprint_patch", False):
        return

    original_resolve = cls.resolve

    def resolve(self, question, history=None):
        fingerprint = _resolve_fingerprint(self, question)
        if fingerprint is not None:
            return fingerprint
        return original_resolve(self, question, history)

    cls.resolve = resolve
    cls._project_fingerprint_patch = True


apply()
