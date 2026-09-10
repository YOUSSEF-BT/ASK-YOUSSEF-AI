"""Hybrid retrieval for Ask Youssef AI.

Combines the existing semantic retriever with an independent BM25-style lexical
retriever, fuses both ranked lists with Reciprocal Rank Fusion (RRF), then applies
a small deterministic evidence-quality reranker. The public `.query()` interface
matches the existing RAG retriever, so the agent/MCP layers do not need to know
which retrieval strategy is underneath.

This module intentionally avoids a heavy cross-encoder dependency. A learned
reranker can be plugged in later behind the same interface once it is benchmarked.
"""
from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any

_TOKEN = re.compile(r"[\w+#.-]+", re.UNICODE)


def _tokens(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN.findall(text or "") if len(t) > 1]


def _key(meta: dict[str, Any]) -> tuple[str, int]:
    return str(meta.get("source", "")), int(meta.get("idx", 0))


@dataclass
class Hit:
    """Retriever-compatible result used by the agent/search formatting layer."""

    score: float
    meta: dict[str, Any]


@dataclass(frozen=True)
class RetrievalTrace:
    semantic_rank: int | None
    lexical_rank: int | None
    rrf_score: float
    lexical_score: float
    exact_match_boost: float


class BM25Index:
    """Small in-memory BM25 index over the same chunks as the semantic store."""

    def __init__(self, metas: list[dict[str, Any]], k1: float = 1.5, b: float = 0.75) -> None:
        self.metas = metas
        self.k1 = k1
        self.b = b
        self.docs = [_tokens(self._searchable_text(m)) for m in metas]
        self.lengths = [len(d) for d in self.docs]
        self.avg_len = (sum(self.lengths) / len(self.lengths)) if self.lengths else 1.0
        self.tf = [Counter(d) for d in self.docs]
        df: Counter[str] = Counter()
        for doc in self.docs:
            df.update(set(doc))
        self.df = df
        self.n = len(self.docs)

    @staticmethod
    def _searchable_text(meta: dict[str, Any]) -> str:
        return " ".join(
            str(meta.get(field, ""))
            for field in ("title", "heading", "source", "text")
        )

    def _idf(self, term: str) -> float:
        n_q = self.df.get(term, 0)
        return math.log(1.0 + (self.n - n_q + 0.5) / (n_q + 0.5)) if self.n else 0.0

    def search(self, query: str, k: int = 12) -> list[tuple[float, dict[str, Any]]]:
        terms = _tokens(query)
        if not terms or not self.metas:
            return []
        scores: list[tuple[float, int]] = []
        for i, freqs in enumerate(self.tf):
            dl = self.lengths[i] or 1
            score = 0.0
            for term in terms:
                f = freqs.get(term, 0)
                if not f:
                    continue
                denom = f + self.k1 * (1.0 - self.b + self.b * dl / self.avg_len)
                score += self._idf(term) * (f * (self.k1 + 1.0)) / denom
            if score > 0:
                scores.append((score, i))
        scores.sort(key=lambda x: x[0], reverse=True)
        return [(score, self.metas[i]) for score, i in scores[:k]]


class HybridRetriever:
    """Semantic + lexical retrieval with RRF and deterministic evidence reranking."""

    def __init__(
        self,
        semantic_rag: Any,
        *,
        rrf_k: int = 60,
        semantic_weight: float = 1.0,
        lexical_weight: float = 1.0,
        candidate_multiplier: int = 4,
    ) -> None:
        self.semantic_rag = semantic_rag
        self.rrf_k = rrf_k
        self.semantic_weight = semantic_weight
        self.lexical_weight = lexical_weight
        self.candidate_multiplier = max(2, candidate_multiplier)
        self._metas = list(getattr(getattr(semantic_rag, "store", None), "metas", []) or [])
        self.lexical = BM25Index(self._metas)

    @property
    def num_chunks(self) -> int:
        return len(self._metas)

    @staticmethod
    def _exact_match_boost(query: str, meta: dict[str, Any]) -> float:
        """Reward exact technical identifiers without overpowering semantic rank."""
        q_terms = set(_tokens(query))
        if not q_terms:
            return 0.0
        title_terms = set(_tokens(f"{meta.get('title', '')} {meta.get('heading', '')}"))
        text_terms = set(_tokens(str(meta.get("text", ""))))
        title_overlap = len(q_terms & title_terms) / len(q_terms)
        text_overlap = len(q_terms & text_terms) / len(q_terms)
        return 0.003 * title_overlap + 0.0015 * text_overlap

    def query(self, question: str, k: int = 4) -> list[Hit]:
        if k <= 0:
            return []
        candidate_k = max(k * self.candidate_multiplier, 12)
        semantic = list(self.semantic_rag.query(question, k=candidate_k))
        lexical = self.lexical.search(question, k=candidate_k)

        metas: dict[tuple[str, int], dict[str, Any]] = {}
        semantic_rank: dict[tuple[str, int], int] = {}
        lexical_rank: dict[tuple[str, int], int] = {}
        lexical_raw: dict[tuple[str, int], float] = {}
        fused: defaultdict[tuple[str, int], float] = defaultdict(float)

        for rank, hit in enumerate(semantic, 1):
            key = _key(hit.meta)
            metas[key] = hit.meta
            semantic_rank[key] = rank
            fused[key] += self.semantic_weight / (self.rrf_k + rank)

        for rank, (score, meta) in enumerate(lexical, 1):
            key = _key(meta)
            metas[key] = meta
            lexical_rank[key] = rank
            lexical_raw[key] = score
            fused[key] += self.lexical_weight / (self.rrf_k + rank)

        if not fused:
            return []

        ideal = (
            self.semantic_weight / (self.rrf_k + 1)
            + self.lexical_weight / (self.rrf_k + 1)
        )
        ranked: list[tuple[float, tuple[str, int], RetrievalTrace]] = []
        for key, rrf in fused.items():
            boost = self._exact_match_boost(question, metas[key])
            normalized = min(1.0, (rrf / ideal) + boost) if ideal else 0.0
            trace = RetrievalTrace(
                semantic_rank=semantic_rank.get(key),
                lexical_rank=lexical_rank.get(key),
                rrf_score=rrf,
                lexical_score=lexical_raw.get(key, 0.0),
                exact_match_boost=boost,
            )
            ranked.append((normalized, key, trace))

        ranked.sort(key=lambda row: row[0], reverse=True)
        results: list[Hit] = []
        for score, key, trace in ranked[:k]:
            meta = dict(metas[key])
            meta["retrieval"] = {
                "strategy": "hybrid_rrf",
                "semantic_rank": trace.semantic_rank,
                "lexical_rank": trace.lexical_rank,
                "rrf_score": round(trace.rrf_score, 6),
                "lexical_score": round(trace.lexical_score, 6),
                "exact_match_boost": round(trace.exact_match_boost, 6),
            }
            results.append(Hit(score=float(score), meta=meta))
        return results
