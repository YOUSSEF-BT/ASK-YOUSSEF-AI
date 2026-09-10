import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from structured_facts import StructuredFactResolver  # noqa: E402


class StructuredPortfolioFactsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.profile = json.loads((BACKEND / "data" / "profile.json").read_text(encoding="utf-8"))
        cls.resolver = StructuredFactResolver(cls.profile)
        cls.oracle = [
            row for row in cls.profile.get("certifications", [])
            if row.get("issuer") == "Oracle"
        ]
        cls.cert_history = [
            {"role": "user", "content": "Which certifications does he have?"},
            {"role": "assistant", "content": "His certifications include credentials from Oracle and other issuers."},
        ]
        cls.oracle_history = [
            {"role": "user", "content": "What about Oracle?"},
            {"role": "assistant", "content": (
                "Youssef's public portfolio lists 3 Oracle certifications: "
                "1. Oracle Agentic AI Certified Foundations Associate "
                "2. Oracle AI Database Certified Foundations Associate "
                "3. Oracle Cloud Infrastructure 2026 Certified Architect Associate"
            )},
        ]

    def test_total_certification_count_comes_from_complete_profile(self):
        expected = len(self.profile["certifications"])
        result = self.resolver.resolve("How many certifications does he have?")
        self.assertIsNotNone(result)
        self.assertIn(str(expected), result.answer)
        self.assertIn("[certifications]", result.answer)
        self.assertEqual(result.tool, "structured_profile")

    def test_broad_certification_question_exposes_total_and_issuer_breakdown(self):
        expected = len(self.profile["certifications"])
        result = self.resolver.resolve("Which certifications does he have?")
        self.assertIsNotNone(result)
        self.assertIn(str(expected), result.answer)
        self.assertIn("Oracle", result.answer)
        self.assertIn("Anthropic", result.answer)
        self.assertIn("LinkedIn", result.answer)
        self.assertNotIn("three certifications issued by LinkedIn", result.answer.lower())

    def test_oracle_inventory_is_complete_as_followup(self):
        self.assertEqual(len(self.oracle), 3)
        result = self.resolver.resolve("What about Oracle?", self.cert_history)
        self.assertIsNotNone(result)
        self.assertIn("3", result.answer)
        for row in self.oracle:
            self.assertIn(row["title"], result.answer)

    def test_matching_oracle_claim_is_confirmed_in_french(self):
        result = self.resolver.resolve("je pense il a 3 certifications de oracle")
        self.assertIsNotNone(result)
        self.assertTrue(result.answer.startswith("Oui"))
        self.assertIn("3", result.answer)
        for row in self.oracle:
            self.assertIn(row["title"], result.answer)

    def test_wrong_oracle_claim_is_corrected_not_agreed_with(self):
        result = self.resolver.resolve("je pense il a 4 certifications de oracle")
        self.assertIsNotNone(result)
        self.assertTrue(result.answer.startswith("Pas exactement"))
        self.assertIn("3", result.answer)
        self.assertIn("pas 4", result.answer)
        for row in self.oracle:
            self.assertIn(row["title"], result.answer)

    def test_ordinal_certification_followup_uses_current_language_and_full_details(self):
        result = self.resolver.resolve("talk about the first one.", self.oracle_history)
        self.assertIsNotNone(result)
        self.assertTrue(result.answer.startswith("Oracle Agentic AI Certified Foundations Associate is"))
        self.assertIn("Aug 2026", result.answer)
        self.assertIn("Foundational certification in agentic AI", result.answer)
        self.assertIn("Verification:", result.answer)
        self.assertNotIn("La première", result.answer)

    def test_specific_oracle_certification_stays_specific(self):
        result = self.resolver.resolve("Which Oracle Agentic AI certification does Youssef have?")
        self.assertIsNotNone(result)
        self.assertIn("Oracle Agentic AI Certified Foundations Associate", result.answer)
        self.assertNotIn("Oracle AI Database Certified Foundations Associate", result.answer)
        self.assertNotIn("Oracle Cloud Infrastructure 2026 Certified Architect Associate", result.answer)

    def test_short_count_followup_inherits_certification_context(self):
        result = self.resolver.resolve("how many?", self.cert_history)
        self.assertIsNotNone(result)
        self.assertIn(str(len(self.profile["certifications"])), result.answer)

    def test_employer_question_uses_work_history_and_disambiguates_issuer(self):
        result = self.resolver.resolve("Did Youssef work at IBM?")
        self.assertIsNotNone(result)
        self.assertIn("No synchronized work-experience entry", result.answer)
        self.assertIn("certification issuer, not as an employer", result.answer)
        self.assertIn("[experience-education]", result.answer)
        self.assertIn("[certifications]", result.answer)

    def test_known_employer_is_confirmed_from_structured_experience(self):
        result = self.resolver.resolve("Did Youssef work at NEXTRONIC?")
        self.assertIsNotNone(result)
        self.assertIn("NEXTRONIC", result.answer)
        self.assertIn("AI/ML Engineer Intern", result.answer)
        self.assertIn("[experience-education]", result.answer)

    def test_issuer_only_without_certification_history_is_not_intercepted(self):
        self.assertIsNone(self.resolver.resolve("What about Oracle?"))

    def test_exact_counts_for_other_structured_collections(self):
        cases = [
            ("How many projects does Youssef have?", "projects", "structured-profile"),
            ("How many professional experiences does Youssef have?", "work_experiences", "experience-education"),
            ("How many education entries does Youssef have?", "education", "experience-education"),
            ("How many skill categories does Youssef have?", "skill_categories", "skills"),
            ("How many public contact options does Youssef have?", "public_links", "public-links"),
        ]
        for question, profile_key, source in cases:
            with self.subTest(question=question):
                result = self.resolver.resolve(question)
                self.assertIsNotNone(result)
                self.assertIn(str(len(self.profile[profile_key])), result.answer)
                self.assertIn(f"[{source}]", result.answer)
                self.assertEqual(result.tool, "structured_profile")

    def test_complete_project_list_contains_every_project_title(self):
        result = self.resolver.resolve("List all projects")
        self.assertIsNotNone(result)
        self.assertIn(str(len(self.profile["projects"])), result.answer)
        for row in self.profile["projects"]:
            self.assertIn(row["title"], result.answer)

    def test_complete_experience_list_contains_every_role(self):
        result = self.resolver.resolve("List all professional experiences")
        self.assertIsNotNone(result)
        for row in self.profile["work_experiences"]:
            self.assertIn(row["role"], result.answer)
            self.assertIn(row["company"], result.answer)

    def test_computer_vision_project_count_is_exact_and_project_only(self):
        result = self.resolver.resolve("How many Computer Vision projects does Youssef have?")
        self.assertIsNotNone(result)
        self.assertIn("exactly 2 Computer Vision project", result.answer)
        self.assertIn("Real-Time Road Accident Detection", result.answer)
        self.assertIn("Traffic MVP", result.answer)
        self.assertNotIn("certification", result.answer.lower())

    def test_python_project_list_is_complete_from_structured_project_metadata(self):
        result = self.resolver.resolve("List all Python projects")
        self.assertIsNotNone(result)
        expected = []
        for row in self.profile["projects"]:
            values = list(row.get("tags", []) or []) + list(row.get("tech_stack", []) or [])
            if any("python" in str(value).lower() for value in values):
                expected.append(row)
        self.assertEqual(len(expected), 9)
        self.assertIn("9 Python project", result.answer)
        for row in expected:
            self.assertIn(row["title"], result.answer)

    def test_rag_project_count_distinguishes_public_projects_from_freelance_work(self):
        result = self.resolver.resolve("combien de rag a construis")
        self.assertIsNotNone(result)
        self.assertIn("exactement 1 projet", result.answer.lower())
        self.assertIn("OpenLegaMa", result.answer)
        self.assertIn("expérience freelance", result.answer)
        self.assertIn("[experience-education]", result.answer)

    def test_current_work_question_returns_present_role_first(self):
        result = self.resolver.resolve("youssef il fait quoi maintenant")
        self.assertIsNotNone(result)
        self.assertTrue(result.answer.startswith("Actuellement"))
        self.assertIn("Freelance AI/ML Engineer", result.answer)
        self.assertIn("Fiverr", result.answer)
        self.assertIn("Sep 2026 — Present", result.answer)
        self.assertIn("RAG systems", result.answer)

    def test_goals_are_not_inferred_when_not_explicitly_declared(self):
        result = self.resolver.resolve("donne moi les objectif et les butes de youssef")
        self.assertIsNotNone(result)
        self.assertIn("ne contient pas de rubrique déclarant explicitement", result.answer)
        self.assertIn("Generative AI & RAG", result.answer)
        self.assertIn("Agentic AI & LLM Orchestration", result.answer)
        self.assertIn("[skills]", result.answer)

    def test_agentic_ai_capability_uses_explicit_skills_experience_and_training(self):
        result = self.resolver.resolve("est ce que il peuve m'aide sur un projet agentic ai ?")
        self.assertIsNotNone(result)
        self.assertTrue(result.answer.startswith("Oui"))
        self.assertIn("Agentic AI & LLM Orchestration", result.answer)
        self.assertIn("Tool Calling", result.answer)
        self.assertIn("Oracle Agentic AI Certified Foundations Associate", result.answer)
        self.assertIn("[skills]", result.answer)
        self.assertIn("[experience-education]", result.answer)
        self.assertIn("[certifications]", result.answer)

    def test_copilot_question_recognizes_this_product(self):
        result = self.resolver.resolve("est ce que il a deja fait un assistant ai copilot")
        self.assertIsNotNone(result)
        self.assertTrue(result.answer.startswith("Oui"))
        self.assertIn("Ask Youssef AI", result.answer)
        self.assertIn("portfolio", result.answer.lower())
        self.assertIn("https://github.com/YOUSSEF-BT/ASK-YOUSSEF-AI", result.answer)

    def test_specific_project_question_is_not_intercepted(self):
        self.assertIsNone(self.resolver.resolve("Which project uses BoT-SORT?"))
        self.assertIsNone(self.resolver.resolve("Tell me about OpenLegaMa"))


if __name__ == "__main__":
    unittest.main()
