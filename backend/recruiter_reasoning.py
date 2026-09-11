"""Evidence-comparison planner for recruiter/client portfolio questions.

This module answers semantic families that require comparing multiple pieces of
structured public evidence. It deliberately follows the hierarchy:
professional experience -> measured projects -> technical projects -> skills ->
certifications/training.

It does not replace normal RAG for arbitrary questions. It only returns a
StructuredFactAnswer when the query clearly asks for an evidence comparison,
calibrated assessment, or executive synthesis.
"""
from __future__ import annotations

import re

import precision_facts as _precision
from router import detect_language


def _project(resolver, slug: str):
    target = _precision._normalize(slug)
    return next(
        (
            row
            for row in resolver.projects
            if _precision._normalize(str(row.get("slug") or "")) == target
        ),
        {},
    )


def _lang(question: str) -> str:
    # Reuse the product router's tested multilingual classifier rather than the
    # legacy fact resolver's broader French heuristics.
    return detect_language(question)


def _referent(normalized: str) -> bool:
    # Word-boundary regex handles Youssef's, qu'il, son/ses, and ordinary
    # pronouns without relying on spaces around punctuation/apostrophes.
    return bool(
        re.search(
            r"\b(?:youssef|his|he|him|son|ses|il|lui|يوسف)\b",
            normalized,
            re.I,
        )
    )


def _answer(answer: str, source: str, evidence: str = ""):
    return _precision.StructuredFactAnswer(answer, source=source, evidence=evidence or None)


def _executive_summary(resolver, question: str, n: str, lang: str):
    summary = bool(re.search(r"\b(?:summari[sz]e|summary|resume|résumé|resumer|résumer)\b", n, re.I))
    audience = any(x in n for x in ("cto", "30 second", "30-second", "executive", "recruiter pitch"))
    if not (_referent(n) and summary and audience):
        return None
    accident = _project(resolver, "real-time-road-accident-detection")
    legal = _project(resolver, "openlegama-moroccan-legal-ai")
    ar, lr = accident.get("results") or {}, legal.get("results") or {}
    if lang == "fr":
        text = (
            "**Résumé CTO en 30 secondes :** Youssef Bouzit est Ingénieur d’État en Data Science orienté AI Engineering. "
            "Il possède une expérience professionnelle en Computer Vision chez NEXTRONIC — ABA Technology et développe en parallèle des solutions IA/ML en indépendant. "
            f"Ses preuves mesurées incluent un système temps réel YOLOv11/BoT-SORT ({ar.get('precision','86.68%')} précision, {ar.get('recall','91.56%')} rappel, ~{ar.get('inferenceSpeed','31.5 FPS')}) "
            f"et OpenLegaMa, un Controlled RAG évalué avec {lr.get('automatedTests','143 / 143 passing')}, {lr.get('curatedBenchmark','610 cases')} + {lr.get('holdoutBenchmark','120 cases')} et {lr.get('indexedArticles','7,708')} articles. "
            "Son profil couvre aussi MLOps et backend AI ; il recherche actuellement un CDI AI/ML. "
            "[experience-education] [project-real-time-road-accident-detection] [project-openlegama-moroccan-legal-ai] [career-status]"
        )
    else:
        text = (
            "**30-second CTO summary:** Youssef Bouzit is a State Engineer in Data Science focused on AI Engineering. "
            "He has professional Computer Vision experience at NEXTRONIC — ABA Technology and parallel independent AI/ML work. "
            f"His measured evidence includes a real-time YOLOv11/BoT-SORT system ({ar.get('precision','86.68%')} precision, {ar.get('recall','91.56%')} recall, ~{ar.get('inferenceSpeed','31.5 FPS')}) "
            f"and OpenLegaMa, an evaluated controlled-RAG system with {lr.get('automatedTests','143 / 143 passing')}, {lr.get('curatedBenchmark','610 cases')} + {lr.get('holdoutBenchmark','120 cases')}, and {lr.get('indexedArticles','7,708')} indexed articles. "
            "He also shows MLOps and AI-backend breadth and is currently seeking a full-time AI/ML role. "
            "[experience-education] [project-real-time-road-accident-detection] [project-openlegama-moroccan-legal-ai] [career-status]"
        )
    return _answer(text, "experience-education", "Executive synthesis from synchronized work, projects, and career status.")


def _production_evidence(resolver, n: str, lang: str):
    if not _referent(n) or not any(
        x in n
        for x in (
            "production-oriented", "production oriented", "academic notebooks",
            "only academic", "isolated notebooks", "production system",
            "production systems", "notebook", "notebooks",
        )
    ):
        return None
    legal = _project(resolver, "openlegama-moroccan-legal-ai")
    accident = _project(resolver, "real-time-road-accident-detection")
    lr, ar = legal.get("results") or {}, accident.get("results") or {}
    if lang == "fr":
        text = (
            "Oui. Le portfolio montre des **systèmes complets orientés produit**, pas seulement des notebooks :\n\n"
            f"1. **OpenLegaMa** — MVP public stable, Controlled RAG multilingue, validation des citations, abstention, {lr.get('automatedTests','143 / 143 passing')} et benchmarks dédiés. [project-openlegama-moroccan-legal-ai]\n"
            f"2. **Road Accident Detection** — système professionnel/PFE avec détection, tracking, logique de décision, alertes, clips MP4 et logs CSV ; ~{ar.get('inferenceSpeed','31.5 FPS')}. [project-real-time-road-accident-detection] [experience-education]\n"
            "3. **Customer MLOps Pipeline** — Airflow, MLflow, MinIO, PostgreSQL, Docker Compose, monitoring et CI/CD. [project-customer-churn-mlops-platform]\n\n"
            "Cela prouve une orientation **système et ingénierie**. Ce n’est toutefois pas une preuve de plusieurs années d’exploitation enterprise à grande échelle."
        )
    else:
        text = (
            "Yes. The portfolio shows **complete, product-oriented systems**, not only notebooks:\n\n"
            f"1. **OpenLegaMa** — a stable public MVP with multilingual controlled RAG, citation validation, abstention, {lr.get('automatedTests','143 / 143 passing')}, and dedicated benchmarks. [project-openlegama-moroccan-legal-ai]\n"
            f"2. **Road Accident Detection** — professional/PFE system with detection, tracking, decision logic, alerts, MP4 evidence clips, and CSV logs; ~{ar.get('inferenceSpeed','31.5 FPS')}. [project-real-time-road-accident-detection] [experience-education]\n"
            "3. **Customer MLOps Pipeline** — Airflow, MLflow, MinIO, PostgreSQL, Docker Compose, monitoring, and CI/CD. [project-customer-churn-mlops-platform]\n\n"
            "That is strong evidence of **system-level engineering**. It should not be overstated as proof of years of large-scale enterprise production ownership."
        )
    return _answer(text, "project-openlegama-moroccan-legal-ai")


def _integrated_systems(resolver, n: str, lang: str):
    if not _referent(n):
        return None
    combine = any(x in n for x in ("combining multiple", "combine multiple", "multiple ai components", "several ai components", "plusieurs composants", "plusieurs briques"))
    system = any(x in n for x in ("one system", "integrated", "cohesive", "un systeme", "un système"))
    if not (combine and system):
        return None
    if lang == "fr":
        text = (
            "Oui. Deux exemples publics sont particulièrement clairs :\n\n"
            "1. **Road Accident Detection** combine détection de véhicules, YOLOv11s fine-tuné, tracking BoT-SORT, analyse comportementale αβγ, fusion de décision, alertes, clips MP4 et logs CSV. [project-real-time-road-accident-detection] [experience-education]\n"
            "2. **OpenLegaMa** combine ingestion documentaire, retrieval, Controlled RAG multilingue, validation de références, citations, abstention et évaluation systématique. [project-openlegama-moroccan-legal-ai]\n\n"
            "Cela montre une capacité d’intégration de composants IA et logiciels, pas seulement l’entraînement d’un modèle isolé."
        )
    else:
        text = (
            "Yes. Two public examples are especially clear:\n\n"
            "1. **Road Accident Detection** combines vehicle detection, a fine-tuned YOLOv11s model, BoT-SORT tracking, αβγ behavioral analysis, decision fusion, alerts, MP4 evidence clips, and CSV event logs. [project-real-time-road-accident-detection] [experience-education]\n"
            "2. **OpenLegaMa** combines document ingestion, retrieval, multilingual controlled RAG, reference validation, citations, abstention, and systematic evaluation. [project-openlegama-moroccan-legal-ai]\n\n"
            "That is evidence of integrating AI and software components rather than training an isolated model only."
        )
    return _answer(text, "project-real-time-road-accident-detection")


def _evaluation(resolver, n: str, lang: str):
    if not _referent(n):
        return None
    evaluation_signal = bool(re.search(r"\b(?:evaluate|evaluation|evaluer|évaluer)\b.*\b(?:ai|system|système)", n, re.I))
    prototype_contrast = any(x in n for x in ("only build prototypes", "only prototypes", "just prototypes", "seulement des prototypes", "que des prototypes"))
    if not (evaluation_signal or prototype_contrast):
        return None
    legal = _project(resolver, "openlegama-moroccan-legal-ai")
    accident = _project(resolver, "real-time-road-accident-detection")
    lr, ar = legal.get("results") or {}, accident.get("results") or {}
    if lang == "fr":
        text = (
            "Oui — le portfolio montre qu’il **évalue ses systèmes**, pas seulement qu’il construit des prototypes.\n\n"
            f"• **OpenLegaMa** : {lr.get('automatedTests','143 / 143 passing')}, benchmark curaté de {lr.get('curatedBenchmark','610 cases')}, holdout de {lr.get('holdoutBenchmark','120 cases')}, Recall@5={lr.get('documentRecallAt5','100% curated')} et exact-article recall={lr.get('exactArticleRecall','100% measured')}. [project-openlegama-moroccan-legal-ai]\n"
            f"• **Road Accident Detection** : benchmark image held-out avec {ar.get('precision','86.68%')} précision, {ar.get('recall','91.56%')} rappel, {ar.get('f1Score','89.06%')} F1 et {ar.get('inferenceSpeed','31.5 FPS')}. [project-real-time-road-accident-detection]\n\n"
            "Nuance : le pipeline vidéo accident complet n’a pas encore de précision/rappel end-to-end officiel faute d’annotations temporelles complètes."
        )
    else:
        text = (
            "Yes — the portfolio shows that he **evaluates AI systems**, not only that he builds prototypes.\n\n"
            f"• **OpenLegaMa**: {lr.get('automatedTests','143 / 143 passing')}, a {lr.get('curatedBenchmark','610 cases')} curated benchmark, a {lr.get('holdoutBenchmark','120 cases')} holdout, Recall@5={lr.get('documentRecallAt5','100% curated')}, and exact-article recall={lr.get('exactArticleRecall','100% measured')}. [project-openlegama-moroccan-legal-ai]\n"
            f"• **Road Accident Detection**: a held-out image benchmark with {ar.get('precision','86.68%')} precision, {ar.get('recall','91.56%')} recall, {ar.get('f1Score','89.06%')} F1, and {ar.get('inferenceSpeed','31.5 FPS')}. [project-real-time-road-accident-detection]\n\n"
            "Important caveat: the complete accident-video pipeline does not yet have official end-to-end precision/recall without complete temporal annotations."
        )
    return _answer(text, "project-openlegama-moroccan-legal-ai")


def _domain_fit(resolver, n: str, lang: str):
    if not _referent(n):
        return None
    domains = (
        any(x in n for x in ("computer vision", "vision par ordinateur")),
        any(x in n for x in ("generative ai", "genai", "rag", "llm")),
        "mlops" in n,
    )
    fit = any(x in n for x in ("better fit", "best fit", "fit for", "would he be", "meilleur profil", "mieux adapte", "mieux adapté"))
    if sum(domains) < 2 or not fit:
        return None
    if lang == "fr":
        text = (
            "Sur la base des **preuves publiques actuelles**, je classerais l’adéquation ainsi :\n\n"
            "1. **Computer Vision — preuve la plus forte professionnellement** : stage/PFE chez NEXTRONIC — ABA Technology, YOLOv11 + BoT-SORT + OpenCV, avec métriques mesurées et temps réel. [experience-education] [project-real-time-road-accident-detection]\n"
            "2. **Generative AI / RAG — preuve publique très forte** : OpenLegaMa est un Controlled RAG évalué avec citations, abstention, benchmarks et MVP public ; son activité freelance mentionne aussi RAG/LLM et agents IA. [project-openlegama-moroccan-legal-ai] [experience-education]\n"
            "3. **MLOps — bonne preuve projet, mais moins de preuve professionnelle publique** : Customer MLOps Pipeline couvre Airflow, MLflow, MinIO, PostgreSQL, Docker Compose et CI/CD. [project-customer-churn-mlops-platform]\n\n"
            "Donc **Computer Vision est le domaine le plus prouvé professionnellement**, tandis que **RAG/Generative AI est presque aussi fort côté projet public évalué**. MLOps est une force complémentaire crédible."
        )
    else:
        text = (
            "Based on the **current public evidence**, I would rank the fit like this:\n\n"
            "1. **Computer Vision — strongest professional evidence**: internship/PFE work at NEXTRONIC — ABA Technology using YOLOv11 + BoT-SORT + OpenCV, with measured metrics and real-time performance. [experience-education] [project-real-time-road-accident-detection]\n"
            "2. **Generative AI / RAG — very strong public project evidence**: OpenLegaMa is an evaluated controlled-RAG system with citations, abstention, benchmarks, and a public MVP; his freelance profile also documents RAG/LLM and AI-agent work. [project-openlegama-moroccan-legal-ai] [experience-education]\n"
            "3. **MLOps — solid project evidence, but less public professional evidence**: Customer MLOps Pipeline covers Airflow, MLflow, MinIO, PostgreSQL, Docker Compose, and CI/CD. [project-customer-churn-mlops-platform]\n\n"
            "So **Computer Vision is the most professionally proven area**, while **RAG/Generative AI is nearly as strong on evaluated public-project evidence**. MLOps is a credible complementary strength."
        )
    return _answer(text, "experience-education")


def _structured_data(resolver, n: str, lang: str):
    if not _referent(n) or not any(x in n for x in ("structured data", "tabular data", "tabular", "donnees structurees", "données structurées")):
        return None
    fraud = _project(resolver, "ai-powered-bank-fraud-detection-machine-learning-explainable-ai")
    results = fraud.get("results") or {}
    if lang == "fr":
        text = (
            "La preuve la plus directe est **AI-Powered Bank Fraud Detection** : dataset tabulaire de cartes bancaires avec "
            f"**{results.get('transactions','284,807')} transactions** et {results.get('fraudCases','492')} cas de fraude, traité avec Pandas/NumPy, Scikit-learn, Random Forest, probabilités de risque et importance des features. [project-ai-powered-bank-fraud-detection-machine-learning-explainable-ai]\n\n"
            "Il a aussi **Customer MLOps Pipeline** avec PostgreSQL [project-customer-churn-mlops-platform] et **Data Quality Monitoring** avec MySQL/REST API [project-2-data-quality-monitoring-2025-12]."
        )
    else:
        text = (
            "The most direct evidence is **AI-Powered Bank Fraud Detection**: a tabular credit-card dataset with "
            f"**{results.get('transactions','284,807')} transactions** and {results.get('fraudCases','492')} fraud cases, using Pandas/NumPy, Scikit-learn, Random Forest, risk probabilities, and feature importance. [project-ai-powered-bank-fraud-detection-machine-learning-explainable-ai]\n\n"
            "He also has **Customer MLOps Pipeline** with PostgreSQL [project-customer-churn-mlops-platform] and **Data Quality Monitoring** with MySQL/REST APIs [project-2-data-quality-monitoring-2025-12]."
        )
    return _answer(text, "project-ai-powered-bank-fraud-detection-machine-learning-explainable-ai")


def _agentic_calibration(resolver, n: str, lang: str):
    if not _referent(n):
        return None
    agentic = "langgraph" in n or "ai agent" in n or "agents" in n
    contrast = any(x in n for x in ("actually experienced", "mainly based", "just skills", "skills and certifications", "vraiment", "principalement", "surtout base", "surtout basé"))
    if not (agentic and contrast):
        return None
    if lang == "fr":
        text = (
            "La preuve est **plus limitée que pour Computer Vision ou RAG**. Le portfolio documente des compétences Agentic AI (agent workflows, tool calling, human-in-the-loop, state management, MCP, guardrails), une activité freelance mentionnant des agents IA et des certifications/formations associées. [skills] [experience-education] [certifications]\n\n"
            "En revanche, le portfolio public synchronisé **ne présente pas encore un projet autonome LangGraph/Agentic AI avec métriques publiques comparables à OpenLegaMa ou au PFE Computer Vision**. Le niveau de preuve est donc une **capacité/hands-on exposure documentée**, pas le même niveau de validation publique qu’en CV ou RAG."
        )
    else:
        text = (
            "The evidence is **more limited than for Computer Vision or RAG**. The portfolio documents Agentic AI skills (agent workflows, tool calling, human-in-the-loop, state management, MCP, guardrails), current freelance work mentioning AI agents, and relevant certifications/training. [skills] [experience-education] [certifications]\n\n"
            "However, the synchronized public portfolio **does not yet show a standalone LangGraph/Agentic AI project with public measured results comparable to OpenLegaMa or the Computer Vision PFE**. The calibrated claim is **documented hands-on capability/exposure**, not the same level of public proof as CV or RAG."
        )
    return _answer(text, "skills")


def _professional_vs_projects(resolver, n: str, lang: str):
    if not _referent(n):
        return None
    professional = bool(re.search(r"\bprofession(?:al|ally|nel|nelle|nellement)?\b", n, re.I))
    project_side = any(x in n for x in ("personal project", "personal projects", "only in", "versus", " vs ", "projets personnels", "projet personnel"))
    technology = any(x in n for x in ("technologies", "technology", "tech stack", "outils"))
    if not (professional and project_side and technology):
        return None
    if lang == "fr":
        text = (
            "Le portfolio permet une séparation **partielle mais solide** :\n\n"
            "**Utilisation professionnelle explicitement documentée**\n"
            "• NEXTRONIC — ABA Technology : **Python, YOLO, OpenCV, BoT-SORT, Deep Learning**. [experience-education] [project-real-time-road-accident-detection]\n"
            "• Freelance indépendant : **RAG, LLMs, AI Agents, Python, Machine Learning** sont explicitement listés dans l’expérience actuelle. [experience-education]\n\n"
            "**Preuves surtout via projets publics/personnels**\n"
            "• OpenLegaMa : Next.js, TypeScript, Controlled RAG, Groq SDK, Python, Vercel. [project-openlegama-moroccan-legal-ai]\n"
            "• Customer MLOps Pipeline : Airflow, MLflow, MinIO, PostgreSQL, Docker Compose, Streamlit. [project-customer-churn-mlops-platform]\n"
            "• Bank Fraud : Scikit-learn, Pandas, Random Forest, Streamlit. [project-ai-powered-bank-fraud-detection-machine-learning-explainable-ai]\n\n"
            "Le portfolio ne permet pas d’affirmer que **chaque** technologie de projet personnel a aussi été utilisée dans une mission commerciale."
        )
    else:
        text = (
            "The portfolio supports a **partial but useful separation**:\n\n"
            "**Explicitly documented professional use**\n"
            "• NEXTRONIC — ABA Technology: **Python, YOLO, OpenCV, BoT-SORT, Deep Learning**. [experience-education] [project-real-time-road-accident-detection]\n"
            "• Independent freelance activity: **RAG, LLMs, AI Agents, Python, Machine Learning** are explicitly listed in the current experience entry. [experience-education]\n\n"
            "**Evidence mainly from public/personal projects**\n"
            "• OpenLegaMa: Next.js, TypeScript, Controlled RAG, Groq SDK, Python, Vercel. [project-openlegama-moroccan-legal-ai]\n"
            "• Customer MLOps Pipeline: Airflow, MLflow, MinIO, PostgreSQL, Docker Compose, Streamlit. [project-customer-churn-mlops-platform]\n"
            "• Bank Fraud: Scikit-learn, Pandas, Random Forest, Streamlit. [project-ai-powered-bank-fraud-detection-machine-learning-explainable-ai]\n\n"
            "The public portfolio does not justify claiming that **every** personal-project technology was also used in commercial work."
        )
    return _answer(text, "experience-education")


def _strengths_gaps(resolver, n: str, lang: str):
    if not _referent(n):
        return None
    strengths = bool(re.search(r"\b(?:top\s*(?:3|three)|strongest|key)\b.*\bstrengths?\b", n, re.I)) or bool(re.search(r"\bstrengths?\b.*\b(?:top\s*(?:3|three)|strongest|key)\b", n, re.I))
    gaps = any(x in n for x in ("less evidence", "less proven", "less proved", "less publicly", "areas where", "moins de preuves", "moins prouve", "moins prouvé"))
    if not (strengths and gaps):
        return None
    if lang == "fr":
        text = (
            "**Top 3 forces appuyées par les preuves publiques :**\n"
            "1. **Computer Vision temps réel** — expérience professionnelle NEXTRONIC + métriques YOLOv11/BoT-SORT. [experience-education] [project-real-time-road-accident-detection]\n"
            "2. **RAG/LLM fiable et évalué** — OpenLegaMa : Controlled RAG, citations, abstention, benchmarks et 143/143 tests. [project-openlegama-moroccan-legal-ai]\n"
            "3. **Ingénierie end-to-end / MLOps** — orchestration, tracking, stockage d’artefacts, bases de données, monitoring et CI/CD. [project-customer-churn-mlops-platform]\n\n"
            "**2 domaines moins prouvés publiquement aujourd’hui :**\n"
            "1. **Agentic AI / LangGraph au niveau d’un projet public mesuré** — compétences, freelance et formations sont documentés, mais pas encore un flagship agentic autonome avec métriques publiques. [skills] [experience-education] [certifications]\n"
            "2. **Ownership enterprise long terme à grande échelle** — moins de preuve publique d’années d’exploitation d’un système enterprise sous forte charge.\n\n"
            "Ce sont des **écarts de preuve publique**, pas des affirmations d’absence de compétence."
        )
    else:
        text = (
            "**Top 3 strengths supported by public evidence:**\n"
            "1. **Real-time Computer Vision** — professional NEXTRONIC experience plus measured YOLOv11/BoT-SORT results. [experience-education] [project-real-time-road-accident-detection]\n"
            "2. **Evaluated, grounded RAG/LLM systems** — OpenLegaMa: controlled RAG, citations, abstention, benchmarks, and 143/143 tests. [project-openlegama-moroccan-legal-ai]\n"
            "3. **End-to-end AI engineering / MLOps** — orchestration, experiment tracking, artifact storage, databases, monitoring, and CI/CD. [project-customer-churn-mlops-platform]\n\n"
            "**Two areas with less public evidence today:**\n"
            "1. **Agentic AI / LangGraph at the level of a measured public flagship** — skills, freelance activity, and training are documented, but not yet a standalone agentic project with public metrics. [skills] [experience-education] [certifications]\n"
            "2. **Long-term large-scale enterprise ownership** — less public evidence of years operating an enterprise system under sustained high load.\n\n"
            "These are **public-evidence gaps**, not claims that he lacks those capabilities."
        )
    return _answer(text, "experience-education")


def _junior_readiness(resolver, n: str, lang: str):
    if not _referent(n) or "junior" not in n or not any(x in n for x in ("ready", "pret", "prêt", "academic", "academique", "académique")):
        return None
    accident = _project(resolver, "real-time-road-accident-detection")
    ar = accident.get("results") or {}
    if lang == "fr":
        text = (
            "Oui. Le portfolio public rend Youssef **crédible pour un poste AI Engineer junior** ; son profil n’est plus seulement académique :\n\n"
            "• **Expérience professionnelle** chez NEXTRONIC — ABA Technology. [experience-education]\n"
            f"• **Système temps réel mesuré** : YOLOv11 + BoT-SORT + OpenCV, {ar.get('precision','86.68%')} précision, {ar.get('recall','91.56%')} rappel et ~{ar.get('inferenceSpeed','31.5 FPS')}. [project-real-time-road-accident-detection]\n"
            "• **RAG évalué** : OpenLegaMa avec citations, abstention, benchmarks et tests. [project-openlegama-moroccan-legal-ai]\n"
            "• **Cycle ML/MLOps** : Airflow, MLflow, MinIO, PostgreSQL, Docker Compose et CI/CD. [project-customer-churn-mlops-platform]\n\n"
            "Les certifications renforcent le profil, mais les **projets et l’expérience professionnelle sont la preuve principale**. Cela soutient un positionnement junior/early-career, pas une prétention senior."
        )
    else:
        text = (
            "Yes. The public portfolio makes Youssef **credible for a junior AI Engineer role**; the profile is no longer only academic:\n\n"
            "• **Professional experience** at NEXTRONIC — ABA Technology. [experience-education]\n"
            f"• **Measured real-time system**: YOLOv11 + BoT-SORT + OpenCV with {ar.get('precision','86.68%')} precision, {ar.get('recall','91.56%')} recall, and ~{ar.get('inferenceSpeed','31.5 FPS')}. [project-real-time-road-accident-detection]\n"
            "• **Evaluated RAG system**: OpenLegaMa with citations, abstention, benchmarks, and tests. [project-openlegama-moroccan-legal-ai]\n"
            "• **ML/MLOps lifecycle**: Airflow, MLflow, MinIO, PostgreSQL, Docker Compose, and CI/CD. [project-customer-churn-mlops-platform]\n\n"
            "Certifications strengthen the profile, but **projects and professional experience are the primary evidence**. That supports junior/early-career positioning, not a senior-level claim."
        )
    return _answer(text, "experience-education")


def _beyond_training(resolver, n: str, lang: str):
    if not _referent(n):
        return None
    signal = bool(re.search(r"(?:other than|beyond|autre chose que|autre chose qu['’]?)\s+.*(?:train|training|entrainer|entraîner)", n, re.I)) or any(x in n for x in ("only train models", "que entrainer un modele", "que entraîner un modèle"))
    if not signal:
        return None
    if lang == "fr":
        text = (
            "Oui. Les preuves les plus fortes vont **au-delà de l’entraînement d’un modèle** :\n\n"
            "1. **Computer Vision complet** : BoT-SORT, analyse comportementale, fusion de décision, alertes, clips MP4 et logs CSV autour de YOLO. [project-real-time-road-accident-detection] [experience-education]\n"
            "2. **OpenLegaMa** : ingestion documentaire, retrieval, Controlled RAG, validation de références, citations, abstention et benchmark/holdout. [project-openlegama-moroccan-legal-ai]\n"
            "3. **Customer MLOps Pipeline** : Airflow, MLflow, MinIO, PostgreSQL, monitoring, Docker Compose et CI/CD. [project-customer-churn-mlops-platform]\n\n"
            "La preuve pratique porte donc sur **l’intégration, l’évaluation et l’ingénierie du pipeline**, pas seulement sur le training."
        )
    else:
        text = (
            "Yes. The strongest evidence goes **well beyond model training**:\n\n"
            "1. **Complete Computer Vision system**: BoT-SORT, behavioral analysis, decision fusion, alerts, MP4 evidence capture, and CSV logging around YOLO. [project-real-time-road-accident-detection] [experience-education]\n"
            "2. **OpenLegaMa**: document ingestion, retrieval, controlled RAG, reference validation, citations, abstention, and benchmark/holdout evaluation. [project-openlegama-moroccan-legal-ai]\n"
            "3. **Customer MLOps Pipeline**: Airflow, MLflow, MinIO, PostgreSQL, monitoring, Docker Compose, and CI/CD. [project-customer-churn-mlops-platform]\n\n"
            "The practical evidence is therefore about **integration, evaluation, and pipeline engineering**, not only training."
        )
    return _answer(text, "project-real-time-road-accident-detection")


def _complete_architecture(resolver, n: str, lang: str):
    if not _referent(n):
        return None
    architecture = any(x in n for x in ("complete architecture", "full architecture", "architecture complete", "architecture complète", "architecture de bout en bout"))
    project = any(x in n for x in ("project", "projet", "مشروع"))
    if not (architecture and project):
        return None
    legal = _project(resolver, "openlegama-moroccan-legal-ai")
    lr = legal.get("results") or {}
    if lang == "fr":
        text = (
            "Pour une **architecture d’application IA complète**, le meilleur exemple est **OpenLegaMa** : ingestion/corpus, retrieval, Controlled RAG multilingue, validation des références, citations, abstention, interface web, tests et évaluation. "
            f"Le projet documente {lr.get('automatedTests','143 / 143 passing')}, {lr.get('curatedBenchmark','610 cases')} + {lr.get('holdoutBenchmark','120 cases')} et un MVP public stable. [project-openlegama-moroccan-legal-ai]\n\n"
            "Pour l’architecture **MLOps du cycle ML**, **Customer MLOps Pipeline** est le meilleur second exemple avec Airflow, MLflow, MinIO, PostgreSQL, Docker Compose, monitoring et CI/CD. [project-customer-churn-mlops-platform]"
        )
    else:
        text = (
            "For a **complete AI-application architecture**, the strongest example is **OpenLegaMa**: corpus ingestion, retrieval, multilingual controlled RAG, reference validation, citations, abstention, web application, testing, and evaluation. "
            f"It documents {lr.get('automatedTests','143 / 143 passing')}, {lr.get('curatedBenchmark','610 cases')} + {lr.get('holdoutBenchmark','120 cases')}, and a stable public MVP. [project-openlegama-moroccan-legal-ai]\n\n"
            "For **ML lifecycle/MLOps architecture**, **Customer MLOps Pipeline** is the strongest second example with Airflow, MLflow, MinIO, PostgreSQL, Docker Compose, monitoring, and CI/CD. [project-customer-churn-mlops-platform]"
        )
    return _answer(text, "project-openlegama-moroccan-legal-ai")


def _certs_vs_practice(resolver, n: str, lang: str):
    if not _referent(n):
        return None
    certs = any(x in n for x in ("certificat", "certification", "certificate", "credentials", "شهاد"))
    practical = any(x in n for x in ("practical proof", "practical evidence", "proof behind", "real proof", "preuves pratiques", "preuve pratique", "derriere", "derrière", "vraiment des preuves", "hands-on"))
    if not (certs and practical):
        return None
    if lang == "fr":
        text = (
            "Oui. Les certifications sont **secondaires** par rapport aux preuves pratiques publiques :\n\n"
            "1. **NEXTRONIC — ABA Technology** : système Computer Vision temps réel développé dans un contexte professionnel/PFE. [experience-education] [project-real-time-road-accident-detection]\n"
            "2. **OpenLegaMa** : RAG public évalué avec citations, abstention, benchmarks et 143/143 tests. [project-openlegama-moroccan-legal-ai]\n"
            "3. **Customer MLOps Pipeline** : orchestration, experiment tracking, artefacts, PostgreSQL, Docker et CI/CD. [project-customer-churn-mlops-platform]\n"
            "4. **Bank Fraud Detection** : ML tabulaire sur 284,807 transactions avec dashboard et explicabilité. [project-ai-powered-bank-fraud-detection-machine-learning-explainable-ai]\n\n"
            "Les **56 certifications** renforcent le CV, mais les projets mesurés et l’expérience professionnelle sont la preuve principale. [certifications]"
        )
    else:
        text = (
            "Yes. Certifications are **secondary** to the practical public evidence:\n\n"
            "1. **NEXTRONIC — ABA Technology**: a real-time Computer Vision system developed in a professional/PFE context. [experience-education] [project-real-time-road-accident-detection]\n"
            "2. **OpenLegaMa**: a public evaluated RAG system with citations, abstention, benchmarks, and 143/143 tests. [project-openlegama-moroccan-legal-ai]\n"
            "3. **Customer MLOps Pipeline**: orchestration, experiment tracking, artifacts, PostgreSQL, Docker, and CI/CD. [project-customer-churn-mlops-platform]\n"
            "4. **Bank Fraud Detection**: tabular ML on 284,807 transactions with a dashboard and explainability. [project-ai-powered-bank-fraud-detection-machine-learning-explainable-ai]\n\n"
            "The **56 certifications** strengthen the CV, but measured projects and professional experience are the primary proof. [certifications]"
        )
    return _answer(text, "experience-education")


def _false_bigtech(resolver, n: str, lang: str):
    entities = any(x in n for x in ("gpt-5", "gpt 5", "openai", "gemini"))
    relation = any(x in n for x in ("build", "built", "work at", "worked at", "contribute", "contributed", "developed"))
    if not (_referent(n) and entities and relation):
        return None
    if lang == "fr":
        text = (
            "Le portfolio public **ne fournit aucune preuve** que Youssef ait construit GPT-5, travaillé chez OpenAI ou contribué à Gemini. Ses expériences professionnelles documentées sont son activité freelance indépendante et son stage/PFE chez NEXTRONIC — ABA Technology. [experience-education]\n\n"
            "Ses projets IA publics incluent notamment OpenLegaMa et le système de détection d’accidents ; ils ne doivent pas être confondus avec une contribution aux modèles propriétaires d’OpenAI ou de Google. [project-openlegama-moroccan-legal-ai] [project-real-time-road-accident-detection]"
        )
    else:
        text = (
            "The public portfolio provides **no evidence** that Youssef built GPT-5, worked at OpenAI, or contributed to Gemini. His documented professional experience is independent freelance AI/ML work and his internship/PFE at NEXTRONIC — ABA Technology. [experience-education]\n\n"
            "His public AI projects include OpenLegaMa and the road-accident system; those should not be confused with contributions to proprietary OpenAI or Google models. [project-openlegama-moroccan-legal-ai] [project-real-time-road-accident-detection]"
        )
    return _answer(text, "experience-education")


def resolve_recruiter_reasoning(resolver, question: str):
    n = _precision._normalize(question)
    lang = _lang(question)
    for handler in (
        _false_bigtech,
        _domain_fit,
        _professional_vs_projects,
        _strengths_gaps,
        _agentic_calibration,
        _structured_data,
        _evaluation,
        _production_evidence,
        _integrated_systems,
        _junior_readiness,
        _beyond_training,
        _complete_architecture,
        _certs_vs_practice,
    ):
        result = handler(resolver, n, lang)
        if result is not None:
            return result
    return _executive_summary(resolver, question, n, lang)


__all__ = ["resolve_recruiter_reasoning"]
