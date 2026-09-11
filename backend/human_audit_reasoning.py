"""Human-audit reasoning for high-stakes recruiter/client portfolio questions.

This layer captures semantic families that a real recruiter, client, or visitor
naturally asks but that are too easy for generic retrieval to answer with a
secondary project. It stays evidence-first and deliberately calibrated:
professional experience -> measured projects -> technical projects -> skills ->
certifications/training.
"""
from __future__ import annotations

import re

import precision_facts as _precision


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


def _answer(text: str, source: str = "experience-education", evidence: str = "Human-audit evidence synthesis."):
    return _precision.StructuredFactAnswer(text, source=source, evidence=evidence)


def _recruiter_pitch(resolver, n: str, lang: str):
    signal = any(x in n for x in (
        "30 seconds", "30 second", "30-second", "convince me", "worth interviewing",
        "worth an interview", "interviewing for a junior", "pitch youssef", "recruiter pitch",
        "convaincs moi", "convainquez moi", "merite un entretien", "mérite un entretien",
    ))
    if not (_referent(n) and signal):
        return None
    accident = _project(resolver, "real-time-road-accident-detection")
    legal = _project(resolver, "openlegama-moroccan-legal-ai")
    ar, lr = accident.get("results") or {}, legal.get("results") or {}
    if lang == "fr":
        text = (
            "En 30 secondes : **Youssef Bouzit est un AI/ML Engineer junior avec déjà une vraie expérience professionnelle et des systèmes mesurés**. "
            "Chez **NEXTRONIC — ABA Technology**, il a travaillé en Computer Vision sur son PFE de détection d’accidents en temps réel avec YOLOv11, BoT-SORT et OpenCV. "
            f"Le benchmark image rapporte {ar.get('precision','86.68%')} de précision, {ar.get('recall','91.56%')} de rappel, {ar.get('f1Score','89.06%')} F1 et ~{ar.get('inferenceSpeed','31.5 FPS')}. "
            f"Il a aussi construit **OpenLegaMa**, un Controlled RAG avec citations, abstention et évaluation ({lr.get('automatedTests','143 / 143 passing')}, {lr.get('indexedArticles','7,708')} articles). "
            "Son portfolio ajoute une vraie couche MLOps/backend. **C’est un profil junior/early-career qui mérite un entretien pour ses preuves pratiques, pas pour ses certificats seuls.** "
            "[experience-education] [project-real-time-road-accident-detection] [project-openlegama-moroccan-legal-ai] [project-customer-churn-mlops-platform]"
        )
    else:
        text = (
            "In 30 seconds: **Youssef Bouzit is a junior AI/ML Engineer who already has real company experience and measured end-to-end systems**. "
            "At **NEXTRONIC — ABA Technology**, he worked on real-time road-accident Computer Vision using YOLOv11, BoT-SORT, and OpenCV. "
            f"The held-out image benchmark reports {ar.get('precision','86.68%')} precision, {ar.get('recall','91.56%')} recall, {ar.get('f1Score','89.06%')} F1, and ~{ar.get('inferenceSpeed','31.5 FPS')}. "
            f"He also built **OpenLegaMa**, an evaluated controlled-RAG system with citations, abstention, {lr.get('automatedTests','143 / 143 passing')}, and {lr.get('indexedArticles','7,708')} indexed articles. "
            "His portfolio adds MLOps/backend breadth. **That makes him worth interviewing as a junior/early-career engineer because of practical evidence, not certificates alone.** "
            "[experience-education] [project-real-time-road-accident-detection] [project-openlegama-moroccan-legal-ai] [project-customer-churn-mlops-platform]"
        )
    return _answer(text)


def _real_company_experience(resolver, n: str, lang: str):
    signal = any(x in n for x in (
        "real company setting", "worked in a real company", "work in a real company", "company setting",
        "corporate setting", "corporate experience", "real company experience", "professional company experience",
        "vraie entreprise", "vraie expérience en entreprise", "vraie experience en entreprise",
        "contexte entreprise", "expérience en entreprise", "experience en entreprise",
    ))
    if not (_referent(n) and signal):
        return None
    if lang == "fr":
        text = (
            "**Oui.** Youssef a une expérience documentée en entreprise chez **NEXTRONIC, filiale d’ABA Technology**, de février à août 2026, comme **AI/ML Engineer Intern orienté Computer Vision**. "
            "Il y a développé son PFE : un système de détection d’accidents routiers en temps réel combinant **YOLOv11, BoT-SORT, OpenCV, logique comportementale, fusion de décision, alertes, clips MP4 et logs CSV**. "
            "Le PFE a obtenu **18/20, mention Excellent**. [experience-education] [project-real-time-road-accident-detection]"
        )
    else:
        text = (
            "**Yes.** Youssef has documented company experience at **NEXTRONIC, an ABA Technology subsidiary**, from February to August 2026 as an **AI/ML Engineer Intern focused on Computer Vision**. "
            "He developed his graduation project there: a real-time road-accident system combining **YOLOv11, BoT-SORT, OpenCV, behavioral logic, decision fusion, alerts, MP4 evidence clips, and CSV logs**. "
            "The PFE received **18/20, Excellent distinction**. [experience-education] [project-real-time-road-accident-detection]"
        )
    return _answer(text)


def _agentic_truth(resolver, n: str, lang: str):
    agentic = any(x in n for x in ("agentic", "ai agent", "ai agents", "langgraph", "tool calling", "human approval", "human-in-the-loop", "human in the loop"))
    proof = any(x in n for x in ("actually", "really", "done this", "has he done", "hands-on", "coursework", "skills", "proof", "evidence", "prouve", "preuve", "vraiment"))
    if not (_referent(n) and agentic and proof):
        return None
    if lang == "fr":
        text = (
            "La réponse calibrée est : **la capacité Agentic AI est documentée, mais elle est moins prouvée publiquement que Computer Vision ou RAG**. "
            "Son profil liste agent workflows, tool calling, human-in-the-loop, state management, MCP, guardrails et une activité freelance mentionnant des agents IA. [skills] [experience-education]\n\n"
            "En revanche, le portfolio public **ne montre pas encore un projet autonome LangGraph/Agentic AI avec tool calling + approbation humaine et des métriques publiques** comparable à OpenLegaMa ou au PFE Computer Vision. "
            "Les certifications renforcent cette capacité — notamment **Oracle Agentic AI Certified Foundations Associate** et les formations Anthropic **Building with the Claude API** / **Model Context Protocol: Advanced Topics** — mais elles ne remplacent pas une preuve projet. [certifications]\n\n"
            "Donc : **hands-on exposure/capacité crédible, mais pas encore un flagship agentic public mesuré**."
        )
    else:
        text = (
            "The calibrated answer is: **Agentic AI capability is documented, but the public proof is weaker than for Computer Vision or RAG**. "
            "His profile lists agent workflows, tool calling, human-in-the-loop, state management, MCP, guardrails, and current freelance work mentioning AI agents. [skills] [experience-education]\n\n"
            "However, the public portfolio **does not yet show a standalone LangGraph/Agentic AI project demonstrating tool calling + human approval with public measured results** comparable to OpenLegaMa or the Computer Vision PFE. "
            "Supporting credentials include **Oracle Agentic AI Certified Foundations Associate** plus Anthropic training in **Building with the Claude API** and **Model Context Protocol: Advanced Topics**; those credentials support the skill claim but do not substitute for project evidence. [certifications]\n\n"
            "So the defensible claim is **documented hands-on capability/exposure, not yet a measured public agentic flagship**."
        )
    return _answer(text, "skills")


def _postgres_structured_business(resolver, n: str, lang: str):
    data_signal = any(x in n for x in ("postgresql", "structured business data", "structured data", "tabular data", "business data", "donnees structurees", "données structurées"))
    if not (_referent(n) and data_signal):
        return None
    fraud = _project(resolver, "ai-powered-bank-fraud-detection-machine-learning-explainable-ai")
    fr = fraud.get("results") or {}
    if lang == "fr":
        text = (
            "**Oui.** Les preuves publiques couvrent à la fois données structurées et documents :\n\n"
            "1. **Customer MLOps Pipeline** — **PostgreSQL**, Airflow, MLflow, MinIO, Docker Compose et monitoring : preuve directe de travail avec une base relationnelle dans un pipeline ML. [project-customer-churn-mlops-platform]\n"
            f"2. **AI-Powered Bank Fraud Detection** — ML tabulaire sur **{fr.get('transactions','284,807')} transactions**, avec Pandas/NumPy, Scikit-learn, Random Forest, probabilités de risque et feature importance. [project-ai-powered-bank-fraud-detection-machine-learning-explainable-ai]\n"
            "3. **OpenLegaMa** — côté documents : ingestion, retrieval, Controlled RAG, citations et abstention. [project-openlegama-moroccan-legal-ai]\n\n"
            "Donc son portfolio ne se limite ni aux images ni aux documents : il montre aussi **SQL/PostgreSQL et données tabulaires métier**."
        )
    else:
        text = (
            "**Yes.** The public evidence covers both structured business data and documents:\n\n"
            "1. **Customer MLOps Pipeline** — **PostgreSQL**, Airflow, MLflow, MinIO, Docker Compose, and monitoring: direct evidence of a relational database inside an ML workflow. [project-customer-churn-mlops-platform]\n"
            f"2. **AI-Powered Bank Fraud Detection** — tabular ML on **{fr.get('transactions','284,807')} transactions**, using Pandas/NumPy, Scikit-learn, Random Forest, risk probabilities, and feature importance. [project-ai-powered-bank-fraud-detection-machine-learning-explainable-ai]\n"
            "3. **OpenLegaMa** — for documents: ingestion, retrieval, controlled RAG, citations, and abstention. [project-openlegama-moroccan-legal-ai]\n\n"
            "So the portfolio is not limited to images or text: it also demonstrates **SQL/PostgreSQL and tabular business-data work**."
        )
    return _answer(text, "project-customer-churn-mlops-platform")


def _client_ready(resolver, n: str, lang: str):
    signal = any(x in n for x in ("client-ready", "client ready", "product-ready", "product ready", "closest to a client", "ready for a client", "prêt pour un client", "pret pour un client", "proche d'un produit client", "proche d’un produit client"))
    if not (_referent(n) and signal):
        return None
    legal = _project(resolver, "openlegama-moroccan-legal-ai")
    lr = legal.get("results") or {}
    if lang == "fr":
        text = (
            "Le projet public **le plus proche d’un produit client-ready aujourd’hui est OpenLegaMa**. Il réunit dans une seule application : ingestion de corpus, retrieval, Controlled RAG multilingue, validation des références, citations, abstention, interface web, tests et évaluation. "
            f"Il documente {lr.get('automatedTests','143 / 143 passing')}, un benchmark de {lr.get('curatedBenchmark','610 cases')} + {lr.get('holdoutBenchmark','120 cases')} holdout et {lr.get('indexedArticles','7,708')} articles indexés. [project-openlegama-moroccan-legal-ai]\n\n"
            "C’est une preuve plus directe d’un **produit IA utilisable et évalué** que les petits projets de démonstration. Il reste toutefois un MVP public, pas la preuve d’années d’exploitation enterprise multi-tenant."
        )
    else:
        text = (
            "The public project **closest to a client-ready AI product today is OpenLegaMa**. In one application it combines corpus ingestion, retrieval, multilingual controlled RAG, reference validation, citations, abstention, a web interface, testing, and evaluation. "
            f"It documents {lr.get('automatedTests','143 / 143 passing')}, a {lr.get('curatedBenchmark','610 cases')} curated benchmark + {lr.get('holdoutBenchmark','120 cases')} holdout, and {lr.get('indexedArticles','7,708')} indexed articles. [project-openlegama-moroccan-legal-ai]\n\n"
            "That is stronger evidence of an **usable, evaluated AI product** than a small demo. It is still a public MVP, not proof of years operating a multi-tenant enterprise product."
        )
    return _answer(text, "project-openlegama-moroccan-legal-ai")


def _two_end_to_end(resolver, n: str, lang: str):
    two = bool(re.search(r"\b(?:two|2|deux)\b", n))
    signal = "end-to-end" in n or "end to end" in n or "bout en bout" in n
    projects = "project" in n or "projet" in n
    if not (_referent(n) and two and signal and projects):
        return None
    if lang == "fr":
        text = (
            "Les **2 projets** qui prouvent le mieux l’ingénierie IA end-to-end sont :\n\n"
            "1. **OpenLegaMa** — ingestion → retrieval → Controlled RAG → validation des références/citations → abstention → interface → tests/benchmarks. [project-openlegama-moroccan-legal-ai]\n"
            "2. **Customer MLOps Pipeline** — données/modèle → Airflow → MLflow → MinIO → PostgreSQL → Docker Compose → monitoring/Streamlit → workflow CI/CD. [project-customer-churn-mlops-platform]\n\n"
            "Ils couvrent deux dimensions complémentaires : **application GenAI complète** et **cycle ML/MLOps complet**."
        )
    else:
        text = (
            "The **two projects** that best demonstrate end-to-end AI engineering are:\n\n"
            "1. **OpenLegaMa** — ingestion → retrieval → controlled RAG → reference/citation validation → abstention → web interface → tests/benchmarks. [project-openlegama-moroccan-legal-ai]\n"
            "2. **Customer MLOps Pipeline** — data/model → Airflow → MLflow → MinIO → PostgreSQL → Docker Compose → monitoring/Streamlit → CI/CD workflow. [project-customer-churn-mlops-platform]\n\n"
            "Together they cover complementary dimensions: a **complete GenAI application** and a **complete ML/MLOps lifecycle**."
        )
    return _answer(text, "project-openlegama-moroccan-legal-ai")


def _three_interesting(resolver, n: str, lang: str):
    signal = bool(re.search(r"\b(?:three|3|trois)\b.*\b(?:most\s+interesting|interesting|interessants?|intéressants?|standout)\b.*\b(?:projects?|projets?)\b", n, re.I)) or bool(re.search(r"\b(?:projects?|projets?)\b.*\b(?:three|3|trois)\b.*\b(?:interesting|interessants?|intéressants?|standout)\b", n, re.I))
    if not (_referent(n) and signal):
        return None
    if lang == "fr":
        text = (
            "Trois projets se démarquent particulièrement :\n\n"
            "1. **Real-Time Road Accident Detection** — expérience professionnelle/PFE Computer Vision, YOLOv11 + BoT-SORT + OpenCV, métriques mesurées et temps réel. [project-real-time-road-accident-detection] [experience-education]\n"
            "2. **OpenLegaMa — Moroccan Legal AI Assistant** — Controlled RAG multilingue, citations, abstention et benchmarks. [project-openlegama-moroccan-legal-ai]\n"
            "3. **Customer MLOps Pipeline** — Airflow, MLflow, MinIO, PostgreSQL, Docker Compose, monitoring et CI/CD. [project-customer-churn-mlops-platform]\n\n"
            "Ensemble, ils montrent **Computer Vision + RAG/LLM + MLOps**."
        )
    else:
        text = (
            "Three projects stand out most:\n\n"
            "1. **Real-Time Road Accident Detection** — professional/PFE Computer Vision work with YOLOv11 + BoT-SORT + OpenCV, measured metrics, and real-time performance. [project-real-time-road-accident-detection] [experience-education]\n"
            "2. **OpenLegaMa — Moroccan Legal AI Assistant** — multilingual controlled RAG with citations, abstention, and benchmarks. [project-openlegama-moroccan-legal-ai]\n"
            "3. **Customer MLOps Pipeline** — Airflow, MLflow, MinIO, PostgreSQL, Docker Compose, monitoring, and CI/CD. [project-customer-churn-mlops-platform]\n\n"
            "Together they show **Computer Vision + RAG/LLM + MLOps**."
        )
    return _answer(text, "project-real-time-road-accident-detection")


def _public_gaps(resolver, n: str, lang: str):
    signal = any(x in n for x in ("evidence still weak", "evidence weak", "weak or incomplete", "weak and incomplete", "less proven publicly", "public evidence incomplete", "preuves encore faibles", "preuves publiques faibles", "moins prouve publiquement", "moins prouvé publiquement", "incomplet"))
    if not (_referent(n) and signal):
        return None
    if lang == "fr":
        text = (
            "Les principaux **écarts de preuve publique** sont :\n\n"
            "1. **Agentic AI / LangGraph** — les skills, le freelance et les formations sont documentés, mais pas encore un flagship public autonome avec tool calling/HITL et métriques comparables à OpenLegaMa. [skills] [experience-education] [certifications]\n"
            "2. **Ownership enterprise long terme à grande échelle** — le portfolio ne prouve pas encore plusieurs années d’exploitation d’un système multi-tenant sous forte charge.\n"
            "3. **Road Accident Detection vidéo end-to-end** — les métriques publiées sont celles du benchmark image YOLOv11s ; pas encore de précision/rappel officiel du pipeline vidéo complet faute d’annotations temporelles complètes. [project-real-time-road-accident-detection]\n\n"
            "Ce sont des limites de **preuve disponible**, pas des affirmations que Youssef est incapable de ces tâches."
        )
    else:
        text = (
            "The main **public-evidence gaps** are:\n\n"
            "1. **Agentic AI / LangGraph** — skills, freelance exposure, and training are documented, but there is not yet a standalone public flagship demonstrating tool calling/HITL with measured results comparable to OpenLegaMa. [skills] [experience-education] [certifications]\n"
            "2. **Long-term large-scale enterprise ownership** — the portfolio does not yet prove years of operating a multi-tenant system under sustained high load.\n"
            "3. **Road Accident Detection end-to-end video metrics** — published precision/recall are for the YOLOv11s image benchmark; there is no official precision/recall for the complete video pipeline without full temporal annotations. [project-real-time-road-accident-detection]\n\n"
            "These are limits of **available public proof**, not claims that Youssef cannot perform those tasks."
        )
    return _answer(text, "skills")


def _certs_compensate(resolver, n: str, lang: str):
    cert = any(x in n for x in ("certificat", "certification", "certificate", "certifications", "56"))
    compensate = any(x in n for x in ("compensate", "make up for", "lack of experience", "manque d'experience", "manque d’expérience", "compensent", "remplacent l'experience", "remplacent l’expérience"))
    if not (_referent(n) and cert and compensate):
        return None
    if lang == "fr":
        text = (
            "**Non : 56 certificats ne remplacent pas l’expérience.** Leur valeur est de renforcer et structurer les connaissances, pas de compenser artificiellement un manque de pratique. [certifications]\n\n"
            "La candidature de Youssef doit d’abord être défendue par **son expérience chez NEXTRONIC — ABA Technology**, son système Computer Vision mesuré, **OpenLegaMa** évalué et son pipeline **MLOps**. [experience-education] [project-real-time-road-accident-detection] [project-openlegama-moroccan-legal-ai] [project-customer-churn-mlops-platform]\n\n"
            "La limite reste celle d’un profil **junior/early-career** : moins d’années d’expérience enterprise qu’un ingénieur confirmé. Les certificats sont donc un **plus secondaire**, pas un substitut."
        )
    else:
        text = (
            "**No: 56 certifications do not replace experience.** Their value is to reinforce and structure knowledge, not to artificially compensate for missing practice. [certifications]\n\n"
            "Youssef's case should be led by **his NEXTRONIC — ABA Technology experience**, the measured Computer Vision system, evaluated **OpenLegaMa**, and the **MLOps** pipeline. [experience-education] [project-real-time-road-accident-detection] [project-openlegama-moroccan-legal-ai] [project-customer-churn-mlops-platform]\n\n"
            "The remaining limitation is normal for a **junior/early-career** profile: fewer years of enterprise experience than an established engineer. Certifications are therefore a **secondary plus, not a substitute**."
        )
    return _answer(text, "experience-education")


def _rag_client_trust(resolver, n: str, lang: str):
    rag = "rag" in n or "document" in n or "knowledge base" in n
    trust = any(x in n for x in ("trust youssef", "why should i trust", "citations and abstention", "reliable", "fiable", "preuves concretes", "preuves concrètes"))
    if not (_referent(n) and rag and trust):
        return None
    legal = _project(resolver, "openlegama-moroccan-legal-ai")
    lr = legal.get("results") or {}
    if lang == "fr":
        text = (
            "La preuve la plus forte est **OpenLegaMa**, un système RAG construit et évalué — pas seulement une compétence déclarée. Il combine **retrieval, Controlled RAG multilingue, validation de références, citations fondées et abstention quand les preuves sont insuffisantes**. "
            f"L’évaluation documente {lr.get('automatedTests','143 / 143 passing')}, {lr.get('curatedBenchmark','610 cases')} curatés + {lr.get('holdoutBenchmark','120 cases')} holdout, {lr.get('indexedArticles','7,708')} articles, Recall@5={lr.get('documentRecallAt5','100% curated')} et exact-article recall={lr.get('exactArticleRecall','100% measured')}. [project-openlegama-moroccan-legal-ai]\n\n"
            "Pour des documents internes d’entreprise, cette architecture peut être adaptée aux permissions, au corpus, au modèle et au jeu d’évaluation. La preuve publique valide le **pattern d’ingénierie RAG**, pas chaque intégration enterprise possible."
        )
    else:
        text = (
            "The strongest evidence is **OpenLegaMa**, a built and evaluated RAG system — not just a declared skill. It combines **retrieval, multilingual controlled RAG, reference validation, grounded citations, and abstention when evidence is insufficient**. "
            f"Documented evaluation includes {lr.get('automatedTests','143 / 143 passing')}, {lr.get('curatedBenchmark','610 cases')} curated + {lr.get('holdoutBenchmark','120 cases')} holdout, {lr.get('indexedArticles','7,708')} indexed articles, Recall@5={lr.get('documentRecallAt5','100% curated')}, and exact-article recall={lr.get('exactArticleRecall','100% measured')}. [project-openlegama-moroccan-legal-ai]\n\n"
            "For internal company documents, that architecture can be adapted to permissions, corpus, model provider, and evaluation set. The public evidence proves the **RAG engineering pattern**, not every possible enterprise integration."
        )
    return _answer(text, "project-openlegama-moroccan-legal-ai")


def _simple_identity(resolver, n: str, lang: str):
    signal = any(x in n for x in ("who is youssef in simple words", "who is he in simple words", "simply who is youssef", "qui est youssef simplement", "en termes simples", "ببساطة من هو يوسف"))
    if not signal:
        return None
    if lang == "fr":
        text = (
            "En termes simples, **Youssef Bouzit est un AI/ML Engineer et Ingénieur d’État en Data Science**, avec ses preuves les plus fortes en **Computer Vision temps réel** et **RAG/LLM**. Il a une expérience professionnelle chez NEXTRONIC — ABA Technology, construit des projets IA end-to-end et exerce aussi en freelance en parallèle de sa recherche d’un CDI AI/ML. [experience-education] [career-status] [project-real-time-road-accident-detection] [project-openlegama-moroccan-legal-ai]"
        )
    else:
        text = (
            "In simple terms, **Youssef Bouzit is an AI/ML Engineer and State Engineer in Data Science**, with his strongest public evidence in **real-time Computer Vision** and **RAG/LLM systems**. He has professional experience at NEXTRONIC — ABA Technology, builds end-to-end AI projects, and also freelances in parallel while seeking a full-time AI/ML role. [experience-education] [career-status] [project-real-time-road-accident-detection] [project-openlegama-moroccan-legal-ai]"
        )
    return _answer(text)


def resolve_human_audit(resolver, question: str):
    n = _n(question)
    lang = _lang(resolver, question)
    for handler in (
        _recruiter_pitch,
        _real_company_experience,
        _agentic_truth,
        _postgres_structured_business,
        _client_ready,
        _two_end_to_end,
        _three_interesting,
        _public_gaps,
        _certs_compensate,
        _rag_client_trust,
        _simple_identity,
    ):
        result = handler(resolver, n, lang)
        if result is not None:
            return result
    return None


__all__ = ["resolve_human_audit"]
