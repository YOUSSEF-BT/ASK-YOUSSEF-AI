import sys
import unittest
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from retrieval.hybrid import HybridRetriever  # noqa: E402
from retrieval.structured import StructuredProfileRetriever  # noqa: E402


PROFILE = {
    "identity": {"name": "Youssef Bouzit", "portfolio_url": "https://example.com"},
    "projects": [
        {
            "slug": "accident",
            "title": "Real-Time Road Accident Detection",
            "url": "https://example.com/projects/accident",
            "description": "Hybrid road accident detection system",
            "role": "Computer Vision & AI Engineer",
            "company": "NEXTRONIC — ABA Technology",
            "tags": ["Computer Vision", "Deep Learning"],
            "tech_stack": ["YOLOv11s", "BoT-SORT", "OpenCV"],
            "results": {"precision": "86.68%", "recall": "91.56%"},
        }
    ],
    "skill_categories": [
        {
            "id": "genai-rag",
            "name": "Generative AI & RAG",
            "description": "Grounded LLM systems",
            "skills": ["RAG", "Embeddings", "Semantic Search", "Evaluation"],
            "evidence": [{"label": "OpenLegaMa", "url": "https://example.com/openlegama"}],
            "url": "https://example.com/skills",
        }
    ],
    "certifications": [
        {
            "title": "Oracle Agentic AI Certified Foundations Associate",
            "issuer": "Oracle",
            "date": "August 2026",
            "category": "agentic-ai-llms",
            "url": "https://example.com/certifications",
        }
    ],
    "work_experiences": [
        {
            "role": "AI/ML Engineer Intern | Computer Vision",
            "company": "NEXTRONIC — ABA Technology",
            "period": "Feb 2026 — Aug 2026",
            "description": "Built a real-time road accident detection system.",
            "technologies": ["Python", "YOLO", "OpenCV"],
            "url": "https://example.com/#experience",
        }
    ],
    "education": [
        {
            "degree": "State Engineering Degree in Data Science",
            "school": "SUP'MTI Rabat",
            "period": "Oct 2023 — Jul 2026",
            "focus": ["Data Science", "Machine Learning", "AI"],
            "url": "https://example.com/#experience",
        }
    ],
    "public_links": [{"url": "https://github.com/YOUSSEF-BT"}],
}


class StructuredProfileRetrieverTests(unittest.TestCase):
    def setUp(self):
        self.retriever = StructuredProfileRetriever(PROFILE)

    def test_exact_technical_project_query(self):
        hits = self.retriever.search("Quel projet utilise YOLOv11s et BoT-SORT ?", k=2)
        self.assertTrue(hits)
        self.assertEqual(hits[0].meta["entity_type"], "project")
        self.assertIn("Road Accident", hits[0].meta["title"])

    def test_certification_intent(self):
        hits = self.retriever.search("Which Oracle certification does Youssef have?", k=2)
        self.assertTrue(hits)
        self.assertEqual(hits[0].meta["entity_type"], "certification")
        self.assertIn("Oracle Agentic AI", hits[0].meta["heading"])

    def test_arabic_skill_query(self):
        hits = self.retriever.search("ما هي مهارات RAG؟", k=2)
        self.assertTrue(hits)
        self.assertEqual(hits[0].meta["entity_type"], "skill_category")
        self.assertIn("RAG", hits[0].meta["heading"])

    def test_company_experience_query(self):
        hits = self.retriever.search("expérience NEXTRONIC ABA", k=2)
        self.assertTrue(hits)
        self.assertEqual(hits[0].meta["entity_type"], "work_experience")


@dataclass
class FakeHit:
    score: float
    meta: dict


class FakeStore:
    def __init__(self, metas):
        self.metas = metas


class FakeSemantic:
    def __init__(self):
        self.store = FakeStore([
            {
                "source": "generic",
                "idx": 0,
                "title": "About",
                "heading": "Profile",
                "text": "Youssef works on AI and machine learning.",
                "url": "https://example.com",
            }
        ])

    def query(self, question, k=4):
        del question, k
        return [FakeHit(0.8, self.store.metas[0])]


class StructuredHybridFusionTests(unittest.TestCase):
    def test_structured_signal_is_fused_and_traced(self):
        retriever = HybridRetriever(
            FakeSemantic(), structured_retriever=StructuredProfileRetriever(PROFILE)
        )
        hits = retriever.query("YOLOv11s BoT-SORT project", k=3)
        structured_hits = [h for h in hits if h.meta["retrieval"]["structured_rank"] is not None]
        self.assertTrue(structured_hits)
        self.assertEqual(hits[0].meta["retrieval"]["strategy"], "hybrid_rrf_structured")
        self.assertEqual(structured_hits[0].meta["entity_type"], "project")


if __name__ == "__main__":
    unittest.main()
