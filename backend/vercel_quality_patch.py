"""Small Vercel-only production quality patches.

The core project stays host-agnostic. Vercel, however, prepares a FastEmbed model
inside the deployment bundle at build time. The runtime embedder must reuse that
exact cache path or a cold function may download/load the model from its default
cache again. This module also performs a final grammatical cleanup after an
untrusted/unknown citation is removed from a generated sentence.
"""
from __future__ import annotations

import os
import re

import grounding as _grounding
import rag as _rag


_DANGLING_AFTER_CITATION = (
    re.compile(
        r"\s+(?:or\s+)?any\s+(?:project|source|claim|evidence|item)\s+"
        r"(?:associated|linked|related)\s+(?:with|to)\s*([.!?])",
        re.I,
    ),
    re.compile(
        r"\s+(?:ou\s+)?(?:tout|toute)\s+(?:projet|source|affirmation|preuve|element)\s+"
        r"(?:associe|associee|lie|liee|relie|reliee)\s+(?:a|avec)\s*([.!?])",
        re.I,
    ),
)


def _cleanup_dangling_citation_text(text: str) -> str:
    cleaned = text or ""
    for pattern in _DANGLING_AFTER_CITATION:
        cleaned = pattern.sub(r"\1", cleaned)
    cleaned = re.sub(r"\(\s*\)", "", cleaned)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    cleaned = re.sub(r"[ \t]+([.,;:!?])", r"\1", cleaned)
    return cleaned.strip()


def _patch_grounding_cleanup() -> None:
    if getattr(_grounding, "_vercel_quality_cleanup", False):
        return

    original_remove = _grounding._remove_unknown_citations
    original_strip = _grounding._strip_malformed_source_brackets

    def remove_unknown(answer, unknown):
        return _cleanup_dangling_citation_text(original_remove(answer, unknown))

    def strip_malformed(text):
        return _cleanup_dangling_citation_text(original_strip(text))

    _grounding._remove_unknown_citations = remove_unknown
    _grounding._strip_malformed_source_brackets = strip_malformed
    _grounding._vercel_quality_cleanup = True


def _patch_fastembed_cache() -> None:
    cls = _rag.FastEmbedEmbedder
    if getattr(cls, "_vercel_cache_path_patch", False):
        return

    def init(self, model_name=None):
        from fastembed import TextEmbedding

        self.model_name = model_name or os.environ.get(
            "FASTEMBED_MODEL", "BAAI/bge-small-en-v1.5"
        )
        cache_dir = (os.environ.get("FASTEMBED_CACHE_PATH") or "").strip()
        kwargs = {"model_name": self.model_name}
        if cache_dir:
            if not os.path.isabs(cache_dir):
                repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                cache_dir = os.path.join(repo_root, cache_dir)
            kwargs["cache_dir"] = cache_dir
        self.model = TextEmbedding(**kwargs)

    cls.__init__ = init
    cls._vercel_cache_path_patch = True


def apply() -> None:
    _patch_fastembed_cache()
    _patch_grounding_cleanup()


apply()
