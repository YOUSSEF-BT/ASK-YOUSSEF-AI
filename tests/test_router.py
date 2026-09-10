import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from router import detect_language, route_question  # noqa: E402


class LanguageRouterTests(unittest.TestCase):
    def test_french(self):
        self.assertEqual(detect_language("Quels sont ses meilleurs projets ?"), "fr")

    def test_arabic(self):
        self.assertEqual(detect_language("ما هي أبرز مشاريع يوسف؟"), "ar")

    def test_english_default(self):
        self.assertEqual(detect_language("What are his strongest projects?"), "en")


class IntentRouterTests(unittest.TestCase):
    def test_project_fact_requires_retrieval(self):
        route = route_question("Quel projet utilise YOLOv11 ?")
        self.assertEqual(route.intent, "projects")
        self.assertTrue(route.requires_retrieval)
        self.assertEqual(route.language, "fr")

    def test_certification_fact_requires_retrieval(self):
        route = route_question("Which Oracle certifications does Youssef have?")
        self.assertEqual(route.intent, "certifications")
        self.assertTrue(route.requires_retrieval)

    def test_arabic_skills_requires_retrieval(self):
        route = route_question("ما هي مهارات يوسف في RAG؟")
        self.assertEqual(route.intent, "skills")
        self.assertTrue(route.requires_retrieval)
        self.assertEqual(route.language, "ar")

    def test_greeting_does_not_force_retrieval(self):
        route = route_question("Bonjour Youssef")
        self.assertEqual(route.intent, "greeting")
        self.assertFalse(route.requires_retrieval)

    def test_contact_info_is_factual(self):
        route = route_question("How can I contact Youssef?")
        self.assertEqual(route.intent, "contact")
        self.assertTrue(route.requires_retrieval)

    def test_send_message_is_action_not_retrieval(self):
        route = route_question("Send Youssef a message for me")
        self.assertEqual(route.intent, "contact_action")
        self.assertFalse(route.requires_retrieval)

    def test_unrelated_general_question_outside_scope(self):
        route = route_question("What is the capital of Japan?")
        self.assertEqual(route.intent, "general")
        self.assertFalse(route.portfolio_scope)


if __name__ == "__main__":
    unittest.main()
