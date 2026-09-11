import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

import vercel_quality_patch  # noqa: E402,F401
import project_fingerprint_patch  # noqa: E402,F401
from structured_facts import StructuredFactResolver  # noqa: E402


class HumanAuditReasoningTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        profile = json.loads((BACKEND / "data" / "profile.json").read_text(encoding="utf-8"))
        cls.resolver = StructuredFactResolver(profile)

    def test_recruiter_30_second_pitch_leads_with_real_company_and_flagships(self):
        result = self.resolver.resolve(
            "I have 30 seconds. Convince me Youssef is worth interviewing for a junior AI Engineer role."
        )
        self.assertIsNotNone(result)
        answer = result.answer
        self.assertIn("NEXTRONIC", answer)
        self.assertIn("YOLOv11", answer)
        self.assertIn("OpenLegaMa", answer)
        self.assertIn("31.5 FPS", answer)
        self.assertNotIn("AI Summarizer", answer)

    def test_real_company_setting_never_denies_nextronic_experience(self):
        result = self.resolver.resolve(
            "Has he worked in a real company setting? What exactly did he do there?"
        )
        self.assertIsNotNone(result)
        answer = result.answer
        self.assertIn("NEXTRONIC", answer)
        self.assertIn("ABA Technology", answer)
        self.assertIn("AI/ML Engineer Intern", answer)
        self.assertIn("18/20", answer)
        self.assertNotIn("do not currently list traditional corporate", answer.lower())

    def test_agentic_client_question_is_calibrated_not_overclaimed(self):
        result = self.resolver.resolve(
            "I need an AI agent that can call tools and require human approval. Has he actually done this or is it mostly skills and coursework?"
        )
        self.assertIsNotNone(result)
        answer = result.answer
        self.assertIn("more limited", answer.lower())
        self.assertIn("does not yet show a standalone LangGraph/Agentic AI project", answer)
        self.assertIn("Oracle Agentic AI Certified Foundations Associate", answer)
        self.assertIn("Building with the Claude API", answer)
        self.assertNotIn("Anthropic's Agentic AI", answer)

    def test_cv_vs_agentic_comparison_prefers_measured_cv_evidence(self):
        result = self.resolver.resolve(
            "If I need someone stronger in Computer Vision than Agentic AI today, is Youssef a fit? Explain with evidence."
        )
        self.assertIsNotNone(result)
        answer = result.answer
        self.assertIn("more strongly proven", answer)
        self.assertIn("NEXTRONIC", answer)
        self.assertIn("86.68%", answer)
        self.assertIn("Agentic AI", answer)
        self.assertIn("not yet a standalone LangGraph", answer)

    def test_postgresql_and_structured_business_data_question_uses_tabular_evidence(self):
        result = self.resolver.resolve(
            "Can Youssef work with PostgreSQL and structured business data as well as documents?"
        )
        self.assertIsNotNone(result)
        answer = result.answer
        self.assertIn("Customer MLOps Pipeline", answer)
        self.assertIn("PostgreSQL", answer)
        self.assertIn("AI-Powered Bank Fraud Detection", answer)
        self.assertIn("284,807", answer)
        self.assertIn("MySQL", answer)
        self.assertIn("OpenLegaMa", answer)

    def test_client_ready_project_is_openlegama_not_small_demo(self):
        result = self.resolver.resolve(
            "Which public project is closest to a client-ready AI product and why?"
        )
        self.assertIsNotNone(result)
        answer = result.answer
        self.assertIn("closest to a client-ready AI product", answer)
        self.assertIn("OpenLegaMa", answer)
        self.assertIn("143 / 143", answer)
        self.assertNotIn("AI Summarizer", answer)

    def test_two_end_to_end_projects_returns_exactly_two_named_choices(self):
        result = self.resolver.resolve(
            "Which two projects best prove end-to-end AI engineering ability, and what did he actually build?"
        )
        self.assertIsNotNone(result)
        answer = result.answer
        self.assertIn("two projects", answer.lower())
        self.assertIn("OpenLegaMa", answer)
        self.assertIn("Customer MLOps Pipeline", answer)
        self.assertNotIn("Road Accident Detection", answer)

    def test_three_interesting_projects_returns_three_not_two(self):
        result = self.resolver.resolve(
            "What are the three most interesting projects on his portfolio?"
        )
        self.assertIsNotNone(result)
        answer = result.answer
        self.assertIn("1. **Real-Time Road Accident Detection**", answer)
        self.assertIn("2. **OpenLegaMa", answer)
        self.assertIn("3. **Customer MLOps Pipeline**", answer)

    def test_public_evidence_gaps_are_broad_and_calibrated(self):
        result = self.resolver.resolve("Where is Youssef's public evidence still weak or incomplete?")
        self.assertIsNotNone(result)
        answer = result.answer
        self.assertIn("Agentic AI / LangGraph", answer)
        self.assertIn("Long-term large-scale enterprise ownership", answer)
        self.assertIn("end-to-end video metrics", answer)
        self.assertIn("available public proof", answer)

    def test_certifications_do_not_replace_experience(self):
        result = self.resolver.resolve(
            "Comme recruteur, est-ce que ses 56 certificats compensent vraiment un manque d'expérience ?"
        )
        self.assertIsNotNone(result)
        answer = result.answer
        self.assertIn("ne remplacent pas l’expérience", answer)
        self.assertIn("NEXTRONIC", answer)
        self.assertIn("OpenLegaMa", answer)
        self.assertIn("junior/early-career", answer)

    def test_rag_client_trust_leads_with_measured_openlegama_evidence(self):
        result = self.resolver.resolve(
            "I need a RAG chatbot over company documents with citations and abstention. Why should I trust Youssef with it?"
        )
        self.assertIsNotNone(result)
        answer = result.answer
        self.assertIn("OpenLegaMa", answer)
        self.assertIn("143 / 143", answer)
        self.assertIn("610 cases", answer)
        self.assertIn("120 cases", answer)
        self.assertIn("7,708", answer)

    def test_client_risk_answer_is_candid_but_evidence_scoped(self):
        result = self.resolver.resolve("What would make Youssef a risky choice for my AI project? Be candid.")
        self.assertIsNotNone(result)
        answer = result.answer
        self.assertIn("Junior/early-career", answer)
        self.assertIn("Agentic AI/LangGraph", answer)
        self.assertIn("Very large enterprise scope", answer)
        self.assertIn("OpenLegaMa", answer)

    def test_simple_identity_positions_ai_ml_not_only_computer_vision(self):
        result = self.resolver.resolve("Who is Youssef in simple words?")
        self.assertIsNotNone(result)
        answer = result.answer
        self.assertIn("AI/ML Engineer", answer)
        self.assertIn("Computer Vision", answer)
        self.assertIn("RAG/LLM", answer)
        self.assertIn("NEXTRONIC", answer)

    def test_semantic_variants_are_not_exact_phrase_only(self):
        expected = {
            "Does Youssef have genuine corporate experience, or only portfolio projects?": ("NEXTRONIC",),
            "What is the biggest gap in his public proof today?": ("Agentic AI / LangGraph", "enterprise"),
            "For a paying customer, which project looks most product-ready?": ("OpenLegaMa", "143 / 143"),
        }
        for question, needles in expected.items():
            with self.subTest(question=question):
                result = self.resolver.resolve(question)
                self.assertIsNotNone(result)
                for needle in needles:
                    self.assertIn(needle, result.answer)


if __name__ == "__main__":
    unittest.main()
