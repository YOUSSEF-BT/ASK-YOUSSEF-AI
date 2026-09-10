"""Vercel entrypoint for Ask Youssef AI.

This wrapper keeps the core backend host-agnostic while selecting settings that
fit Vercel Hobby: bundled portfolio snapshot, in-process retrieval, local
FastEmbed vectors, and the public GitHub Pages origin. GEMINI_API_KEY remains a
secret and is used for answer generation only; it is never committed here.
"""
from __future__ import annotations

import os

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
    "GEMINI_TIMEOUT": "45",
    "GEMINI_RETRIES": "4",
    "MAX_QUESTION_CHARS": "600",
    "MAX_TURN_CHARS": "600",
    "RATE_PER_MIN": "6",
    "RATE_PER_DAY": "40",
    "GLOBAL_PER_DAY": "800",
}

for _key, _value in _DEFAULTS.items():
    os.environ.setdefault(_key, _value)

# Vercel's FastAPI runtime discovers the exported variable named `app`.
from backend.app import app  # noqa: E402,F401
