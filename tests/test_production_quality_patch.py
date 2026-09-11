import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

import vercel_quality_patch as quality  # noqa: E402,F401
from structured_facts import StructuredFactResolver  # noqa: E402


class ProductionQualityPatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        profile = json.loads((BACKEND / "data" / "profile.json").read_text(encoding="utf-8"))
        cls.resolver = StructuredFactResolver(profile)

    def test_dangling_record_clause_is_removed_after_invalid_citation_cleanup(self):
        text = (
            "I could not verify that Youssef built a quantum computer, "
            "nor is there any record of. Youssef's actual portfolio contains AI projects."
        )
        cleaned = quality._cleanup_dangling_citation_text(text)
        self.assertNotIn("record of.", cleaned.lower())
        self.assertNotIn("nor is there any record", cleaned.lower())
        self.assertIn("Youssef's actual portfolio", cleaned)

    def test_arabic_false_employer_uses_structured_employer_lane(self):
        result = self.resolver.resolve("هل عمل يوسف في Google؟")
        self.assertIsNotNone(result)
        self.assertIn("لا", result.answer)
        self.assertIn("[experience-education]", result.answer)
        self.assertNotIn("Vertex AI", result.answer)

    def test_professional_summary_is_deterministic_and_current(self):
        result = self.resolver.resolve("Write a short professional summary of Youssef.")
        self.assertIsNotNone(result)
        self.assertIn("Freelance AI/ML Engineer", result.answer)
        self.assertIn("Fiverr", result.answer)
        self.assertIn("full-time AI/ML opportunity", result.answer)
        self.assertIn("[experience-education]", result.answer)
        self.assertIn("[career-status]", result.answer)
        self.assertIn("[skills]", result.answer)

    def test_french_conversational_profile_is_current(self):
        result = self.resolver.resolve("Tu peux me parler de lui ?")
        self.assertIsNotNone(result)
        self.assertIn("Youssef Bouzit", result.answer)
        self.assertIn("Ingénieur IA/ML Freelance", result.answer)
        self.assertIn("Fiverr", result.answer)
        self.assertIn("CDI", result.answer)

    def test_salary_address_phone_and_age_do_not_go_to_generation(self):
        cases = [
            ("What salary does Youssef currently earn?", "salary"),
            ("What is Youssef's home address?", "address"),
            ("What is Youssef's phone number?", "phone"),
            ("How old is Youssef?", "age"),
        ]
        for question, label in cases:
            with self.subTest(label=label):
                result = self.resolver.resolve(question)
                self.assertIsNotNone(result)
                self.assertEqual(result.source, "structured-profile")
                self.assertIn("does not provide", result.answer)
                self.assertIn("won't infer", result.answer)
                self.assertNotIn("[project-", result.answer)
                self.assertNotIn("[skills]", result.answer)


if __name__ == "__main__":
    unittest.main()
