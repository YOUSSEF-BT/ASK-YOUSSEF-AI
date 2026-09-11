"""Final conversational quality layer over the production structured-fact resolver.

The lower layers keep exact counts, complete inventories, safety behavior, and
legacy regression contracts. This shim handles high-value visitor questions
where a generic top-k RAG answer can be factually correct yet professionally
weak. It uses an evidence hierarchy:

professional experience -> measured/shipped projects -> technical project work
-> declared skills -> certifications/training.
"""
from __future__ import annotations

import re

import precision_facts as _precision
import structured_facts_live_base as _live

StructuredFactAnswer = _live.StructuredFactAnswer

_precision._COMMON.update({"exactement"})

_precision._CURRENT_PATTERNS += (
    r"\bwhat is (?:youssef|he) doing for work (?:right now|now|currently)\b",
    r"\bwhat does (?:youssef|he) do for work (?:right now|now|currently)\b",
)

_WHY_YOUSSEF_PATTERNS = (
    r"\b(?:pourquoi|pour\s+quoi)\s+(?:choisir\s+)?youssef(?:\s+et|\s+plutot que|\s+plutôt que)\s+(?:pas\s+)?(?:un|une|quelqu['’]?un|candidat|profil|autre)\b",
    r"\b(?:pourquoi|pour\s+quoi)\s+(?:choisir|recruter|prendre|embaucher)\s+youssef\b",
    r"\b(?:pourquoi|pour\s+quoi)\s+(?:lui|le choisir|le recruter)\b",
    r"\bwhy\s+(?:choose|hire|pick|recruit)\s+youssef\b",
    r"\bwhy\s+youssef\s+(?:instead of|over|and not)\b",
    r"لماذا.*يوسف.*(?:وليس|بدل|بدلاً|اختيار)",
)

_EXPERIENCE_OVERVIEW_PATTERNS = (
    r"\b(?:donne(?:\s+moi)?|montre(?:\s+moi)?|liste|quelles?\s+sont)\b.*\b(?:experiences?|expériences?)\b.*\byoussef\b",
    r"\b(?:experiences?|expériences?)\s+(?:professionnelles?\s+)?(?:de|d['’])\s*youssef\b",
    r"\b(?:donne(?:\s+moi)?|montre(?:\s+moi)?|liste)\b.*\bexpressions?\b.*\byoussef\b",
    r"\bexpressions?\s+(?:de|d['’])\s*youssef\b",
    r"\b(?:tell me|show me|list)\b.*\b(?:experience|experiences)\b.*\byoussef\b",
    r"\b(?:youssef['’]?s|his)\s+(?:work\s+)?experiences?\b",
    r"خبرات.*يوسف|تجارب.*يوسف",
)

_LITERAL_EXPRESSION_HINTS = {
    "citation", "citations", "phrase", "phrases", "dicton", "dictons",
    "quote", "quotes", "saying", "sayings", "mots", "favori", "favorite",
}

_DOMAIN_EVIDENCE_HINTS = (
    "experience", "background", "expertise", "skill", "skills", "evidence",
    "proof", "prove", "hands-on", "practical", "worked", "work",
    "experience professionnelle", "expérience professionnelle", "experience de",
    "expérience de", "competence", "compétence", "competences", "compétences",
    "preuve", "preuves", "expertise", "maitrise", "maîtrise",
    "خبرة", "خبراته", "مهارة", "مهارات", "دليل", "أثبت",
)

_STRONGEST_PROJECT_HINTS = (
    "strongest", "best", "top ai project", "top ai projects", "most impressive",
    "flagship", "meilleur projet", "meilleurs projets", "projets les plus forts",
    "plus fort projet", "projets phares", "أقوى مشروع", "أقوى المشاريع", "أفضل مشروع",
)


class StructuredFactResolver(_live.StructuredFactResolver):
    @staticmethod
    def _effective_language(question: str) -> str:
        raw = question or ""
        if re.search(r"[\u0600-\u06FF]", raw):
            return "ar"
        normalized = _precision._normalize(raw)
        french_hints = (
            "c kwa", "c'est quoi", "son mail", "mail pro", "dis que",
            "meme si", "chomage", "chomeur", "travaille chez", "donne moi",
            "quel age", "combien", "emploi", "travail ou nn", "pourquoi",
            "pour quoi", "expressions de", "experiences de", "expérience de",
            "preuve", "compétence", "projet phare", "projets phares",
        )
        if any(hint in normalized for hint in french_hints):
            return "fr"
        return _precision.detect_language(raw)

    @staticmethod
    def _matches_any(patterns, question: str) -> bool:
        normalized = _precision._normalize(question)
        return any(re.search(pattern, normalized, re.I) for pattern in patterns)

    def _project_by_slug(self, slug: str):
        target = _precision._normalize(slug)
        return next(
            (row for row in self.projects if _precision._normalize(str(row.get("slug") or "")) == target),
            None,
        )

    def _experience_by_company(self, company_fragment: str):
        target = _precision._normalize(company_fragment)
        return next(
            (row for row in self.experiences if target in _precision._normalize(str(row.get("company") or ""))),
            None,
        )

    def _cert_by_title(self, title: str):
        target = _precision._normalize(title)
        return next(
            (row for row in self.certifications if _precision._normalize(str(row.get("title") or "")) == target),
            None,
        )

    def _resolve_why_youssef(self, question: str, language: str):
        if not self._matches_any(_WHY_YOUSSEF_PATTERNS, question):
            return None

        accident = self._project_by_slug("real-time-road-accident-detection")
        legal = self._project_by_slug("openlegama-moroccan-legal-ai")
        career = self.profile.get("career_status") or {}
        accident_results = (accident or {}).get("results") or {}
        legal_results = (legal or {}).get("results") or {}
        precision = str(accident_results.get("precision") or "86.68%")
        recall = str(accident_results.get("recall") or "91.56%")
        fps = str(accident_results.get("inferenceSpeed") or "31.5 FPS")
        tests = str(legal_results.get("automatedTests") or "143 / 143 passing")
        articles = str(legal_results.get("indexedArticles") or "7,708")
        seeking = isinstance(career, dict) and career.get("seeking_full_time") is True

        if language == "fr":
            text = (
                "Je ne peux pas affirmer que Youssef est « meilleur que tous les autres » sans comparer les candidats. "
                "En revanche, son profil donne plusieurs raisons concrètes de le choisir :\n\n"
                f"• **Résultats mesurés** : son PFE de détection d’accidents atteint {precision} de précision, {recall} de rappel et environ {fps}. [project-real-time-road-accident-detection]\n"
                f"• **AI Engineering polyvalent** : Computer Vision, Machine Learning et RAG/LLM. OpenLegaMa est évalué avec {tests} et {articles} articles juridiques indexés. [project-openlegama-moroccan-legal-ai]\n"
                "• **Capacité end-to-end** : modèle, retrieval, API, évaluation, guardrails, intégration et déploiement.\n"
                "• **Disponible pour une équipe** : diplôme d’ingénieur d’État en Data Science terminé"
                + (" et recherche active d’un CDI à temps plein" if seeking else "")
                + ". [experience-education] [career-status]\n\n"
                "Sa différence vient surtout de la combinaison **AI/ML + Computer Vision + RAG/LLM + systèmes complets avec preuves mesurables**."
            )
        elif language == "ar":
            text = (
                "لا يمكنني القول إن يوسف «أفضل من الجميع» من دون مقارنة فعلية مع مرشحين آخرين، لكن ملفه يقدم أدلة قوية لاختياره:\n\n"
                f"• **نتائج قابلة للقياس**: مشروع اكتشاف الحوادث حقق دقة {precision} واسترجاعاً {recall} وبسرعة تقارب {fps}. [project-real-time-road-accident-detection]\n"
                f"• **تنوع قوي في AI Engineering**: Computer Vision وMachine Learning وRAG/LLM. مشروع OpenLegaMa موثق بـ {tests} و{articles} مادة قانونية مفهرسة. [project-openlegama-moroccan-legal-ai]\n"
                "• **قدرة end-to-end**: من النموذج والاسترجاع إلى API والتقييم والحواجز الأمنية والنشر.\n"
                "• **جاهزية مهنية**: أنهى دبلوم مهندس دولة في Data Science"
                + (" ويبحث حالياً عن فرصة بدوام كامل" if seeking else "")
                + ". [experience-education] [career-status]\n\n"
                "الخلاصة: قوته هي الجمع بين **AI/ML + Computer Vision + RAG/LLM + أنظمة متكاملة قابلة للقياس**."
            )
        else:
            text = (
                "I cannot honestly claim Youssef is better than every other candidate without a direct comparison. What his portfolio does provide is concrete evidence for choosing him:\n\n"
                f"• **Measured results**: his real-time accident-detection PFE reports {precision} precision, {recall} recall, and about {fps}. [project-real-time-road-accident-detection]\n"
                f"• **Broad AI engineering range**: Computer Vision, Machine Learning, and RAG/LLM. OpenLegaMa is documented with {tests} and {articles} indexed legal articles. [project-openlegama-moroccan-legal-ai]\n"
                "• **End-to-end delivery**: models, retrieval, APIs, evaluation, guardrails, integration, and deployment.\n"
                "• **Ready for a team**: he completed his State Engineering degree in Data Science"
                + (" and is actively seeking a full-time role" if seeking else "")
                + ". [experience-education] [career-status]\n\n"
                "The differentiator is the combination of **AI/ML + Computer Vision + RAG/LLM + measurable end-to-end systems**."
            )
        return StructuredFactAnswer(text, source="career-status", evidence="Evidence-first synthesis from synchronized career, education, accident-detection, and OpenLegaMa records.")

    def _resolve_experience_overview(self, question: str, language: str):
        tokens = _precision._tokens(question)
        typo_expression = "expression" in tokens or "expressions" in tokens
        if typo_expression and (tokens & _LITERAL_EXPRESSION_HINTS):
            return None
        if not self._matches_any(_EXPERIENCE_OVERVIEW_PATTERNS, question):
            return None
        if not self.experiences:
            return None

        if language == "fr":
            intro = "Si par « expressions » tu voulais dire **expériences professionnelles**, voici les principales :" if typo_expression else "Voici les principales expériences professionnelles de Youssef :"
            lines = [intro]
            for index, row in enumerate(self.experiences, 1):
                role = str(row.get("role_fr") or row.get("role") or "").strip()
                company = str(row.get("company_fr") or row.get("company") or "").strip()
                period = str(row.get("period_fr") or row.get("period") or "").strip()
                description = str(row.get("description_fr") or row.get("description") or "").strip()
                if "fiverr" in _precision._normalize(company) and "freelance" in _precision._normalize(role):
                    lines.append(f"{index}. **{role} en indépendant, via {company}** — {period}. {description}")
                else:
                    lines.append(f"{index}. **{role} — {company}** — {period}. {description}")
            career = self.profile.get("career_status") or {}
            if isinstance(career, dict) and career.get("seeking_full_time") is True:
                lines.append("\nAujourd’hui, le freelance est mené en parallèle : Youssef recherche toujours activement un **CDI à temps plein en AI/ML**. [career-status]")
            lines.append("[experience-education]")
            text = "\n".join(lines)
        elif language == "ar":
            lines = ["أهم الخبرات المهنية الموثقة ليوسف هي:"]
            for index, row in enumerate(self.experiences, 1):
                role = str(row.get("role") or "").strip()
                company = str(row.get("company") or "").strip()
                period = str(row.get("period") or "").strip()
                description = str(row.get("description") or "").strip()
                lines.append(f"{index}. **{role} — {company}** — {period}. {description}")
            career = self.profile.get("career_status") or {}
            if isinstance(career, dict) and career.get("seeking_full_time") is True:
                lines.append("\nالعمل الحر نشاط موازٍ؛ يوسف ما زال يبحث عن **فرصة عمل بدوام كامل في AI/ML**. [career-status]")
            lines.append("[experience-education]")
            text = "\n".join(lines)
        else:
            lines = ["Youssef's main documented professional experiences are:"]
            for index, row in enumerate(self.experiences, 1):
                role = str(row.get("role") or "").strip()
                company = str(row.get("company") or "").strip()
                period = str(row.get("period") or "").strip()
                description = str(row.get("description") or "").strip()
                if "fiverr" in _precision._normalize(company) and "freelance" in _precision._normalize(role):
                    lines.append(f"{index}. **{role}, independently via {company}** — {period}. {description}")
                else:
                    lines.append(f"{index}. **{role} — {company}** — {period}. {description}")
            career = self.profile.get("career_status") or {}
            if isinstance(career, dict) and career.get("seeking_full_time") is True:
                lines.append("\nFreelancing is a parallel activity; Youssef is still actively seeking a **full-time AI/ML role**. [career-status]")
            lines.append("[experience-education]")
            text = "\n".join(lines)
        return StructuredFactAnswer(text, source="experience-education")

    def _resolve_domain_evidence(self, question: str, language: str):
        normalized = _precision._normalize(question)
        if self._matches(_precision._COUNT_PATTERNS, question) or self._matches(_precision._LIST_ALL_PATTERNS, question):
            return None
        referent = any(token in normalized for token in ("youssef", "his ", " he ", "son ", "ses ", " il ", "يوسف", "له", "خبرته"))
        if not referent or not any(hint in normalized for hint in _DOMAIN_EVIDENCE_HINTS):
            return None
        cv = "computer vision" in normalized or "vision par ordinateur" in normalized or "رؤية حاسوبية" in normalized or "الرؤية الحاسوبية" in normalized
        rag = any(term in normalized for term in ("rag", "retrieval augmented generation", "retrieval-augmented generation", "llm", "llms", "large language model", "large language models", "generative ai", "ia generative", "ia générative", "نماذج لغوية", "التوليد المعزز بالاسترجاع"))
        if not (cv or rag):
            return None

        if cv:
            accident = self._project_by_slug("real-time-road-accident-detection") or {}
            nextronic = self._experience_by_company("NEXTRONIC") or {}
            ar = accident.get("results") or {}
            precision = str(ar.get("precision") or "86.68%")
            recall = str(ar.get("recall") or "91.56%")
            f1 = str(ar.get("f1Score") or "89.06%")
            fps = str(ar.get("inferenceSpeed") or "31.5 FPS")
            period = str(nextronic.get("period") or "Feb 2026 — Aug 2026")
            if language == "fr":
                text = (
                    "Son expérience en **Computer Vision est pratique et professionnelle**, pas seulement académique :\n\n"
                    f"1. **NEXTRONIC — ABA Technology ({period})** — stage AI/ML orienté vision par ordinateur. Il y a conçu le système de détection d’accidents routiers en temps réel pour CCTV. [experience-education]\n"
                    f"2. **Preuves mesurées sur le PFE** — YOLOv11 + BoT-SORT + OpenCV, avec {precision} de précision, {recall} de rappel, {f1} de F1-score et environ {fps} sur le benchmark image. [project-real-time-road-accident-detection]\n"
                    "3. **Projet complémentaire Traffic MVP** — détection de véhicules et analyse de trafic en temps réel avec YOLOv8, OpenCV, export CSV et dashboard Streamlit. [project-traffic-mvp-image-processing]\n\n"
                    "Stack démontrée : **Python, YOLOv8/YOLOv11, OpenCV, BoT-SORT, object detection, multi-object tracking, real-time video et Roboflow**. [skills]\n\n"
                    "En bref : il possède à la fois une **expérience entreprise en Computer Vision** et plusieurs systèmes vidéo réellement construits."
                )
            elif language == "ar":
                text = (
                    "خبرة يوسف في **Computer Vision عملية ومهنية** وليست مجرد دراسة:\n\n"
                    f"1. **NEXTRONIC — ABA Technology ({period})** — تدريب AI/ML موجه للرؤية الحاسوبية، حيث صمم نظاماً آنياً لاكتشاف حوادث الطرق من CCTV. [experience-education]\n"
                    f"2. **نتائج مقاسة في مشروع التخرج** — YOLOv11 + BoT-SORT + OpenCV مع دقة {precision} واسترجاع {recall} وF1 بقيمة {f1} وسرعة تقارب {fps}. [project-real-time-road-accident-detection]\n"
                    "3. **Traffic MVP** — كشف المركبات وتحليل حركة المرور في الزمن الحقيقي باستخدام YOLOv8 وOpenCV مع CSV وStreamlit. [project-traffic-mvp-image-processing]\n\n"
                    "الأدوات المثبتة عملياً تشمل Python وYOLOv8/YOLOv11 وOpenCV وBoT-SORT وتتبع الأجسام والفيديو الآني وRoboflow. [skills]"
                )
            else:
                text = (
                    "Youssef's **Computer Vision experience is hands-on and professional**, not just coursework:\n\n"
                    f"1. **NEXTRONIC — ABA Technology ({period})** — AI/ML Engineer Intern focused on Computer Vision, where he designed a real-time CCTV road-accident detection system. [experience-education]\n"
                    f"2. **Measured PFE evidence** — YOLOv11 + BoT-SORT + OpenCV, reporting {precision} precision, {recall} recall, {f1} F1-score, and about {fps} on the image benchmark. [project-real-time-road-accident-detection]\n"
                    "3. **Traffic MVP** — a second real-time vision system using YOLOv8 and OpenCV for vehicle detection and traffic-flow analysis, with CSV metrics and a Streamlit dashboard. [project-traffic-mvp-image-processing]\n\n"
                    "Demonstrated stack: **Python, YOLOv8/YOLOv11, OpenCV, BoT-SORT, object detection, multi-object tracking, real-time video, and Roboflow**. [skills]\n\n"
                    "So the evidence is **company experience + measured project results + a second working vision application**."
                )
            return StructuredFactAnswer(text, source="project-real-time-road-accident-detection", evidence="Evidence hierarchy: professional CV experience, measured accident-detection project, supporting traffic-vision project, then skills.")

        legal = self._project_by_slug("openlegama-moroccan-legal-ai") or {}
        lr = legal.get("results") or {}
        tests = str(lr.get("automatedTests") or "143 / 143 passing")
        indexed = str(lr.get("indexedArticles") or "7,708")
        texts = str(lr.get("activeLegalTexts") or "30")
        curated = str(lr.get("curatedBenchmark") or "610 cases")
        holdout = str(lr.get("holdoutBenchmark") or "120 cases")
        recall5 = str(lr.get("documentRecallAt5") or "100% curated")
        exact = str(lr.get("exactArticleRecall") or "100% measured")
        if language == "fr":
            text = (
                "La preuve la plus forte de ses compétences **RAG/LLM** est un système construit et évalué, pas une simple ligne de CV :\n\n"
                f"1. **OpenLegaMa — Moroccan Legal AI Assistant** : RAG contrôlé multilingue avec validation des références juridiques, citations reliées aux preuves et abstention lorsque les sources sont insuffisantes. [project-openlegama-moroccan-legal-ai]\n"
                f"2. **Évaluation réelle** : {tests}, {curated} de benchmark curaté + {holdout} de holdout, {indexed} articles issus de {texts} textes juridiques actifs, document Recall@5 = {recall5} et exact-article recall = {exact} sur les benchmarks mesurés. [project-openlegama-moroccan-legal-ai]\n"
                "3. **Expérience actuelle** : son activité freelance documente des systèmes RAG, des applications LLM, des agents IA et des workflows d’intelligence documentaire. [experience-education]\n"
                "4. **Stack associée** : RAG, embeddings, semantic search, document processing, prompt/context engineering et évaluation. [skills]\n\n"
                "Conclusion : ses compétences RAG/LLM sont appuyées par **un produit public évalué + une pratique professionnelle actuelle + une stack explicite**."
            )
        elif language == "ar":
            text = (
                "أقوى دليل على مهارات يوسف في **RAG/LLM** هو نظام مبني ومقاس فعلياً، وليس مجرد مهارة مكتوبة في السيرة:\n\n"
                f"1. **OpenLegaMa** — نظام RAG قانوني متعدد اللغات مع التحقق من المراجع، ربط الادعاءات بالمصادر، والامتناع عندما لا تكون الأدلة كافية. [project-openlegama-moroccan-legal-ai]\n"
                f"2. **تقييم فعلي**: {tests}، و{curated} للاختبار المنسق + {holdout} holdout، و{indexed} مادة قانونية من {texts} نصاً قانونياً، مع Recall@5 = {recall5} واسترجاع المادة الدقيقة = {exact}. [project-openlegama-moroccan-legal-ai]\n"
                "3. **العمل الحالي**: نشاطه الحر يوثق أنظمة RAG وتطبيقات LLM ووكلاء AI وذكاء الوثائق. [experience-education]\n"
                "4. **التقنيات**: embeddings وsemantic search ومعالجة الوثائق وprompt/context engineering والتقييم. [skills]"
            )
        else:
            text = (
                "The strongest evidence of Youssef's **RAG and LLM skills is a built and evaluated system**, not just a skills-page claim:\n\n"
                f"1. **OpenLegaMa — Moroccan Legal AI Assistant** — a multilingual controlled-RAG system that retrieves official legal text, validates exact law/article references, ties claims to evidence, and abstains when verified evidence is insufficient. [project-openlegama-moroccan-legal-ai]\n"
                f"2. **Evaluation evidence** — {tests}; {curated} curated benchmark + {holdout} independent holdout; {indexed} indexed legal articles from {texts} active legal texts; document Recall@5 = {recall5}; exact-article recall = {exact} on the measured benchmarks. [project-openlegama-moroccan-legal-ai]\n"
                "3. **Current professional practice** — his freelance work explicitly includes RAG systems, LLM-powered applications, AI agents, and document-intelligence workflows. [experience-education]\n"
                "4. **Supporting stack** — RAG, embeddings, semantic search, document processing, prompt/context engineering, NLP, and evaluation. [skills]\n\n"
                "So the evidence is **a public evaluated RAG product + current applied work + the underlying retrieval/evaluation stack**."
            )
        return StructuredFactAnswer(text, source="project-openlegama-moroccan-legal-ai", evidence="Evidence hierarchy: evaluated RAG product, current professional practice, then supporting skills.")

    def _resolve_strongest_projects(self, question: str, language: str):
        normalized = _precision._normalize(question)
        has_project = "project" in normalized or "projet" in normalized or "مشروع" in normalized or "مشاريع" in normalized
        if not has_project or not any(hint in normalized for hint in _STRONGEST_PROJECT_HINTS):
            return None
        accident = self._project_by_slug("real-time-road-accident-detection") or {}
        legal = self._project_by_slug("openlegama-moroccan-legal-ai") or {}
        ar = accident.get("results") or {}
        lr = legal.get("results") or {}
        precision = str(ar.get("precision") or "86.68%")
        recall = str(ar.get("recall") or "91.56%")
        fps = str(ar.get("inferenceSpeed") or "31.5 FPS")
        tests = str(lr.get("automatedTests") or "143 / 143 passing")
        indexed = str(lr.get("indexedArticles") or "7,708")
        curated = str(lr.get("curatedBenchmark") or "610 cases")
        holdout = str(lr.get("holdoutBenchmark") or "120 cases")
        if language == "fr":
            text = (
                "Si on les classe par **profondeur technique, preuves mesurées et valeur AI Engineering**, les projets les plus forts sont :\n\n"
                f"1. **Real-Time Road Accident Detection** — projet PFE réalisé chez NEXTRONIC — ABA Technology : YOLOv11, BoT-SORT, OpenCV et analyse comportementale, avec {precision} de précision, {recall} de rappel et environ {fps}. [project-real-time-road-accident-detection] [experience-education]\n"
                f"2. **OpenLegaMa — Moroccan Legal AI Assistant** — Controlled RAG multilingue avec citations/abstention et évaluation sérieuse : {tests}, {curated} + {holdout}, {indexed} articles indexés. [project-openlegama-moroccan-legal-ai]\n"
                "3. **Customer MLOps Pipeline** — pipeline ML end-to-end avec Airflow, MLflow, MinIO, PostgreSQL, Docker Compose et monitoring Streamlit, montrant la capacité à industrialiser un workflow ML. [project-customer-churn-mlops-platform]\n\n"
                "Ces trois projets montrent trois dimensions complémentaires : **Computer Vision temps réel**, **RAG/LLM fiable**, et **MLOps/production ML**."
            )
        elif language == "ar":
            text = (
                "إذا رتبنا المشاريع حسب **العمق التقني والنتائج المقاسة وقيمة AI Engineering** فأقوى المشاريع هي:\n\n"
                f"1. **Real-Time Road Accident Detection** — مشروع PFE لدى NEXTRONIC — ABA Technology باستخدام YOLOv11 وBoT-SORT وOpenCV، بدقة {precision} واسترجاع {recall} وسرعة تقارب {fps}. [project-real-time-road-accident-detection] [experience-education]\n"
                f"2. **OpenLegaMa** — نظام Controlled RAG متعدد اللغات مع citations وabstention وتقييم: {tests}، و{curated} + {holdout}، و{indexed} مادة قانونية مفهرسة. [project-openlegama-moroccan-legal-ai]\n"
                "3. **Customer MLOps Pipeline** — خط ML متكامل باستخدام Airflow وMLflow وMinIO وPostgreSQL وDocker وStreamlit. [project-customer-churn-mlops-platform]\n\n"
                "المشاريع الثلاثة تثبت قدراته في **الرؤية الحاسوبية الآنية، RAG/LLM، وMLOps**."
            )
        else:
            text = (
                "Based on **technical depth, measured evidence, and AI-engineering value**, his strongest portfolio projects are:\n\n"
                f"1. **Real-Time Road Accident Detection** — PFE work at NEXTRONIC — ABA Technology using YOLOv11, BoT-SORT, OpenCV, and behavioral analysis; {precision} precision, {recall} recall, and about {fps} on the image benchmark. [project-real-time-road-accident-detection] [experience-education]\n"
                f"2. **OpenLegaMa — Moroccan Legal AI Assistant** — multilingual controlled RAG with grounded citations and abstention; {tests}, {curated} curated benchmark + {holdout} holdout, and {indexed} indexed legal articles. [project-openlegama-moroccan-legal-ai]\n"
                "3. **Customer MLOps Pipeline** — an end-to-end ML production workflow with Airflow orchestration, MLflow experiment tracking, MinIO artifacts, PostgreSQL, Docker Compose, and Streamlit monitoring. [project-customer-churn-mlops-platform]\n\n"
                "Together they show three complementary strengths: **real-time Computer Vision, reliable RAG/LLM systems, and production-oriented MLOps**."
            )
        return StructuredFactAnswer(text, source="project-real-time-road-accident-detection", evidence="Projects ranked by professional context, measured evaluation, system depth, and production relevance.")

    def _resolve_broad_certifications_quality(self, question: str, language: str):
        normalized = _precision._normalize(question)
        if not any(re.search(pattern, normalized, re.I) for pattern in _precision._BROAD_CERT_PATTERNS):
            return None
        wanted = [
            "Oracle Agentic AI Certified Foundations Associate",
            "Oracle AI Database Certified Foundations Associate",
            "Oracle Cloud Infrastructure 2026 Certified Architect Associate",
            "Machine Learning with Python Professional Certificate by Anaconda",
            "OpenCV Bootcamp",
            "Vision Language Models (VLM) Bootcamp",
            "PyTorch Bootcamp",
            "Building with the Claude API",
            "Model Context Protocol: Advanced Topics",
        ]
        selected = []
        for title in wanted:
            row = self._cert_by_title(title)
            if row is not None:
                selected.append(row)
        counts = {}
        for row in self.certifications:
            issuer = str(row.get("issuer") or "").strip()
            if issuer:
                counts[issuer] = counts.get(issuer, 0) + 1
        lines = "\n".join(f"• **{row.get('title')}** — {row.get('issuer')}" for row in selected)
        issuer_names = ", ".join(sorted(counts, key=str.lower))
        if language == "fr":
            text = (
                f"Youssef a **{len(self.certifications)} certifications/certificats** au total. Plutôt que de les énumérer sans hiérarchie, voici les plus pertinentes pour son positionnement AI Engineer :\n\n{lines}\n\n"
                f"Le reste couvre notamment Anthropic/Claude, LinkedIn, IBM, OpenCV, data science, deep learning, prompt engineering et MLOps. Les organismes présents dans le portfolio sont : {issuer_names}. [certifications]\n\n"
                "Si vous demandez **« list all certifications »**, le copilote peut afficher la liste complète."
            )
        elif language == "ar":
            text = (
                f"لدى يوسف **{len(self.certifications)} شهادة/اعتماداً** بالمجموع. بدلاً من سردها كلها دون ترتيب، هذه أبرز الشهادات الأكثر ارتباطاً بمسار AI Engineer:\n\n{lines}\n\n"
                f"وتغطي بقية الشهادات Claude/Anthropic وLinkedIn وIBM وOpenCV وData Science وDeep Learning وPrompt Engineering وMLOps. الجهات الموجودة في الملف: {issuer_names}. [certifications]\n\n"
                "يمكن عرض القائمة الكاملة عند طلب جميع الشهادات صراحةً."
            )
        else:
            text = (
                f"Youssef currently has **{len(self.certifications)} certifications/certificates** in his public portfolio. Rather than dumping all of them without context, these are the most career-relevant highlights for an AI Engineer profile:\n\n{lines}\n\n"
                f"The remaining credentials cover Claude/Anthropic, LinkedIn learning, IBM, OpenCV, data science, deep learning, prompt engineering, and MLOps. Issuers represented in the portfolio include: {issuer_names}. [certifications]\n\n"
                "If you ask for **all certifications**, I can return the complete inventory."
            )
        return StructuredFactAnswer(text, source="certifications", evidence="Broad certification answer ranked for career relevance while preserving the complete synchronized total.")

    def _resolve_current_work(self, question: str, language: str):
        if not self._matches(_precision._CURRENT_PATTERNS, question):
            return None
        row = self._current_row()
        if row is None:
            return None
        career = self.profile.get("career_status") or {}
        seeking = isinstance(career, dict) and career.get("seeking_full_time") is True
        if language == "fr":
            role = str(row.get("role_fr") or row.get("role") or "Ingénieur IA/ML Freelance").strip()
            period = str(row.get("period_fr") or row.get("period") or "").strip()
            description = str(row.get("description_fr") or row.get("description") or "").strip()
            text = f"Actuellement, Youssef exerce comme **{role}**, en indépendant via Fiverr"
            if period:
                text += f" ({period})"
            text += "."
            if description:
                text += f" {description}"
            text += " Ses activités documentées comprennent notamment des **Systèmes RAG**, des applications LLM, des agents IA, du Machine Learning et de la vision par ordinateur. [experience-education]"
            if seeking:
                text += "\n\nIl **n’a pas choisi le freelance à la place d’un CDI** : il recherche une opportunité en CDI à temps plein comme AI Engineer, Computer Vision Engineer, Machine Learning Engineer ou Data Scientist. Le freelance est une activité parallèle. [career-status]"
        elif language == "ar":
            text = "حالياً، يعمل يوسف كمهندس ذكاء اصطناعي وتعلّم آلي مستقل عبر Fiverr منذ سبتمبر 2026. يركز عمله الموثق على أنظمة RAG وتطبيقات LLM، ووكلاء الذكاء الاصطناعي وذكاء الوثائق، وحلول تعلم الآلة والرؤية الحاسوبية. [experience-education]"
            if seeking:
                text += "\n\nلكنه **لم يختر العمل الحر بدلاً من الوظيفة الدائمة**؛ فهو يبحث حالياً عن فرصة **بدوام كامل** في AI/ML، والعمل الحر نشاط موازٍ. [career-status]"
        else:
            role = str(row.get("role") or "Freelance AI/ML Engineer").strip()
            period = str(row.get("period") or "").strip()
            description = str(row.get("description") or "").strip()
            text = f"Right now, Youssef works as a **{role}**, independently via Fiverr"
            if period:
                text += f" ({period})"
            text += "."
            if description:
                text += f" {description}"
            text += " His documented work includes RAG systems, LLM applications, AI agents, Machine Learning, and Computer Vision. [experience-education]"
            if seeking:
                text += "\n\nHe **has not chosen freelancing instead of a full-time career**: he is actively seeking a **full-time AI/ML role**. Freelancing is a parallel activity. [career-status]"
        return StructuredFactAnswer(text, source="experience-education")

    def _resolve_certifications(self, question, history, language):
        normalized = _precision._normalize(question)
        if language == "fr" and re.search(r"\bcombien\s+de\s+(?:certificats?|certifications?)\b", normalized, re.I):
            tokens = _precision._tokens(question)
            if "youssef" in normalized or "il" in tokens or "lui" in tokens:
                return StructuredFactAnswer(f"Le profil professionnel public de Youssef répertorie exactement {len(self.certifications)} certifications. [certifications]", source="certifications")
        result = self._resolve_broad_certifications_quality(question, language)
        if result is not None:
            return result
        return super()._resolve_certifications(question, history, language)

    def resolve(self, question, history=None):
        language = self._effective_language(question)
        normalized = _precision._normalize(question)
        for resolver in (
            lambda: self._resolve_why_youssef(question, language),
            lambda: self._resolve_experience_overview(question, language),
            lambda: self._resolve_domain_evidence(question, language),
            lambda: self._resolve_strongest_projects(question, language),
        ):
            result = resolver()
            if result is not None:
                return result
        if language == "en" and re.search(r"\b(?:phone|telephone|mobile)\s*(?:number)?\b", normalized, re.I):
            return StructuredFactAnswer("The synchronized public professional profile does not provide a public phone number for Youssef, so no public phone number is available from the portfolio. I won't infer or invent unpublished personal information.", source="structured-profile", evidence="No public phone field is present in the synchronized professional profile.")
        return super().resolve(question, history)

    def _resolve_employer(self, question: str, language: str):
        original = self._extract_employer_target(question)
        clean = self._extract_employer_target_clean(question)
        if not clean:
            return None
        if original and _precision._normalize(original) == _precision._normalize(clean):
            result = _live._base.StructuredFactResolver._resolve_employer(self, question, language)
            if result is not None:
                return result
        target_norm = _precision._normalize(clean)
        matches = [row for row in self.experiences if target_norm in _precision._normalize(str(row.get("company") or "")) or _precision._normalize(str(row.get("company") or "")) in target_norm]
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