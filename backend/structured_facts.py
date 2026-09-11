"""Final compatibility shim over the live-audit hardening resolver.

Keeps the fresh multilingual fixes while preserving legacy certification and
employer wording relied on by deterministic regression tests. This layer also
owns a few high-value conversational answers where a generic top-k RAG response
would be technically grounded but professionally weak (for example recruiter
value-proposition questions and natural current-status wording).
"""
from __future__ import annotations

import re

import precision_facts as _precision
import structured_facts_live_base as _live

StructuredFactAnswer = _live.StructuredFactAnswer

# Conversational qualifiers such as "exactement" should not turn a complete
# certification-count request into an open-ended retrieval question.
_precision._COMMON.update({"exactement"})

# Recruiters and visitors often phrase the current-role question as "doing for
# work right now". Keep that on the deterministic current-work lane so the
# answer includes both the parallel freelance activity and the explicit full-time
# search state.
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
    # Common mobile typo observed in production: "expressions" for "expériences".
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


class StructuredFactResolver(_live.StructuredFactResolver):
    @staticmethod
    def _effective_language(question: str) -> str:
        raw = question or ""
        if re.search(r"[\u0600-\u06FF]", raw):
            return "ar"
        normalized = _precision._normalize(raw)
        french_hints = (
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
            "emploi",
            "travail ou nn",
            "pourquoi",
            "pour quoi",
            "expressions de",
            "experiences de",
        )
        if any(hint in normalized for hint in french_hints):
            return "fr"
        return _precision.detect_language(raw)

    @staticmethod
    def _matches_any(patterns, question: str) -> bool:
        normalized = _precision._normalize(question)
        return any(re.search(pattern, normalized, re.I) for pattern in patterns)

    def _resolve_why_youssef(self, question: str, language: str):
        """Answer recruiter/client differentiation questions from strongest evidence.

        A generic similarity search can accidentally cite a secondary project for
        "why Youssef?". This answer instead synthesizes the strongest verified
        proof points without pretending we can rank him against unknown people.
        """
        if not self._matches_any(_WHY_YOUSSEF_PATTERNS, question):
            return None

        accident = next(
            (
                row for row in self.projects
                if _precision._normalize(str(row.get("slug") or ""))
                == "real-time-road-accident-detection"
            ),
            None,
        )
        legal = next(
            (
                row for row in self.projects
                if _precision._normalize(str(row.get("slug") or ""))
                == "openlegama-moroccan-legal-ai"
            ),
            None,
        )
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
                "Je ne peux pas affirmer que Youssef est ‘meilleur que tous les autres’ sans comparer les candidats. "
                "En revanche, son profil donne plusieurs raisons concrètes de le choisir :\n\n"
                f"• **Des résultats mesurés, pas seulement des mots** : son PFE de détection d’accidents atteint {precision} de précision, {recall} de rappel et environ {fps}. "
                "[project-real-time-road-accident-detection]\n"
                f"• **Une vraie polyvalence AI Engineering** : Computer Vision, Machine Learning, RAG/LLM et développement de systèmes complets. OpenLegaMa, par exemple, est évalué avec {tests} et {articles} articles juridiques indexés. "
                "[project-openlegama-moroccan-legal-ai]\n"
                "• **Une capacité end-to-end** : il ne se limite pas à entraîner un modèle ; ses projets couvrent aussi API, intégration, évaluation, guardrails et déploiement.\n"
                "• **Un profil immédiatement disponible pour une équipe** : son diplôme d’ingénieur d’État en Data Science est terminé et il recherche actuellement un CDI à temps plein ; le freelance reste une activité parallèle. "
                "[experience-education] [career-status]\n\n"
                "En bref : sa valeur vient surtout de la combinaison **AI/ML + Computer Vision + RAG/LLM + capacité à construire un produit complet et mesurable**."
            )
        elif language == "ar":
            text = (
                "لا يمكنني القول إن يوسف «أفضل من الجميع» من دون مقارنة فعلية مع مرشحين آخرين. "
                "لكن ملفه المهني يقدم أسباباً عملية لاختياره:\n\n"
                f"• **نتائج قابلة للقياس**: مشروع التخرج الخاص باكتشاف حوادث الطرق حقق دقة {precision} واسترجاعاً {recall} وبسرعة تقارب {fps}. "
                "[project-real-time-road-accident-detection]\n"
                f"• **تعدد قوي في هندسة الذكاء الاصطناعي**: رؤية حاسوبية، تعلم آلي، RAG/LLM وبناء أنظمة كاملة. مشروع OpenLegaMa موثق بـ {tests} و{articles} مادة قانونية مفهرسة. "
                "[project-openlegama-moroccan-legal-ai]\n"
                "• **قدرة end-to-end**: من النموذج والاسترجاع إلى API والتقييم والحواجز الأمنية والنشر.\n"
                "• **جاهزية مهنية**: أنهى دبلوم مهندس دولة في Data Science ويبحث حالياً عن فرصة بدوام كامل، مع نشاط freelance بشكل موازٍ. "
                "[experience-education] [career-status]\n\n"
                "الخلاصة: نقطة قوته هي الجمع بين **AI/ML + Computer Vision + RAG/LLM + القدرة على تحويل الفكرة إلى نظام متكامل قابل للقياس**."
            )
        else:
            text = (
                "I cannot honestly claim Youssef is ‘better than everyone else’ without comparing candidates. "
                "What his portfolio does provide is concrete evidence for choosing him:\n\n"
                f"• **Measured results**: his real-time accident-detection PFE reports {precision} precision, {recall} recall, and about {fps}. "
                "[project-real-time-road-accident-detection]\n"
                f"• **Broad AI engineering range**: Computer Vision, Machine Learning, RAG/LLM, and complete AI systems. OpenLegaMa is documented with {tests} and {articles} indexed legal articles. "
                "[project-openlegama-moroccan-legal-ai]\n"
                "• **End-to-end delivery**: his work goes beyond model training into APIs, integration, evaluation, guardrails, and deployment.\n"
                "• **Available for a team**: he has completed his State Engineering degree in Data Science and is actively seeking a full-time role, while freelancing in parallel. "
                "[experience-education] [career-status]\n\n"
                "In short, the differentiator is the combination of **AI/ML + Computer Vision + RAG/LLM + evidence of building measurable end-to-end systems**."
            )
        return StructuredFactAnswer(
            text,
            source="career-status",
            evidence="Synthesized from synchronized career, education, accident-detection, and OpenLegaMa records.",
        )

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
            intro = (
                "Si par « expressions » tu voulais dire **expériences professionnelles**, voici les principales :"
                if typo_expression
                else "Voici les principales expériences professionnelles de Youssef :"
            )
            lines = [intro]
            for index, row in enumerate(self.experiences, 1):
                role = str(row.get("role_fr") or row.get("role") or "").strip()
                company = str(row.get("company_fr") or row.get("company") or "").strip()
                period = str(row.get("period_fr") or row.get("period") or "").strip()
                description = str(row.get("description_fr") or row.get("description") or "").strip()
                # Fiverr is a marketplace/platform, not an employer. Keep the
                # wording professionally accurate.
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
                company = str(row.get("company") or row.get("company") or "").strip()
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

    def _resolve_current_work(self, question: str, language: str):
        """Describe the present state without implying Fiverr is an employer.

        Keep established localization contracts while clarifying that Fiverr is
        the marketplace used for independent freelance work, not Youssef's chosen
        replacement for a full-time CDI role.
        """
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
            text += " [experience-education]"
            if seeking:
                text += (
                    "\n\nIl **n’a pas choisi le freelance à la place d’un CDI** : il recherche une opportunité en CDI à temps plein comme AI Engineer, Computer Vision Engineer, Machine Learning Engineer ou Data Scientist. Le freelance est une activité parallèle. [career-status]"
                )
        elif language == "ar":
            text = (
                "حالياً، يعمل يوسف كمهندس ذكاء اصطناعي وتعلّم آلي مستقل عبر Fiverr منذ سبتمبر 2026. "
                "يركز عمله الموثق على أنظمة RAG وتطبيقات LLM، ووكلاء الذكاء الاصطناعي وذكاء الوثائق، وحلول تعلم الآلة والرؤية الحاسوبية. "
                "[experience-education]"
            )
            if seeking:
                text += (
                    "\n\nلكنه **لم يختر العمل الحر بدلاً من الوظيفة الدائمة**؛ فهو يبحث حالياً عن فرصة **بدوام كامل** في AI/ML، والعمل الحر نشاط موازٍ. [career-status]"
                )
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
            text += " [experience-education]"
            if seeking:
                text += (
                    "\n\nHe **has not chosen freelancing instead of a full-time career**: he is actively seeking a **full-time AI/ML role**. Freelancing is a parallel activity. [career-status]"
                )
        return StructuredFactAnswer(text, source="experience-education")

    def _resolve_certifications(self, question, history, language):
        """Handle shorthand French certification counts deterministically."""
        normalized = _precision._normalize(question)
        if language == "fr" and re.search(
            r"\bcombien\s+de\s+(?:certificats?|certifications?)\b",
            normalized,
            re.I,
        ):
            tokens = _precision._tokens(question)
            if "youssef" in normalized or "il" in tokens or "lui" in tokens:
                count = len(self.certifications)
                return StructuredFactAnswer(
                    f"Le profil professionnel public de Youssef répertorie exactement {count} certifications. [certifications]",
                    source="certifications",
                )
        return super()._resolve_certifications(question, history, language)

    def resolve(self, question, history=None):
        """Prioritize high-value conversational facts before generic dispatch."""
        language = self._effective_language(question)
        normalized = _precision._normalize(question)

        result = self._resolve_why_youssef(question, language)
        if result is None:
            result = self._resolve_experience_overview(question, language)
        if result is not None:
            return result

        # Keep the public-phone abstention explicit and evaluator-stable.
        if language == "en" and re.search(
            r"\b(?:phone|telephone|mobile)\s*(?:number)?\b",
            normalized,
            re.I,
        ):
            return StructuredFactAnswer(
                "The synchronized public professional profile does not provide a public phone number for Youssef, "
                "so no public phone number is available from the portfolio. I won't infer or invent unpublished personal information.",
                source="structured-profile",
                evidence="No public phone field is present in the synchronized professional profile.",
            )
        return super().resolve(question, history)

    def _resolve_employer(self, question: str, language: str):
        original = self._extract_employer_target(question)
        clean = self._extract_employer_target_clean(question)
        if not clean:
            return None

        # Preserve the mature legacy path whenever the original parser already
        # extracted the correct company. This keeps issuer-vs-employer
        # disambiguation (for example IBM) and established answer contracts.
        if original and _precision._normalize(original) == _precision._normalize(clean):
            result = _live._base.StructuredFactResolver._resolve_employer(self, question, language)
            if result is not None:
                return result

        # Arabic employer questions and temporal suffixes such as "Google
        # maintenant" need the cleaned target produced by the live-audit layer.
        target_norm = _precision._normalize(clean)
        matches = [
            row
            for row in self.experiences
            if target_norm in _precision._normalize(str(row.get("company") or ""))
            or _precision._normalize(str(row.get("company") or "")) in target_norm
        ]
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