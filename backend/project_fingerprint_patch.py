"""Deterministic recruiter reasoning for high-confidence portfolio questions.

The synchronized profile already contains enough structured evidence to answer a
number of recruiter/client questions without asking the LLM to invent a ranking
or decide whether evidence is sufficient. This layer handles two things:

1. unique project fingerprints (for example Controlled RAG + Moroccan law), and
2. evidence-comparison questions where the answer should follow a stable
   hierarchy: professional experience -> measured projects -> technical projects
   -> declared skills -> certifications/training.

The goal is not to hard-code arbitrary wording. Each resolver below recognizes a
semantic family and builds its answer from synchronized profile data.
"""
from __future__ import annotations

import re

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


def _language(resolver, question: str) -> str:
    return (
        resolver._effective_language(question)
        if hasattr(resolver, "_effective_language")
        else _precision.detect_language(question)
    )


def _referent(normalized: str) -> bool:
    padded = f" {normalized} "
    return any(
        token in padded
        for token in (" youssef ", " his ", " he ", " son ", " ses ", " il ", " lui ", " يوسف ")
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


def _executive_summary(resolver, question: str, normalized: str, language: str):
    summary_signal = any(x in normalized for x in ("summar", "resume", "résume", "profile in", "profil en"))
    audience_signal = any(x in normalized for x in ("cto", "30 second", "30-second", "executive", "recruiter pitch"))
    if not (_referent(normalized) and summary_signal and audience_signal):
        return None

    accident = _project_by_slug(resolver, "real-time-road-accident-detection")
    legal = _project_by_slug(resolver, "openlegama-moroccan-legal-ai")
    ar = accident.get("results") or {}
    lr = legal.get("results") or {}
    if language == "fr":
        answer = (
            "**Résumé CTO en 30 secondes :** Youssef Bouzit est Ingénieur d’État en Data Science orienté AI Engineering. "
            "Il possède une expérience professionnelle en Computer Vision chez NEXTRONIC — ABA Technology et développe en parallèle des solutions IA/ML en indépendant. "
            f"Ses preuves mesurées incluent un système temps réel YOLOv11/BoT-SORT ({ar.get('precision','86.68%')} précision, {ar.get('recall','91.56%')} rappel, ~{ar.get('inferenceSpeed','31.5 FPS')}) "
            f"et OpenLegaMa, un Controlled RAG évalué avec {lr.get('automatedTests','143 / 143 passing')}, {lr.get('curatedBenchmark','610 cases')} + {lr.get('holdoutBenchmark','120 cases')} et {lr.get('indexedArticles','7,708')} articles. "
            "Son profil couvre aussi MLOps et backend AI ; il recherche actuellement un CDI AI/ML. "
            "[experience-education] [project-real-time-road-accident-detection] [project-openlegama-moroccan-legal-ai] [career-status]"
        )
    else:
        answer = (
            "**30-second CTO summary:** Youssef Bouzit is a State Engineer in Data Science focused on AI Engineering. "
            "He has professional Computer Vision experience at NEXTRONIC — ABA Technology and parallel independent AI/ML work. "
            f"His measured evidence includes a real-time YOLOv11/BoT-SORT system ({ar.get('precision','86.68%')} precision, {ar.get('recall','91.56%')} recall, ~{ar.get('inferenceSpeed','31.5 FPS')}) "
            f"and OpenLegaMa, an evaluated controlled-RAG system with {lr.get('automatedTests','143 / 143 passing')}, {lr.get('curatedBenchmark','610 cases')} + {lr.get('holdoutBenchmark','120 cases')}, and {lr.get('indexedArticles','7,708')} indexed articles. "
            "He also shows MLOps and AI-backend breadth and is currently seeking a full-time AI/ML role. "
            "[experience-education] [project-real-time-road-accident-detection] [project-openlegama-moroccan-legal-ai] [career-status]"
        )
    return _precision.StructuredFactAnswer(
        answer,
        source="experience-education",
        evidence="Executive summary composed from synchronized professional experience, measured projects, and career status.",
    )


def _production_oriented_evidence(resolver, normalized: str, language: str):
    if not _referent(normalized):
        return None
    signals = (
        "production-oriented", "production oriented", "academic notebooks", "only academic", "isolated notebooks",
        "production system", "production systems", "notebook", "notebooks",
    )
    if not any(x in normalized for x in signals):
        return None
    legal = _project_by_slug(resolver, "openlegama-moroccan-legal-ai")
    accident = _project_by_slug(resolver, "real-time-road-accident-detection")
    mlops = _project_by_slug(resolver, "customer-churn-mlops-platform")
    lr = legal.get("results") or {}
    ar = accident.get("results") or {}
    if language == "fr":
        answer = (
            "Oui. Le portfolio montre des **systèmes complets orientés produit**, pas seulement des notebooks :\n\n"
            f"1. **OpenLegaMa** — MVP public stable, Controlled RAG multilingue, validation des citations, abstention, {lr.get('automatedTests','143 / 143 passing')} et benchmarks dédiés. [project-openlegama-moroccan-legal-ai]\n"
            f"2. **Road Accident Detection** — système temps réel professionnel/PFE avec détection, tracking, logique de décision, alertes, clips MP4 et logs CSV ; ~{ar.get('inferenceSpeed','31.5 FPS')}. [project-real-time-road-accident-detection] [experience-education]\n"
            "3. **Customer MLOps Pipeline** — Airflow, MLflow, MinIO, PostgreSQL, Docker Compose, monitoring et CI/CD. [project-customer-churn-mlops-platform]\n\n"
            "Cela prouve une orientation **système et ingénierie**. Le portfolio ne doit toutefois pas être interprété comme la preuve de plusieurs années d’exploitation enterprise à grande échelle."
        )
    else:
        answer = (
            "Yes. The portfolio shows **complete, product-oriented systems**, not only notebooks:\n\n"
            f"1. **OpenLegaMa** — a stable public MVP with multilingual controlled RAG, citation validation, abstention, {lr.get('automatedTests','143 / 143 passing')}, and dedicated benchmarks. [project-openlegama-moroccan-legal-ai]\n"
            f"2. **Road Accident Detection** — professional/PFE real-time system with detection, tracking, decision logic, alerts, MP4 evidence clips, and CSV logs; ~{ar.get('inferenceSpeed','31.5 FPS')}. [project-real-time-road-accident-detection] [experience-education]\n"
            "3. **Customer MLOps Pipeline** — Airflow, MLflow, MinIO, PostgreSQL, Docker Compose, monitoring, and CI/CD. [project-customer-churn-mlops-platform]\n\n"
            "That is strong evidence of **system-level engineering**. It should not be overstated as proof of years of large-scale enterprise production ownership."
        )
    return _precision.StructuredFactAnswer(answer, source="project-openlegama-moroccan-legal-ai")


def _integrated_systems(resolver, normalized: str, language: str):
    if not _referent(normalized):
        return None
    combine = any(x in normalized for x in ("combining multiple", "combine multiple", "multiple ai components", "several ai components", "plusieurs composants", "plusieurs briques"))
    system = any(x in normalized for x in ("one system", "integrated", "cohesive", "un systeme", "un système"))
    if not (combine and system):
        return None
    if language == "fr":
        answer = (
            "Oui. Deux exemples publics sont particulièrement clairs :\n\n"
            "1. **Road Accident Detection** combine détection de véhicules, modèle YOLOv11s fine-tuné, tracking BoT-SORT, analyse comportementale αβγ, logique de fusion, alertes, clips MP4 et logs CSV. [project-real-time-road-accident-detection] [experience-education]\n"
            "2. **OpenLegaMa** combine ingestion documentaire, retrieval, Controlled RAG multilingue, validation de références, citations, abstention et évaluation systématique. [project-openlegama-moroccan-legal-ai]\n\n"
            "Cela montre une capacité d’intégration de composants IA et logiciels, pas seulement l’entraînement d’un modèle isolé."
        )
    else:
        answer = (
            "Yes. Two public examples are especially clear:\n\n"
            "1. **Road Accident Detection** combines vehicle detection, a fine-tuned YOLOv11s model, BoT-SORT tracking, αβγ behavioral analysis, decision fusion, alerts, MP4 evidence clips, and CSV event logs. [project-real-time-road-accident-detection] [experience-education]\n"
            "2. **OpenLegaMa** combines document ingestion, retrieval, multilingual controlled RAG, reference validation, citations, abstention, and systematic evaluation. [project-openlegama-moroccan-legal-ai]\n\n"
            "That is evidence of integrating AI and software components rather than training an isolated model only."
        )
    return _precision.StructuredFactAnswer(answer, source="project-real-time-road-accident-detection")


def _evaluation_capability(resolver, normalized: str, language: str):
    if not _referent(normalized):
        return None
    evaluation_signal = any(x in normalized for x in ("evaluate an ai", "evaluate ai", "evaluation properly", "properly evaluate", "evaluer un", "évaluer un", "evaluer l", "évaluer l"))
    prototype_contrast = any(x in normalized for x in ("only build prototypes", "only prototypes", "just prototypes", "seulement des prototypes", "que des prototypes"))
    if not (evaluation_signal or prototype_contrast):
        return None
    legal = _project_by_slug(resolver, "openlegama-moroccan-legal-ai")
    accident = _project_by_slug(resolver, "real-time-road-accident-detection")
    lr = legal.get("results") or {}
    ar = accident.get("results") or {}
    if language == "fr":
        answer = (
            "Oui — le portfolio montre qu’il **évalue ses systèmes**, pas seulement qu’il construit des prototypes.\n\n"
            f"• **OpenLegaMa** : {lr.get('automatedTests','143 / 143 passing')}, benchmark curaté de {lr.get('curatedBenchmark','610 cases')}, holdout de {lr.get('holdoutBenchmark','120 cases')}, Recall@5={lr.get('documentRecallAt5','100% curated')} et exact-article recall={lr.get('exactArticleRecall','100% measured')}. [project-openlegama-moroccan-legal-ai]\n"
            f"• **Road Accident Detection** : benchmark image held-out avec {ar.get('precision','86.68%')} précision, {ar.get('recall','91.56%')} rappel, {ar.get('f1Score','89.06%')} F1 et {ar.get('inferenceSpeed','31.5 FPS')}. [project-real-time-road-accident-detection]\n\n"
            "Nuance importante : le pipeline vidéo accident complet n’a pas encore de précision/rappel end-to-end officiel faute d’annotations temporelles complètes."
        )
    else:
        answer = (
            "Yes — the portfolio shows that he **evaluates AI systems**, not only that he builds prototypes.\n\n"
            f"• **OpenLegaMa**: {lr.get('automatedTests','143 / 143 passing')}, a {lr.get('curatedBenchmark','610 cases')} curated benchmark, a {lr.get('holdoutBenchmark','120 cases')} holdout, Recall@5={lr.get('documentRecallAt5','100% curated')}, and exact-article recall={lr.get('exactArticleRecall','100% measured')}. [project-openlegama-moroccan-legal-ai]\n"
            f"• **Road Accident Detection**: a held-out image benchmark with {ar.get('precision','86.68%')} precision, {ar.get('recall','91.56%')} recall, {ar.get('f1Score','89.06%')} F1, and {ar.get('inferenceSpeed','31.5 FPS')}. [project-real-time-road-accident-detection]\n\n"
            "Important caveat: the complete accident-video pipeline does not yet have official end-to-end precision/recall without complete temporal annotations."
        )
    return _precision.StructuredFactAnswer(answer, source="project-openlegama-moroccan-legal-ai")


def _domain_fit_comparison(resolver, normalized: str, language: str):
    if not _referent(normalized):
        return None
    domains = {
        "cv": any(x in normalized for x in ("computer vision", "vision par ordinateur")),
        "genai": any(x in normalized for x in ("generative ai", "genai", "rag", "llm")),
        "mlops": "mlops" in normalized,
    }
    if sum(domains.values()) < 2 or not any(x in normalized for x in ("better fit", "best fit", "fit for", "would he be", "meilleur profil", "mieux adapte", "mieux adapté")):
        return None
    if language == "fr":
        answer = (
            "Sur la base des **preuves publiques actuelles**, je classerais l’adéquation ainsi :\n\n"
            "1. **Computer Vision — preuve la plus forte professionnellement** : stage/PFE chez NEXTRONIC — ABA Technology, YOLOv11 + BoT-SORT + OpenCV, avec métriques mesurées et temps réel. [experience-education] [project-real-time-road-accident-detection]\n"
            "2. **Generative AI / RAG — preuve publique très forte** : OpenLegaMa est un Controlled RAG évalué avec citations, abstention, benchmarks et MVP public ; son activité freelance mentionne aussi RAG/LLM et agents IA. [project-openlegama-moroccan-legal-ai] [experience-education]\n"
            "3. **MLOps — bonne preuve projet, mais moins de preuve professionnelle publique** : Customer MLOps Pipeline couvre Airflow, MLflow, MinIO, PostgreSQL, Docker Compose et CI/CD. [project-customer-churn-mlops-platform]\n\n"
            "Donc, pour un recrutement immédiat, **Computer Vision est le domaine le plus prouvé professionnellement**, tandis que **RAG/Generative AI est presque aussi fort côté projet public évalué**. MLOps est une compétence complémentaire crédible plutôt que son axe le plus démontré."
        )
    else:
        answer = (
            "Based on the **current public evidence**, I would rank the fit like this:\n\n"
            "1. **Computer Vision — strongest professional evidence**: internship/PFE work at NEXTRONIC — ABA Technology using YOLOv11 + BoT-SORT + OpenCV, with measured metrics and real-time performance. [experience-education] [project-real-time-road-accident-detection]\n"
            "2. **Generative AI / RAG — very strong public project evidence**: OpenLegaMa is an evaluated controlled-RAG system with citations, abstention, benchmarks, and a public MVP; his freelance profile also documents RAG/LLM and AI-agent work. [project-openlegama-moroccan-legal-ai] [experience-education]\n"
            "3. **MLOps — solid project evidence, but less public professional evidence**: Customer MLOps Pipeline covers Airflow, MLflow, MinIO, PostgreSQL, Docker Compose, and CI/CD. [project-customer-churn-mlops-platform]\n\n"
            "So for immediate hiring, **Computer Vision is the most professionally proven area**, while **RAG/Generative AI is nearly as strong on evaluated public-project evidence**. MLOps is a credible complementary strength rather than his most proven specialization."
        )
    return _precision.StructuredFactAnswer(answer, source="experience-education")


def _structured_data_evidence(resolver, normalized: str, language: str):
    if not _referent(normalized):
        return None
    if not any(x in normalized for x in ("structured data", "tabular data", "tabular", "donnees structurees", "données structurées")):
        return None
    fraud = _project_by_slug(resolver, "ai-powered-bank-fraud-detection-machine-learning-explainable-ai")
    fr = fraud.get("results") or {}
    if language == "fr":
        answer = (
            "La preuve la plus directe est **AI-Powered Bank Fraud Detection** : il travaille sur un dataset tabulaire de cartes bancaires contenant "
            f"**{fr.get('transactions','284,807')} transactions** et {fr.get('fraudCases','492')} cas de fraude, avec Pandas/NumPy, Scikit-learn, Random Forest, probabilités de risque et analyse d’importance des features. "
            "[project-ai-powered-bank-fraud-detection-machine-learning-explainable-ai]\n\n"
            "Il a aussi des projets explicitement data/database : **Customer MLOps Pipeline** avec PostgreSQL [project-customer-churn-mlops-platform] et **Data Quality Monitoring** avec MySQL/REST API [project-2-data-quality-monitoring-2025-12]."
        )
    else:
        answer = (
            "The most direct evidence is **AI-Powered Bank Fraud Detection**: it works on a tabular credit-card dataset containing "
            f"**{fr.get('transactions','284,807')} transactions** and {fr.get('fraudCases','492')} fraud cases, using Pandas/NumPy, Scikit-learn, Random Forest, risk probabilities, and feature-importance analysis. "
            "[project-ai-powered-bank-fraud-detection-machine-learning-explainable-ai]\n\n"
            "He also has explicitly data/database-oriented projects: **Customer MLOps Pipeline** with PostgreSQL [project-customer-churn-mlops-platform] and **Data Quality Monitoring** with MySQL/REST APIs [project-2-data-quality-monitoring-2025-12]."
        )
    return _precision.StructuredFactAnswer(answer, source="project-ai-powered-bank-fraud-detection-machine-learning-explainable-ai")


def _agentic_evidence_calibration(resolver, normalized: str, language: str):
    if not _referent(normalized):
        return None
    agentic = "langgraph" in normalized or "ai agent" in normalized or "agents" in normalized
    contrast = any(x in normalized for x in ("actually experienced", "mainly based", "just skills", "skills and certifications", "vraiment", "principalement", "surtout base", "surtout basé"))
    if not (agentic and contrast):
        return None
    if language == "fr":
        answer = (
            "La preuve est **plus limitée que pour Computer Vision ou RAG**. Le portfolio documente des compétences Agentic AI (agent workflows, tool calling, human-in-the-loop, state management, MCP, guardrails), une activité freelance mentionnant des agents IA, et des certifications/formations associées. [skills] [experience-education] [certifications]\n\n"
            "En revanche, le portfolio public synchronisé **ne présente pas encore un projet autonome LangGraph/Agentic AI avec métriques publiques comparables à OpenLegaMa ou au PFE Computer Vision**. Il est donc plus précis de parler de **capacité/hands-on exposure documentée**, et non du même niveau de preuve publique qu’en CV ou RAG."
        )
    else:
        answer = (
            "The evidence is **more limited than for Computer Vision or RAG**. The portfolio documents Agentic AI skills (agent workflows, tool calling, human-in-the-loop, state management, MCP, guardrails), current freelance work mentioning AI agents, and relevant certifications/training. [skills] [experience-education] [certifications]\n\n"
            "However, the synchronized public portfolio **does not yet show a standalone LangGraph/Agentic AI project with public measured results comparable to OpenLegaMa or the Computer Vision PFE**. The calibrated claim is therefore **documented hands-on capability/exposure**, not the same level of public proof as CV or RAG."
        )
    return _precision.StructuredFactAnswer(answer, source="skills")


def _professional_vs_project_tech(resolver, normalized: str, language: str):
    if not _referent(normalized):
        return None
    professional = any(x in normalized for x in ("professionally", "professional", "professionnel", "professionnelle"))
    project_side = any(x in normalized for x in ("personal project", "personal projects", "only in", "versus", "vs", "projets personnels", "projet personnel"))
    technologies = any(x in normalized for x in ("technologies", "technology", "tech stack", "outils", "technologies"))
    if not (professional and project_side and technologies):
        return None
    if language == "fr":
        answer = (
            "Le portfolio permet une séparation **partielle mais solide** :\n\n"
            "**Utilisation professionnelle explicitement documentée**\n"
            "• NEXTRONIC — ABA Technology : **Python, YOLO, OpenCV, BoT-SORT, Deep Learning** dans le système de détection d’accidents. [experience-education] [project-real-time-road-accident-detection]\n"
            "• Activité freelance indépendante : **RAG, LLMs, AI Agents, Python, Machine Learning** sont explicitement listés dans l’expérience actuelle. [experience-education]\n\n"
            "**Preuves surtout via projets publics/personnels**\n"
            "• OpenLegaMa : Next.js, TypeScript, Controlled RAG, Groq SDK, Python, Vercel. [project-openlegama-moroccan-legal-ai]\n"
            "• Customer MLOps Pipeline : Airflow, MLflow, MinIO, PostgreSQL, Docker Compose, Streamlit. [project-customer-churn-mlops-platform]\n"
            "• Bank Fraud : Scikit-learn, Pandas, Random Forest, Streamlit. [project-ai-powered-bank-fraud-detection-machine-learning-explainable-ai]\n\n"
            "Le portfolio ne permet pas d’affirmer que **chaque** technologie de projet personnel a aussi été utilisée dans une mission commerciale."
        )
    else:
        answer = (
            "The portfolio supports a **partial but useful separation**:\n\n"
            "**Explicitly documented professional use**\n"
            "• NEXTRONIC — ABA Technology: **Python, YOLO, OpenCV, BoT-SORT, Deep Learning** in the road-accident system. [experience-education] [project-real-time-road-accident-detection]\n"
            "• Independent freelance activity: **RAG, LLMs, AI Agents, Python, Machine Learning** are explicitly listed in the current experience entry. [experience-education]\n\n"
            "**Evidence mainly from public/personal projects**\n"
            "• OpenLegaMa: Next.js, TypeScript, Controlled RAG, Groq SDK, Python, Vercel. [project-openlegama-moroccan-legal-ai]\n"
            "• Customer MLOps Pipeline: Airflow, MLflow, MinIO, PostgreSQL, Docker Compose, Streamlit. [project-customer-churn-mlops-platform]\n"
            "• Bank Fraud: Scikit-learn, Pandas, Random Forest, Streamlit. [project-ai-powered-bank-fraud-detection-machine-learning-explainable-ai]\n\n"
            "The public portfolio does not justify claiming that **every** personal-project technology was also used in commercial work."
        )
    return _precision.StructuredFactAnswer(answer, source="experience-education")


def _strengths_and_gaps(resolver, normalized: str, language: str):
    if not _referent(normalized):
        return None
    strengths = any(x in normalized for x in ("top 3 strength", "top three strength", "3 strengths", "3 forces", "trois forces"))
    gaps = any(x in normalized for x in ("less evidence", "less proven", "areas where", "moins de preuves", "moins prouve", "moins prouvé"))
    if not (strengths and gaps):
        return None
    if language == "fr":
        answer = (
            "**Top 3 forces appuyées par les preuves publiques :**\n"
            "1. **Computer Vision temps réel** — expérience professionnelle NEXTRONIC + métriques YOLOv11/BoT-SORT. [experience-education] [project-real-time-road-accident-detection]\n"
            "2. **RAG/LLM fiable et évalué** — OpenLegaMa : Controlled RAG, citations, abstention, benchmarks et 143/143 tests. [project-openlegama-moroccan-legal-ai]\n"
            "3. **Ingénierie end-to-end / MLOps** — orchestration, tracking, stockage d’artefacts, bases de données, monitoring et CI/CD via Customer MLOps Pipeline. [project-customer-churn-mlops-platform]\n\n"
            "**2 domaines moins prouvés publiquement aujourd’hui :**\n"
            "1. **Agentic AI / LangGraph à l’échelle d’un projet public mesuré** — le portfolio montre compétences, freelance et formations, mais pas encore un flagship agentic autonome avec métriques publiques. [skills] [experience-education] [certifications]\n"
            "2. **Ownership enterprise long terme à grande échelle** — le portfolio montre PFE professionnel, freelance et projets complets, mais moins de preuve publique d’années d’exploitation d’un système enterprise sous forte charge.\n\n"
            "Ce sont des **écarts de preuve publique**, pas des affirmations d’absence de compétence."
        )
    else:
        answer = (
            "**Top 3 strengths supported by public evidence:**\n"
            "1. **Real-time Computer Vision** — professional NEXTRONIC experience plus measured YOLOv11/BoT-SORT results. [experience-education] [project-real-time-road-accident-detection]\n"
            "2. **Evaluated, grounded RAG/LLM systems** — OpenLegaMa: controlled RAG, citations, abstention, benchmarks, and 143/143 tests. [project-openlegama-moroccan-legal-ai]\n"
            "3. **End-to-end AI engineering / MLOps** — orchestration, experiment tracking, artifact storage, databases, monitoring, and CI/CD through Customer MLOps Pipeline. [project-customer-churn-mlops-platform]\n\n"
            "**Two areas with less public evidence today:**\n"
            "1. **Agentic AI / LangGraph at the level of a measured public flagship** — the portfolio shows skills, freelance activity, and training, but not yet a standalone agentic project with public metrics. [skills] [experience-education] [certifications]\n"
            "2. **Long-term large-scale enterprise ownership** — there is professional PFE, freelance activity, and complete projects, but less public evidence of years operating an enterprise system under sustained high load.\n\n"
            "These are **public-evidence gaps**, not claims that he lacks those capabilities."
        )
    return _precision.StructuredFactAnswer(answer, source="experience-education")


def _junior_readiness(resolver, normalized: str, language: str):
    if not _referent(normalized) or "junior" not in normalized:
        return None
    readiness = any(x in normalized for x in ("ready", "pret", "prêt", "academic", "academique", "académique"))
    if not readiness:
        return None
    accident = _project_by_slug(resolver, "real-time-road-accident-detection")
    ar = accident.get("results") or {}
    if language == "fr":
        answer = (
            "Oui. Sur la base du portfolio public, Youssef est **crédible pour un poste AI Engineer junior** et son profil n’est plus seulement académique :\n\n"
            "• **Expérience professionnelle** : stage AI/ML Engineer | Computer Vision chez NEXTRONIC — ABA Technology. [experience-education]\n"
            f"• **Système mesuré en conditions temps réel** : YOLOv11 + BoT-SORT + OpenCV, {ar.get('precision','86.68%')} précision, {ar.get('recall','91.56%')} rappel et ~{ar.get('inferenceSpeed','31.5 FPS')}. [project-real-time-road-accident-detection]\n"
            "• **RAG évalué** : OpenLegaMa avec citations, abstention, benchmarks et tests automatisés. [project-openlegama-moroccan-legal-ai]\n"
            "• **Cycle ML/MLOps** : Airflow, MLflow, MinIO, PostgreSQL, Docker Compose et CI/CD dans Customer MLOps Pipeline. [project-customer-churn-mlops-platform]\n\n"
            "Les certifications renforcent le profil, mais les **projets et l’expérience professionnelle sont la preuve principale**. Cela soutient un positionnement junior/early-career ; ce n’est pas une preuve d’un niveau senior avec plusieurs années d’ownership production."
        )
    else:
        answer = (
            "Yes. Based on the public portfolio, Youssef is **credible for a junior AI Engineer role** and the profile is no longer only academic:\n\n"
            "• **Professional experience**: AI/ML Engineer | Computer Vision internship at NEXTRONIC — ABA Technology. [experience-education]\n"
            f"• **Measured real-time system**: YOLOv11 + BoT-SORT + OpenCV with {ar.get('precision','86.68%')} precision, {ar.get('recall','91.56%')} recall, and ~{ar.get('inferenceSpeed','31.5 FPS')}. [project-real-time-road-accident-detection]\n"
            "• **Evaluated RAG system**: OpenLegaMa with citations, abstention, benchmarks, and automated tests. [project-openlegama-moroccan-legal-ai]\n"
            "• **ML/MLOps lifecycle**: Airflow, MLflow, MinIO, PostgreSQL, Docker Compose, and CI/CD in Customer MLOps Pipeline. [project-customer-churn-mlops-platform]\n\n"
            "Certifications strengthen the profile, but **projects and professional experience are the primary evidence**. That supports a junior/early-career positioning; it is not evidence of senior-level multi-year production ownership."
        )
    return _precision.StructuredFactAnswer(answer, source="experience-education")


def _beyond_training(resolver, normalized: str, language: str):
    if not _referent(normalized):
        return None
    model_train = any(x in normalized for x in ("other than train", "beyond training", "only train", "autre chose que entrainer", "autre chose qu entrainer", "que entrainer un modele", "que entraîner un modèle"))
    if not model_train:
        return None
    if language == "fr":
        answer = (
            "Oui. Les preuves les plus fortes vont **au-delà de l’entraînement d’un modèle** :\n\n"
            "1. **Système Computer Vision complet** : tracking BoT-SORT, analyse comportementale, fusion de décision, alertes, sauvegarde MP4 et journalisation CSV autour des modèles YOLO. [project-real-time-road-accident-detection] [experience-education]\n"
            "2. **OpenLegaMa** : ingestion documentaire, retrieval, Controlled RAG, validation de références, citations, abstention et benchmark/holdout. [project-openlegama-moroccan-legal-ai]\n"
            "3. **Customer MLOps Pipeline** : orchestration Airflow, tracking MLflow, stockage MinIO, PostgreSQL, monitoring, Docker Compose et CI/CD. [project-customer-churn-mlops-platform]\n\n"
            "Donc la preuve pratique porte sur **l’intégration, l’évaluation et l’exploitation du pipeline**, pas seulement sur `fit()`/training."
        )
    else:
        answer = (
            "Yes. The strongest evidence goes **well beyond model training**:\n\n"
            "1. **Complete Computer Vision system**: BoT-SORT tracking, behavioral analysis, decision fusion, alerts, MP4 evidence capture, and CSV logging around the YOLO models. [project-real-time-road-accident-detection] [experience-education]\n"
            "2. **OpenLegaMa**: document ingestion, retrieval, controlled RAG, reference validation, citations, abstention, and benchmark/holdout evaluation. [project-openlegama-moroccan-legal-ai]\n"
            "3. **Customer MLOps Pipeline**: Airflow orchestration, MLflow tracking, MinIO storage, PostgreSQL, monitoring, Docker Compose, and CI/CD. [project-customer-churn-mlops-platform]\n\n"
            "So the practical evidence is about **integration, evaluation, and pipeline engineering**, not only model `fit()`/training."
        )
    return _precision.StructuredFactAnswer(answer, source="project-real-time-road-accident-detection")


def _complete_architecture(resolver, normalized: str, language: str):
    if not _referent(normalized):
        return None
    architecture = any(x in normalized for x in ("complete architecture", "full architecture", "architecture complete", "architecture complète", "architecture de bout en bout"))
    project = any(x in normalized for x in ("project", "projet", "مشروع"))
    if not (architecture and project):
        return None
    legal = _project_by_slug(resolver, "openlegama-moroccan-legal-ai")
    lr = legal.get("results") or {}
    if language == "fr":
        answer = (
            "Pour une **architecture d’application IA complète**, le meilleur exemple est **OpenLegaMa** : ingestion/corpus, retrieval, Controlled RAG multilingue, validation des références, citations, abstention, interface web, tests et évaluation. "
            f"Le projet documente {lr.get('automatedTests','143 / 143 passing')}, {lr.get('curatedBenchmark','610 cases')} + {lr.get('holdoutBenchmark','120 cases')} et un MVP public stable. [project-openlegama-moroccan-legal-ai]\n\n"
            "Pour l’architecture **MLOps du cycle ML**, **Customer MLOps Pipeline** est le meilleur second exemple avec Airflow, MLflow, MinIO, PostgreSQL, Docker Compose, monitoring et CI/CD. [project-customer-churn-mlops-platform]"
        )
    else:
        answer = (
            "For a **complete AI-application architecture**, the strongest example is **OpenLegaMa**: corpus ingestion, retrieval, multilingual controlled RAG, reference validation, citations, abstention, web application, testing, and evaluation. "
            f"It documents {lr.get('automatedTests','143 / 143 passing')}, {lr.get('curatedBenchmark','610 cases')} + {lr.get('holdoutBenchmark','120 cases')}, and a stable public MVP. [project-openlegama-moroccan-legal-ai]\n\n"
            "For **ML lifecycle/MLOps architecture**, **Customer MLOps Pipeline** is the strongest second example with Airflow, MLflow, MinIO, PostgreSQL, Docker Compose, monitoring, and CI/CD. [project-customer-churn-mlops-platform]"
        )
    return _precision.StructuredFactAnswer(answer, source="project-openlegama-moroccan-legal-ai")


def _certs_vs_practice(resolver, normalized: str, language: str):
    if not _referent(normalized):
        return None
    certs = any(x in normalized for x in ("certificat", "certification", "certificate", "credentials", "شهاد"))
    practical = any(x in normalized for x in ("practical proof", "practical evidence", "proof behind", "real proof", "preuves pratiques", "preuve pratique", "derriere", "derrière", "vraiment des preuves", "hands-on"))
    if not (certs and practical):
        return None
    if language == "fr":
        answer = (
            "Oui. Les certifications sont **secondaires** par rapport aux preuves pratiques déjà publiques :\n\n"
            "1. **Expérience NEXTRONIC — ABA Technology** : système Computer Vision temps réel développé dans un contexte professionnel/PFE. [experience-education] [project-real-time-road-accident-detection]\n"
            "2. **OpenLegaMa** : système RAG public et évalué, avec citations, abstention, benchmarks et 143/143 tests. [project-openlegama-moroccan-legal-ai]\n"
            "3. **Customer MLOps Pipeline** : orchestration, experiment tracking, artifact storage, PostgreSQL, Docker et CI/CD. [project-customer-churn-mlops-platform]\n"
            "4. **Bank Fraud Detection** : ML tabulaire sur 284,807 transactions avec dashboard et explicabilité. [project-ai-powered-bank-fraud-detection-machine-learning-explainable-ai]\n\n"
            "Donc les **56 certifications** renforcent le CV, mais elles ne sont pas la preuve principale : les projets mesurés et l’expérience professionnelle le sont. [certifications]"
        )
    else:
        answer = (
            "Yes. The certifications are **secondary** to the practical evidence already public:\n\n"
            "1. **NEXTRONIC — ABA Technology experience**: a real-time Computer Vision system developed in a professional/PFE context. [experience-education] [project-real-time-road-accident-detection]\n"
            "2. **OpenLegaMa**: a public, evaluated RAG system with citations, abstention, benchmarks, and 143/143 tests. [project-openlegama-moroccan-legal-ai]\n"
            "3. **Customer MLOps Pipeline**: orchestration, experiment tracking, artifact storage, PostgreSQL, Docker, and CI/CD. [project-customer-churn-mlops-platform]\n"
            "4. **Bank Fraud Detection**: tabular ML on 284,807 transactions with a dashboard and explainability. [project-ai-powered-bank-fraud-detection-machine-learning-explainable-ai]\n\n"
            "So the **56 certifications** strengthen the CV, but they are not the primary proof: measured projects and professional experience are. [certifications]"
        )
    return _precision.StructuredFactAnswer(answer, source="experience-education")


def _false_bigtech_claims(resolver, normalized: str, language: str):
    entities = any(x in normalized for x in ("gpt-5", "gpt 5", "openai", "gemini"))
    relation = any(x in normalized for x in ("build", "built", "work at", "worked at", "contribute", "contributed", "developed"))
    if not (_referent(normalized) and entities and relation):
        return None
    if language == "fr":
        answer = (
            "Le portfolio public **ne fournit aucune preuve** que Youssef ait construit GPT-5, travaillé chez OpenAI ou contribué à Gemini. Ses expériences professionnelles documentées sont son activité freelance indépendante et son stage/PFE chez NEXTRONIC — ABA Technology. [experience-education]\n\n"
            "Ses projets IA publics incluent notamment OpenLegaMa et le système de détection d’accidents, mais ils ne doivent pas être confondus avec une contribution aux modèles propriétaires d’OpenAI ou de Google. [project-openlegama-moroccan-legal-ai] [project-real-time-road-accident-detection]"
        )
    else:
        answer = (
            "The public portfolio provides **no evidence** that Youssef built GPT-5, worked at OpenAI, or contributed to Gemini. His documented professional experience is independent freelance AI/ML work and his internship/PFE at NEXTRONIC — ABA Technology. [experience-education]\n\n"
            "His public AI projects include OpenLegaMa and the road-accident system, but those should not be confused with contributions to proprietary OpenAI or Google models. [project-openlegama-moroccan-legal-ai] [project-real-time-road-accident-detection]"
        )
    return _precision.StructuredFactAnswer(answer, source="experience-education")


def _resolve_recruiter_reasoning(resolver, question: str):
    normalized = _precision._normalize(question)
    language = _language(resolver, question)

    # Unique technical fingerprints first.
    if _openlegama_fingerprint(normalized):
        return _answer_openlegama(resolver, language)
    if _accident_fingerprint(normalized):
        return _answer_accident(resolver, language)

    # Evidence-comparison families. Order matters from most specific to broadest.
    for handler in (
        _false_bigtech_claims,
        _executive_summary,
        _domain_fit_comparison,
        _professional_vs_project_tech,
        _strengths_and_gaps,
        _agentic_evidence_calibration,
        _structured_data_evidence,
        _evaluation_capability,
        _production_oriented_evidence,
        _integrated_systems,
        _junior_readiness,
        _beyond_training,
        _complete_architecture,
        _certs_vs_practice,
    ):
        result = handler(resolver, question, normalized, language) if handler is _executive_summary else handler(resolver, normalized, language)
        if result is not None:
            return result
    return None


def apply() -> None:
    cls = _structured.StructuredFactResolver
    if getattr(cls, "_project_fingerprint_patch", False):
        return

    original_resolve = cls.resolve

    def resolve(self, question, history=None):
        planned = _resolve_recruiter_reasoning(self, question)
        if planned is not None:
            return planned
        return original_resolve(self, question, history)

    cls.resolve = resolve
    cls._project_fingerprint_patch = True


apply()
