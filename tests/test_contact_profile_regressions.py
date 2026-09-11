import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from structured_facts import StructuredFactResolver  # noqa: E402


class ContactAndProfileRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        profile = json.loads((BACKEND / "data" / "profile.json").read_text(encoding="utf-8"))
        cls.resolver = StructuredFactResolver(profile)

    def test_contact_overview_is_complete_and_includes_email(self):
        result = self.resolver.resolve("How can I contact Youssef?")
        self.assertIsNotNone(result)
        self.assertIn("bt.youssef.369@gmail.com", result.answer)
        self.assertIn("linkedin.com/in/youssef-bouzit-74863239b", result.answer)
        self.assertIn("github.com/YOUSSEF-BT", result.answer)
        self.assertIn("fiverr.com/youssef_bouzit", result.answer)
        self.assertIn("[public-links]", result.answer)
        self.assertNotIn("send him a direct message", result.answer.lower())

    def test_short_email_followup_returns_clean_plain_email(self):
        history = [
            {"role": "user", "content": "How can I contact Youssef?"},
            {"role": "assistant", "content": "Public professional contact options are available."},
        ]
        result = self.resolver.resolve("email ?", history)
        self.assertIsNotNone(result)
        self.assertIn("bt.youssef.369@gmail.com", result.answer)
        self.assertIn("[public-links]", result.answer)
        self.assertNotIn("mailto:", result.answer)
        self.assertNotIn("\\@", result.answer)

    def test_contact_action_is_not_hijacked_by_information_resolver(self):
        self.assertIsNone(self.resolver._resolve_contact_details("Send an email to Youssef", "en"))
        self.assertIsNone(self.resolver._resolve_contact_details("Envoie un message à Youssef", "fr"))

    def test_marital_question_gets_targeted_private_detail_refusal(self):
        result = self.resolver.resolve("hi is married ?")
        self.assertIsNotNone(result)
        answer = result.answer.lower()
        self.assertIn("marital", answer)
        self.assertIn("private personal", answer)
        self.assertIn("don't infer", answer)
        self.assertNotIn("yes", answer)
        self.assertNotIn("no,", answer)

    def test_incomplete_professional_fragment_returns_actual_profile_summary(self):
        result = self.resolver.resolve("his professional")
        self.assertIsNotNone(result)
        self.assertIn("Freelance AI/ML Engineer", result.answer)
        self.assertIn("Fiverr", result.answer)
        self.assertIn("full-time opportunity", result.answer)
        self.assertIn("[experience-education]", result.answer)
        self.assertIn("[skills]", result.answer)

    def test_french_conversational_current_work_variant_is_exact(self):
        result = self.resolver.resolve("que ce qu’il fait youssef")
        self.assertIsNotNone(result)
        self.assertTrue(result.answer.startswith("Actuellement"))
        self.assertIn("Ingénieur IA/ML Freelance", result.answer)
        self.assertIn("Fiverr", result.answer)
        self.assertIn("Sept 2026 — Aujourd’hui", result.answer)
        self.assertIn("recherche une opportunité en CDI", result.answer)


if __name__ == "__main__":
    unittest.main()
