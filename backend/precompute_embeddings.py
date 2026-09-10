"""Precompute + commit the document embeddings for the crawl snapshot.

Run in CI (see .github/workflows/crawl.yml) right after the crawl, so the
embedding cache is committed alongside backend/data/site. Render then finds a
cache hit on boot and never embeds the whole corpus on a cold start (which at
the free-tier 100 req/min pace would take minutes and blow the port-open
timeout).

It builds the exact same index app.py builds at boot — RAG(make_embedder()).
build(CORPUS_DIR) — so the cache key (hash of model|dim|chunk-texts) matches
what the app computes. Anything that changes the corpus text changes the key and
forces a re-embed; an identical corpus is a hit.

Usage:  GEMINI_API_KEY=... EMBEDDER=gemini \\
        CORPUS_DIR=backend/data/site EMBED_CACHE_DIR=backend/data/embcache \\
        python backend/precompute_embeddings.py
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from rag import RAG, make_embedder  # noqa: E402


def main() -> int:
    corpus = os.environ.get("CORPUS_DIR", os.path.join(HERE, "data", "site"))
    if not (os.path.isdir(corpus) and os.listdir(corpus)):
        print(f"[precompute] no snapshot at {corpus}; nothing to embed", flush=True)
        return 0
    embedder = make_embedder()
    cache_dir = getattr(embedder, "cache_dir", "?")
    print(f"[precompute] embedding {corpus} with {type(embedder).__name__} "
          f"(model={getattr(embedder, 'model', '?')}, dim={getattr(embedder, 'dim', '?')}) "
          f"→ cache {cache_dir}", flush=True)
    rag = RAG(embedder=embedder).build(corpus)
    print(f"[precompute] done — {rag.num_chunks} chunks embedded and cached", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
