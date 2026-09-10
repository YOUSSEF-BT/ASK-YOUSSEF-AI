"""Phase 1 — Retrieval-Augmented Generation, from scratch.

The whole RAG pipeline in one file, read top to bottom as the data flows:

    posts ──► chunk ──► embed ──► vector store ──► retrieve ──► generate ──► answer

Each stage is a small, swappable piece behind a tiny interface — that
separation is the design lesson of Phase 1. Swap TF-IDF for a real embedding
model, or the NumPy store for FAISS, without touching the orchestrator.

    rag = RAG().build("data/posts")
    hits = rag.query("how does attention work?", k=4)
    print(ExtractiveGenerator().answer("how does attention work?", hits))

Sections:
  1. Chunking      — split markdown into retrieval-sized, heading-aware pieces
  2. Embeddings    — TF-IDF (from scratch) and semantic (sentence-transformers)
  3. Vector store  — flat in-memory cosine index + top-k
  4. RAG           — ties chunk + embed + store together
  5. Generation    — turn retrieved chunks into an answer (extractive or LLM)
"""
from __future__ import annotations

import glob
import math
import os
import re
import textwrap
from dataclasses import dataclass
from typing import Any

import numpy as np


# ===========================================================================
# 1. Chunking — from scratch
# ---------------------------------------------------------------------------
# Split a blog post into retrieval-sized chunks while preserving the nearest
# heading as context. No dependencies: this is the "understand the mechanics"
# version. Production would use a token-aware, overlap-aware splitter, but the
# idea is exactly this.
# ===========================================================================

_FRONTMATTER = re.compile(r"^---\n.*?\n---\n", re.DOTALL)
_HEADING = re.compile(r"^(#{1,6})\s+(.*)$")
_JSX_TAG = re.compile(r"^<[A-Za-z/].*?>$")


@dataclass
class Chunk:
    text: str        # the chunk body
    source: str      # slug the chunk came from (e.g. "gpt-2-attention")
    heading: str     # nearest section heading, for citation context
    idx: int         # position of the chunk within its source
    url: str = ""    # canonical page URL (from frontmatter), for real citations
    title: str = ""  # page title (from frontmatter), for display


def strip_frontmatter(md: str) -> str:
    return _FRONTMATTER.sub("", md, count=1)


def parse_frontmatter(md: str) -> dict[str, str]:
    """Pull simple `key: value` pairs out of a leading `--- … ---` block.
    Used to carry the page title and canonical URL from crawled snapshots."""
    m = _FRONTMATTER.match(md)
    if not m:
        return {}
    fields: dict[str, str] = {}
    for line in m.group(0).splitlines()[1:-1]:      # skip the two --- fences
        if ":" in line:
            key, _, val = line.partition(":")
            fields[key.strip()] = val.strip().strip('"').strip("'")
    return fields


def clean(md: str) -> str:
    """Drop MDX import lines and standalone component/HTML tags so retrieval
    sees prose, not markup."""
    out = []
    for line in md.splitlines():
        s = line.strip()
        if s.startswith("import ") and " from " in s:
            continue
        if _JSX_TAG.match(s):
            continue
        out.append(line)
    return "\n".join(out)


def _window(text: str, max_chars: int) -> list[str]:
    """Greedily pack blank-line-separated paragraphs into <= max_chars pieces."""
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    pieces, buf = [], ""
    for p in paras:
        if buf and len(buf) + len(p) + 2 > max_chars:
            pieces.append(buf)
            buf = p
        else:
            buf = f"{buf}\n\n{p}" if buf else p
    if buf:
        pieces.append(buf)
    return pieces


def chunk_markdown(md: str, source: str, max_chars: int = 800,
                   url: str = "", title: str = "") -> list[Chunk]:
    body = clean(strip_frontmatter(md))
    chunks: list[Chunk] = []
    heading = title or source
    section: list[str] = []
    counter = 0

    def flush() -> None:
        nonlocal section, counter
        text = "\n".join(section).strip()
        section = []
        if not text:
            return
        for piece in _window(text, max_chars):
            chunks.append(Chunk(text=piece, source=source, heading=heading,
                                idx=counter, url=url, title=title))
            counter += 1

    for line in body.splitlines():
        m = _HEADING.match(line)
        if m:
            flush()               # close out the previous section
            heading = m.group(2).strip()
        else:
            section.append(line)
    flush()
    return chunks


# ===========================================================================
# 2. Embeddings
# ---------------------------------------------------------------------------
# Two backends behind one tiny interface (`fit`, `encode`):
#   * TfidfEmbedder — from scratch, NumPy only. Instant, no download. Great for
#     understanding *why* retrieval works (weighted word overlap → vectors →
#     cosine), but lexical: it can't tell "car" and "automobile" are related.
#   * SentenceTransformerEmbedder — semantic embeddings from a real model (the
#     Phase-1b upgrade; needs `pip install sentence-transformers`). Same
#     interface, so the rest of the pipeline doesn't change.
# Swap the backend, keep the system.
# ===========================================================================

_TOKEN = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


class TfidfEmbedder:
    """Classic TF-IDF vectors, L2-normalized so a dot product == cosine."""

    def __init__(self) -> None:
        self.vocab: dict[str, int] = {}
        self.idf: np.ndarray | None = None

    def fit(self, docs: list[str]) -> "TfidfEmbedder":
        # build vocabulary and document frequencies
        df: dict[str, int] = {}
        for doc in docs:
            for tok in set(tokenize(doc)):
                df[tok] = df.get(tok, 0) + 1
        self.vocab = {tok: i for i, tok in enumerate(sorted(df))}
        n = len(docs)
        idf = np.zeros(len(self.vocab), dtype=np.float32)
        for tok, i in self.vocab.items():
            # smoothed idf: rare words weigh more
            idf[i] = math.log((1 + n) / (1 + df[tok])) + 1.0
        self.idf = idf
        return self

    def encode(self, texts: list[str]) -> np.ndarray:
        if self.idf is None:
            raise RuntimeError("call fit() before encode()")
        mat = np.zeros((len(texts), len(self.vocab)), dtype=np.float32)
        for r, text in enumerate(texts):
            for tok in tokenize(text):
                j = self.vocab.get(tok)
                if j is not None:
                    mat[r, j] += 1.0            # term frequency
        mat *= self.idf                          # weight by idf
        norms = np.linalg.norm(mat, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return mat / norms                       # L2 normalize -> cosine via dot


class SentenceTransformerEmbedder:
    """Semantic embeddings (Phase 1b). Same interface as TfidfEmbedder."""

    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2") -> None:
        from sentence_transformers import SentenceTransformer  # lazy import
        self.model = SentenceTransformer(model_name)

    def fit(self, docs: list[str]) -> "SentenceTransformerEmbedder":
        return self  # pretrained; nothing to fit

    def encode(self, texts: list[str]) -> np.ndarray:
        return self.model.encode(texts, normalize_embeddings=True).astype(np.float32)


class FastEmbedEmbedder:
    """Semantic embeddings via **fastembed** — ONNX runtime, no torch (~300 MB
    instead of ~1 GB), no API key, no per-query cost. Same `fit`/`encode`
    interface as the others, so the rest of the pipeline is untouched.

    This is the deploy embedder: it gives real semantic retrieval (synonyms,
    "email" → the "get in touch" section) while fitting a 512 MB free tier, and
    it keeps the LLM key (Gemini) spent on generation only."""

    def __init__(self, model_name: str | None = None) -> None:
        from fastembed import TextEmbedding  # lazy: downloads the ONNX model once
        self.model_name = model_name or os.environ.get(
            "FASTEMBED_MODEL", "BAAI/bge-small-en-v1.5")
        self.model = TextEmbedding(model_name=self.model_name)

    def fit(self, docs: list[str]) -> "FastEmbedEmbedder":
        return self  # pretrained; nothing to fit

    def encode(self, texts: list[str]) -> np.ndarray:
        # fastembed yields one vector per text; stack then L2-normalize so a dot
        # product is cosine (VectorStore assumes unit vectors).
        vecs = np.asarray(list(self.model.embed(list(texts))), dtype=np.float32)
        if vecs.ndim == 1:                      # single text → (d,) → (1, d)
            vecs = vecs.reshape(1, -1)
        norms = np.linalg.norm(vecs, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return vecs / norms


class GeminiEmbedder:
    """Semantic embeddings via the **Gemini Embedding API** (`gemini-embedding-001`).

    Unlike FastEmbedEmbedder there is NO local model / onnxruntime in memory — the
    vectors come from the API — so this fits tiny hosts (Render's 512 MB free tier,
    where loading fastembed OOMs). It reuses the same GEMINI_API_KEY.

    Retrieval quality: documents are embedded with task_type RETRIEVAL_DOCUMENT and
    queries with RETRIEVAL_QUERY (via `encode_query`), which is what the model wants
    for search. Vectors are truncated to `output_dimensionality` (MRL) then
    re-normalized to unit length (truncated Gemini vectors aren't unit by default),
    so VectorStore's dot-product == cosine still holds.

    Rate-limit hygiene (see module notes): gemini-embedding-2 returns exactly one
    embedding per request, so documents are embedded one text per call, pacing
    `per_min` requests then cooling down to stay under the 100/min free-tier cap.
    Results are cached to disk (keyed by content hash) so a given corpus is
    embedded once — CI precomputes + commits that cache, so Render boots on a cache
    hit and never embeds the whole site on a cold start. Transient errors (429,
    5xx) are retried with exponential backoff. A user query is a single request."""

    def __init__(self, model: str | None = None, dim: int | None = None,
                 per_min: int | None = None) -> None:
        import time as _time
        from google import genai
        from google.genai import types
        self._time = _time
        self._types = types
        self.model = model or os.environ.get("GEMINI_EMBED_MODEL", "gemini-embedding-2")
        self.dim = int(dim or os.environ.get("GEMINI_EMBED_DIM", "768"))
        # Free tier = 100 embed requests/min and EACH TEXT counts as one request
        # (a 100-item call consumes 100). So we send at most `per_min` texts per
        # window, then cool down `cooldown`s. Default 50/min — half the limit, to
        # stay safe alongside query-time embeds sharing the same key.
        self.per_min = int(per_min or os.environ.get("GEMINI_EMBED_PER_MIN", "50"))
        self.cooldown = float(os.environ.get("GEMINI_EMBED_COOLDOWN", "60"))
        self.retries = int(os.environ.get("GEMINI_EMBED_RETRIES", "5"))
        # Default to a committed cache next to this file (backend/data/embcache):
        # CI (crawl.yml) precomputes + commits it, so Render finds a cache hit on
        # boot and never embeds the whole corpus on a cold start. Override with
        # EMBED_CACHE_DIR. Resolved from __file__ so cwd doesn't matter.
        self.cache_dir = os.environ.get("EMBED_CACHE_DIR") or os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "data", "embcache")
        self.client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

    def fit(self, docs: list[str]) -> "GeminiEmbedder":
        return self  # pretrained; nothing to fit

    @staticmethod
    def _retry_delay(exc: Exception) -> float:
        """Honor the server's 'Please retry in Xs' hint from a 429 body."""
        m = re.search(r"retry in ([0-9.]+)s", str(exc))
        return float(m.group(1)) + 1.0 if m else 0.0

    def _embed_one(self, text: str, task_type: str) -> list[float]:
        """Embed a single text. gemini-embedding-2 returns exactly one embedding
        per request (it ignores extra items in a multi-text call), so we always
        send one text at a time and read embeddings[0]."""
        cfg = self._types.EmbedContentConfig(
            task_type=task_type, output_dimensionality=self.dim)
        last_exc = None
        for attempt in range(self.retries):
            try:
                resp = self.client.models.embed_content(
                    model=self.model, contents=[text], config=cfg)
                return list(resp.embeddings[0].values)
            except Exception as exc:            # 429 / 5xx / transient
                last_exc = exc
                wait = self._retry_delay(exc) or min(2 ** attempt, 30)
                self._time.sleep(wait)
        raise last_exc

    def _embed(self, texts: list[str], task_type: str) -> np.ndarray:
        rows: list[list[float]] = []
        n = len(texts)
        for idx, text in enumerate(texts):
            rows.append(self._embed_one(text, task_type))
            done = idx + 1
            # each request counts against the 100/min free-tier cap; after every
            # `per_min` requests, cool down so we never approach it.
            if done < n and done % self.per_min == 0:
                print(f"[embed] {done}/{n} texts; cooling down {self.cooldown:.0f}s "
                      f"(free tier {self.per_min}/min)", flush=True)
                self._time.sleep(self.cooldown)
        vecs = np.asarray(rows, dtype=np.float32)
        if vecs.ndim == 1:
            vecs = vecs.reshape(1, -1)
        norms = np.linalg.norm(vecs, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return vecs / norms                      # re-normalize truncated vectors

    def _cache_path(self, texts: list[str]) -> str:
        import hashlib
        # key on model|dim|corpus text so a content change misses (re-embeds) and
        # an identical corpus hits — regardless of which host built the cache.
        h = hashlib.sha256(f"{self.model}|{self.dim}|{len(texts)}".encode())
        for t in texts:
            h.update(b"\x00")
            h.update(t.encode("utf-8", "replace"))
        return os.path.join(self.cache_dir, h.hexdigest() + ".npy")

    def encode(self, texts: list[str]) -> np.ndarray:
        """Embed DOCUMENTS (used at index time). Cached to disk by content hash so
        the same corpus isn't re-embedded on every boot — the main rate-limit lever."""
        texts = list(texts)
        path = self._cache_path(texts)
        try:
            if os.path.exists(path):
                vecs = np.load(path)
                if vecs.shape[0] == len(texts):
                    return vecs
        except Exception:
            pass                                 # corrupt/mismatched cache → re-embed
        vecs = self._embed(texts, "RETRIEVAL_DOCUMENT")
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            np.save(path, vecs)
        except Exception:
            pass                                 # cache is best-effort
        return vecs

    def encode_query(self, texts: list[str]) -> np.ndarray:
        """Embed QUERIES (used at search time) — RETRIEVAL_QUERY, no caching."""
        return self._embed(list(texts), "RETRIEVAL_QUERY")


def make_embedder(kind: str | None = None) -> Any:
    """Pick the embedder by name (env EMBEDDER; default 'gemini' for the deploy).

      gemini  → GeminiEmbedder          (API, no local model — fits 512 MB)
      fastembed → FastEmbedEmbedder     (local ONNX — needs ~more RAM)
      st      → SentenceTransformerEmbedder (needs torch)
      tfidf   → TfidfEmbedder           (lexical, zero deps)"""
    kind = (kind or os.environ.get("EMBEDDER", "gemini")).lower()
    if kind in ("gemini", "gemini-embedding", "api"):
        return GeminiEmbedder()
    if kind in ("fastembed", "onnx"):
        return FastEmbedEmbedder()
    if kind in ("st", "sentence-transformer", "sentencetransformer"):
        return SentenceTransformerEmbedder()
    return TfidfEmbedder()


# ===========================================================================
# 3. Vector store — from scratch
# ---------------------------------------------------------------------------
# A flat in-memory index: a matrix of normalized vectors plus parallel metadata.
# Search is a single matrix-vector product (every chunk's cosine similarity to
# the query at once) then a top-k. This is exactly what a vector DB does under
# the hood — Phase 1b swaps this for FAISS/Qdrant behind the same `search` call.
# ===========================================================================

@dataclass
class Hit:
    score: float
    meta: dict[str, Any]


class VectorStore:
    def __init__(self) -> None:
        self.vectors: np.ndarray | None = None   # (N, d), L2-normalized
        self.metas: list[dict[str, Any]] = []

    def add(self, vectors: np.ndarray, metas: list[dict[str, Any]]) -> None:
        self.vectors = vectors if self.vectors is None else np.vstack([self.vectors, vectors])
        self.metas.extend(metas)

    def search(self, query_vec: np.ndarray, k: int = 4) -> list[Hit]:
        if self.vectors is None:
            return []
        # both sides are unit-normalized, so the dot product is cosine similarity.
        # (errstate silences a spurious matmul warning from Apple's Accelerate BLAS;
        # the inputs are finite — verified — so the result is correct.)
        with np.errstate(divide="ignore", over="ignore", invalid="ignore"):
            sims = self.vectors @ query_vec.reshape(-1)
        k = min(k, len(sims))
        top = np.argpartition(-sims, k - 1)[:k]
        top = top[np.argsort(-sims[top])]
        return [Hit(score=float(sims[i]), meta=self.metas[i]) for i in top]


# ===========================================================================
# 4. RAG orchestrator — ties chunking + embeddings + the store together
# ===========================================================================

class RAG:
    def __init__(self, embedder: Any | None = None) -> None:
        self.embedder = embedder or TfidfEmbedder()
        self.store = VectorStore()
        self.chunks: list[Any] = []

    def build(self, posts_dir: str, max_chars: int = 800) -> "RAG":
        paths = sorted(glob.glob(os.path.join(posts_dir, "*.md")) +
                       glob.glob(os.path.join(posts_dir, "*.mdx")))
        if not paths:
            raise FileNotFoundError(f"no .md/.mdx posts found in {posts_dir}")

        for path in paths:
            slug = os.path.splitext(os.path.basename(path))[0]
            with open(path, encoding="utf-8") as fh:
                md = fh.read()
            fm = parse_frontmatter(md)
            self.chunks.extend(chunk_markdown(
                md, slug, max_chars=max_chars,
                url=fm.get("url", ""), title=fm.get("title", "")))
        return self._index()

    def build_pages(self, pages: list[Any], max_chars: int = 800) -> "RAG":
        """Build the index straight from crawled `Page` objects (url/title/text),
        no disk round-trip. Lets the app crawl the live site on boot and index it
        in memory — same chunking + embedding as build(), different source."""
        from crawl import slug_for  # local import: crawl doesn't import rag
        for page in pages:
            self.chunks.extend(chunk_markdown(
                page.text, slug_for(page.url), max_chars=max_chars,
                url=page.url, title=page.title))
        if not self.chunks:
            raise ValueError("no chunks produced from the crawled pages")
        return self._index()

    def _index(self) -> "RAG":
        """Embed the accumulated chunks and load them into the vector store."""
        texts = [c.text for c in self.chunks]
        self.embedder.fit(texts)
        vectors = self.embedder.encode(texts)
        metas = [{"text": c.text, "source": c.source, "heading": c.heading,
                  "idx": c.idx, "url": c.url, "title": c.title}
                 for c in self.chunks]
        self.store.add(vectors, metas)
        return self

    def query(self, question: str, k: int = 4) -> list[Hit]:
        # some embedders (Gemini) want a distinct task_type for queries vs docs;
        # use encode_query when available, else fall back to the shared encode.
        encode_q = getattr(self.embedder, "encode_query", self.embedder.encode)
        qvec = encode_q([question])[0]
        return self.store.search(qvec, k=k)

    @property
    def num_chunks(self) -> int:
        return len(self.chunks)


# ===========================================================================
# 5. Answer generation — pluggable
# ---------------------------------------------------------------------------
# The retriever finds the relevant chunks; the *generator* turns them into an
# answer, behind a tiny interface so the RAG loop doesn't care which is used:
#   * ExtractiveGenerator — no LLM, no key, no download. Stitches the top chunks
#     into a cited answer. The honest baseline: proves retrieval does the work.
#   * OpenAIGenerator — the real thing. Feeds context into a chat model with a
#     grounded prompt. Needs OPENAI_API_KEY. Same interface.
# The prompt in build_prompt is what forces the model to stay grounded.
# ===========================================================================

def build_prompt(question: str, hits: list[Any]) -> str:
    """Assemble a grounded RAG prompt from retrieved hits."""
    blocks = []
    for i, h in enumerate(hits, 1):
        src = h.meta.get("title") or h.meta.get("source", "?")
        head = h.meta.get("heading", "")
        url = h.meta.get("url", "")
        cite = f"{src} — {head}" + (f" <{url}>" if url else "")
        blocks.append(f"[{i}] (source: {cite})\n{h.meta['text']}")
    context = "\n\n".join(blocks)
    return textwrap.dedent(f"""\
        You are answering questions about Youssef and his website (blog posts,
        projects, and about/contact info). Use ONLY the context below. If the
        context does not contain the answer, say you don't know. Cite sources
        inline using their [number].

        Context:
        {context}

        Question: {question}
        Answer:""")


class ExtractiveGenerator:
    """No-LLM baseline: returns the top chunks as a cited answer."""

    def answer(self, question: str, hits: list[Any]) -> str:
        if not hits:
            return "I couldn't find anything relevant in the blog."
        lines = [f"Here's what the site says (top {len(hits)} passages):\n"]
        for i, h in enumerate(hits, 1):
            src = h.meta.get("title") or h.meta.get("source", "?")
            head = h.meta.get("heading", "")
            url = h.meta.get("url", "")
            cite = f"[{src}]({url})" if url else src
            snippet = " ".join(h.meta["text"].split())
            if len(snippet) > 400:
                snippet = snippet[:400].rsplit(" ", 1)[0] + "…"
            lines.append(f"[{i}] {cite} — {head} (score {h.score:.2f})\n    {snippet}\n")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# The `search_site` tool's text output, defined once here so the MCP server
# (mcp_server/blog_server.py) and the in-process MCP client (src/mcp.py) return
# byte-identical passages — the transport differs, the capability doesn't.
# ---------------------------------------------------------------------------

def _snippet(text: str, limit: int = 320) -> str:
    """A compact but information-preserving excerpt. Unlike a first-sentence
    preview, this keeps enough of the passage that details buried later in a
    chunk (an email, a number, a name) survive for the model to quote."""
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0] + "…"


def search_site_text(rag: "RAG", query: str, k: int = 3, min_score: float = 0.25) -> str:
    """Retrieve and format passages for the `search_site` tool."""
    hits = rag.query(query, k=k)
    if not hits:
        return "No results found. Try a different query."
    body = " || ".join(
        f"[{h.meta['source']} · relevance {h.score:.2f}] {_snippet(h.meta['text'])}"
        for h in hits
    )
    if hits[0].score < min_score:
        body += (f"  [NOTE: top relevance is only {hits[0].score:.2f} — these may "
                 "not answer the question; consider rephrasing and searching again.]")
    return body


class OpenAIGenerator:
    """Grounded generation with an OpenAI chat model (Phase 1b)."""

    def __init__(self, model: str = "gpt-4o-mini") -> None:
        from openai import OpenAI  # lazy import
        self.client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        self.model = model

    def answer(self, question: str, hits: list[Any]) -> str:
        prompt = build_prompt(question, hits)
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )
        return resp.choices[0].message.content or ""


class GeminiGenerator:
    """Grounded generation with a Gemini model (the deploy generator). Gemini is
    used for generation ONLY — embeddings are local (FastEmbedEmbedder) so the
    key/free-tier isn't spent per chunk. Same `.answer` interface."""

    def __init__(self, model: str | None = None) -> None:
        import time as _time
        from google import genai  # lazy import (google-genai SDK)
        from google.genai import types
        self._time = _time
        # short per-attempt timeout + retry: the API occasionally stalls, and one
        # retry (usually instant) beats making the caller wait out a long hang.
        # 10s = the API's minimum allowed deadline (a stalled call is dropped then retried)
        timeout_ms = max(10, int(float(os.environ.get("GEMINI_TIMEOUT", "10")))) * 1000
        self.retries = int(os.environ.get("GEMINI_RETRIES", "3"))
        self.client = genai.Client(
            api_key=os.environ["GEMINI_API_KEY"],
            http_options=types.HttpOptions(timeout=timeout_ms))
        self.model = model or os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite")

    def answer(self, question: str, hits: list[Any]) -> str:
        prompt = build_prompt(question, hits)
        last_exc = None
        for attempt in range(self.retries):
            try:
                resp = self.client.models.generate_content(
                    model=self.model, contents=prompt)
                text = (resp.text or "").strip()
                if text:
                    return text
            except Exception as exc:
                last_exc = exc
            if attempt < self.retries - 1:
                self._time.sleep(0.4 * (attempt + 1))
        if last_exc is not None:
            raise last_exc
        return ""
