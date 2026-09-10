"""Vercel entrypoint for Ask Youssef AI.

This wrapper keeps the core backend host-agnostic while selecting settings that
fit Vercel Hobby: bundled portfolio snapshot, in-process retrieval, local
FastEmbed vectors, and the public GitHub Pages origin. GEMINI_API_KEY remains a
secret and is used for answer generation only; it is never committed here.
"""
from __future__ import annotations

import os
import sys

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

# Vercel's FastAPI runtime discovers the exported variable named `app`.
from backend.app import app  # noqa: E402,F401
