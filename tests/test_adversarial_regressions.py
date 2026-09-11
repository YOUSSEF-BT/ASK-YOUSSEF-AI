import json
import sys
import unittest
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from grounding import enforce_grounding  # noqa: E402
from router import detect_language, route_question  # noqa: E402
from structured_facts import StructuredFactResolver  # noqa: E402


@dataclass
class Step:
    action: str | None = None
    observation: str | None = None


class AdversarialRoutingTests(unittest.TestCase):
    def test_french_write_bio_is_profile_fact_not_contact_action(self):
        route = route_question("Peux-tu écrire une courte bio professionnelle de Youssef ?")
        self.assertEqual(route.language, "fr")
        self.assertNotEqual(route.intent, "contact_action")
        self.assertTrue(route.requires_retrieval)
        self.assertTrue(route.portfolio_scope)

    def test_english_write_summary_is_profile_fact_not_contact_action(self):
        route = route_question("Write a short professional summary of Youssef.")
        self.assertNotEqual(route.intent, "contact_action")
        self.assertTrue(route.requires_retrieval)

    def test_actual_message_action_remains_contact_action(self):
        cases = [
            "Send Youssef a message for me",
            "Write an email to Youssef for me",
            "Écris un message à Youssef",
            "Envoie un email à Youssef",
        ]
        for question in cases:
            with self.subTest(question=question):
                route = route_question(question)
                self.assertEqual(route.intent, "contact_action")
                self.assertFalse(route.requires_retrieval)

    def test_conversational_french_referent_is_detected(self):
        question = "Tu peux me parler de lui ?"
        self.assertEqual(detect_language(question), "fr")
        route = route_question(question)
        self.assertTrue(route.requires_retrieval)
        self.assertTrue(route.portfolio_scope)

    def test_job_search_variants_are_french_profile_questions(self):
        for question in (
            "Youssef cherche-t-il un CDI ?",
            "Est-ce que Youssef recherche un emploi ?",
            "Youssef est-il ouvert à un poste à temps plein ?",
        ):
            with self.subTest(question=question):
                route = route_question(question)
                self.assertEqual(route.language, "fr")
                self.assertTrue(route.requires_retrieval)


class AdversarialStructuredFactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        profile = json.loads((BACKEND / "data" / "profile.json").read_text(encoding="utf-8"))
        cls.resolver = StructuredFactResolver(profile)

    def test_specific_oracle_agentic_question_is_certification_not_generic_capability(self):
        result = self.resolver.resolve("Which Oracle Agentic AI certification does Youssef have?")
        self.assertIsNotNone(result)
        self.assertTrue(result.answer.startswith("Oracle Agentic AI Certified Foundations Associate is a certification issued by Oracle"))
        self.assertIn("[certifications]", result.answer)
        self.assertNotIn("standalone public project explicitly labeled", result.answer)
        self.assertNotIn("Agentic AI & LLM Orchestration skills", result.answer)

    def test_french_job_search_hyphenated_variant_uses_explicit_career_status(self):
        result = self.resolver.resolve("Youssef cherche-t-il un CDI ?")
        self.assertIsNotNone(result)
        self.assertTrue(result.answer.startswith("Oui"))
        self.assertIn("CDI", result.answer)
        self.assertIn("Freelance", result.answer)
        self.assertIn("[career-status]", result.answer)

    def test_french_open_to_full_time_variant_uses_explicit_career_status(self):
        result = self.resolver.resolve("Youssef est-il ouvert à un poste à temps plein ?")
        self.assertIsNotNone(result)
        self.assertTrue(result.answer.startswith("Oui"))
        self.assertIn("CDI", result.answer)
        self.assertIn("[career-status]", result.answer)


class AdversarialGroundingTests(unittest.TestCase):
    def setUp(self):
        self.steps = [Step(
            action="search_site",
            observation=(
                "[project-openlegama-moroccan-legal-ai · relevance 0.93] "
                "OpenLegaMa uses Controlled RAG for Moroccan legal retrieval. || "
                "[skills · relevance 0.72] Generative AI & RAG skills are documented."
            ),
        )]

    def test_malformed_model_citation_is_removed(self):
        answer, _ = enforce_grounding(
            "OpenLegaMa utilise Controlled RAG [project-openle gama-moroccan-legal-ai · skills].",
            self.steps,
        )
        self.assertNotIn("project-openle gama", answer)
        self.assertNotIn("· skills", answer)
        self.assertIn("[project-openlegama-moroccan-legal-ai]", answer)

    def test_french_unsupported_number_abstention_stays_french(self):
        answer, report = enforce_grounding(
            "Le projet atteint 99,99 % de précision [project-openlegama-moroccan-legal-ai].",
            self.steps,
        )
        self.assertFalse(report.high_risk_supported)
        self.assertIn("Je n’ai pas pu vérifier", answer)
        self.assertNotIn("I couldn't verify", answer)
        self.assertNotIn("99,99", answer)

    def test_unknown_simple_citation_is_removed(self):
        answer, report = enforce_grounding(
            "OpenLegaMa utilise Controlled RAG [project-fake].",
            self.steps,
        )
        self.assertFalse(report.citation_integrity)
        self.assertNotIn("[project-fake]", answer)
        self.assertIn("[project-openlegama-moroccan-legal-ai]", answer)


if __name__ == "__main__":
    unittest.main()
