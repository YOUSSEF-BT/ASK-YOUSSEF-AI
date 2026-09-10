"""Vercel entrypoint for Ask Youssef AI.

This wrapper keeps the core backend host-agnostic while selecting settings that
fit Vercel Hobby: bundled portfolio snapshot, in-process retrieval, local
FastEmbed vectors, and the public GitHub Pages origin. GEMINI_API_KEY remains a
secret and is used for answer generation only; it is never committed here.
"""
from __future__ import annotations

import os
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

# Apply Vercel-only reliability/latency optimizations before backend.app
# imports and builds the shared agent. Core local/Docker behavior is unchanged.
_BACKEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend")
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)
import vercel_agent_patch  # noqa: E402,F401
import vercel_gemini_failover  # noqa: E402,F401

import backend.app as _backend  # noqa: E402

# Vercel's FastAPI runtime discovers the exported variable named `app`.
app = _backend.app

# Greetings are deterministic product UX, not a knowledge-retrieval task. Keep
# them instant and free: no Gemini call, no search tool, no accidental citation.
_original_stream = _backend._stream


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


def _production_stream(question: str, history=None):
    route = _backend.route_question(question)
    if route.intent == "greeting":
        started = time.monotonic()
        _backend.TELEMETRY.record_request(route)
        answer = _greeting_answer(route.language)
        _backend.TELEMETRY.record_completed(
            latency_ms=(time.monotonic() - started) * 1000.0,
            retrieval_used=False,
            grounding_intervened=False,
        )
        yield _backend._sse("final", answer=answer, tools_used=[])
        return
    yield from _original_stream(question, history)


_backend._stream = _production_stream


@app.get("/")
def service_root():
    """Human-friendly root for visitors who open the backend URL directly."""
    return {
        "name": "Ask Youssef AI",
        "status": "live",
        "description": "Multilingual, retrieval-grounded professional portfolio copilot for Youssef Bouzit.",
        "portfolio": "https://youssef-bt.github.io/",
        "health": "/health",
        "capabilities": "/capabilities",
        "api_docs": "/docs",
    }
