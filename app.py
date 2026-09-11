"""Vercel entrypoint for Ask Youssef AI.

This wrapper keeps the core backend host-agnostic while selecting settings that
fit Vercel Hobby: bundled portfolio snapshot, in-process retrieval, local
FastEmbed vectors, and the public GitHub Pages origin. GEMINI_API_KEY remains a
secret and is used for answer generation only; it is never committed here.
"""
from __future__ import annotations

import os
import re
import sys
import time

# Zero-cost / serverless-safe production defaults. Explicit environment
# variables in Vercel can still override any of these values.
_DEFAULTS = {
    "CRAWL_SITES": "",
    "CORPUS_DIR": "/tmp/site",
    "MCP_TRANSPORT": "inprocess",
    "ALLOWED_ORIGINS": "https://youssef-bt.github.io",
    "EMBEDDER": "fastembed",
    "FASTEMBED_MODEL": "BAAI/bge-small-en-v1.5",
    "FASTEMBED_CACHE_PATH": "backend/data/fastembed_cache",
    "GEMINI_MODEL": "gemini-3.7-flash",
    "GEMINI_FALLBACK_MODEL": "gemini-3.5-flash-lite",
    # Two attempts can now be primary -> fallback. 24s keeps the worst-case
    # provider budget comfortably inside Vercel Hobby's request window.
    "GEMINI_TIMEOUT": "24",
    "GEMINI_RETRIES": "2",
    "MAX_QUESTION_CHARS": "600",
    "MAX_TURN_CHARS": "600",
    "RATE_PER_MIN": "6",
    "RATE_PER_DAY": "40",
    "GLOBAL_PER_DAY": "800",
}

for _key, _value in _DEFAULTS.items():
    os.environ.setdefault(_key, _value)

# Apply Vercel-only reliability/latency/quality optimizations before backend.app
# imports and builds the shared agent. Core local/Docker behavior is unchanged.
_BACKEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend")
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)
import vercel_quality_patch  # noqa: E402,F401
import project_fingerprint_patch  # noqa: E402,F401
import vercel_agent_patch  # noqa: E402,F401
import vercel_gemini_failover  # noqa: E402,F401

import backend.app as _backend  # noqa: E402

# Vercel's FastAPI runtime discovers the exported variable named `app`.
app = _backend.app

# Greetings, clearly out-of-scope requests, and secret-exfiltration attempts are
# deterministic product UX. They do not need a model call or retrieval.
_original_stream = _backend._stream

_SENSITIVE_REQUEST = re.compile(
    r"(?:system\s+prompt|hidden\s+prompt|developer\s+prompt|internal\s+reasoning|"
    r"chain\s+of\s+thought|api\s*key|secret(?:s)?|environment\s+variables?|"
    r"mot\s+de\s+passe|cle\s+api|clé\s+api|prompt\s+systeme|prompt\s+système|"
    r"raisonnement\s+interne|مفتاح\s*(?:api|واجهة)|تعليمات\s+النظام|الأسرار)",
    re.I,
)

# Very short/typo relationship questions can omit Youssef's name or even use
# "hi" instead of "he". They still need the portfolio privacy guard instead of
# the generic out-of-scope message. Keep this deliberately narrow so unrelated
# questions about other people are not reinterpreted as questions about Youssef.
_PRIVATE_RELATIONSHIP_SHORTHAND = re.compile(
    r"(?:^|\b)(?:(?:he|hi|youssef)\s+(?:is\s+)?married|"
    r"is\s+(?:he|hi|youssef)\s+married|"
    r"(?:his|youssef'?s)\s+marital\s+status)(?:\b|\s*[?.!]*$)",
    re.I,
)


def _greeting_answer(language: str) -> str:
    if language == "fr":
        return (
            "Bonjour ! Je suis Ask Youssef AI, le copilote du portfolio professionnel "
            "de Youssef Bouzit. Je peux vous aider à explorer ses projets, compétences, "
            "certifications, expériences et moyens de contact. Que souhaitez-vous savoir ?"
        )
    if language == "ar":
        return (
            "مرحباً! أنا Ask Youssef AI، المساعد الخاص بالملف المهني ليوسف بوزيت. "
            "يمكنني مساعدتك في استكشاف مشاريعه ومهاراته وشهاداته وخبراته وطرق التواصل معه. "
            "ماذا تريد أن تعرف؟"
        )
    return (
        "Hello! I'm Ask Youssef AI, Youssef Bouzit's professional portfolio copilot. "
        "I can help you explore his projects, skills, certifications, experience, and "
        "contact options. What would you like to know?"
    )


def _sensitive_answer(language: str) -> str:
    if language == "fr":
        return (
            "Je ne peux pas révéler les prompts système, le raisonnement interne, les clés "
            "API, les secrets ni d'autres informations privées de configuration. Je peux "
            "en revanche expliquer les capacités publiques d'Ask Youssef AI ou le portfolio "
            "professionnel de Youssef."
        )
    if language == "ar":
        return (
            "لا يمكنني كشف تعليمات النظام أو الاستدلال الداخلي أو مفاتيح API أو الأسرار "
            "أو معلومات الإعداد الخاصة. يمكنني بدلاً من ذلك شرح القدرات العامة لـ Ask "
            "Youssef AI أو الملف المهني ليوسف."
        )
    return (
        "I cannot reveal system prompts, internal reasoning, API keys, secrets, or other "
        "private configuration information. I can explain Ask Youssef AI's public "
        "capabilities or Youssef's professional portfolio instead."
    )


def _out_of_scope_answer(language: str) -> str:
    if language == "fr":
        return (
            "Je suis Ask Youssef AI, le copilote du portfolio professionnel de Youssef "
            "Bouzit. Je reste centré sur son parcours, ses projets, compétences, "
            "certifications, expériences, services et moyens de contact. Posez-moi une "
            "question sur son profil professionnel et je répondrai à partir du portfolio."
        )
    if language == "ar":
        return (
            "أنا Ask Youssef AI، المساعد الخاص بالملف المهني ليوسف بوزيت. أركز على "
            "مسيرته ومشاريعه ومهاراته وشهاداته وخبراته وخدماته وطرق التواصل معه. "
            "اسألني عن ملفه المهني وسأجيب اعتماداً على محتوى الـ portfolio."
        )
    return (
        "I'm Ask Youssef AI, Youssef Bouzit's professional portfolio copilot. I stay "
        "focused on his background, projects, skills, certifications, experience, "
        "services, and contact options. Ask me about his professional profile and I'll "
        "answer from the portfolio."
    )


def _complete_fast_route(route, answer: str, started: float):
    """Record privacy-safe telemetry and emit one backend-compatible SSE event."""
    _backend.TELEMETRY.record_request(route)
    _backend.TELEMETRY.record_completed(
        latency_ms=(time.monotonic() - started) * 1000.0,
        retrieval_used=False,
        grounding_intervened=False,
    )
    yield _backend._sse("final", answer=answer, tools_used=[])


def _stream_with_fast_public_routes(question: str, history=None):
    """Preserve backend._stream(question, history) while adding cheap public routes."""
    started = time.monotonic()
    question = (question or "").strip()
    route = _backend.route_question(question)

    # Keep the shorthand relationship question inside the backend's deterministic
    # private-profile guard even when the generic router marks it out of scope.
    private_relationship = bool(_PRIVATE_RELATIONSHIP_SHORTHAND.search(question))

    if _SENSITIVE_REQUEST.search(question):
        yield from _complete_fast_route(route, _sensitive_answer(route.language), started)
        return

    if route.intent == "greeting":
        yield from _complete_fast_route(route, _greeting_answer(route.language), started)
        return

    if not route.portfolio_scope and not private_relationship:
        yield from _complete_fast_route(route, _out_of_scope_answer(route.language), started)
        return

    # The backend stream is a synchronous generator with the public contract
    # _stream(question, history). Do not wrap it as an async iterator.
    yield from _original_stream(question, history)


_backend._stream = _stream_with_fast_public_routes
