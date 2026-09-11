import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

# Production quality patches are applied before the public resolver is imported.
import vercel_quality_patch  # noqa: E402,F401
import project_fingerprint_patch  # noqa: E402,F401
from structured_facts import StructuredFactResolver  # noqa: E402


class FinalRecruiterPolishTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        profile = json.loads((BACKEND / "data" / "profile.json").read_text(encoding="utf-8"))
        cls.resolver = StructuredFactResolver(profile)

    def test_strongest_technical_skills_are_ranked_from_evidence(self):
        result = self.resolver.resolve("What are Youssef's strongest technical skills?")
        self.assertIsNotNone(result)
        answer = result.answer
        self.assertIn("Computer Vision & Deep Learning", answer)
        self.assertIn("RAG / LLM & Grounded AI", answer)
        self.assertIn("Customer MLOps Pipeline", answer)
        self.assertIn("86.68%", answer)
        self.assertIn("143 / 143", answer)
        self.assertIn("[skills]", answer)
        self.assertNotIn("couldn't verify", answer.lower())

    def test_most_valuable_certifications_are_ranked_for_ai_engineer(self):
        result = self.resolver.resolve(
            "What are his most valuable certifications for an AI Engineer position?"
        )
        self.assertIsNotNone(result)
        answer = result.answer
        self.assertIn("Machine Learning with Python Professional Certificate by Anaconda", answer)
        self.assertIn("Oracle Agentic AI Certified Foundations Associate", answer)
        self.assertIn("OpenCV Bootcamp", answer)
        self.assertIn("Building with the Claude API", answer)
        self.assertIn("Oracle Cloud Infrastructure 2026 Certified Architect Associate", answer)
        self.assertIn("[certifications]", answer)
        self.assertNotIn("couldn't verify", answer.lower())

    def test_realtime_traffic_metric_has_fps_unit(self):
        result = self.resolver.resolve(
            "Has Youssef worked on real-time AI systems? Show me evidence."
        )
        self.assertIsNotNone(result)
        self.assertIn("30+ FPS on CPU", result.answer)
        self.assertNotIn("30+ on CPU", result.answer)

    def test_professional_summary_never_calls_fiverr_an_employer(self):
        result = self.resolver.resolve("Write a short professional summary of Youssef.")
        self.assertIsNotNone(result)
        answer = result.answer
        self.assertIn("independent", answer.lower())
        self.assertIn("via Fiverr", answer)
        self.assertNotIn(" at Fiverr", answer)

    def test_controlled_rag_moroccan_law_fingerprint_is_deterministic(self):
        result = self.resolver.resolve(
            "Quel projet de Youssef utilise du Controlled RAG pour le droit marocain ?"
        )
        self.assertIsNotNone(result)
        answer = result.answer
        self.assertIn("OpenLegaMa", answer)
        self.assertIn("Controlled RAG", answer)
        self.assertIn("droit marocain", answer)
        self.assertIn("[project-openlegama-moroccan-legal-ai]", answer)
        self.assertNotIn("indisponible", answer.lower())

    def test_compound_yolo_tracker_fingerprint_is_deterministic(self):
        result = self.resolver.resolve(
            "Which Youssef project uses YOLOv11s and BoT-SORT?"
        )
        self.assertIsNotNone(result)
        answer = result.answer
        self.assertIn("Real-Time Road Accident Detection", answer)
        self.assertIn("YOLOv11s", answer)
        self.assertIn("BoT-SORT", answer)
        self.assertIn("[project-real-time-road-accident-detection]", answer)

    def test_generic_specific_project_questions_still_delegate(self):
        # Only unique compound fingerprints are intercepted. Generic project
        # questions remain available to the normal retrieval/generation path.
        fresh_profile = json.loads((BACKEND / "data" / "profile.json").read_text(encoding="utf-8"))
        import structured_facts as structured_module

        resolver = structured_module.StructuredFactResolver(fresh_profile)
        self.assertIsNone(resolver.resolve("Which project uses BoT-SORT?"))
        self.assertIsNone(resolver.resolve("Tell me about OpenLegaMa"))


if __name__ == "__main__":
    unittest.main()
