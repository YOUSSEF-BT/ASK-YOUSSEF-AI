import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from structured_facts import StructuredFactResolver  # noqa: E402


class EvidenceFirstAnswerQualityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        profile = json.loads((BACKEND / "data" / "profile.json").read_text(encoding="utf-8"))
        cls.resolver = StructuredFactResolver(profile)

    def test_computer_vision_experience_leads_with_professional_and_measured_evidence(self):
        result = self.resolver.resolve("What is his Computer Vision experience?")
        self.assertIsNotNone(result)
        answer = result.answer
        self.assertIn("NEXTRONIC", answer)
        self.assertIn("AI/ML Engineer Intern", answer)
        self.assertIn("86.68%", answer)
        self.assertIn("91.56%", answer)
        self.assertIn("31.5 FPS", answer)
        self.assertIn("Traffic MVP", answer)
        self.assertIn("[experience-education]", answer)
        self.assertIn("[project-real-time-road-accident-detection]", answer)
        self.assertIn("[project-traffic-mvp-image-processing]", answer)

    def test_rag_llm_evidence_leads_with_openlegama_evaluation_not_training(self):
        result = self.resolver.resolve("Show evidence of his RAG and LLM skills")
        self.assertIsNotNone(result)
        answer = result.answer
        self.assertIn("OpenLegaMa", answer)
        self.assertIn("143 / 143", answer)
        self.assertIn("610 cases", answer)
        self.assertIn("120 cases", answer)
        self.assertIn("7,708", answer)
        self.assertIn("Current professional practice", answer)
        self.assertIn("[experience-education]", answer)
        self.assertIn("[skills]", answer)
        self.assertNotIn("Continuous Learning", answer)

    def test_broad_certifications_prioritize_career_relevant_credentials(self):
        result = self.resolver.resolve("Which certifications does he have?")
        self.assertIsNotNone(result)
        answer = result.answer
        self.assertIn("56", answer)
        self.assertIn("Oracle Agentic AI Certified Foundations Associate", answer)
        self.assertIn("Oracle AI Database Certified Foundations Associate", answer)
        self.assertIn("Oracle Cloud Infrastructure 2026 Certified Architect Associate", answer)
        self.assertIn("Machine Learning with Python Professional Certificate by Anaconda", answer)
        self.assertIn("OpenCV Bootcamp", answer)
        self.assertIn("Building with the Claude API", answer)
        self.assertIn("Anthropic", answer)
        self.assertIn("LinkedIn", answer)
        self.assertIn("[certifications]", answer)

    def test_strongest_ai_projects_use_ranked_evidence_not_secondary_summarizer(self):
        result = self.resolver.resolve("Show me Youssef's strongest AI projects")
        self.assertIsNotNone(result)
        answer = result.answer
        self.assertIn("Real-Time Road Accident Detection", answer)
        self.assertIn("OpenLegaMa", answer)
        self.assertIn("Customer MLOps Pipeline", answer)
        self.assertIn("86.68%", answer)
        self.assertIn("143 / 143", answer)
        self.assertNotIn("AI Summarizer", answer)

    def test_generalized_cv_proof_variant_uses_same_evidence_hierarchy(self):
        result = self.resolver.resolve("Give me proof that he can build Computer Vision systems")
        self.assertIsNotNone(result)
        self.assertIn("NEXTRONIC", result.answer)
        self.assertIn("Measured PFE evidence", result.answer)
        self.assertIn("Traffic MVP", result.answer)


if __name__ == "__main__":
    unittest.main()
