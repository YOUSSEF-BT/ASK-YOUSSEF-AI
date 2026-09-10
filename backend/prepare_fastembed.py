"""Prepare the local FastEmbed model during the Vercel build.

The model is downloaded once into a project-local cache so serverless cold
starts do not spend Gemini embedding quota and do not need to download the
model again. Runtime still uses Gemini for answer generation.
"""
from __future__ import annotations

import os

from fastembed import TextEmbedding

MODEL = os.environ.get("FASTEMBED_MODEL", "BAAI/bge-small-en-v1.5")
CACHE = os.environ.get("FASTEMBED_CACHE_PATH", "backend/data/fastembed_cache")

print(f"[build] preparing FastEmbed model {MODEL} in {CACHE}", flush=True)
TextEmbedding(model_name=MODEL, cache_dir=CACHE)
print("[build] FastEmbed model ready", flush=True)
