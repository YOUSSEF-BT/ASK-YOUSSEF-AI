import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from structured_facts import StructuredFactResolver  # noqa: E402


class RecruiterIntentRoutingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        profile = json.loads((BACKEND / "data" / "profile.json").read_text(encoding="utf-8"))
        cls.resolver = StructuredFactResolver(profile)

    def test_why_should_company_hire_youssef_is_evidence_first(self):
        result = self.resolver.resolve("Why should a company hire Youssef instead of another junior AI Engineer?")
        self.assertIsNotNone(result)
        self.assertIn("NEXTRONIC", result.answer)
        self.assertIn("86.68%", result.answer)
        self.assertIn("OpenLegaMa", result.answer)
        self.assertNotIn("couldn't verify", result.answer.lower())

    def test_realtime_ai_system_question_returns_two_concrete_systems(self):
        result = self.resolver.resolve("Has Youssef worked on real-time AI systems? Show me evidence.")
        self.assertIsNotNone(result)
        self.assertIn("Road Accident Detection", result.answer)
        self.assertIn("Traffic MVP", result.answer)
        self.assertIn("31.5 FPS", result.answer)
        self.assertNotIn("couldn't verify", result.answer.lower())

    def test_accident_results_question_returns_measured_metrics_and_scope(self):
        result = self.resolver.resolve("What results did he achieve on his road accident detection project?")
        self.assertIsNotNone(result)
        self.assertIn("86.68%", result.answer)
        self.assertIn("91.56%", result.answer)
        self.assertIn("89.06%", result.answer)
        self.assertIn("31.5 FPS", result.answer)
        self.assertIn("image", result.answer.lower())
        self.assertIn("end-to-end", result.answer)

    def test_accident_limitations_use_structured_project_data(self):
        result = self.resolver.resolve("What are the limitations of his road accident detection system?")
        self.assertIsNotNone(result)
        answer = result.answer.lower()
        self.assertIn("night", answer)
        self.assertIn("rain", answer)
        self.assertIn("occlusion", answer)
        self.assertIn("camera angles", answer)
        self.assertNotIn("not detailed", answer)

    def test_strongest_rag_project_returns_only_relevant_flagship(self):
        result = self.resolver.resolve("What is Youssef's strongest RAG project and why is it important?")
        self.assertIsNotNone(result)
        self.assertIn("OpenLegaMa", result.answer)
        self.assertIn("143 / 143", result.answer)
        self.assertNotIn("Customer MLOps Pipeline", result.answer)
        self.assertNotIn("Real-Time Road Accident Detection", result.answer)

    def test_recruiter_top3_ranking_returns_three_complementary_projects(self):
        result = self.resolver.resolve("Rank his top 3 projects for an AI Engineer recruiter and explain why.")
        self.assertIsNotNone(result)
        self.assertIn("Real-Time Road Accident Detection", result.answer)
        self.assertIn("OpenLegaMa", result.answer)
        self.assertIn("Customer MLOps Pipeline", result.answer)
        self.assertNotIn("couldn't verify", result.answer.lower())

    def test_best_machine_learning_project_is_not_generic_top3(self):
        result = self.resolver.resolve("Which project best demonstrates Machine Learning skills?")
        self.assertIsNotNone(result)
        self.assertIn("Real-Time Road Accident Detection", result.answer)
        self.assertIn("86.68%", result.answer)
        self.assertNotIn("Customer MLOps Pipeline", result.answer)

    def test_best_mlops_project_returns_mlops_project_directly(self):
        result = self.resolver.resolve("Which project best demonstrates production or MLOps skills?")
        self.assertIsNotNone(result)
        self.assertIn("Customer MLOps Pipeline", result.answer)
        self.assertIn("Airflow", result.answer)
        self.assertIn("MLflow", result.answer)
        self.assertNotIn("Real-Time Road Accident Detection", result.answer)

    def test_oracle_count_and_names_returns_all_three_titles(self):
        result = self.resolver.resolve("How many Oracle certifications does he have and what are they?")
        self.assertIsNotNone(result)
        self.assertIn("3", result.answer)
        self.assertIn("Oracle Agentic AI Certified Foundations Associate", result.answer)
        self.assertIn("Oracle AI Database Certified Foundations Associate", result.answer)
        self.assertIn("Oracle Cloud Infrastructure 2026 Certified Architect Associate", result.answer)

    def test_multiple_issuer_employers_are_all_disambiguated(self):
        result = self.resolver.resolve("Did Youssef work at Oracle, IBM or Anthropic?")
        self.assertIsNotNone(result)
        self.assertIn("Oracle", result.answer)
        self.assertIn("IBM", result.answer)
        self.assertIn("Anthropic", result.answer)
        self.assertIn("certification issuer", result.answer)
        self.assertNotIn("No synchronized work-experience entry lists Anthropic", result.answer)

    def test_overview_never_calls_fiverr_an_employer(self):
        result = self.resolver.resolve("Tell me about Youssef Bouzit.")
        self.assertIsNotNone(result)
        self.assertIn("independent", result.answer.lower())
        self.assertIn("via Fiverr", result.answer)
        self.assertNotIn("at Fiverr", result.answer)
        self.assertIn("full-time", result.answer.lower())

    def test_current_work_never_calls_fiverr_an_employer(self):
        result = self.resolver.resolve("What is Youssef doing professionally right now?")
        self.assertIsNotNone(result)
        self.assertIn("independent", result.answer.lower())
        self.assertIn("via Fiverr", result.answer)
        self.assertNotIn("at Fiverr", result.answer)

    def test_document_chatbot_answer_is_evidence_based_and_calibrated(self):
        result = self.resolver.resolve("Can Youssef build an AI chatbot for company documents? What evidence supports that?")
        self.assertIsNotNone(result)
        self.assertIn("OpenLegaMa", result.answer)
        self.assertIn("143 / 143", result.answer)
        self.assertIn("core engineering pattern", result.answer)
        self.assertNotIn("production-grade", result.answer.lower())

    def test_grounded_ai_answer_does_not_claim_universal_hallucination_elimination(self):
        result = self.resolver.resolve("Does Youssef have experience with grounded AI answers, citations and hallucination control?")
        self.assertIsNotNone(result)
        self.assertIn("OpenLegaMa", result.answer)
        self.assertIn("hallucination-risk reduction", result.answer)
        self.assertIn("not a claim", result.answer.lower())


if __name__ == "__main__":
    unittest.main()
