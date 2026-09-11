"""Small Vercel-only production quality patches.

The core project stays host-agnostic. Vercel, however, prepares a FastEmbed model
inside the deployment bundle at build time. The runtime embedder must reuse that
exact cache path or a cold function may download/load the model from its default
cache again.

This module also applies narrow production-hardening fixes that are safer to keep
deterministic than to delegate to a generative model: grammatical cleanup after
an invalid citation is removed, multilingual employer verification, concise
professional profile summaries, recruiter-oriented skill/certification ranking,
and unsupported private-profile questions.
"""
from __future__ import annotations

import os
import re
from dataclasses import replace

import grounding as _grounding
import precision_facts as _precision
import rag as _rag


_DANGLING_AFTER_CITATION = (
    re.compile(
        r"\s+(?:or\s+)?any\s+(?:project|source|claim|evidence|item)\s+"
        r"(?:associated|linked|related)\s+(?:with|to)\s*([.!?])",
        re.I,
    ),
    re.compile(
        r"\s+(?:ou\s+)?(?:tout|toute)\s+(?:projet|source|affirmation|preuve|element)\s+"
        r"(?:associe|associee|lie|liee|relie|reliee)\s+(?:a|avec)\s*([.!?])",
        re.I,
    ),
)

# Removing an unknown source token can leave fragments such as
# "nor is there any record of a in his projects", "record of.", or
# "reference to ``.". Rewrite/remove only those narrow malformed constructions;
# do not paraphrase otherwise valid generated prose.
_BROKEN_RECORD_FRAGMENT = re.compile(
    r"\bnor\s+is\s+there\s+any\s+record\s+of\s+(?:a|an|the)?\s*"
    r"(?P<prep>in|among|within)\b",
    re.I,
)
_DANGLING_RECORD_CLAUSE = re.compile(
    r",?\s*(?:nor\s+)?(?:is\s+there\s+)?(?:any\s+)?record\s+of\s*([.!?])",
    re.I,
)
_DANGLING_REFERENCE_CLAUSE = re.compile(
    r",?\s*(?:nor\s+)?(?:is\s+there\s+)?(?:any\s+)?reference\s+to\s*"
    r"(?:``|`\s*`|''|\"\")?\s*([.!?])",
    re.I,
)
_DANGLING_ASSOCIATION = re.compile(
    r",?\s*(?:or\s+)?(?:is\s+)?associated\s+(?:with|to)\s*([.!?])",
    re.I,
)

# Recruiters and visitors phrase employer checks in several languages and may
# also embed a false declarative claim inside a prompt injection. Keep those in
# the exact structured-employer lane instead of asking the model to interpret it.
_EXTRA_EMPLOYER_PATTERNS = (
    re.compile(
        r"(?:هل\s+)?(?:سبق\s+(?:ان|أن)\s+)?عمل\s+(?:يوسف|هو)\s+(?:في|لدى|مع)\s+([^؟?.!]+)",
        re.I,
    ),
    re.compile(r"\b(?:youssef|he)\s+works\s+at\s+([^?.!]+)", re.I),
)

_PROFILE_SUMMARY_PATTERNS = (
    re.compile(r"\b(?:write|give|draft)\b.*\b(?:professional\s+)?(?:summary|bio|profile)\b.*\b(?:youssef|him)\b", re.I),
    re.compile(r"\b(?:short|brief)\s+(?:professional\s+)?(?:summary|bio|profile)\b.*\b(?:youssef|him)\b", re.I),
    re.compile(r"\b(?:tell|talk)\s+(?:me\s+)?about\s+(?:youssef|him)\b", re.I),
    re.compile(r"\b(?:bio|resume)\s+professionnelle?\b.*\b(?:youssef|lui)\b", re.I),
    re.compile(r"\b(?:parle|parler)\b.*\b(?:de\s+)?(?:youssef|lui)\b", re.I),
)

_SKILL_RANKING_PATTERNS = (
    re.compile(r"\b(?:strongest|best|top|key|core|most\s+(?:valuable|relevant|important))\b.*\b(?:technical\s+)?skills?\b", re.I),
    re.compile(r"\b(?:technical\s+)?skills?\b.*\b(?:strongest|best|top|key|core|most\s+(?:valuable|relevant|important))\b", re.I),
    re.compile(r"\b(?:competences?|compétences?)\b.*\b(?:techniques?\b)?.*\b(?:plus\s+fortes?|meilleures?|principales?|cles?|clés?|plus\s+pertinentes?)\b", re.I),
    re.compile(r"\b(?:plus\s+fortes?|meilleures?|principales?|cles?|clés?)\b.*\b(?:competences?|compétences?)\b", re.I),
    re.compile(r"(?:أقوى|أفضل|أهم).*مهارات|مهارات.*(?:أقوى|أفضل|أهم)", re.I),
)

_CERT_RANKING_PATTERNS = (
    re.compile(r"\b(?:most\s+(?:valuable|relevant|important)|strongest|best|top|key)\b.*\b(?:certifications?|certificates?|credentials?)\b", re.I),
    re.compile(r"\b(?:certifications?|certificates?|credentials?)\b.*\b(?:most\s+(?:valuable|relevant|important)|strongest|best|top|key)\b", re.I),
    re.compile(r"\b(?:certifications?|certificats?)\b.*\b(?:plus\s+(?:utiles?|pertinentes?|importantes?|fortes?)|meilleures?|principales?)\b", re.I),
    re.compile(r"\b(?:plus\s+(?:utiles?|pertinentes?|importantes?|fortes?)|meilleures?|principales?)\b.*\b(?:certifications?|certificats?)\b", re.I),
    re.compile(r"(?:أهم|أفضل|أقوى).*شهاد|شهاد.*(?:أهم|أفضل|أقوى)", re.I),
)

_PRIVATE_PROFILE_PATTERNS = {
    "salary": (
        re.compile(r"\b(?:salary|compensation|income|earnings|pay)\b", re.I),
        re.compile(r"\b(?:salaire|remuneration|revenu)\b", re.I),
        re.compile(r"(?:راتب|دخل|أجر)", re.I),
    ),
    "address": (
        re.compile(r"\b(?:home|personal|private)\s+address\b", re.I),
        re.compile(r"\b(?:adresse\s+(?:personnelle|privee)|adresse\s+de\s+domicile)\b", re.I),
        re.compile(r"(?:عنوان\s+(?:المنزل|السكن|الشخصي))", re.I),
    ),
    "phone": (
        re.compile(r"\b(?:phone|telephone|mobile)\s*(?:number)?\b", re.I),
        re.compile(r"\b(?:telephone|numero\s+de\s+telephone)\b", re.I),
        re.compile(r"(?:رقم\s+(?:الهاتف|الجوال)|هاتف)", re.I),
    ),
    "age": (
        re.compile(r"\b(?:how old|age|date of birth|birthday)\b", re.I),
        re.compile(r"\b(?:age|date\s+de\s+naissance|anniversaire)\b", re.I),
        re.compile(r"(?:العمر|تاريخ\s+الميلاد|كم\s+عمر)", re.I),
    ),
}


def _cleanup_dangling_citation_text(text: str) -> str:
    cleaned = text or ""
    for pattern in _DANGLING_AFTER_CITATION:
        cleaned = pattern.sub(r"\1", cleaned)
    cleaned = _BROKEN_RECORD_FRAGMENT.sub(
        lambda match: f"nor is there any corresponding record {match.group('prep')}",
        cleaned,
    )
    cleaned = _DANGLING_RECORD_CLAUSE.sub(r"\1", cleaned)
    cleaned = _DANGLING_REFERENCE_CLAUSE.sub(r"\1", cleaned)
    cleaned = _DANGLING_ASSOCIATION.sub(r"\1", cleaned)
    cleaned = re.sub(r"`\s*`", "", cleaned)
    cleaned = re.sub(r"\(\s*\)", "", cleaned)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    cleaned = re.sub(r"[ \t]+([.,;:!?])", r"\1", cleaned)
    cleaned = re.sub(r"([.!?])\s*\1+", r"\1", cleaned)
    return cleaned.strip()


def _patch_grounding_cleanup() -> None:
    if getattr(_grounding, "_vercel_quality_cleanup", False):
        return

    original_remove = _grounding._remove_unknown_citations
    original_strip = _grounding._strip_malformed_source_brackets

    def remove_unknown(answer, unknown):
        return _cleanup_dangling_citation_text(original_remove(answer, unknown))

    def strip_malformed(text):
        return _cleanup_dangling_citation_text(original_strip(text))

    _grounding._remove_unknown_citations = remove_unknown
    _grounding._strip_malformed_source_brackets = strip_malformed
    _grounding._vercel_quality_cleanup = True


def _patch_fastembed_cache() -> None:
    cls = _rag.FastEmbedEmbedder
    if getattr(cls, "_vercel_cache_path_patch", False):
        return

    def init(self, model_name=None):
        from fastembed import TextEmbedding

        self.model_name = model_name or os.environ.get(
            "FASTEMBED_MODEL", "BAAI/bge-small-en-v1.5"
        )
        cache_dir = (os.environ.get("FASTEMBED_CACHE_PATH") or "").strip()
        kwargs = {"model_name": self.model_name}
        if cache_dir:
            if not os.path.isabs(cache_dir):
                repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                cache_dir = os.path.join(repo_root, cache_dir)
            kwargs["cache_dir"] = cache_dir
        self.model = TextEmbedding(**kwargs)

    cls.__init__ = init
    cls._vercel_cache_path_patch = True


def _profile_summary_answer(resolver, language: str):
    current = next(
        (
            row for row in resolver.experiences
            if "present" in _precision._normalize(str(row.get("period") or ""))
        ),
        resolver.experiences[0] if resolver.experiences else {},
    )
    previous = next((row for row in resolver.experiences if row is not current), {})
    career = resolver.profile.get("career_status") or {}

    if language == "fr":
        role = str(current.get("role_fr") or current.get("role") or "Ingénieur IA/ML Freelance")
        company = str(current.get("company_fr") or current.get("company") or "Fiverr")
        period = str(current.get("period_fr") or current.get("period") or "")
        prev_role = str(previous.get("role_fr") or previous.get("role") or "")
        prev_company = str(previous.get("company_fr") or previous.get("company") or "")
        if "fiverr" in _precision._normalize(company) and "freelance" in _precision._normalize(role):
            text = f"Youssef Bouzit exerce actuellement comme {role}, en indépendant via {company}"
        else:
            text = f"Youssef Bouzit exerce actuellement comme {role} chez {company}"
        if period:
            text += f" ({period})"
        text += ". Son profil public documente des travaux en RAG/LLM, agents IA, Machine Learning et vision par ordinateur."
        if prev_role and prev_company:
            text += f" Son expérience précédente comprend {prev_role} chez {prev_company}."
        if isinstance(career, dict) and career.get("seeking_full_time") is True:
            text += " En parallèle, il recherche une opportunité en CDI à temps plein dans l’IA/ML."
    elif language == "ar":
        role = str(current.get("role") or "Freelance AI/ML Engineer")
        company = str(current.get("company") or "Fiverr")
        period = str(current.get("period") or "")
        prev_role = str(previous.get("role") or "")
        prev_company = str(previous.get("company") or "")
        if "fiverr" in _precision._normalize(company) and "freelance" in _precision._normalize(role):
            text = f"يعمل يوسف بوزيت حالياً كـ {role} بشكل مستقل عبر {company}"
        else:
            text = f"يعمل يوسف بوزيت حالياً كـ {role} لدى {company}"
        if period:
            text += f" ({period})"
        text += ". ويوثق ملفه المهني أعمالاً في RAG/LLM وAI Agents وMachine Learning وComputer Vision."
        if prev_role and prev_company:
            text += f" وتشمل خبرته السابقة {prev_role} لدى {prev_company}."
        if isinstance(career, dict) and career.get("seeking_full_time") is True:
            text += " وبالتوازي مع العمل الحر، يبحث عن فرصة عمل بدوام كامل في مجال AI/ML."
    else:
        role = str(current.get("role") or "Freelance AI/ML Engineer")
        company = str(current.get("company") or "Fiverr")
        period = str(current.get("period") or "")
        prev_role = str(previous.get("role") or "")
        prev_company = str(previous.get("company") or "")
        if "fiverr" in _precision._normalize(company) and "freelance" in _precision._normalize(role):
            text = f"Youssef Bouzit currently works as an independent {role} via {company}"
        else:
            text = f"Youssef Bouzit currently works as a {role} at {company}"
        if period:
            text += f" ({period})"
        text += ". His public portfolio documents work across RAG/LLM applications, AI agents, Machine Learning, and Computer Vision."
        if prev_role and prev_company:
            text += f" His previous experience includes {prev_role} at {prev_company}."
        if isinstance(career, dict) and career.get("seeking_full_time") is True:
            text += " In parallel with freelance work, he is seeking a full-time AI/ML opportunity."

    return _precision.StructuredFactAnswer(
        text + " [experience-education] [career-status] [skills]",
        source="experience-education",
        evidence="Deterministic professional summary from synchronized current/prior experience, career availability, and skills.",
    )


def _project_by_slug(resolver, slug: str):
    target = _precision._normalize(slug)
    return next(
        (
            row for row in resolver.projects
            if _precision._normalize(str(row.get("slug") or "")) == target
        ),
        {},
    )


def _cert_by_title(resolver, title: str):
    target = _precision._normalize(title)
    return next(
        (
            row for row in resolver.certifications
            if _precision._normalize(str(row.get("title") or "")) == target
        ),
        None,
    )


def _strong_skills_answer(resolver, language: str):
    accident = _project_by_slug(resolver, "real-time-road-accident-detection")
    legal = _project_by_slug(resolver, "openlegama-moroccan-legal-ai")
    accident_results = accident.get("results") or {}
    legal_results = legal.get("results") or {}

    if language == "fr":
        text = (
            "D’après les **preuves publiques les plus fortes**, et pas seulement les libellés de compétences, les principaux domaines techniques de Youssef sont :\n\n"
            f"1. **Computer Vision & Deep Learning** — expérience PFE chez NEXTRONIC — ABA Technology avec YOLOv11, BoT-SORT et OpenCV ; {accident_results.get('precision','86.68%')} précision, {accident_results.get('recall','91.56%')} rappel et ~{accident_results.get('inferenceSpeed','31.5 FPS')}. [experience-education] [project-real-time-road-accident-detection]\n"
            f"2. **RAG / LLM & Grounded AI** — OpenLegaMa : Controlled RAG, citations, abstention, {legal_results.get('automatedTests','143 / 143 passing')} et {legal_results.get('indexedArticles','7,708')} articles indexés. [project-openlegama-moroccan-legal-ai] [skills]\n"
            "3. **MLOps & AI Systems** — Airflow, MLflow, MinIO, PostgreSQL, Docker Compose, suivi d’expériences et monitoring via Customer MLOps Pipeline. [project-customer-churn-mlops-platform] [skills]\n"
            "4. **Machine Learning** — Scikit-learn, feature engineering, évaluation, cross-validation, classification et Explainable AI. [skills]\n"
            "5. **Backend & AI Engineering** — Python, FastAPI, REST APIs, SQL, Git, Linux et interfaces de déploiement. [skills]\n\n"
            "Ses preuves mesurées les plus fortes aujourd’hui sont surtout en **Computer Vision** et **RAG/LLM**."
        )
    elif language == "ar":
        text = (
            "بناءً على **أقوى الأدلة العامة** وليس مجرد أسماء المهارات، أبرز المجالات التقنية لدى يوسف هي:\n\n"
            f"1. **Computer Vision & Deep Learning** — خبرة PFE لدى NEXTRONIC — ABA Technology باستخدام YOLOv11 وBoT-SORT وOpenCV، مع {accident_results.get('precision','86.68%')} دقة و{accident_results.get('recall','91.56%')} استرجاع و~{accident_results.get('inferenceSpeed','31.5 FPS')}. [experience-education] [project-real-time-road-accident-detection]\n"
            f"2. **RAG / LLM & Grounded AI** — OpenLegaMa مع Controlled RAG والاستشهادات والامتناع عند نقص الأدلة، و{legal_results.get('automatedTests','143 / 143 passing')} و{legal_results.get('indexedArticles','7,708')} مادة مفهرسة. [project-openlegama-moroccan-legal-ai] [skills]\n"
            "3. **MLOps & AI Systems** — Airflow وMLflow وMinIO وPostgreSQL وDocker Compose والمراقبة. [project-customer-churn-mlops-platform] [skills]\n"
            "4. **Machine Learning** — Scikit-learn وFeature Engineering وModel Evaluation وExplainable AI. [skills]\n"
            "5. **Backend & AI Engineering** — Python وFastAPI وREST APIs وSQL وGit وLinux. [skills]\n\n"
            "أقوى الأدلة المقاسة حالياً تظهر خصوصاً في **Computer Vision** و**RAG/LLM**."
        )
    else:
        text = (
            "Based on the **strongest public evidence**, not just declared skill labels, Youssef's strongest technical areas are:\n\n"
            f"1. **Computer Vision & Deep Learning** — professional PFE work at NEXTRONIC — ABA Technology with YOLOv11, BoT-SORT, and OpenCV; {accident_results.get('precision','86.68%')} precision, {accident_results.get('recall','91.56%')} recall, and ~{accident_results.get('inferenceSpeed','31.5 FPS')}. [experience-education] [project-real-time-road-accident-detection]\n"
            f"2. **RAG / LLM & Grounded AI** — OpenLegaMa demonstrates controlled RAG, citations, abstention, {legal_results.get('automatedTests','143 / 143 passing')}, and {legal_results.get('indexedArticles','7,708')} indexed articles. [project-openlegama-moroccan-legal-ai] [skills]\n"
            "3. **MLOps & AI Systems** — Airflow, MLflow, MinIO, PostgreSQL, Docker Compose, experiment tracking, and monitoring through Customer MLOps Pipeline. [project-customer-churn-mlops-platform] [skills]\n"
            "4. **Machine Learning** — Scikit-learn, feature engineering, evaluation, cross-validation, classification, and Explainable AI. [skills]\n"
            "5. **Backend & AI Engineering** — Python, FastAPI, REST APIs, SQL, Git, Linux, and deployment-oriented interfaces. [skills]\n\n"
            "His strongest measured evidence today is especially in **Computer Vision** and **RAG/LLM**."
        )
    return _precision.StructuredFactAnswer(
        text,
        source="skills",
        evidence="Evidence-ranked technical skill summary from synchronized experience, projects, and skill categories.",
    )


def _valuable_certifications_answer(resolver, language: str):
    wanted = [
        "Machine Learning with Python Professional Certificate by Anaconda",
        "Oracle Agentic AI Certified Foundations Associate",
        "OpenCV Bootcamp",
        "Vision Language Models (VLM) Bootcamp",
        "PyTorch Bootcamp",
        "Building with the Claude API",
        "Model Context Protocol: Advanced Topics",
        "Oracle Cloud Infrastructure 2026 Certified Architect Associate",
        "Oracle AI Database Certified Foundations Associate",
    ]
    present = {title: _cert_by_title(resolver, title) for title in wanted}

    def has(title: str) -> bool:
        return present.get(title) is not None

    if language == "fr":
        lines = []
        if has(wanted[0]):
            lines.append("1. **Machine Learning with Python Professional Certificate by Anaconda** — directement aligné avec le Machine Learning appliqué.")
        if has(wanted[1]):
            lines.append("2. **Oracle Agentic AI Certified Foundations Associate** — pertinent pour les agents IA et workflows LLM.")
        vision = [title for title in wanted[2:5] if has(title)]
        if vision:
            lines.append("3. **OpenCV University** — " + ", ".join(vision) + " : forte cohérence avec Computer Vision / Deep Learning / VLM.")
        llm = [title for title in wanted[5:7] if has(title)]
        if llm:
            lines.append("4. **Anthropic** — " + ", ".join(llm) + " : pratique API LLM et MCP.")
        if has(wanted[7]):
            lines.append("5. **Oracle Cloud Infrastructure 2026 Certified Architect Associate** — utile pour l’architecture cloud et le déploiement.")
        if has(wanted[8]):
            lines.append("6. **Oracle AI Database Certified Foundations Associate** — complément data/database pour les systèmes IA.")
        text = (
            "Pour un poste **AI Engineer**, voici les certifications documentées les plus directement alignées avec le rôle :\n\n"
            + "\n".join(lines)
            + f"\n\nYoussef possède {len(resolver.certifications)} certifications/certificats au total. Cette sélection est un **classement par pertinence pour un poste AI Engineer**, pas une valeur universelle des certifications. [certifications]"
        )
    elif language == "ar":
        lines = []
        if has(wanted[0]):
            lines.append("1. **Machine Learning with Python Professional Certificate by Anaconda** — مرتبط مباشرة بتطبيقات Machine Learning.")
        if has(wanted[1]):
            lines.append("2. **Oracle Agentic AI Certified Foundations Associate** — مناسب لـ AI Agents وLLM workflows.")
        vision = [title for title in wanted[2:5] if has(title)]
        if vision:
            lines.append("3. **OpenCV University** — " + ", ".join(vision) + " — دعم قوي لـ Computer Vision / Deep Learning / VLM.")
        llm = [title for title in wanted[5:7] if has(title)]
        if llm:
            lines.append("4. **Anthropic** — " + ", ".join(llm) + " — خبرة مرتبطة بـ LLM APIs وMCP.")
        if has(wanted[7]):
            lines.append("5. **Oracle Cloud Infrastructure 2026 Certified Architect Associate** — مفيدة للبنية السحابية والنشر.")
        if has(wanted[8]):
            lines.append("6. **Oracle AI Database Certified Foundations Associate** — تكمل جانب البيانات وقواعد البيانات في أنظمة AI.")
        text = (
            "بالنسبة إلى منصب **AI Engineer**، هذه أكثر الشهادات الموثقة ارتباطاً بالدور:\n\n"
            + "\n".join(lines)
            + f"\n\nلدى يوسف {len(resolver.certifications)} شهادة/اعتماداً في ملفه العام. هذا **ترتيب حسب ملاءمة الدور** وليس حكماً عالمياً على قيمة الشهادات. [certifications]"
        )
    else:
        lines = []
        if has(wanted[0]):
            lines.append("1. **Machine Learning with Python Professional Certificate by Anaconda** — directly aligned with applied Machine Learning.")
        if has(wanted[1]):
            lines.append("2. **Oracle Agentic AI Certified Foundations Associate** — relevant to AI agents and LLM-enabled workflows.")
        vision = [title for title in wanted[2:5] if has(title)]
        if vision:
            lines.append("3. **OpenCV University** — " + ", ".join(vision) + " — strong alignment with Computer Vision / Deep Learning / VLM work.")
        llm = [title for title in wanted[5:7] if has(title)]
        if llm:
            lines.append("4. **Anthropic** — " + ", ".join(llm) + " — practical LLM API and MCP relevance.")
        if has(wanted[7]):
            lines.append("5. **Oracle Cloud Infrastructure 2026 Certified Architect Associate** — useful cloud architecture and deployment evidence.")
        if has(wanted[8]):
            lines.append("6. **Oracle AI Database Certified Foundations Associate** — useful data/database context for AI systems.")
        text = (
            "For an **AI Engineer** position, these are the documented certifications most directly aligned with the role:\n\n"
            + "\n".join(lines)
            + f"\n\nYoussef has {len(resolver.certifications)} certifications/certificates in total. This is a **role-fit ranking**, not a claim that these credentials are universally more valuable than all others. [certifications]"
        )
    return _precision.StructuredFactAnswer(
        text,
        source="certifications",
        evidence="Role-fit certification ranking from the synchronized certification inventory.",
    )


def _private_profile_answer(kind: str, language: str):
    if language == "fr":
        labels = {
            "salary": "le salaire ou la rémunération actuelle de Youssef",
            "address": "l’adresse personnelle ou le domicile de Youssef",
            "phone": "un numéro de téléphone public de Youssef",
            "age": "l’âge ou la date de naissance de Youssef",
        }
        return _precision.StructuredFactAnswer(
            f"Le profil professionnel public synchronisé ne fournit pas {labels[kind]}. Je ne vais pas déduire ni inventer une information personnelle non publiée.",
            source="structured-profile",
            evidence=f"Unsupported private profile field: {kind}; absent from the synchronized public professional profile.",
        )
    if language == "ar":
        labels = {
            "salary": "راتب يوسف أو دخله الحالي",
            "address": "عنوان منزل يوسف أو عنوانه الشخصي",
            "phone": "رقم هاتف عام ليوسف",
            "age": "عمر يوسف أو تاريخ ميلاده",
        }
        return _precision.StructuredFactAnswer(
            f"لا يتضمن الملف المهني العام المتزامن {labels[kind]}. لن أستنتج أو أختلق معلومات شخصية غير منشورة.",
            source="structured-profile",
            evidence=f"Unsupported private profile field: {kind}; absent from the synchronized public professional profile.",
        )
    labels = {
        "salary": "Youssef's current salary or compensation",
        "address": "Youssef's home or private address",
        "phone": "a public phone number for Youssef",
        "age": "Youssef's age or date of birth",
    }
    return _precision.StructuredFactAnswer(
        f"The synchronized public professional profile does not provide {labels[kind]}. I won't infer or invent unpublished personal information.",
        source="structured-profile",
        evidence=f"Unsupported private profile field: {kind}; absent from the synchronized public professional profile.",
    )


def _patch_precision_quality() -> None:
    if getattr(_precision, "_vercel_precision_quality_patch", False):
        return

    # Extend exact employer extraction before the resolver is used.
    _precision._EMPLOYER_PATTERNS += _EXTRA_EMPLOYER_PATTERNS

    original_resolve = _precision.StructuredFactResolver.resolve

    def resolve(self, question, history=None):
        language = _precision.detect_language(question)
        normalized = _precision._normalize(question)

        if any(pattern.search(normalized) for pattern in _PROFILE_SUMMARY_PATTERNS):
            return _profile_summary_answer(self, language)

        for kind, patterns in _PRIVATE_PROFILE_PATTERNS.items():
            if any(pattern.search(normalized) for pattern in patterns):
                return _private_profile_answer(kind, language)

        return original_resolve(self, question, history)

    _precision.StructuredFactResolver.resolve = resolve
    _precision._vercel_precision_quality_patch = True


def _patch_structured_professional_quality() -> None:
    # Imported lazily so the Vercel entrypoint can still apply this module before
    # backend.app builds its shared resolver.
    import structured_facts as _structured

    cls = _structured.StructuredFactResolver
    if getattr(cls, "_vercel_recruiter_quality_patch", False):
        return

    original_resolve = cls.resolve
    original_realtime = cls._realtime

    def realtime(self, question, language):
        result = original_realtime(self, question, language)
        if result is not None and "30+ on CPU" in result.answer:
            result = replace(result, answer=result.answer.replace("30+ on CPU", "30+ FPS on CPU"))
        return result

    def resolve(self, question, history=None):
        normalized = _precision._normalize(question)
        language = self._effective_language(question) if hasattr(self, "_effective_language") else _precision.detect_language(question)

        if any(pattern.search(normalized) for pattern in _SKILL_RANKING_PATTERNS):
            return _strong_skills_answer(self, language)

        if any(pattern.search(normalized) for pattern in _CERT_RANKING_PATTERNS):
            return _valuable_certifications_answer(self, language)

        result = original_resolve(self, question, history)
        if result is not None and "30+ on CPU" in result.answer:
            return replace(result, answer=result.answer.replace("30+ on CPU", "30+ FPS on CPU"))
        return result

    cls._realtime = realtime
    cls.resolve = resolve
    cls._vercel_recruiter_quality_patch = True


def apply() -> None:
    _patch_fastembed_cache()
    _patch_grounding_cleanup()
    _patch_precision_quality()
    _patch_structured_professional_quality()


apply()