"""Compatibility layer for deterministic portfolio precision facts.

The implementation lives in ``precision_facts.py`` so the precision lane can
evolve independently from hybrid retrieval. This module keeps backward-compatible
aggregate vocabulary, canonicalizes project citations, and owns a small set of
high-risk career-state answers that must come from explicit synchronized fields
rather than LLM inference.
"""
from dataclasses import replace
import re

import precision_facts as _precision

# Natural aggregate phrasing such as "public contact options" is semantically
# equivalent to "public contacts". Keep these generic nouns neutral so they do
# not turn a complete-set request into a filtered query.
_precision._COMMON.update({"option", "options"})

# Real visitors do not always write grammatically perfect French. These variants
# intentionally cover common conversational/typo forms while keeping the match
# narrow enough not to hijack unrelated portfolio questions.
_precision._CURRENT_PATTERNS += (
    r"\b(?:youssef(?:\s+il)?|il)\s+fai(?:t|s)\s+quoi\s+(?:en ce moment|maintenant|actuellement)\b",
    r"\b(?:youssef(?:\s+il)?|il)\s+fai(?:t|s)\s+quoi\b.*\b(?:en ce moment|maintenant|actuellement)\b",
    r"\bque\s+ce\s+qu.?il\s+fai(?:t|s)\s+youssef\b",
    r"\bqu.?est[- ]ce\s+qu.?il\s+fai(?:t|s)\s+youssef\b",
)

StructuredFactAnswer = _precision.StructuredFactAnswer


_JOB_SEARCH_PATTERNS = (
    r"\b(?:is|does) (?:youssef|he) (?:currently )?(?:looking|searching) for (?:a )?(?:job|work|position|role)\b",
    r"\b(?:is|does) (?:youssef|he) (?:seeking|looking for) (?:a )?(?:full-time|full time)\b",
    r"\b(?:is|does) (?:youssef|he) (?:open|available) (?:to|for) (?:full-time|full time|work|opportunities)\b",
    r"\b(?:est ce que |est-ce que )?(?:youssef|il) .*\b(?:recherche|cherche)\b.*\b(?:emploi|travail|poste|job|cdi|opportunite)\b",
    r"\b(?:youssef\s+)?(?:recherche|cherche)(?:-t-il)?\b.*\b(?:emploi|travail|poste|job|cdi|opportunite)\b",
    r"\b(?:youssef|il) (?:recherche|cherche) (?:un |une |des )?(?:emploi|travail|poste|job|cdi|opportunite)\b",
    r"\b(?:youssef|il) .*\b(?:ouvert|disponible)\b.*\b(?:cdi|emploi|travail|opportunite|temps plein)\b",
    r"\b(?:est-il|il est|youssef est)\b.*\b(?:ouvert|disponible)\b.*\b(?:cdi|emploi|travail|opportunite|temps plein)\b",
    r"هل .*يوسف.*(?:يبحث|يبحث حاليا).*(?:عمل|وظيفة|فرصة)",
)

_CONTACT_QUERY_PATTERNS = (
    r"\bhow (?:can|do|could) i (?:contact|reach) (?:youssef|him)\b",
    r"\bhow to (?:contact|reach) (?:youssef|him)\b",
    r"\b(?:youssef'?s|his) contact (?:details|info|information|options)\b",
    r"\bcomment (?:puis[- ]je |peux[- ]je |peut[- ]on )?(?:contacter|joindre) (?:youssef|le|lui)\b",
    r"\b(?:coordonnees|coordonnées) (?:de )?youssef\b",
    r"كيف (?:يمكنني )?(?:التواصل|الاتصال) مع يوسف",
)

_PROFESSIONAL_OVERVIEW_PATTERNS = (
    r"^\s*(?:his|youssef'?s) professional\s*[?.!]*$",
    r"^\s*(?:his|youssef'?s) profession\s*[?.!]*$",
    r"^\s*(?:his|youssef'?s) professional profile\s*[?.!]*$",
    r"^\s*(?:tell me about )?(?:his|youssef'?s) professional profile\s*[?.!]*$",
    r"^\s*(?:son|le) profil professionnel(?: de youssef)?\s*[?.!]*$",
    r"^\s*(?:quelle est )?(?:la )?profession de youssef\s*[?.!]*$",
)

_PRIVATE_RELATIONSHIP_TERMS = (
    "married", "marital status", "wife", "husband", "spouse", "girlfriend", "boyfriend",
    "marie", "mariee", "statut matrimonial", "epouse", "epoux", "petite amie", "petit ami",
    "متزوج", "متزوجة", "زوجته", "زوجها", "الحالة الاجتماعية",
)


class StructuredFactResolver(_precision.StructuredFactResolver):
    """Precision resolver with canonical source IDs and explicit career state."""

    @staticmethod
    def _job_search_question(question: str) -> bool:
        normalized = _precision._normalize(question)
        return any(re.search(pattern, normalized, re.I) for pattern in _JOB_SEARCH_PATTERNS)

    @staticmethod
    def _looks_like_contact_action(question: str) -> bool:
        normalized = _precision._normalize(question)
        return bool(
            re.search(
                r"\b(?:send|message|write|draft|envoie|envoyer|ecris|ecrire|redige|rediger|ارسِل|ارسل|أرسل)\b",
                normalized,
                re.I,
            )
            or re.search(r"^\s*(?:email|mail)\s+(?:youssef|him)\b", normalized, re.I)
        )

    def _public_contact_values(self):
        values = {"email": "", "linkedin": "", "github": "", "fiverr": ""}
        for row in self.links:
            url = str(row.get("url") or "").strip()
            label = _precision._normalize(str(row.get("label") or ""))
            value = str(row.get("value") or "").strip()
            if label == "email" or url.lower().startswith("mailto:"):
                values["email"] = value or url.split(":", 1)[-1]
            elif "linkedin.com" in url.lower():
                values["linkedin"] = url
            elif "github.com" in url.lower():
                values["github"] = url
            elif "fiverr.com" in url.lower():
                values["fiverr"] = url
        return values

    def _resolve_contact_details(self, question: str, language: str):
        """Return complete public contact data instead of a top-k subset.

        Information queries are deterministic. Actual send-message requests stay
        on the contact-action tool path and are intentionally not intercepted.
        """
        if self._looks_like_contact_action(question):
            return None

        normalized = _precision._normalize(question)
        tokens = _precision._tokens(question)
        email_requested = bool(tokens & {"email", "e-mail", "mail", "courriel", "ايميل", "إيميل", "بريد"})
        broad_contact = any(re.search(pattern, normalized, re.I) for pattern in _CONTACT_QUERY_PATTERNS)
        if not (email_requested or broad_contact):
            return None

        values = self._public_contact_values()
        if email_requested and not broad_contact:
            email = values.get("email")
            if not email:
                return None
            if language == "fr":
                text = f"L’adresse e-mail professionnelle publique de Youssef est : {email}."
            elif language == "ar":
                text = f"البريد الإلكتروني المهني العام ليوسف هو: {email}."
            else:
                text = f"Youssef's public professional email is: {email}."
            return StructuredFactAnswer(text + " [public-links]", source="public-links")

        rows = []
        if values.get("email"):
            rows.append(("Email", values["email"]))
        if values.get("linkedin"):
            rows.append(("LinkedIn", values["linkedin"]))
        if values.get("github"):
            rows.append(("GitHub", values["github"]))
        if values.get("fiverr"):
            rows.append(("Fiverr", values["fiverr"]))
        if not rows:
            return None

        listing = "\n".join(f"• {label}: {value}" for label, value in rows)
        if language == "fr":
            intro = "Vous pouvez contacter ou retrouver Youssef via ses canaux professionnels publics :"
        elif language == "ar":
            intro = "يمكنك التواصل مع يوسف أو العثور عليه عبر قنواته المهنية العامة التالية:"
        else:
            intro = "You can contact or connect with Youssef through these public professional channels:"
        return StructuredFactAnswer(f"{intro}\n{listing}\n[public-links]", source="public-links")

    @staticmethod
    def _resolve_private_relationship(question: str, language: str):
        normalized = _precision._normalize(question)
        if not any(_precision._normalize(term) in normalized for term in _PRIVATE_RELATIONSHIP_TERMS):
            return None
        if language == "fr":
            text = (
                "Je n’ai pas d’information professionnelle publique vérifiée sur la situation matrimoniale "
                "ou relationnelle de Youssef. Je ne déduis pas et je ne spécule pas sur ses informations personnelles privées."
            )
        elif language == "ar":
            text = (
                "لا أملك معلومات مهنية عامة وموثقة عن الحالة الزوجية أو العاطفية ليوسف، "
                "ولا أستنتج أو أتخمن معلوماته الشخصية الخاصة."
            )
        else:
            text = (
                "I don't have verified public professional information about Youssef's marital or relationship status. "
                "I don't infer or speculate about private personal details."
            )
        return StructuredFactAnswer(
            text,
            source="structured-profile",
            evidence="No verified public professional relationship-status field is present in the synchronized portfolio profile.",
        )

    def _resolve_professional_overview(self, question: str, language: str):
        normalized = _precision._normalize(question)
        if not any(re.search(pattern, normalized, re.I) for pattern in _PROFESSIONAL_OVERVIEW_PATTERNS):
            return None

        current = next(
            (
                row for row in self.experiences
                if "present" in _precision._normalize(str(row.get("period") or ""))
            ),
            self.experiences[0] if self.experiences else None,
        )
        if current is None:
            return None

        skill_names = [
            str(row.get("name") or row.get("category") or "").strip()
            for row in self.skills
            if str(row.get("name") or row.get("category") or "").strip()
        ]
        focus = ", ".join(skill_names)
        career = self.profile.get("career_status") or {}
        seeking = isinstance(career, dict) and career.get("seeking_full_time") is True

        if language == "fr":
            role = str(current.get("role_fr") or current.get("role") or "")
            company = str(current.get("company_fr") or current.get("company") or "")
            period = str(current.get("period_fr") or current.get("period") or "")
            text = f"Le rôle professionnel public actuel de Youssef est {role} chez {company} ({period})."
            if focus:
                text += f" Son portfolio met notamment en avant : {focus}."
            if seeking:
                text += " Il recherche également une opportunité en CDI à temps plein."
        elif language == "ar":
            role = str(current.get("role") or "")
            company = str(current.get("company") or "")
            period = str(current.get("period") or "")
            text = f"الدور المهني العام الحالي ليوسف هو {role} لدى {company} ({period})."
            if focus:
                text += f" ويركز ملفه المهني خصوصاً على: {focus}."
            if seeking:
                text += " كما أنه يبحث عن فرصة عمل بدوام كامل."
        else:
            role = str(current.get("role") or "")
            company = str(current.get("company") or "")
            period = str(current.get("period") or "")
            text = f"Youssef's current public professional role is {role} at {company} ({period})."
            if focus:
                text += f" His portfolio highlights these professional focus areas: {focus}."
            if seeking:
                text += " He is also seeking a full-time opportunity."

        citations = " [experience-education] [skills]"
        if seeking:
            citations += " [career-status]"
        return StructuredFactAnswer(text + citations, source="experience-education")

    @staticmethod
    def _format_cert_details(row, language: str):
        """Return certification details without accidental mixed-language prose.

        Certification descriptions synchronized from the portfolio are currently
        authored in English. For French/Arabic questions we therefore only emit a
        localized description when an explicit localized field exists; otherwise
        we keep the verified title, issuer, date and verification URL and avoid
        silently mixing an English paragraph into an otherwise localized answer.
        """
        title = str(row.get("title") or "Certification")
        issuer = str(row.get("issuer") or "")
        date = str(row.get("date") or "").strip()
        verification = str(row.get("verification_url") or "").strip()

        if language == "fr":
            description = str(row.get("description_fr") or "").strip()
            parts = [f"{title} est une certification délivrée par {issuer}."]
            if date:
                parts.append(f"Date : {date}.")
            if description:
                parts.append(f"Elle couvre : {description}")
            if verification:
                parts.append(f"Vérification : {verification}")
        elif language == "ar":
            description = str(row.get("description_ar") or "").strip()
            parts = [f"{title} هي شهادة صادرة عن {issuer}."]
            if date:
                parts.append(f"التاريخ: {date}.")
            if description:
                parts.append(f"المحتوى: {description}")
            if verification:
                parts.append(f"رابط التحقق: {verification}")
        else:
            description = str(row.get("description") or "").strip()
            parts = [f"{title} is a certification issued by {issuer}."]
            if date:
                parts.append(f"Date: {date}.")
            if description:
                parts.append(f"It covers: {description}")
            if verification:
                parts.append(f"Verification: {verification}")

        return StructuredFactAnswer(" ".join(parts) + " [certifications]", source="certifications")

    def _resolve_job_search(self, question: str, language: str):
        if not self._job_search_question(question):
            return None
        status = self.profile.get("career_status") or {}
        if not isinstance(status, dict) or "seeking_full_time" not in status:
            return None

        seeking = status.get("seeking_full_time") is True
        roles = [str(role).strip() for role in status.get("target_roles", []) if str(role).strip()]
        role_text = ", ".join(roles)
        freelance = status.get("freelance_parallel") is True

        if language == "fr":
            if seeking:
                text = "Oui. Le portfolio public indique explicitement que Youssef recherche actuellement une opportunité en CDI à temps plein"
                if role_text:
                    text += f" comme {role_text}"
                text += "."
                if freelance:
                    text += " En parallèle, il exerce comme Ingénieur IA/ML Freelance ; cette activité freelance ne remplace pas sa recherche de CDI."
            else:
                text = "Non. Le statut professionnel public synchronisé n’indique pas actuellement une recherche de CDI à temps plein."
        elif language == "ar":
            if seeking:
                text = "نعم. يذكر ملف يوسف المهني العام صراحةً أنه يبحث حالياً عن فرصة عمل بدوام كامل"
                if role_text:
                    text += f" في أدوار مثل: {role_text}"
                text += "."
                if freelance:
                    text += " وفي الوقت نفسه يعمل كمهندس AI/ML مستقل؛ العمل الحر لا يعني أنه أوقف بحثه عن وظيفة بدوام كامل."
            else:
                text = "لا. الحالة المهنية العامة المتزامنة لا تشير حالياً إلى أنه يبحث عن وظيفة بدوام كامل."
        else:
            if seeking:
                text = "Yes. Youssef's public portfolio explicitly states that he is currently seeking a full-time opportunity"
                if role_text:
                    text += f" as {role_text}"
                text += "."
                if freelance:
                    text += " He is freelancing in parallel; the freelance role does not replace his full-time job search."
            else:
                text = "No. The synchronized public career status does not currently indicate a full-time job search."

        return StructuredFactAnswer(
            text + " [career-status] [experience-education]",
            source="career-status",
            evidence="Resolved from explicit public career-availability statements synchronized from the portfolio About/Contact copy.",
        )

    def _resolve_current_work(self, question: str, language: str):
        """Use localized structured fields and include parallel CDI availability."""
        if not self._matches(_precision._CURRENT_PATTERNS, question):
            return None
        current = [
            row for row in self.experiences
            if "present" in _precision._normalize(str(row.get("period") or ""))
        ]
        if not current:
            return None
        row = current[0]
        career = self.profile.get("career_status") or {}

        if language == "fr":
            role = str(row.get("role_fr") or row.get("role") or "")
            company = str(row.get("company_fr") or row.get("company") or "")
            period = str(row.get("period_fr") or row.get("period") or "")
            description = str(row.get("description_fr") or row.get("description") or "").strip()
            highlights = [str(x) for x in (row.get("highlights_fr") or row.get("highlights") or []) if str(x).strip()]
            text = f"Actuellement, Youssef exerce comme {role} chez {company} ({period}). {description}"
            if highlights:
                text += " Ses activités documentées comprennent : " + "; ".join(highlights) + "."
            if isinstance(career, dict) and career.get("seeking_full_time") is True:
                text += " En parallèle, son portfolio indique explicitement qu’il recherche une opportunité en CDI à temps plein."
        elif language == "ar":
            role = str(row.get("role") or "")
            company = str(row.get("company") or "")
            period = str(row.get("period") or "")
            description = str(row.get("description") or "").strip()
            highlights = [str(x) for x in row.get("highlights", []) if str(x).strip()]
            text = f"حالياً، يعمل يوسف كـ {role} لدى {company} ({period}). {description}"
            if highlights:
                text += " وتشمل أنشطته الموثقة: " + "؛ ".join(highlights) + "."
            if isinstance(career, dict) and career.get("seeking_full_time") is True:
                text += " وبالتوازي مع ذلك، يذكر ملفه العام صراحةً أنه يبحث عن فرصة عمل بدوام كامل."
        else:
            role = str(row.get("role") or "")
            company = str(row.get("company") or "")
            period = str(row.get("period") or "")
            description = str(row.get("description") or "").strip()
            highlights = [str(x) for x in row.get("highlights", []) if str(x).strip()]
            text = f"Youssef's current public professional role is {role} at {company} ({period}). {description}"
            if highlights:
                text += " His documented current work includes: " + "; ".join(highlights) + "."
            if isinstance(career, dict) and career.get("seeking_full_time") is True:
                text += " In parallel, his public portfolio explicitly states that he is seeking a full-time opportunity."

        citations = " [experience-education]"
        if isinstance(career, dict) and career.get("seeking_full_time") is True:
            citations += " [career-status]"
        return StructuredFactAnswer(text + citations, source="experience-education")

    def _resolve_employer(self, question: str, language: str):
        """Confirm known employers using localized structured experience fields."""
        target = self._extract_employer_target(question)
        if not target:
            return None
        target_norm = _precision._normalize(target)
        matches = [
            row for row in self.experiences
            if target_norm in _precision._normalize(str(row.get("company") or ""))
            or _precision._normalize(str(row.get("company") or "")) in target_norm
        ]
        if not matches:
            return super()._resolve_employer(question, language)

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
        return StructuredFactAnswer(text + " [experience-education]", source="experience-education")

    def _resolve_openlegama_rag(self, question: str, language: str):
        """Answer OpenLegaMa Controlled-RAG questions from synchronized project data.

        This is intentionally narrow: it only fires when the named project and a
        RAG term are both present. Generic "Tell me about OpenLegaMa" questions
        still go through hybrid retrieval so visitors can receive richer answers.
        """
        normalized = _precision._normalize(question)
        if "openlegama" not in normalized:
            return None
        if not any(
            term in normalized
            for term in (
                "rag",
                "controlled rag",
                "retrieval augmented generation",
                "retrieval-augmented generation",
            )
        ):
            return None

        row = next(
            (
                project
                for project in self.projects
                if _precision._normalize(str(project.get("slug") or ""))
                == "openlegama-moroccan-legal-ai"
            ),
            None,
        )
        if row is None:
            return None

        source = "project-openlegama-moroccan-legal-ai"
        if language == "fr":
            text = (
                "Dans OpenLegaMa, le Controlled RAG récupère des textes juridiques officiels, "
                "vérifie les références exactes des lois et des articles, relie les affirmations "
                "juridiques aux preuves acceptées et s’abstient lorsque les sources vérifiées "
                "sont insuffisantes."
            )
        elif language == "ar":
            text = (
                "في OpenLegaMa، يستخدم Controlled RAG لاسترجاع النصوص القانونية الرسمية، "
                "والتحقق من المراجع الدقيقة للقوانين والمواد، وربط الادعاءات القانونية بالأدلة "
                "المقبولة، والامتناع عن الإجابة عندما تكون المصادر الموثقة غير كافية."
            )
        else:
            text = (
                "In OpenLegaMa, Controlled RAG retrieves official legal texts, validates exact "
                "law and article references, connects legal claims to accepted evidence, and "
                "abstains when verified sources are insufficient."
            )

        return StructuredFactAnswer(
            f"{text} [{source}]",
            source=source,
            evidence=(
                "Resolved from the synchronized OpenLegaMa project description: controlled "
                "Retrieval-Augmented Generation retrieves official legal texts, validates exact "
                "law/article references, grounds legal claims in accepted evidence, and abstains "
                "when verified sources are insufficient."
            ),
        )

    def _canonicalize_project_sources(self, result):
        answer = result.answer
        source = result.source
        for row in self.projects:
            slug = str(row.get("slug") or "").strip()
            if not slug:
                continue
            canonical = f"project-{slug}"
            answer = answer.replace(f"[{slug}]", f"[{canonical}]")
            if source == slug:
                source = canonical

        if answer == result.answer and source == result.source:
            return result
        return replace(result, answer=answer, source=source)

    def resolve(self, question, history=None):
        history = history or []
        language = _precision.detect_language(question)

        # Private personal details get a targeted refusal instead of a vague
        # generic scope response, even for shorthand such as "hi is married?".
        result = self._resolve_private_relationship(question, language)

        # Contact information is a complete structured inventory. Answering it
        # deterministically prevents the email from disappearing from a top-k RAG
        # subset and avoids malformed mailto Markdown in the widget.
        if result is None:
            result = self._resolve_contact_details(question, language)

        # Incomplete but common recruiter shorthand such as "his professional"
        # is interpreted as a request for the public professional profile summary.
        if result is None:
            result = self._resolve_professional_overview(question, language)

        # Highest-risk career state is explicit, never inferred from freelance.
        if result is None:
            result = self._resolve_job_search(question, language)

        # Certification wording must be handled before generic "Agentic AI"
        # capability matching. Otherwise a question such as "Which Oracle Agentic
        # AI certification does he have?" can be semantically hijacked by the
        # capability resolver merely because its title contains "Agentic AI".
        if result is None:
            result = self._resolve_certifications(question, history, language)

        # OpenLegaMa's Controlled-RAG behavior is explicitly documented in the
        # synchronized project description, so answer this high-value factual
        # question deterministically rather than letting the model abstain despite
        # having sufficient evidence.
        if result is None:
            result = self._resolve_openlegama_rag(question, language)

        if result is None:
            result = super().resolve(question, history)
        if result is None:
            return None
        return self._canonicalize_project_sources(result)


__all__ = ["StructuredFactAnswer", "StructuredFactResolver"]
