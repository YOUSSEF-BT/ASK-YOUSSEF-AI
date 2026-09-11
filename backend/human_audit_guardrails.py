"""Compatibility-aware semantic guardrails for recruiter/client human audits.

This layer sits in front of ``human_audit_reasoning``. It handles broad natural
phrasing discovered by live human audits while deliberately yielding to older,
more specialized recruiter handlers when their richer contract should win.
"""
from __future__ import annotations

import re

import precision_facts as _precision
import human_audit_reasoning as _base


def _n(text: str) -> str:
    return _precision._normalize(text or "")


def _lang(resolver, question: str) -> str:
    if hasattr(resolver, "_effective_language"):
        return resolver._effective_language(question)
    return _precision.detect_language(question)


def _referent(n: str) -> bool:
    return bool(re.search(r"\b(?:youssef|his|he|him|son|ses|il|lui|يوسف)\b", n, re.I))


def _project(resolver, slug: str):
    target = _precision._normalize(slug)
    return next(
        (row for row in resolver.projects if _precision._normalize(str(row.get("slug") or "")) == target),
        {},
    )


def _answer(text: str, source: str, evidence: str):
    return _precision.StructuredFactAnswer(text, source=source, evidence=evidence)


def _agentic(resolver, n: str, lang: str):
    agentic = any(x in n for x in (
        "agentic", "langgraph", "ai agent", "ai agents", "tool calling",
        "human approval", "human-in-the-loop", "human in the loop",
    ))
    contrast = any(x in n for x in (
        "actually", "really", "done this", "has he done", "hands-on", "coursework",
        "skills", "certifications", "mainly based", "vraiment", "preuve", "prouve",
    ))
    if not (_referent(n) and agentic and contrast):
        return None
    if lang == "fr":
        text = (
            "La preuve Agentic AI est **plus limitée que pour Computer Vision ou RAG**. Le portfolio documente agent workflows, tool calling, human-in-the-loop, state management, MCP, guardrails, ainsi qu’une activité freelance mentionnant des agents IA. [skills] [experience-education]\n\n"
            "Mais le portfolio public **ne montre pas encore un projet autonome LangGraph/Agentic AI avec tool calling + approbation humaine et des résultats publics mesurés** comparables à OpenLegaMa ou au PFE Computer Vision. La formulation correcte est donc **capacité/hands-on exposure documentée**, pas expérience enterprise démontrée au même niveau.\n\n"
            "Les preuves de formation sont **Oracle Agentic AI Certified Foundations Associate**, puis côté Anthropic **Building with the Claude API** et **Model Context Protocol: Advanced Topics**. [certifications]"
        )
    else:
        text = (
            "The Agentic AI evidence is **more limited than for Computer Vision or RAG**. The portfolio documents agent workflows, tool calling, human-in-the-loop, state management, MCP, guardrails, and freelance exposure mentioning AI agents. [skills] [experience-education]\n\n"
            "However, the public portfolio **does not yet show a standalone LangGraph/Agentic AI project with tool calling + human approval and public measured results** comparable to OpenLegaMa or the Computer Vision PFE. The defensible claim is therefore **documented hands-on capability/exposure**, not enterprise experience proven at the same level.\n\n"
            "Supporting training evidence is **Oracle Agentic AI Certified Foundations Associate**, plus Anthropic's **Building with the Claude API** and **Model Context Protocol: Advanced Topics**. [certifications]"
        )
    return _answer(text, "skills", "Calibrated agentic capability from skills, freelance exposure, and issuer-correct training evidence.")


def _structured_data(resolver, n: str, lang: str):
    signal = any(x in n for x in (
        "structured data", "structured business data", "business data", "tabular data",
        "tabular", "postgresql", "donnees structurees", "données structurées",
    ))
    if not (_referent(n) and signal):
        return None
    fraud = _project(resolver, "ai-powered-bank-fraud-detection-machine-learning-explainable-ai")
    results = fraud.get("results") or {}
    if lang == "fr":
        text = (
            "Oui. La preuve la plus directe sur les **données structurées métier** est **AI-Powered Bank Fraud Detection** : "
            f"ML tabulaire sur **{results.get('transactions','284,807')} transactions** avec Pandas/NumPy, Scikit-learn, Random Forest, probabilités de risque et feature importance. [project-ai-powered-bank-fraud-detection-machine-learning-explainable-ai]\n\n"
            "Côté bases de données, **Customer MLOps Pipeline** utilise **PostgreSQL** dans un workflow Airflow/MLflow/MinIO/Docker [project-customer-churn-mlops-platform], et **Data Quality Monitoring** documente **MySQL + REST API** [project-2-data-quality-monitoring-2025-12]. "
            "Pour les documents, **OpenLegaMa** apporte ingestion, retrieval, Controlled RAG, citations et abstention. [project-openlegama-moroccan-legal-ai]"
        )
    else:
        text = (
            "Yes. The most direct evidence for **structured business data** is **AI-Powered Bank Fraud Detection**: "
            f"tabular ML on **{results.get('transactions','284,807')} transactions** using Pandas/NumPy, Scikit-learn, Random Forest, risk probabilities, and feature importance. [project-ai-powered-bank-fraud-detection-machine-learning-explainable-ai]\n\n"
            "For databases, **Customer MLOps Pipeline** uses **PostgreSQL** inside an Airflow/MLflow/MinIO/Docker workflow [project-customer-churn-mlops-platform], while **Data Quality Monitoring** documents **MySQL + REST APIs** [project-2-data-quality-monitoring-2025-12]. "
            "For documents, **OpenLegaMa** adds ingestion, retrieval, controlled RAG, citations, and abstention. [project-openlegama-moroccan-legal-ai]"
        )
    return _answer(text, "project-ai-powered-bank-fraud-detection-machine-learning-explainable-ai", "Cross-project structured-data evidence.")


def _client_ready(resolver, n: str, lang: str):
    signal = any(x in n for x in (
        "client-ready", "client ready", "product-ready", "product ready", "most product-ready",
        "closest to a client", "ready for a client", "paying customer", "prêt pour un client",
        "pret pour un client", "produit client",
    ))
    if not signal:
        return None
    legal = _project(resolver, "openlegama-moroccan-legal-ai")
    r = legal.get("results") or {}
    if lang == "fr":
        text = (
            "Le projet public **le plus proche d’un produit client-ready aujourd’hui est OpenLegaMa**. Il réunit ingestion de corpus, retrieval, Controlled RAG multilingue, validation des références, citations, abstention, interface web, tests et évaluation. "
            f"Il documente {r.get('automatedTests','143 / 143 passing')}, {r.get('curatedBenchmark','610 cases')} cas curatés + {r.get('holdoutBenchmark','120 cases')} holdout et {r.get('indexedArticles','7,708')} articles indexés. [project-openlegama-moroccan-legal-ai]\n\n"
            "Cela en fait une preuve plus directe d’un **produit IA utilisable et évalué** que les petits projets de démonstration. Il reste néanmoins un MVP public, pas une preuve d’années d’exploitation enterprise multi-tenant."
        )
    else:
        text = (
            "The public project **closest to a client-ready AI product today is OpenLegaMa**. It combines corpus ingestion, retrieval, multilingual controlled RAG, reference validation, citations, abstention, a web interface, testing, and evaluation. "
            f"It documents {r.get('automatedTests','143 / 143 passing')}, {r.get('curatedBenchmark','610 cases')} curated cases + {r.get('holdoutBenchmark','120 cases')} holdout, and {r.get('indexedArticles','7,708')} indexed articles. [project-openlegama-moroccan-legal-ai]\n\n"
            "That is more direct evidence of an **usable, evaluated AI product** than a small demo. It is still a public MVP, not proof of years operating a multi-tenant enterprise product."
        )
    return _answer(text, "project-openlegama-moroccan-legal-ai", "Client-readiness ranking from complete public product evidence.")


def _public_gap(resolver, n: str, lang: str):
    strength_and_gap = (
        "strength" in n
        and any(x in n for x in ("less proven", "less evidence", "gap", "where"))
    )
    if strength_and_gap:
        # Preserve the older combined strengths+gaps contract, which returns both.
        return None
    signal = any(x in n for x in (
        "evidence still weak", "evidence weak", "weak or incomplete", "weak and incomplete",
        "less proven publicly", "public evidence incomplete", "biggest gap", "main gap",
        "gap in his public proof", "public proof gap", "public evidence gap",
        "preuves encore faibles", "preuves publiques faibles", "moins prouve publiquement",
        "moins prouvé publiquement", "plus grande lacune", "incomplet",
    ))
    if not (_referent(n) and signal):
        return None
    if lang == "fr":
        text = (
            "Les principaux **écarts de preuve publique** sont :\n\n"
            "1. **Agentic AI / LangGraph** — skills, exposition freelance et formations sont documentés, mais pas encore un flagship public autonome avec tool calling/HITL et métriques comparables à OpenLegaMa. [skills] [experience-education] [certifications]\n"
            "2. **Ownership enterprise long terme à grande échelle** — pas encore de preuve publique de plusieurs années d’exploitation d’un système multi-tenant sous forte charge.\n"
            "3. **Road Accident Detection vidéo end-to-end** — les métriques publiées portent sur le benchmark image YOLOv11s ; pas encore de précision/rappel officiel du pipeline vidéo complet sans annotations temporelles complètes. [project-real-time-road-accident-detection]\n\n"
            "Ce sont des limites de **preuve publique disponible**, pas des affirmations d’absence de compétence."
        )
    else:
        text = (
            "The main **public-evidence gaps** are:\n\n"
            "1. **Agentic AI / LangGraph** — skills, freelance exposure, and training are documented, but there is not yet a standalone public flagship demonstrating tool calling/HITL with measured results comparable to OpenLegaMa. [skills] [experience-education] [certifications]\n"
            "2. **Long-term large-scale enterprise ownership** — the portfolio does not yet prove years operating a multi-tenant system under sustained high load.\n"
            "3. **Road Accident Detection end-to-end video metrics** — published precision/recall are for the YOLOv11s image benchmark; there is no official precision/recall for the complete video pipeline without full temporal annotations. [project-real-time-road-accident-detection]\n\n"
            "These are limits of **available public proof**, not claims that he lacks those capabilities."
        )
    return _answer(text, "skills", "Calibrated public-evidence gap analysis.")


def _cv_vs_agentic(resolver, n: str, lang: str):
    if not (_referent(n) and "computer vision" in n and any(x in n for x in ("agentic", "ai agent", "agents"))):
        return None
    comparison = any(x in n for x in ("stronger", "fit", "better", "today", "plus fort", "meilleur", "adapté", "adapte"))
    if not comparison:
        return None
    accident = _project(resolver, "real-time-road-accident-detection")
    r = accident.get("results") or {}
    if lang == "fr":
        text = (
            "**Oui : si le besoin prioritaire est Computer Vision, Youssef est aujourd’hui nettement plus prouvé publiquement qu’en Agentic AI.** "
            "Il a une expérience professionnelle chez NEXTRONIC — ABA Technology et un système YOLOv11 + BoT-SORT + OpenCV mesuré à "
            f"{r.get('precision','86.68%')} précision, {r.get('recall','91.56%')} rappel, {r.get('f1Score','89.06%')} F1 et ~{r.get('inferenceSpeed','31.5 FPS')}. [experience-education] [project-real-time-road-accident-detection]\n\n"
            "En Agentic AI, les compétences, le freelance et les formations sont documentés, mais il n’y a pas encore un flagship LangGraph/agentic autonome avec métriques publiques comparables. [skills] [certifications]"
        )
    else:
        text = (
            "**Yes: if Computer Vision is the priority, Youssef is currently much more strongly proven there than in Agentic AI.** "
            "He has professional NEXTRONIC — ABA Technology experience and a measured YOLOv11 + BoT-SORT + OpenCV system with "
            f"{r.get('precision','86.68%')} precision, {r.get('recall','91.56%')} recall, {r.get('f1Score','89.06%')} F1, and ~{r.get('inferenceSpeed','31.5 FPS')}. [experience-education] [project-real-time-road-accident-detection]\n\n"
            "For Agentic AI, skills, freelance exposure, and training are documented, but there is not yet a standalone LangGraph/agentic flagship with comparable public metrics. [skills] [certifications]"
        )
    return _answer(text, "project-real-time-road-accident-detection", "Direct evidence comparison between Computer Vision and Agentic AI.")


def _client_risk(resolver, n: str, lang: str):
    signal = any(x in n for x in ("risky choice", "risk for my", "what would make", "be candid", "risque", "risqué", "risquee", "risquée"))
    if not (_referent(n) and signal):
        return None
    if lang == "fr":
        text = (
            "Pour un client, les risques à évaluer sont surtout **des limites de preuve et de périmètre**, pas des défauts inventés :\n\n"
            "• **Profil junior/early-career** : moins d’années d’ownership enterprise qu’un ingénieur senior. [experience-education]\n"
            "• **Agentic AI/LangGraph** : capacité documentée, mais pas encore un flagship public mesuré avec HITL/tool calling. [skills] [certifications]\n"
            "• **Très gros projet enterprise** : un scope multi-tenant, compliance lourde ou grande équipe doit être cadré avant de le confier à un ingénieur freelance individuel.\n\n"
            "En revanche, pour **Computer Vision, RAG/LLM, ML/MLOps et prototypes/MVPs orientés produit**, son portfolio fournit des preuves techniques concrètes et mesurées. [project-real-time-road-accident-detection] [project-openlegama-moroccan-legal-ai] [project-customer-churn-mlops-platform]"
        )
    else:
        text = (
            "For a client, the main risks are **evidence and scope limitations**, not invented weaknesses:\n\n"
            "• **Junior/early-career profile**: fewer years of enterprise ownership than a senior engineer. [experience-education]\n"
            "• **Agentic AI/LangGraph**: documented capability, but not yet a measured public flagship demonstrating HITL/tool calling. [skills] [certifications]\n"
            "• **Very large enterprise scope**: multi-tenant infrastructure, heavy compliance, or agency-scale staffing should be scoped carefully before assigning it to one freelance engineer.\n\n"
            "For **Computer Vision, RAG/LLM, ML/MLOps, and product-oriented prototypes/MVPs**, however, the portfolio provides concrete measured technical evidence. [project-real-time-road-accident-detection] [project-openlegama-moroccan-legal-ai] [project-customer-churn-mlops-platform]"
        )
    return _answer(text, "experience-education", "Candid client risk assessment grounded in public-evidence scope.")


def resolve_human_audit(resolver, question: str):
    n = _n(question)
    lang = _lang(resolver, question)

    # Preserve specialized legacy recruiter contracts when the query explicitly
    # asks for a CTO summary or a combined strengths+gaps answer.
    if "cto" in n and any(x in n for x in ("summary", "summarize", "30 second", "30-second")):
        return None
    if "strength" in n and any(x in n for x in ("less proven", "less evidence", "gap", "where")):
        return None

    for handler in (
        _cv_vs_agentic,
        _agentic,
        _structured_data,
        _client_ready,
        _public_gap,
        _client_risk,
    ):
        result = handler(resolver, n, lang)
        if result is not None:
            return result

    return _base.resolve_human_audit(resolver, question)


__all__ = ["resolve_human_audit"]
