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
        self.assertNotIn("currently lists three certifications issued by LinkedIn", result.answer.lower())

    def test_oracle_inventory_is_complete_as_followup(self):
        self.assertEqual(len(self.oracle), 3, "Current public portfolio should contain three Oracle certifications")
        result = self.resolver.resolve("What about Oracle?", self.cert_history)
        self.assertIsNotNone(result)
        self.assertIn("3", result.answer)
        for row in self.oracle:
            self.assertIn(row["title"], result.answer)

    def test_oracle_challenge_in_french_returns_real_inventory(self):
        result = self.resolver.resolve("je pense il a 3 certifications de oracle")
        self.assertIsNotNone(result)
        self.assertIn("3", result.answer)
        for row in self.oracle:
            self.assertIn(row["title"], result.answer)

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

    def test_issuer_name_does_not_hijack_employer_question(self):
        self.assertIsNone(self.resolver.resolve("Did Youssef work at IBM?"))
        self.assertIsNone(self.resolver.resolve("Did Youssef work at Oracle?"))

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

    def test_filtered_project_aggregates_are_not_mistaken_for_total_inventory(self):
        self.assertIsNone(self.resolver.resolve("How many Computer Vision projects does Youssef have?"))
        self.assertIsNone(self.resolver.resolve("How many RAG projects does Youssef have?"))
        self.assertIsNone(self.resolver.resolve("List all Python projects"))

    def test_specific_project_question_is_not_intercepted(self):
        self.assertIsNone(self.resolver.resolve("Which project uses BoT-SORT?"))
        self.assertIsNone(self.resolver.resolve("Tell me about OpenLegaMa"))

    def test_specific_experience_question_is_not_intercepted(self):
        self.assertIsNone(self.resolver.resolve("Did Youssef work at NEXTRONIC?"))


if __name__ == "__main__":
    unittest.main()
