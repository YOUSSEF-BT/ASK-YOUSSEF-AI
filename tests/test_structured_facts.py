import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from structured_facts import StructuredFactResolver  # noqa: E402


class StructuredCertificationFactsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.profile = json.loads((BACKEND / "data" / "profile.json").read_text(encoding="utf-8"))
        cls.resolver = StructuredFactResolver(cls.profile)
        cls.oracle = [
            row for row in cls.profile.get("certifications", [])
            if row.get("issuer") == "Oracle"
        ]

    def test_total_count_comes_from_complete_profile(self):
        expected = len(self.profile["certifications"])
        result = self.resolver.resolve("How many certifications does he have?")
        self.assertIsNotNone(result)
        self.assertIn(str(expected), result.answer)
        self.assertIn("[certifications]", result.answer)
        self.assertEqual(result.tool, "structured_profile")

    def test_broad_question_exposes_total_and_issuer_breakdown(self):
        expected = len(self.profile["certifications"])
        result = self.resolver.resolve("Which certifications does he have?")
        self.assertIsNotNone(result)
        self.assertIn(str(expected), result.answer)
        self.assertIn("Oracle", result.answer)
        self.assertIn("Anthropic", result.answer)
        self.assertIn("LinkedIn", result.answer)
        self.assertNotIn("currently lists three certifications issued by LinkedIn", result.answer.lower())

    def test_oracle_inventory_is_complete(self):
        self.assertEqual(len(self.oracle), 3, "Current public portfolio should contain three Oracle certifications")
        result = self.resolver.resolve("What about Oracle?")
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
        history = [
            {"role": "user", "content": "Which certifications does he have?"},
            {"role": "assistant", "content": "His certifications are listed on the portfolio certifications page."},
        ]
        result = self.resolver.resolve("how many?", history)
        self.assertIsNotNone(result)
        self.assertIn(str(len(self.profile["certifications"])), result.answer)

    def test_unrelated_question_is_not_intercepted(self):
        self.assertIsNone(self.resolver.resolve("Which project uses BoT-SORT?"))


if __name__ == "__main__":
    unittest.main()
