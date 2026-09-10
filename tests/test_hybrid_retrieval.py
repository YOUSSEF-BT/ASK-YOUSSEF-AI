import sys
import unittest
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from retrieval.hybrid import BM25Index, HybridRetriever  # noqa: E402


@dataclass
class FakeHit:
    score: float
    meta: dict


class FakeStore:
    def __init__(self, metas):
        self.metas = metas


class FakeSemanticRAG:
    def __init__(self, metas, ranked_indices):
        self.store = FakeStore(metas)
        self._ranked_indices = ranked_indices

    def query(self, question, k=4):
        del question
        return [
            FakeHit(score=1.0 - (rank * 0.05), meta=self.store.metas[idx])
            for rank, idx in enumerate(self._ranked_indices[:k])
        ]


METAS = [
    {
        "source": "accident-detection",
        "idx": 0,
        "title": "Real-Time Road Accident Detection",
        "heading": "Model",
        "text": "The accident detector uses YOLOv11s with BoT-SORT tracking and OpenCV.",
        "url": "https://example.com/accident",
    },
    {
        "source": "rag-project",
        "idx": 0,
        "title": "Legal RAG System",
        "heading": "Retrieval",
        "text": "A grounded RAG pipeline performs semantic retrieval and citations over legal documents.",
        "url": "https://example.com/rag",
    },
    {
        "source": "generic-profile",
        "idx": 0,
        "title": "About",
        "heading": "Profile",
        "text": "Youssef builds machine learning and artificial intelligence projects.",
        "url": "https://example.com/about",
    },
]


class BM25IndexTests(unittest.TestCase):
    def test_exact_technical_identifier_is_retrieved(self):
        index = BM25Index(METAS)
        hits = index.search("YOLOv11s BoT-SORT", k=2)
        self.assertTrue(hits)
        self.assertEqual(hits[0][1]["source"], "accident-detection")

    def test_empty_query_returns_no_lexical_hits(self):
        self.assertEqual(BM25Index(METAS).search("", k=3), [])


class HybridRetrieverTests(unittest.TestCase):
    def _retriever(self, semantic):
        # These tests validate the semantic+BM25 baseline in isolation. Structured
        # profile fusion has its own deterministic tests in test_structured_retrieval.py.
        return HybridRetriever(semantic, structured_retriever=False)

    def test_rrf_combines_semantic_and_lexical_evidence(self):
        semantic = FakeSemanticRAG(METAS, [2, 0, 1])
        hits = self._retriever(semantic).query("Which project uses YOLOv11s?", k=2)

        self.assertEqual(hits[0].meta["source"], "accident-detection")
        self.assertEqual(hits[0].meta["retrieval"]["strategy"], "hybrid_rrf")
        self.assertIsNotNone(hits[0].meta["retrieval"]["lexical_rank"])
        self.assertIsNotNone(hits[0].meta["retrieval"]["semantic_rank"])

    def test_output_respects_k(self):
        semantic = FakeSemanticRAG(METAS, [0, 1, 2])
        hits = self._retriever(semantic).query("AI projects", k=1)
        self.assertEqual(len(hits), 1)

    def test_zero_k_returns_empty(self):
        semantic = FakeSemanticRAG(METAS, [0, 1, 2])
        self.assertEqual(self._retriever(semantic).query("AI", k=0), [])


if __name__ == "__main__":
    unittest.main()
