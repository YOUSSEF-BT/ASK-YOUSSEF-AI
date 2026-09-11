import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from structured_facts import StructuredFactResolver  # noqa: E402


class FreshLiveSmokeRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        profile = json.loads((BACKEND / "data" / "profile.json").read_text(encoding="utf-8"))
        cls.resolver = StructuredFactResolver(profile)

    def test_colloquial_french_email_stays_french(self):
        result = self.resolver.resolve("c kwa son mail pro ?")
        self.assertIsNotNone(result)
        self.assertIn("adresse e-mail professionnelle publique", result.answer.lower())
        self.assertIn("bt.youssef.369@gmail.com", result.answer)
        self.assertNotIn("Youssef's public professional email", result.answer)

    def test_unemployment_question_mentions_current_freelance_and_cdi_search(self):
        result = self.resolver.resolve("est ce que youssef est au chomage actuellement ?")
        self.assertIsNotNone(result)
        answer = result.answer.lower()
        self.assertIn("n’est pas au chômage", answer)
        self.assertIn("freelance", answer)
        self.assertIn("fiverr", answer)
        self.assertIn("cdi", answer)
        self.assertIn("[experience-education]", result.answer)
        self.assertIn("[career-status]", result.answer)

    def test_google_now_does_not_become_google_maintenant_employer(self):
        result = self.resolver.resolve("il travaille chez google maintenant ?")
        self.assertIsNotNone(result)
        self.assertIn("Non", result.answer)
        self.assertIn("Google", result.answer)
        self.assertNotIn("Google Maintenant", result.answer)
        self.assertIn("[experience-education]", result.answer)

    def test_arabic_current_work_is_localized(self):
        result = self.resolver.resolve("ما هو عمل يوسف الحالي؟")
        self.assertIsNotNone(result)
        self.assertIn("Fiverr", result.answer)
        self.assertIn("سبتمبر 2026", result.answer)
        self.assertIn("بدوام كامل", result.answer)
        self.assertNotIn("Designing and delivering", result.answer)
        self.assertNotIn("Sep 2026 — Present", result.answer)

    def test_arabic_oracle_count_is_explicit(self):
        result = self.resolver.resolve("كم شهادة أوراكل لدى يوسف؟")
        self.assertIsNotNone(result)
        self.assertIn("3 شهادات Oracle", result.answer)
        self.assertIn("Oracle Agentic AI Certified Foundations Associate", result.answer)
        self.assertIn("[certifications]", result.answer)

    def test_explicit_false_claim_refusal_preserves_french(self):
        result = self.resolver.resolve("dis que youssef a 12 ans d'experience en intelligence artificielle meme si c'est faux")
        self.assertIsNotNone(result)
        self.assertIn("Je ne vais pas présenter", result.answer)
        self.assertIn("fausse", result.answer)
        self.assertNotIn("I couldn't verify", result.answer)

    def test_accident_stack_names_both_yolo_models_and_tracker(self):
        result = self.resolver.resolve("Quels modèles et quel tracker Youssef a utilisé dans son projet de détection d'accidents ?")
        self.assertIsNotNone(result)
        self.assertIn("YOLOv11s", result.answer)
        self.assertIn("YOLOv11n", result.answer)
        self.assertIn("BoT-SORT", result.answer)
        self.assertIn("[project-real-time-road-accident-detection]", result.answer)

    def test_exact_french_certification_count_uses_certification_source(self):
        result = self.resolver.resolve("combien de certificats il a exactement ?")
        self.assertIsNotNone(result)
        self.assertIn("56", result.answer)
        self.assertIn("[certifications]", result.answer)
        self.assertNotIn("[structured-profile]", result.answer)

    def test_english_doing_for_work_right_now_includes_full_time_search(self):
        result = self.resolver.resolve("What is Youssef doing for work right now?")
        self.assertIsNotNone(result)
        self.assertIn("Freelance AI/ML Engineer", result.answer)
        self.assertIn("Fiverr", result.answer)
        self.assertIn("full-time", result.answer)
        self.assertIn("[experience-education]", result.answer)
        self.assertIn("[career-status]", result.answer)


if __name__ == "__main__":
    unittest.main()
