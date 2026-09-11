"""Evidence-first professional answer layer for Ask Youssef AI.

The preserved production resolver remains the source of truth for exact counts,
contact/privacy behavior, safety, and legacy conversational contracts. This shim
adds a recruiter/client answer planner for high-value questions where generic
RAG can select the wrong evidence.

Evidence priority:
professional experience -> measured/shipped projects -> technical projects
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
    r"\bwhat is (?:youssef|he) doing professionally (?:right now|now|currently)\b",
)

_LITERAL_EXPRESSION_HINTS = {
    "citation", "citations", "phrase", "phrases", "dicton", "dictons",
    "quote", "quotes", "saying", "sayings", "mots", "favori", "favorite",
}

_EXPERIENCE_PATTERNS = (
    r"\b(?:donne(?:\s+moi)?|montre(?:\s+moi)?|liste|quelles?\s+sont)\b.*\b(?:experiences?|expériences?|expressions?)\b.*\byoussef\b",
    r"\b(?:experiences?|expériences?|expressions?)\s+(?:professionnelles?\s+)?(?:de|d['’])\s*youssef\b",
    r"\b(?:tell me|show me|list)\b.*\b(?:experience|experiences)\b.*\byoussef\b",
    r"\b(?:youssef['’]?s|his)\s+(?:work\s+)?experiences?\b",
    r"خبرات.*يوسف|تجارب.*يوسف",
)

_WHY_PATTERNS = (
    r"\bwhy\s+(?:should\s+.+?\s+)?(?:choose|hire|pick|recruit)\s+youssef\b",
    r"\bwhy\s+youssef\s+(?:instead of|over|and not)\b",
    r"\bwhat makes youssef different\b",
    r"\bwhat differentiates youssef\b",
    r"\b(?:pourquoi|pour\s+quoi)\s+(?:choisir|recruter|prendre|embaucher)\s+youssef\b",
    r"\b(?:pourquoi|pour\s+quoi)\s+youssef.*(?:autre|candidat|profil)\b",
    r"لماذا.*يوسف.*(?:وليس|بدل|اختيار)|ما الذي يميز.*يوسف",
)

_OVERVIEW_PATTERNS = (
    r"^\s*tell me about youssef(?: bouzit)?[?.!]*\s*$",
    r"^\s*who is youssef(?: bouzit)?[?.!]*\s*$",
    r"^\s*introduce youssef(?: bouzit)?[?.!]*\s*$",
    r"^\s*(?:parle|parlez)[ -]moi de youssef(?: bouzit)?[?.!]*\s*$",
    r"^\s*(?:presente|présente|présentez) youssef(?: bouzit)?[?.!]*\s*$",
    r"عرفني.*يوسف|من هو يوسف",
)

# This must require an explicit full-time-vs-freelance contrast. Simple job-search
# questions are intentionally left to the preserved career-status resolver.
_CURRENT_VS_FREELANCE = (
    r"\bfull[- ]time\b.*\bfreelanc",
    r"\bfreelanc.*\bfull[- ]time\b",
    r"\bcdi\b.*\bfreelanc",
    r"\bfreelanc.*\bcdi\b",
    r"\bchosen freelanc",
    r"\bchoisi.*freelanc",
)

_DOMAIN_EVIDENCE_HINTS = (
    "experience", "background", "expertise", "skill", "skills", "evidence",
    "proof", "prove", "hands-on", "practical", "worked", "work",
    "compétence", "compétences", "preuve", "preuves", "maîtrise",
    "خبرة", "مهارة", "مهارات", "دليل",
)

_STRONG_HINTS = (
    "strongest", "best", "top", "most impressive", "flagship",
    "meilleur", "meilleurs", "plus fort", "plus forts", "phare", "phares",
    "أقوى", "أفضل",
)


class StructuredFactResolver(_live.StructuredFactResolver):
    @staticmethod
    def _effective_language(question: str) -> str:
        raw = question or ""
        if re.search(r"[\u0600-\u06FF]", raw):
            return "ar"
        normalized = _precision._normalize(raw)
        french = (
            "c kwa", "c'est quoi", "son mail", "mail pro", "dis que", "meme si",
            "chomage", "chomeur", "travaille chez", "donne moi", "quel age",
            "combien", "emploi", "travail ou nn", "pourquoi", "pour quoi",
            "expressions de", "experiences de", "expérience de", "preuve",
            "compétence", "projet phare", "meilleur projet", "limites",
        )
        return "fr" if any(x in normalized for x in french) else _precision.detect_language(raw)

    @staticmethod
    def _matches_any(patterns, question: str) -> bool:
        n = _precision._normalize(question)
        return any(re.search(pattern, n, re.I) for pattern in patterns)

    @staticmethod
    def _referent(n: str) -> bool:
        padded = f" {n} "
        return any(x in padded for x in (" youssef ", " his ", " he ", " son ", " ses ", " il ", " يوسف "))

    def _project(self, slug: str):
        target = _precision._normalize(slug)
        return next(
            (x for x in self.projects if _precision._normalize(str(x.get("slug") or "")) == target),
            None,
        )

    def _experience(self, fragment: str):
        target = _precision._normalize(fragment)
        return next(
            (x for x in self.experiences if target in _precision._normalize(str(x.get("company") or ""))),
            None,
        )

    def _cert(self, title: str):
        target = _precision._normalize(title)
        return next(
            (x for x in self.certifications if _precision._normalize(str(x.get("title") or "")) == target),
            None,
        )

    def _seeking(self) -> bool:
        career = self.profile.get("career_status") or {}
        return isinstance(career, dict) and career.get("seeking_full_time") is True

    def _current_row(self):
        return next(
            (
                x for x in self.experiences
                if "present" in _precision._normalize(str(x.get("period") or ""))
                or "aujourd" in _precision._normalize(str(x.get("period_fr") or ""))
            ),
            None,
        )

    def _overview(self, question: str, language: str):
        if not self._matches_any(_OVERVIEW_PATTERNS, question):
            return None
        accident = self._project("real-time-road-accident-detection") or {}
        legal = self._project("openlegama-moroccan-legal-ai") or {}
        ar = accident.get("results") or {}
        lr = legal.get("results") or {}

        if language == "fr":
            text = (
                "Youssef Bouzit est **Ingénieur d’État en Data Science** orienté AI Engineering. "
                "Il exerce actuellement comme **Ingénieur IA/ML Freelance, en indépendant via Fiverr**, "
                "tout en recherchant activement un **CDI à temps plein en AI/ML**. [career-status] [experience-education]\n\n"
                f"Ses preuves fortes incluent un PFE Computer Vision chez NEXTRONIC — ABA Technology "
                f"({ar.get('precision','86.68%')} précision, {ar.get('recall','91.56%')} rappel, ~{ar.get('inferenceSpeed','31.5 FPS')}) "
                "[project-real-time-road-accident-detection], ainsi qu’OpenLegaMa, un Controlled RAG évalué avec "
                f"{lr.get('automatedTests','143 / 143 passing')} et {lr.get('indexedArticles','7,708')} articles indexés "
                "[project-openlegama-moroccan-legal-ai]."
            )
        elif language == "ar":
            text = (
                "يوسف بوزيت **مهندس دولة في علم البيانات** وموجه نحو AI Engineering. يعمل حالياً "
                "**كمهندس AI/ML مستقل عبر Fiverr** ويبحث بالتوازي عن وظيفة بدوام كامل في AI/ML. "
                "[career-status] [experience-education]\n\n"
                f"من أقوى أدلته مشروع Computer Vision بنتائج {ar.get('precision','86.68%')} دقة و"
                f"{ar.get('recall','91.56%')} استرجاع، ومشروع OpenLegaMa المقاس بـ "
                f"{lr.get('automatedTests','143 / 143 passing')}. "
                "[project-real-time-road-accident-detection] [project-openlegama-moroccan-legal-ai]"
            )
        else:
            text = (
                "Youssef Bouzit is a **State Engineer in Data Science** focused on AI Engineering. "
                "He currently works as an **independent Freelance AI/ML Engineer via Fiverr**, while actively seeking a "
                "**full-time AI/ML role**. [career-status] [experience-education]\n\n"
                f"His strongest evidence includes professional Computer Vision PFE work at NEXTRONIC — ABA Technology "
                f"({ar.get('precision','86.68%')} precision, {ar.get('recall','91.56%')} recall, ~{ar.get('inferenceSpeed','31.5 FPS')}) "
                "[project-real-time-road-accident-detection], plus OpenLegaMa, an evaluated controlled-RAG system with "
                f"{lr.get('automatedTests','143 / 143 passing')} and {lr.get('indexedArticles','7,708')} indexed legal articles "
                "[project-openlegama-moroccan-legal-ai]."
            )
        return StructuredFactAnswer(text, source="experience-education")

    def _current(self, question: str, language: str):
        current = self._matches(_precision._CURRENT_PATTERNS, question)
        compare = self._matches_any(_CURRENT_VS_FREELANCE, question)
        if not current and not compare:
            return None

        if compare:
            if language == "fr":
                text = (
                    "Youssef **n’a pas choisi le freelance à la place d’un CDI**. Son objectif principal reste un "
                    "**CDI à temps plein en AI/ML** ; le freelance est une **activité parallèle**, menée "
                    "**en indépendant via Fiverr**. [career-status] [experience-education]"
                )
            elif language == "ar":
                text = (
                    "يوسف **لم يختر العمل الحر بدلاً من المسار الوظيفي بدوام كامل**. هدفه الرئيسي ما زال وظيفة "
                    "بدوام كامل في AI/ML، بينما العمل الحر نشاط موازٍ يتم بشكل مستقل عبر Fiverr. "
                    "[career-status] [experience-education]"
                )
            else:
                text = (
                    "Youssef **has not chosen freelancing instead of a full-time career**. His main goal remains a "
                    "**full-time AI/ML role**; freelancing is a parallel activity carried out **independently via Fiverr**. "
                    "[career-status] [experience-education]"
                )
            return StructuredFactAnswer(text, source="career-status")

        row = self._current_row() or {}
        if language == "fr":
            period = str(row.get("period_fr") or "Sept 2026 — Aujourd’hui").strip()
            text = (
                f"Actuellement, Youssef exerce comme **Ingénieur IA/ML Freelance, en indépendant via Fiverr** ({period}). "
                "Son travail documenté couvre notamment les **Systèmes RAG**, les applications LLM, les agents IA, "
                "le Machine Learning et la Computer Vision. [experience-education]"
            )
            if self._seeking():
                text += (
                    " Son activité freelance reste une **activité parallèle** ; il **recherche une opportunité en CDI "
                    "à temps plein en AI/ML**. [career-status]"
                )
        elif language == "ar":
            text = (
                "حالياً، يعمل يوسف **كمهندس AI/ML مستقل عبر Fiverr منذ سبتمبر 2026** في أنظمة RAG، "
                "وتطبيقات LLM، ووكلاء الذكاء الاصطناعي، وMachine Learning وComputer Vision. "
                "[experience-education]"
            )
            if self._seeking():
                text += " وبالتوازي، يبحث عن فرصة عمل **بدوام كامل** في AI/ML. [career-status]"
        else:
            period = str(row.get("period") or "Sep 2026 — Present").strip()
            text = (
                f"Right now, Youssef works as an **independent Freelance AI/ML Engineer via Fiverr** ({period}). "
                "His documented work includes RAG systems, LLM applications, AI agents, Machine Learning, and Computer Vision. "
                "[experience-education]"
            )
            if self._seeking():
                text += (
                    " Freelancing is a **parallel activity**; he is actively seeking a **full-time AI/ML role**. "
                    "[career-status]"
                )
        return StructuredFactAnswer(text, source="experience-education")

    def _resolve_current_work(self, question: str, language: str):
        result = self._current(question, language)
        if result is not None:
            return result
        return super()._resolve_current_work(question, language)

    def _resolve_unemployment(self, question: str, language: str):
        n = _precision._normalize(question)
        if not any(x in n for x in ("chomage", "chomeur", "unemployed", "jobless", "عاطل", "البطالة")):
            return None
        if language == "fr":
            text = (
                "Non. Youssef **n’est pas au chômage** selon son profil professionnel public : il exerce actuellement "
                "comme **Ingénieur IA/ML Freelance en indépendant via Fiverr**."
            )
            if self._seeking():
                text += " En parallèle, il recherche activement un **CDI à temps plein**."
        elif language == "ar":
            text = "لا. وفق ملفه المهني العام، يوسف ليس عاطلاً عن العمل؛ فهو يعمل حالياً كمهندس AI/ML مستقل عبر Fiverr."
            if self._seeking():
                text += " وبالتوازي، يبحث عن فرصة عمل بدوام كامل."
        else:
            text = "No. According to his public profile, Youssef is not unemployed; he currently works independently as a Freelance AI/ML Engineer via Fiverr."
            if self._seeking():
                text += " In parallel, he is actively seeking a full-time opportunity."
        citations = " [experience-education]"
        if self._seeking():
            citations += " [career-status]"
        return StructuredFactAnswer(text + citations, source="experience-education")

    def _why(self, question: str, language: str):
        if not self._matches_any(_WHY_PATTERNS, question):
            return None
        accident = self._project("real-time-road-accident-detection") or {}
        legal = self._project("openlegama-moroccan-legal-ai") or {}
        ar, lr = accident.get("results") or {}, legal.get("results") or {}
        if language == "fr":
            text = (
                "Je ne peux pas affirmer que Youssef est « meilleur que tous les autres » sans comparer les candidats. "
                "En revanche, son profil donne plusieurs **raisons concrètes** de le recruter :\n\n"
                "• **Expérience professionnelle Computer Vision** chez NEXTRONIC — ABA Technology. [experience-education]\n"
                f"• **Résultats mesurés** : {ar.get('precision','86.68%')} précision, {ar.get('recall','91.56%')} rappel et ~{ar.get('inferenceSpeed','31.5 FPS')}. [project-real-time-road-accident-detection]\n"
                f"• **RAG/LLM évalué** : OpenLegaMa avec {lr.get('automatedTests','143 / 143 passing')} et {lr.get('indexedArticles','7,708')} articles indexés. [project-openlegama-moroccan-legal-ai]\n"
                "• **Profil end-to-end** : Computer Vision, ML, RAG/LLM, MLOps, APIs, évaluation et déploiement. [skills]\n"
                "• **Recherche active d’un CDI AI/ML** ; freelance en parallèle. [career-status]\n\n"
                "Sa différence est la combinaison **expérience terrain + systèmes complets + preuves mesurables**."
            )
        elif language == "ar":
            text = (
                "لا يمكنني القول إنه أفضل من مرشحين لم تتم مقارنتهم، لكن ملفه يقدم أسباباً عملية لتوظيفه:\n\n"
                "• خبرة مهنية في Computer Vision لدى NEXTRONIC — ABA Technology. [experience-education]\n"
                f"• نتائج مقاسة: {ar.get('precision','86.68%')} دقة و{ar.get('recall','91.56%')} استرجاع و~{ar.get('inferenceSpeed','31.5 FPS')}. [project-real-time-road-accident-detection]\n"
                f"• OpenLegaMa موثق بـ {lr.get('automatedTests','143 / 143 passing')} و{lr.get('indexedArticles','7,708')} مادة مفهرسة. [project-openlegama-moroccan-legal-ai]\n"
                "• قدرة end-to-end عبر AI/ML وComputer Vision وRAG/LLM وMLOps. [skills] [career-status]"
            )
        else:
            text = (
                "I cannot claim he is better than an unexamined candidate, but his portfolio gives concrete reasons to hire him:\n\n"
                "• **Professional Computer Vision experience** at NEXTRONIC — ABA Technology. [experience-education]\n"
                f"• **Measured results**: {ar.get('precision','86.68%')} precision, {ar.get('recall','91.56%')} recall, ~{ar.get('inferenceSpeed','31.5 FPS')}. [project-real-time-road-accident-detection]\n"
                f"• **Evaluated RAG/LLM work**: OpenLegaMa with {lr.get('automatedTests','143 / 143 passing')} and {lr.get('indexedArticles','7,708')} indexed articles. [project-openlegama-moroccan-legal-ai]\n"
                "• **End-to-end range** across CV, ML, RAG/LLM, MLOps, APIs, evaluation, and deployment. [skills]\n"
                "• **Actively seeking a full-time AI/ML role**; freelancing is parallel work. [career-status]\n\n"
                "The differentiator is **hands-on experience + complete systems + measurable evidence**."
            )
        return StructuredFactAnswer(text, source="career-status")

    def _experience_overview(self, question: str, language: str):
        tokens = _precision._tokens(question)
        typo = "expression" in tokens or "expressions" in tokens
        if typo and tokens & _LITERAL_EXPRESSION_HINTS:
            return None
        if not self._matches_any(_EXPERIENCE_PATTERNS, question) or not self.experiences:
            return None

        if language == "fr":
            lines = [
                "Si par « expressions » tu voulais dire **expériences professionnelles**, voici les principales :"
                if typo else "Voici les principales expériences professionnelles de Youssef :"
            ]
        elif language == "ar":
            lines = ["أهم الخبرات المهنية الموثقة ليوسف هي:"]
        else:
            lines = ["Youssef's main documented professional experiences are:"]

        for index, row in enumerate(self.experiences, 1):
            if language == "fr":
                role = str(row.get("role_fr") or row.get("role") or "").strip()
                company = str(row.get("company_fr") or row.get("company") or "").strip()
                period = str(row.get("period_fr") or row.get("period") or "").strip()
                desc = str(row.get("description_fr") or row.get("description") or "").strip()
                if "fiverr" in _precision._normalize(company) and "freelance" in _precision._normalize(role):
                    lines.append(f"{index}. **{role} en indépendant, via {company}** — {period}. {desc}")
                else:
                    lines.append(f"{index}. **{role} — {company}** — {period}. {desc}")
            else:
                role = str(row.get("role") or "").strip()
                company = str(row.get("company") or "").strip()
                period = str(row.get("period") or "").strip()
                desc = str(row.get("description") or "").strip()
                if "fiverr" in _precision._normalize(company) and "freelance" in _precision._normalize(role):
                    lines.append(f"{index}. **{role}, independently via {company}** — {period}. {desc}")
                else:
                    lines.append(f"{index}. **{role} — {company}** — {period}. {desc}")

        if self._seeking():
            if language == "fr":
                lines.append("\nAujourd’hui, le freelance est une **activité parallèle** : Youssef recherche toujours activement un **CDI à temps plein en AI/ML**. [career-status]")
            elif language == "ar":
                lines.append("\nالعمل الحر نشاط موازٍ؛ يوسف ما زال يبحث عن فرصة عمل بدوام كامل في AI/ML. [career-status]")
            else:
                lines.append("\nFreelancing is a **parallel activity**; Youssef is still actively seeking a **full-time AI/ML role**. [career-status]")
        lines.append("[experience-education]")
        return StructuredFactAnswer("\n".join(lines), source="experience-education")

    # Compatibility contract used directly by regression tests and older callers.
    def _resolve_experience_overview(self, question: str, language: str):
        return self._experience_overview(question, language)

    def _domain_evidence(self, question: str, language: str):
        n = _precision._normalize(question)
        if self._matches(_precision._COUNT_PATTERNS, question) or self._matches(_precision._LIST_ALL_PATTERNS, question):
            return None
        if not self._referent(n) or not any(x in n for x in _DOMAIN_EVIDENCE_HINTS):
            return None
        cv = "computer vision" in n or "vision par ordinateur" in n or "الرؤية الحاسوبية" in n
        rag = any(x in n for x in ("rag", "retrieval augmented", "llm", "large language model", "generative ai", "ia générative"))
        if not cv and not rag:
            return None

        if cv:
            accident = self._project("real-time-road-accident-detection") or {}
            exp = self._experience("NEXTRONIC") or {}
            r = accident.get("results") or {}
            period = str(exp.get("period") or "Feb 2026 — Aug 2026")
            if language == "fr":
                text = (
                    "Son expérience en **Computer Vision est pratique et professionnelle** :\n\n"
                    f"1. **NEXTRONIC — ABA Technology ({period})** — stage AI/ML orienté Computer Vision. [experience-education]\n"
                    f"2. **Preuves mesurées sur le PFE** — YOLOv11 + BoT-SORT + OpenCV : {r.get('precision','86.68%')} précision, {r.get('recall','91.56%')} rappel, {r.get('f1Score','89.06%')} F1 et ~{r.get('inferenceSpeed','31.5 FPS')}. [project-real-time-road-accident-detection]\n"
                    "3. **Traffic MVP** — second système temps réel YOLOv8 + OpenCV, CSV et Streamlit. [project-traffic-mvp-image-processing]\n\n"
                    "Stack démontrée : Python, YOLOv8/YOLOv11, OpenCV, BoT-SORT, tracking, real-time video et Roboflow. [skills]"
                )
            else:
                text = (
                    "Youssef's **Computer Vision experience is hands-on and professional**, not just coursework:\n\n"
                    f"1. **NEXTRONIC — ABA Technology ({period})** — AI/ML Engineer Intern focused on Computer Vision. [experience-education]\n"
                    f"2. **Measured PFE evidence** — YOLOv11 + BoT-SORT + OpenCV: {r.get('precision','86.68%')} precision, {r.get('recall','91.56%')} recall, {r.get('f1Score','89.06%')} F1-score, and ~{r.get('inferenceSpeed','31.5 FPS')}. [project-real-time-road-accident-detection]\n"
                    "3. **Traffic MVP** — a second real-time vision system with YOLOv8 + OpenCV, CSV metrics, and Streamlit. [project-traffic-mvp-image-processing]\n\n"
                    "Demonstrated stack: Python, YOLOv8/YOLOv11, OpenCV, BoT-SORT, object detection, tracking, real-time video, and Roboflow. [skills]"
                )
            return StructuredFactAnswer(text, source="project-real-time-road-accident-detection")

        legal = self._project("openlegama-moroccan-legal-ai") or {}
        r = legal.get("results") or {}
        if language == "fr":
            text = (
                "La preuve la plus forte de ses compétences **RAG/LLM** est un système construit et évalué :\n\n"
                "1. **OpenLegaMa** — Controlled RAG multilingue, validation de références, citations reliées aux preuves et abstention. [project-openlegama-moroccan-legal-ai]\n"
                f"2. **Évaluation** — {r.get('automatedTests','143 / 143 passing')}; {r.get('curatedBenchmark','610 cases')} + {r.get('holdoutBenchmark','120 cases')}; "
                f"{r.get('indexedArticles','7,708')} articles; Recall@5={r.get('documentRecallAt5','100% curated')}; exact-article recall={r.get('exactArticleRecall','100% measured')}. [project-openlegama-moroccan-legal-ai]\n"
                "3. **Pratique actuelle** — RAG, applications LLM, agents IA et document intelligence. [experience-education]\n"
                "4. **Stack** — embeddings, semantic search, document processing, prompt/context engineering et évaluation. [skills]"
            )
        else:
            text = (
                "The strongest evidence of Youssef's **RAG and LLM skills is a built and evaluated system**, not just training:\n\n"
                "1. **OpenLegaMa — Moroccan Legal AI Assistant** — multilingual controlled RAG with exact-reference validation, grounded citations, and abstention. [project-openlegama-moroccan-legal-ai]\n"
                f"2. **Evaluation evidence** — {r.get('automatedTests','143 / 143 passing')}; {r.get('curatedBenchmark','610 cases')} curated benchmark + {r.get('holdoutBenchmark','120 cases')} independent holdout; "
                f"{r.get('indexedArticles','7,708')} indexed articles; document Recall@5 = {r.get('documentRecallAt5','100% curated')}; exact-article recall = {r.get('exactArticleRecall','100% measured')}. [project-openlegama-moroccan-legal-ai]\n"
                "3. **Current professional practice** — his freelance work includes RAG systems, LLM applications, AI agents, and document intelligence. [experience-education]\n"
                "4. **Supporting stack** — embeddings, semantic search, document processing, prompt/context engineering, NLP, and evaluation. [skills]"
            )
        return StructuredFactAnswer(text, source="project-openlegama-moroccan-legal-ai")

    def _realtime(self, question: str, language: str):
        n = _precision._normalize(question)
        if not self._referent(n) or not any(x in n for x in ("real-time", "real time", "temps reel", "temps réel")):
            return None
        if not any(x in n for x in ("ai", "system", "systems", "système", "worked", "experience", "evidence", "proof", "project", "projet")):
            return None
        accident = self._project("real-time-road-accident-detection") or {}
        traffic = self._project("traffic-mvp-image-processing") or {}
        ar, tr = accident.get("results") or {}, traffic.get("results") or {}
        if language == "fr":
            text = (
                "Oui. Il a construit au moins **deux systèmes Computer Vision temps réel** :\n\n"
                f"• **Road Accident Detection** — PFE chez NEXTRONIC — ABA Technology ; {ar.get('precision','86.68%')} précision, {ar.get('recall','91.56%')} rappel, ~{ar.get('inferenceSpeed','31.5 FPS')}. [project-real-time-road-accident-detection] [experience-education]\n"
                f"• **Traffic MVP** — YOLOv8 + OpenCV ; le portfolio indique {tr.get('fps','30+ on CPU')}. [project-traffic-mvp-image-processing]"
            )
        else:
            text = (
                "Yes. His portfolio documents at least **two real-time Computer Vision systems**:\n\n"
                f"• **Road Accident Detection** — PFE work at NEXTRONIC — ABA Technology; {ar.get('precision','86.68%')} precision, {ar.get('recall','91.56%')} recall, ~{ar.get('inferenceSpeed','31.5 FPS')}. [project-real-time-road-accident-detection] [experience-education]\n"
                f"• **Traffic MVP** — YOLOv8 + OpenCV; the portfolio records {tr.get('fps','30+ on CPU')}. [project-traffic-mvp-image-processing]"
            )
        return StructuredFactAnswer(text, source="project-real-time-road-accident-detection")

    def _accident_results(self, question: str, language: str):
        n = _precision._normalize(question)
        if "accident" not in n or not any(x in n for x in ("result", "metric", "performance", "achiev", "obtenu", "résultat", "resultat", "نتائج")):
            return None
        project = self._project("real-time-road-accident-detection") or {}
        r = project.get("results") or {}
        if language == "fr":
            text = (
                f"Sur le **benchmark image de test**, le YOLOv11s rapporte **{r.get('precision','86.68%')} précision, {r.get('recall','91.56%')} rappel, "
                f"{r.get('f1Score','89.06%')} F1 et {r.get('inferenceSpeed','31.5 FPS')}** sur un dataset de {r.get('datasetSize','12,716 images')}. "
                "[project-real-time-road-accident-detection]\n\n"
                "Ces métriques ne sont pas une mesure officielle de précision/rappel du pipeline vidéo end-to-end."
            )
        else:
            text = (
                f"On the **held-out image test benchmark**, YOLOv11s reports **{r.get('precision','86.68%')} precision, {r.get('recall','91.56%')} recall, "
                f"{r.get('f1Score','89.06%')} F1-score, and {r.get('inferenceSpeed','31.5 FPS')}** on a dataset of {r.get('datasetSize','12,716 images')}. "
                "[project-real-time-road-accident-detection]\n\n"
                "Those figures are not official end-to-end video precision/recall for the full hybrid pipeline."
            )
        return StructuredFactAnswer(text, source="project-real-time-road-accident-detection")

    def _accident_limits(self, question: str, language: str):
        n = _precision._normalize(question)
        if "accident" not in n or not any(x in n for x in ("limitation", "limit", "weakness", "limite", "faiblesse", "contraint", "قيود")):
            return None
        if language == "fr":
            text = (
                "Les limites publiques documentées sont :\n\n"
                "• **Pas encore de précision/rappel officiel end-to-end vidéo** faute d’annotations temporelles complètes.\n"
                "• **Robustesse réduite** la nuit, sous la pluie et sous forte occlusion.\n"
                "• **Tracking sensible** aux angles de caméra difficiles.\n\n"
                "Les métriques publiées concernent le benchmark image YOLOv11s, pas l’ensemble du pipeline vidéo. "
                "[project-real-time-road-accident-detection]"
            )
        else:
            text = (
                "The public project record documents these limitations:\n\n"
                "• **No official end-to-end video precision/recall yet** without complete temporal annotations.\n"
                "• **Reduced robustness** at night, in rain, and under dense occlusion.\n"
                "• **Tracking remains sensitive** to difficult camera angles.\n\n"
                "The published metrics apply to the YOLOv11s image benchmark, not the full video pipeline. "
                "[project-real-time-road-accident-detection]"
            )
        return StructuredFactAnswer(text, source="project-real-time-road-accident-detection")

    def _openlegama_eval(self, question: str, language: str):
        n = _precision._normalize(question)
        if "openlegama" not in n or not any(x in n for x in ("evaluat", "benchmark", "test", "metric", "mesur", "évalu")):
            return None
        project = self._project("openlegama-moroccan-legal-ai") or {}
        r = project.get("results") or {}
        if language == "fr":
            text = (
                f"OpenLegaMa est évalué avec **{r.get('automatedTests','143 / 143 passing')}**, un benchmark curaté de "
                f"**{r.get('curatedBenchmark','610 cases')}** + **{r.get('holdoutBenchmark','120 cases')} holdout**, "
                f"**Recall@5={r.get('documentRecallAt5','100% curated')}** et **exact-article recall={r.get('exactArticleRecall','100% measured')}**. "
                f"Le corpus mesuré contient {r.get('indexedArticles','7,708')} articles issus de {r.get('activeLegalTexts','30')} textes actifs. "
                "[project-openlegama-moroccan-legal-ai]\n\n"
                "Ces chiffres décrivent les datasets mesurés ; ils ne prétendent pas à une exactitude juridique universelle."
            )
        else:
            text = (
                f"OpenLegaMa's documented evaluation includes **{r.get('automatedTests','143 / 143 passing')}**, "
                f"a **{r.get('curatedBenchmark','610 cases')} curated benchmark** + **{r.get('holdoutBenchmark','120 cases')} holdout**, "
                f"**Recall@5={r.get('documentRecallAt5','100% curated')}**, and **exact-article recall={r.get('exactArticleRecall','100% measured')}**. "
                f"Scope: {r.get('indexedArticles','7,708')} articles from {r.get('activeLegalTexts','30')} active legal texts. "
                "[project-openlegama-moroccan-legal-ai]\n\n"
                "These are measured-dataset results, not a claim of universal legal accuracy or complete Moroccan-law coverage."
            )
        return StructuredFactAnswer(text, source="project-openlegama-moroccan-legal-ai")

    def _top3(self, language: str):
        accident = self._project("real-time-road-accident-detection") or {}
        legal = self._project("openlegama-moroccan-legal-ai") or {}
        ar, lr = accident.get("results") or {}, legal.get("results") or {}
        intro = (
            "Pour un recruteur AI Engineer, je classerais les 3 projets selon **contexte professionnel, profondeur technique, preuves mesurées et valeur de production** :"
            if language == "fr"
            else "For an AI Engineer recruiter, I would rank the top 3 by **professional context, technical depth, measured evidence, and production value**:"
        )
        text = (
            f"{intro}\n\n"
            f"1. **Real-Time Road Accident Detection** — NEXTRONIC — ABA Technology; {ar.get('precision','86.68%')} precision, {ar.get('recall','91.56%')} recall, ~{ar.get('inferenceSpeed','31.5 FPS')}. [project-real-time-road-accident-detection] [experience-education]\n"
            f"2. **OpenLegaMa — Moroccan Legal AI Assistant** — controlled RAG; {lr.get('automatedTests','143 / 143 passing')}, {lr.get('curatedBenchmark','610 cases')} + {lr.get('holdoutBenchmark','120 cases')}, {lr.get('indexedArticles','7,708')} articles. [project-openlegama-moroccan-legal-ai]\n"
            "3. **Customer MLOps Pipeline** — Airflow, MLflow, MinIO, PostgreSQL, Docker Compose, Streamlit. [project-customer-churn-mlops-platform]\n\n"
            "Together they show **real-time Computer Vision + reliable RAG/LLM + MLOps**."
        )
        return StructuredFactAnswer(text, source="project-real-time-road-accident-detection")

    def _project_selection(self, question: str, language: str):
        n = _precision._normalize(question)
        if not any(x in n for x in ("project", "projects", "projet", "projets", "مشروع", "مشاريع")):
            return None
        if not any(x in n for x in _STRONG_HINTS):
            return None

        rank = any(x in n for x in ("rank", "top 3", "top three", "classe", "classer", "3 projets"))
        rag = any(x in n for x in ("rag", "llm", "retrieval augmented", "legal ai"))
        mlops = "mlops" in n or "production" in n or "industrial" in n
        cv = "computer vision" in n or "vision par ordinateur" in n
        ml = "machine learning" in n or re.search(r"\bml\b", n) is not None

        if rank:
            return self._top3(language)
        if rag:
            p = self._project("openlegama-moroccan-legal-ai") or {}
            r = p.get("results") or {}
            return StructuredFactAnswer(
                f"**OpenLegaMa — Moroccan Legal AI Assistant** is Youssef's strongest documented RAG/LLM project. "
                f"It combines multilingual controlled RAG, grounded citations and abstention with {r.get('automatedTests','143 / 143 passing')}, "
                f"{r.get('curatedBenchmark','610 cases')} curated + {r.get('holdoutBenchmark','120 cases')} holdout, and {r.get('indexedArticles','7,708')} indexed articles. "
                "[project-openlegama-moroccan-legal-ai]\n\n"
                "It is important because retrieval, grounding, citation integrity, abstention, multilingual UX, and systematic evaluation are demonstrated in one complete application.",
                source="project-openlegama-moroccan-legal-ai",
            )
        if mlops:
            return StructuredFactAnswer(
                "**Customer MLOps Pipeline** is the clearest project for production/MLOps skills. It combines **Airflow orchestration, MLflow tracking, "
                "MinIO artifact storage, PostgreSQL, Docker Compose, Streamlit monitoring, and an automated deployment workflow**. "
                "[project-customer-churn-mlops-platform]\n\n"
                "It demonstrates the lifecycle around an ML model, not only model training.",
                source="project-customer-churn-mlops-platform",
            )
        if cv or ml:
            p = self._project("real-time-road-accident-detection") or {}
            r = p.get("results") or {}
            domain = "Computer Vision" if cv else "Machine Learning / Deep Learning"
            return StructuredFactAnswer(
                f"**Real-Time Road Accident Detection** is the strongest project for {domain} evidence because it combines professional PFE work at "
                f"NEXTRONIC — ABA Technology with a fine-tuned YOLOv11s and measured results: {r.get('precision','86.68%')} precision, "
                f"{r.get('recall','91.56%')} recall, {r.get('f1Score','89.06%')} F1, and ~{r.get('inferenceSpeed','31.5 FPS')}. "
                "[project-real-time-road-accident-detection] [experience-education]",
                source="project-real-time-road-accident-detection",
            )
        return self._top3(language)

    def _capability(self, question: str, language: str):
        n = _precision._normalize(question)
        if not self._referent(n):
            return None
        legal = self._project("openlegama-moroccan-legal-ai") or {}
        r = legal.get("results") or {}
        grounded = (
            any(x in n for x in ("grounded", "citation", "citations", "hallucination", "abstention"))
            and any(x in n for x in ("experience", "have", "has", "control", "answer"))
        )
        docs = (
            any(x in n for x in ("chatbot", "assistant", "company document", "company documents", "documents", "knowledge base"))
            and any(x in n for x in ("build", "can", "create", "construire"))
        )
        end2end = "end-to-end" in n or "end to end" in n or "de bout en bout" in n

        if grounded:
            return StructuredFactAnswer(
                "Yes. The strongest public evidence is **OpenLegaMa**, a controlled-RAG system that retrieves official text, validates exact references, "
                "grounds claims in accepted evidence, and abstains when evidence is insufficient. "
                f"Measured evaluation includes {r.get('automatedTests','143 / 143 passing')}, Recall@5={r.get('documentRecallAt5','100% curated')}, and "
                f"exact-article recall={r.get('exactArticleRecall','100% measured')}. [project-openlegama-moroccan-legal-ai] [skills]\n\n"
                "This supports hands-on experience with grounding, citations, abstention, and hallucination-risk reduction; it is not a claim of universal hallucination elimination.",
                source="project-openlegama-moroccan-legal-ai",
            )
        if docs:
            return StructuredFactAnswer(
                "Yes — his portfolio provides strong evidence that he can build a document-grounded AI assistant. **OpenLegaMa** combines corpus ingestion, retrieval, "
                "grounded generation, exact citations, abstention, multilingual interaction, and evaluation. "
                f"It is measured with {r.get('automatedTests','143 / 143 passing')} and {r.get('indexedArticles','7,708')} indexed articles. "
                "[project-openlegama-moroccan-legal-ai] [skills]\n\n"
                "For a company, the pattern can be adapted to its documents, permissions, retrieval strategy, model provider, and evaluation set. "
                "The portfolio proves the core engineering pattern, not every possible enterprise integration.",
                source="project-openlegama-moroccan-legal-ai",
            )
        if end2end:
            return StructuredFactAnswer(
                "Yes. His portfolio demonstrates more than model training:\n\n"
                "• **OpenLegaMa** — retrieval, grounded generation, citations, evaluation, multilingual UI, deployment. [project-openlegama-moroccan-legal-ai]\n"
                "• **Customer MLOps Pipeline** — orchestration, tracking, artifact storage, PostgreSQL, Docker Compose, monitoring, deployment workflow. [project-customer-churn-mlops-platform]\n"
                "• **Road Accident Detection** — model inference, tracking, behavioral logic, alerts, MP4 evidence clips, CSV logs. [project-real-time-road-accident-detection]\n\n"
                "These are concrete end-to-end systems rather than isolated model-training exercises.",
                source="structured-profile",
            )
        return None

    def _broad_certs(self, question: str, language: str):
        n = _precision._normalize(question)
        if not any(re.search(p, n, re.I) for p in _precision._BROAD_CERT_PATTERNS):
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
        selected = [row for title in wanted if (row := self._cert(title)) is not None]
        lines = "\n".join(f"• **{row.get('title')}** — {row.get('issuer')}" for row in selected)
        issuers = sorted(
            {str(row.get("issuer") or "").strip() for row in self.certifications if row.get("issuer")},
            key=str.lower,
        )
        lead = (
            f"Youssef a **{len(self.certifications)} certifications/certificats** dans son portfolio public. Les plus pertinentes pour un profil AI Engineer sont :"
            if language == "fr"
            else f"Youssef currently has **{len(self.certifications)} certifications/certificates** in his public portfolio. The most career-relevant highlights for an AI Engineer profile are:"
        )
        return StructuredFactAnswer(
            f"{lead}\n\n{lines}\n\nIssuers represented include: {', '.join(issuers)}. [certifications]\n\n"
            "If you ask for **all certifications**, I can return the complete inventory.",
            source="certifications",
        )

    def _oracle_inventory(self, question: str, language: str):
        n = _precision._normalize(question)
        has_oracle = "oracle" in n or re.search(r"(?:أوراكل|اوراكل|أوركل|اوركل)", question or "")
        if not has_oracle:
            return None
        cert_context = any(x in n for x in ("certification", "certificate", "certificat", "credential", "شهاد"))
        if not cert_context:
            return None
        specific = any(x in n for x in ("agentic", "database", "architect", "infrastructure", "foundations associate"))
        inventory = (
            self._matches(_precision._COUNT_PATTERNS, question)
            or any(x in n for x in ("what are they", "which ones", "names", "list", "quelles", "lesquelles", "cite", "ما هي"))
        )
        if specific and not self._matches(_precision._COUNT_PATTERNS, question):
            return None
        if not inventory:
            return None
        rows = [row for row in self.certifications if "oracle" in _precision._normalize(str(row.get("issuer") or ""))]
        lines = "\n".join(f"{i}. {row.get('title')}" for i, row in enumerate(rows, 1))
        if language == "fr":
            text = f"Youssef possède exactement **{len(rows)} certifications Oracle** :\n{lines}\n[certifications]"
        elif language == "ar":
            text = f"لدى يوسف {len(rows)} شهادات Oracle موثقة في ملفه المهني العام:\n{lines}\n[certifications]"
        else:
            text = f"Youssef's public portfolio lists exactly **{len(rows)} Oracle certifications**:\n{lines}\n[certifications]"
        return StructuredFactAnswer(text, source="certifications")

    def _resolve_certifications(self, question, history, language):
        n = _precision._normalize(question)
        if language == "fr" and re.search(r"\bcombien\s+de\s+(?:certificats?|certifications?)\b", n, re.I):
            tokens = _precision._tokens(question)
            if "youssef" in n or "il" in tokens or "lui" in tokens:
                return StructuredFactAnswer(
                    f"Le profil professionnel public de Youssef répertorie exactement {len(self.certifications)} certifications. [certifications]",
                    source="certifications",
                )
        return (
            self._oracle_inventory(question, language)
            or self._broad_certs(question, language)
            or super()._resolve_certifications(question, history, language)
        )

    def _orgs(self, question: str):
        n, tokens = _precision._normalize(question), _precision._tokens(question)
        aliases = {
            "oracle": "Oracle",
            "ibm": "IBM",
            "anthropic": "Anthropic",
            "anaconda": "Anaconda",
            "knime": "KNIME",
            "linkedin": "LinkedIn",
            "opencv": "OpenCV University",
            "fiverr": "Fiverr",
            "nextronic": "NEXTRONIC",
        }
        return [display for token, display in aliases.items() if token in tokens or token in n]

    def _multi_employer(self, question: str, language: str):
        n = _precision._normalize(question)
        if not any(x in n for x in ("work at", "work for", "worked at", "worked for", "travaille chez", "عمل")):
            return None
        orgs = self._orgs(question)
        if len(orgs) < 2:
            return None

        lines = []
        for org in orgs:
            orgn = _precision._normalize(org)
            exp = next(
                (row for row in self.experiences if orgn in _precision._normalize(str(row.get("company") or ""))),
                None,
            )
            issuer = any(
                orgn in _precision._normalize(str(row.get("issuer") or ""))
                or _precision._normalize(str(row.get("issuer") or "")) in orgn
                for row in self.certifications
            )
            if exp and "fiverr" not in orgn:
                lines.append(f"• **{org}** — yes, documented work experience ({exp.get('role')}, {exp.get('period')}).")
            elif "fiverr" in orgn:
                lines.append("• **Fiverr** — not an employer relationship; his profile describes independent freelance work via the platform.")
            elif issuer:
                lines.append(f"• **{org}** — no documented employment; it appears as a certification issuer, not as an employer.")
            else:
                lines.append(f"• **{org}** — no synchronized work-experience entry.")
        text = "No — not for the organizations listed only as certification issuers.\n\n" + "\n".join(lines)
        return StructuredFactAnswer(text + "\n[experience-education] [certifications]", source="experience-education")

    def _resolve_employer(self, question: str, language: str):
        target = self._extract_employer_target_clean(question)
        if not target:
            return None
        tn = _precision._normalize(target)

        if "fiverr" in tn:
            if language == "fr":
                text = "Fiverr n’est pas présenté comme l’employeur de Youssef : il exerce **en indépendant via la plateforme Fiverr**. [experience-education]"
            elif language == "ar":
                text = "Fiverr ليست جهة توظيف ليوسف؛ ملفه يصف عمله الحر **بشكل مستقل عبر منصة Fiverr**. [experience-education]"
            else:
                text = "Fiverr is not presented as Youssef's employer; he works **independently via the Fiverr platform**. [experience-education]"
            return StructuredFactAnswer(text, source="experience-education")

        matches = [
            row for row in self.experiences
            if tn in _precision._normalize(str(row.get("company") or ""))
            or _precision._normalize(str(row.get("company") or "")) in tn
        ]
        if matches:
            row = matches[0]
            if language == "fr":
                company = str(row.get("company_fr") or row.get("company") or target)
                role = str(row.get("role_fr") or row.get("role") or "")
                period = str(row.get("period_fr") or row.get("period") or "")
                text = f"Oui. Le portfolio public répertorie une expérience chez {company} : {role} ({period}). [experience-education]"
            elif language == "ar":
                company = str(row.get("company") or target)
                role = str(row.get("role") or "")
                period = str(row.get("period") or "")
                text = f"نعم. يعرض الملف المهني العام خبرة لدى {company}: {role} ({period}). [experience-education]"
            else:
                company = str(row.get("company") or target)
                role = str(row.get("role") or "")
                period = str(row.get("period") or "")
                text = f"Yes. The public portfolio lists work experience at {company}: {role} ({period}). [experience-education]"
            return StructuredFactAnswer(text, source="experience-education")

        issuer = next(
            (
                str(row.get("issuer") or "")
                for row in self.certifications
                if tn in _precision._normalize(str(row.get("issuer") or ""))
                or _precision._normalize(str(row.get("issuer") or "")) in tn
            ),
            None,
        )
        display = target[:1].upper() + target[1:]
        if language == "fr":
            text = f"Non. Aucune expérience professionnelle synchronisée ne répertorie {display} comme employeur de Youssef."
            if issuer:
                text += f" {issuer} apparaît comme organisme de certification, pas comme employeur. [certifications]"
        elif language == "ar":
            text = f"لا. لا يعرض الملف المهني العام المتزامن أي خبرة عمل لدى {display}."
            if issuer:
                text += f" {issuer} تظهر كجهة إصدار شهادة، وليست كجهة توظيف. [certifications]"
        else:
            text = f"No synchronized work-experience entry lists {display} as Youssef's employer."
            if issuer:
                text += f" {issuer} appears as a certification issuer, not as an employer. [certifications]"
        return StructuredFactAnswer(text + " [experience-education]", source="experience-education")

    def resolve(self, question, history=None):
        history = history or []
        language = self._effective_language(question)
        normalized = _precision._normalize(question)

        for resolver in (
            lambda: self._overview(question, language),
            lambda: self._current(question, language),
            lambda: self._why(question, language),
            lambda: self._experience_overview(question, language),
            lambda: self._realtime(question, language),
            lambda: self._accident_results(question, language),
            lambda: self._accident_limits(question, language),
            lambda: self._openlegama_eval(question, language),
            lambda: self._capability(question, language),
            lambda: self._domain_evidence(question, language),
            lambda: self._project_selection(question, language),
            lambda: self._oracle_inventory(question, language),
            lambda: self._multi_employer(question, language),
        ):
            result = resolver()
            if result is not None:
                return result

        if language == "en" and re.search(r"\b(?:phone|telephone|mobile)\s*(?:number)?\b", normalized, re.I):
            return StructuredFactAnswer(
                "The synchronized public professional profile does not provide a public phone number for Youssef, so no public phone number is available from the portfolio. I won't infer or invent unpublished personal information.",
                source="structured-profile",
                evidence="No public phone field is present in the synchronized professional profile.",
            )
        return super().resolve(question, history)


def __getattr__(name):
    return getattr(_live, name)


__all__ = ["StructuredFactAnswer", "StructuredFactResolver"]
