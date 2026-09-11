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


class RecruiterReasoningStressTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        profile = json.loads((BACKEND / "data" / "profile.json").read_text(encoding="utf-8"))
        cls.resolver = StructuredFactResolver(profile)

    def test_cto_summary_is_evidence_based_not_abstention(self):
        result = self.resolver.resolve(
            "If you had to summarize Youssef's profile in 30 seconds for a CTO, what would you say?"
        )
        self.assertIsNotNone(result)
        answer = result.answer
        self.assertIn("30-second CTO summary", answer)
        self.assertIn("NEXTRONIC", answer)
        self.assertIn("OpenLegaMa", answer)
        self.assertIn("86.68%", answer)
        self.assertIn("143 / 143", answer)
        self.assertNotIn("couldn't verify", answer.lower())

    def test_production_oriented_question_uses_system_evidence(self):
        result = self.resolver.resolve(
            "What evidence shows Youssef can work on production-oriented AI systems rather than only academic notebooks?"
        )
        self.assertIsNotNone(result)
        answer = result.answer
        self.assertIn("OpenLegaMa", answer)
        self.assertIn("Road Accident Detection", answer)
        self.assertIn("Customer MLOps Pipeline", answer)
        self.assertIn("enterprise", answer.lower())
        self.assertNotIn("production-grade", answer.lower())

    def test_integrated_components_question_returns_two_complete_examples(self):
        result = self.resolver.resolve(
            "Does Youssef have experience combining multiple AI components in one integrated system?"
        )
        self.assertIsNotNone(result)
        answer = result.answer
        self.assertIn("BoT-SORT", answer)
        self.assertIn("decision fusion", answer)
        self.assertIn("OpenLegaMa", answer)
        self.assertIn("abstention", answer)

    def test_ai_evaluation_question_does_not_abstain(self):
        result = self.resolver.resolve(
            "Can Youssef evaluate an AI system properly, or does he only build prototypes?"
        )
        self.assertIsNotNone(result)
        answer = result.answer
        self.assertIn("610 cases", answer)
        self.assertIn("120 cases", answer)
        self.assertIn("86.68%", answer)
        self.assertIn("end-to-end", answer)
        self.assertNotIn("couldn't verify", answer.lower())

    def test_domain_fit_compares_all_requested_domains(self):
        result = self.resolver.resolve(
            "Would Youssef be a better fit for Computer Vision, Generative AI, or MLOps? Explain using evidence."
        )
        self.assertIsNotNone(result)
        answer = result.answer
        self.assertIn("Computer Vision", answer)
        self.assertIn("Generative AI / RAG", answer)
        self.assertIn("MLOps", answer)
        self.assertIn("strongest professional evidence", answer)
        self.assertIn("less public professional evidence", answer)

    def test_structured_data_prefers_tabular_evidence(self):
        result = self.resolver.resolve(
            "Which project proves he can work with structured data and not only images or text?"
        )
        self.assertIsNotNone(result)
        answer = result.answer
        self.assertIn("AI-Powered Bank Fraud Detection", answer)
        self.assertIn("284,807", answer)
        self.assertIn("PostgreSQL", answer)
        self.assertIn("MySQL", answer)
        self.assertNotIn("The strongest public evidence of Youssef working with structured data is OpenLegaMa", answer)

    def test_agentic_claim_is_calibrated_against_public_project_evidence(self):
        result = self.resolver.resolve(
            "Is Youssef actually experienced with LangGraph and AI agents, or is this mainly based on skills and certifications?"
        )
        self.assertIsNotNone(result)
        answer = result.answer
        self.assertIn("more limited", answer.lower())
        self.assertIn("does not yet show a standalone LangGraph/Agentic AI project", answer)
        self.assertIn("hands-on capability/exposure", answer)
        self.assertIn("[certifications]", answer)

    def test_professional_vs_personal_tech_has_explicit_separation(self):
        result = self.resolver.resolve(
            "What technologies has Youssef used professionally versus only in personal projects?"
        )
        self.assertIsNotNone(result)
        answer = result.answer
        self.assertIn("Explicitly documented professional use", answer)
        self.assertIn("NEXTRONIC", answer)
        self.assertIn("BoT-SORT", answer)
        self.assertIn("Evidence mainly from public/personal projects", answer)
        self.assertIn("Airflow", answer)
        self.assertIn("every", answer.lower())

    def test_strengths_and_public_evidence_gaps_are_answered(self):
        result = self.resolver.resolve(
            "Give me Youssef's top 3 strengths and top 2 areas where his public portfolio has less evidence."
        )
        self.assertIsNotNone(result)
        answer = result.answer
        self.assertIn("Top 3 strengths", answer)
        self.assertIn("Real-time Computer Vision", answer)
        self.assertIn("RAG/LLM", answer)
        self.assertIn("End-to-end AI engineering / MLOps", answer)
        self.assertIn("Two areas with less public evidence", answer)
        self.assertIn("Agentic AI / LangGraph", answer)
        self.assertIn("public-evidence gaps", answer)
        self.assertNotIn("couldn't verify", answer.lower())

    def test_junior_readiness_leads_with_professional_and_project_proof(self):
        result = self.resolver.resolve(
            "est ce que youssef est vraiment pret pour un poste ai engineer junior ou son profil est encore surtout academique ?"
        )
        self.assertIsNotNone(result)
        answer = result.answer
        self.assertIn("AI Engineer junior", answer)
        self.assertIn("NEXTRONIC", answer)
        self.assertIn("OpenLegaMa", answer)
        self.assertIn("Cycle ML/MLOps", answer)
        self.assertIn("Airflow", answer)
        self.assertIn("certifications", answer.lower())
        self.assertIn("preuve principale", answer)

    def test_beyond_model_training_uses_system_engineering_evidence(self):
        result = self.resolver.resolve(
            "si je suis recruteur, quelle preuve concrete me montre qu'il sait faire autre chose que entrainer un modele ?"
        )
        self.assertIsNotNone(result)
        answer = result.answer
        self.assertIn("BoT-SORT", answer)
        self.assertIn("OpenLegaMa", answer)
        self.assertIn("Airflow", answer)
        self.assertNotIn("Oracle Agentic AI", answer)

    def test_complete_architecture_uses_project_sources(self):
        result = self.resolver.resolve(
            "quel projet de youssef montre le mieux qu'il sait construire une architecture complete ?"
        )
        self.assertIsNotNone(result)
        answer = result.answer
        self.assertIn("OpenLegaMa", answer)
        self.assertIn("Customer MLOps Pipeline", answer)
        self.assertIn("[project-openlegama-moroccan-legal-ai]", answer)
        self.assertIn("[project-customer-churn-mlops-platform]", answer)

    def test_certificates_vs_practical_evidence_does_not_abstain(self):
        result = self.resolver.resolve(
            "youssef a beaucoup de certificats mais est ce qu'il a vraiment des preuves pratiques derrière ?"
        )
        self.assertIsNotNone(result)
        answer = result.answer
        self.assertIn("NEXTRONIC", answer)
        self.assertIn("OpenLegaMa", answer)
        self.assertIn("Customer MLOps Pipeline", answer)
        self.assertIn("56 certifications", answer)
        self.assertNotIn("pas pu vérifier", answer.lower())

    def test_false_bigtech_claims_stay_in_question_language(self):
        result = self.resolver.resolve(
            "Did Youssef build GPT-5, work at OpenAI, or contribute to Gemini?"
        )
        self.assertIsNotNone(result)
        answer = result.answer
        self.assertTrue(answer.startswith("The public portfolio"))
        self.assertIn("no evidence", answer.lower())
        self.assertIn("OpenAI", answer)
        self.assertIn("Gemini", answer)
        self.assertNotIn("Le portfolio", answer)

    def test_semantic_variants_are_not_exact_phrase_only(self):
        result = self.resolver.resolve(
            "For a hiring manager, where is Youssef less proven publicly despite his top three technical strengths?"
        )
        self.assertIsNotNone(result)
        answer = result.answer
        self.assertIn("Top 3 strengths", answer)
        self.assertIn("public-evidence gaps", answer)


if __name__ == "__main__":
    unittest.main()
