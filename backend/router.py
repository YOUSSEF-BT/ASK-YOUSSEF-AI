"""Lightweight intent/language routing for Ask Youssef AI.

Routing is deterministic and runs before the LLM. It does not answer questions;
it only labels the turn so the orchestration layer can enforce retrieval for
portfolio facts, keep greetings cheap, and preserve the visitor's language.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

_ARABIC = re.compile(r"[\u0600-\u06ff]")
_WORD = re.compile(r"[\w+#.-]+", re.UNICODE)


def _norm(text: str) -> str:
    value = unicodedata.normalize("NFKD", text or "")
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    return value.lower().strip()


def _tokens(text: str) -> set[str]:
    return {t for t in _WORD.findall(_norm(text)) if t}


FRENCH_HINTS = {
    "quel", "quelle", "quels", "quelles", "comment", "pourquoi", "projet",
    "projets", "competence", "competences", "certificat", "certificats",
    "certification", "experience", "formation", "etudes", "travail", "stage",
    "contact", "contacter", "bonjour", "salut", "merci", "avec", "dans",
    "est", "sont", "ses", "son", "meilleur", "meilleurs", "montre", "parle",
}

INTENT_TERMS = {
    "projects": {
        "project", "projects", "projet", "projets", "github", "demo", "demos",
        "repository", "repo", "repositories", "مشروع", "مشاريع", "المشاريع",
    },
    "skills": {
        "skill", "skills", "competence", "competences", "stack", "technology",
        "technologies", "tech", "مهارة", "مهارات", "المهارات", "تقنيات",
    },
    "certifications": {
        "certification", "certifications", "certificate", "certificates", "certificat",
        "certificats", "oracle", "anthropic", "شهادة", "شهادات", "الشهادات",
    },
    "experience": {
        "experience", "experiences", "work", "job", "jobs", "internship", "intern",
        "stage", "emploi", "travail", "fiverr", "nextronic", "aba", "خبرة", "عمل",
    },
    "education": {
        "education", "degree", "school", "university", "diploma", "diplome",
        "formation", "etudes", "supmti", "etudie", "دراسة", "تعليم", "جامعة",
    },
    "contact": {
        "contact", "email", "linkedin", "fiverr", "upwork", "reach", "contacter",
        "joindre", "تواصل", "اتصال", "ايميل", "إيميل", "بريد",
    },
}

GREETING_TERMS = {
    "hi", "hello", "hey", "bonjour", "salut", "bonsoir", "مرحبا", "سلام",
    "شكرا", "thanks", "thank", "merci",
}

CONTACT_ACTION_PATTERNS = (
    r"\b(send|email|message|write)\b.*\b(youssef|him)\b",
    r"\b(envoie|envoyer|ecris|ecrire|message)\b.*\b(youssef|lui)\b",
    r"(?:ارسل|أرسل|ابعث|أبعث).*(?:يوسف|له)",
)

PROFILE_REFERENTS = {
    "youssef", "his", "him", "he", "il", "lui", "son", "ses", "youssefs",
    "يوسف", "له", "عنده", "لديه",
}


@dataclass(frozen=True)
class Route:
    language: str
    intent: str
    requires_retrieval: bool
    portfolio_scope: bool
    confidence: float

    def as_hint(self) -> str:
        return (
            f"language={self.language}; intent={self.intent}; "
            f"requires_retrieval={str(self.requires_retrieval).lower()}; "
            f"portfolio_scope={str(self.portfolio_scope).lower()}"
        )


def detect_language(text: str) -> str:
    if _ARABIC.search(text or ""):
        return "ar"
    toks = _tokens(text)
    french_score = len(toks & FRENCH_HINTS)
    if french_score >= 1 or any(ch in (text or "").lower() for ch in "éèêàâçùûôîïœ"):
        return "fr"
    return "en"


def _contact_action(text: str) -> bool:
    normalized = _norm(text)
    return any(re.search(pattern, normalized, re.I) for pattern in CONTACT_ACTION_PATTERNS)


def route_question(text: str) -> Route:
    text = (text or "").strip()
    language = detect_language(text)
    toks = _tokens(text)

    if not text:
        return Route(language=language, intent="greeting", requires_retrieval=False,
                     portfolio_scope=True, confidence=1.0)

    if _contact_action(text):
        return Route(language=language, intent="contact_action", requires_retrieval=False,
                     portfolio_scope=True, confidence=0.95)

    scores = {intent: len(toks & terms) for intent, terms in INTENT_TERMS.items()}
    best_intent = max(scores, key=scores.get)
    best_score = scores[best_intent]

    if best_score:
        # Questions about public links/contact methods are factual portfolio
        # questions, so they still retrieve. Actual send-message actions above do not.
        confidence = min(0.99, 0.72 + 0.09 * best_score)
        return Route(language=language, intent=best_intent, requires_retrieval=True,
                     portfolio_scope=True, confidence=confidence)

    greeting_only = bool(toks) and toks.issubset(GREETING_TERMS | {"youssef", "يوسف"})
    if greeting_only:
        return Route(language=language, intent="greeting", requires_retrieval=False,
                     portfolio_scope=True, confidence=0.96)

    # A generic question explicitly referring to Youssef is still a factual
    # portfolio turn even when no narrow intent keyword is present.
    if toks & PROFILE_REFERENTS:
        return Route(language=language, intent="profile", requires_retrieval=True,
                     portfolio_scope=True, confidence=0.75)

    return Route(language=language, intent="general", requires_retrieval=False,
                 portfolio_scope=False, confidence=0.65)
