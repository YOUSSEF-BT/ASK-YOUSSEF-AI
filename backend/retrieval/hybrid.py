"""Hybrid retrieval for Ask Youssef AI.

Combines semantic retrieval, an independent BM25-style lexical retriever, and a
field-aware structured professional-profile retriever. Ranked lists are fused
with Reciprocal Rank Fusion (RRF), followed by small deterministic evidence
quality boosts. The public `.query()` interface matches the existing RAG
retriever, so the agent/MCP layers do not need to know which retrieval strategy
is underneath.

This module intentionally avoids a heavy cross-encoder dependency. A learned
reranker can be plugged in later behind the same interface once it is benchmarked.
"""
from __future__ import annotations

import math
import os
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from retrieval.structured import StructuredProfileRetriever

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
    structured_rank: int | None
    rrf_score: float
    lexical_score: float
    structured_score: float
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
    """Semantic + lexical + synchronized structured retrieval with RRF fusion."""

    def __init__(
        self,
        semantic_rag: Any,
        *,
        structured_retriever: Any | bool | None = None,
        rrf_k: int = 60,
        semantic_weight: float = 1.0,
        lexical_weight: float = 1.0,
        structured_weight: float = 1.15,
        candidate_multiplier: int = 4,
    ) -> None:
        self.semantic_rag = semantic_rag
        if structured_retriever is False:
            self.structured = None
        elif structured_retriever is None:
            default_profile = Path(__file__).resolve().parents[1] / "data" / "profile.json"
            profile_path = Path(os.environ.get("STRUCTURED_PROFILE_PATH", str(default_profile)))
            loaded = StructuredProfileRetriever.from_path(profile_path)
            self.structured = loaded if loaded.count else None
        else:
            self.structured = structured_retriever
        self.rrf_k = rrf_k
        self.semantic_weight = semantic_weight
        self.lexical_weight = lexical_weight
        self.structured_weight = structured_weight
        self.candidate_multiplier = max(2, candidate_multiplier)
        self._metas = list(getattr(getattr(semantic_rag, "store", None), "metas", []) or [])
        self.lexical = BM25Index(self._metas)

    @property
    def num_chunks(self) -> int:
        return len(self._metas)

    @staticmethod
    def _exact_match_boost(query: str, meta: dict[str, Any]) -> float:
        """Reward exact technical identifiers without overpowering rank fusion."""
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
        structured = (
            list(self.structured.search(question, k=candidate_k))
            if self.structured is not None
            else []
        )

        metas: dict[tuple[str, int], dict[str, Any]] = {}
        semantic_rank: dict[tuple[str, int], int] = {}
        lexical_rank: dict[tuple[str, int], int] = {}
        structured_rank: dict[tuple[str, int], int] = {}
        lexical_raw: dict[tuple[str, int], float] = {}
        structured_raw: dict[tuple[str, int], float] = {}
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

        for rank, hit in enumerate(structured, 1):
            key = _key(hit.meta)
            metas[key] = hit.meta
            structured_rank[key] = rank
            structured_raw[key] = float(hit.score)
            fused[key] += self.structured_weight / (self.rrf_k + rank)

        if not fused:
            return []

        ideal = (
            self.semantic_weight / (self.rrf_k + 1)
            + self.lexical_weight / (self.rrf_k + 1)
            + ((self.structured_weight / (self.rrf_k + 1)) if self.structured is not None else 0.0)
        )
        ranked: list[tuple[float, tuple[str, int], RetrievalTrace]] = []
        for key, rrf in fused.items():
            boost = self._exact_match_boost(question, metas[key])
            # Structured retrieval has explicit field/intent evidence. Preserve a
            # bounded part of that confidence after rank fusion so exact entities
            # (model names, issuers, companies, certifications) are not diluted.
            structured_confidence = structured_raw.get(key, 0.0)
            structured_boost = 0.08 * structured_confidence
            normalized = min(1.0, (rrf / ideal) + boost + structured_boost) if ideal else 0.0
            trace = RetrievalTrace(
                semantic_rank=semantic_rank.get(key),
                lexical_rank=lexical_rank.get(key),
                structured_rank=structured_rank.get(key),
                rrf_score=rrf,
                lexical_score=lexical_raw.get(key, 0.0),
                structured_score=structured_confidence,
                exact_match_boost=boost,
            )
            ranked.append((normalized, key, trace))

        ranked.sort(key=lambda row: row[0], reverse=True)
        results: list[Hit] = []
        strategy = "hybrid_rrf_structured" if self.structured is not None else "hybrid_rrf"
        for score, key, trace in ranked[:k]:
            meta = dict(metas[key])
            meta["retrieval"] = {
                "strategy": strategy,
                "semantic_rank": trace.semantic_rank,
                "lexical_rank": trace.lexical_rank,
                "structured_rank": trace.structured_rank,
                "rrf_score": round(trace.rrf_score, 6),
                "lexical_score": round(trace.lexical_score, 6),
                "structured_score": round(trace.structured_score, 6),
                "exact_match_boost": round(trace.exact_match_boost, 6),
            }
            results.append(Hit(score=float(score), meta=meta))
        return results
