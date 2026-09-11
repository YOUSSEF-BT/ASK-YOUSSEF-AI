import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from structured_facts import StructuredFactResolver  # noqa: E402


class CareerStatusRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.profile = json.loads((BACKEND / "data" / "profile.json").read_text(encoding="utf-8"))
        cls.resolver = StructuredFactResolver(cls.profile)

    def test_profile_explicitly_tracks_full_time_search(self):
        status = self.profile.get("career_status") or {}
        self.assertIs(status.get("seeking_full_time"), True)
        self.assertEqual(status.get("employment_type"), "CDI / full-time")
        self.assertTrue(status.get("freelance_parallel"))
        self.assertIn("full-time", str(status.get("summary", "")).lower())
        self.assertIn("CDI", str(status.get("summary_fr", "")))

    def test_french_job_search_question_cannot_infer_not_searching_from_freelance(self):
        result = self.resolver.resolve("est ce que youssef il recherche un emploi")
        self.assertIsNotNone(result)
        answer = result.answer.lower()
        self.assertIn("oui", answer)
        self.assertIn("cdi", answer)
        self.assertIn("[career-status]", result.answer)
        self.assertIn("freelance", answer)
        self.assertNotIn("il ne recherche donc pas", answer)
        self.assertNotIn("ne recherche pas un emploi salarié", answer)

    def test_english_job_search_question_uses_explicit_status(self):
        result = self.resolver.resolve("Is Youssef looking for a full-time job?")
        self.assertIsNotNone(result)
        self.assertIn("Yes", result.answer)
        self.assertIn("full-time", result.answer)
        self.assertIn("[career-status]", result.answer)

    def test_french_current_work_answer_positions_freelance_as_parallel(self):
        result = self.resolver.resolve("youssef il fait quoi maintenant ?")
        self.assertIsNotNone(result)
        answer = result.answer.lower()
        self.assertIn("en indépendant via fiverr", answer)
        self.assertIn("cdi à temps plein", answer)
        self.assertIn("activité parallèle", answer)
        self.assertIn("[experience-education]", result.answer)
        self.assertIn("[career-status]", result.answer)
        self.assertNotIn("chez fiverr", answer)

    def test_current_freelance_and_full_time_search_are_both_true(self):
        current = next(
            row for row in self.profile.get("work_experiences", [])
            if "present" in str(row.get("period", "")).lower()
        )
        self.assertIn("Freelance", current.get("role", ""))
        self.assertIs((self.profile.get("career_status") or {}).get("seeking_full_time"), True)

    def test_why_youssef_uses_strong_evidence_not_secondary_summarizer(self):
        result = self.resolver.resolve("pour quoi youssef et pas un autre")
        self.assertIsNotNone(result)
        answer = result.answer.lower()
        self.assertIn("raisons concrètes", answer)
        self.assertIn("86.68%", result.answer)
        self.assertIn("openlegama", answer)
        self.assertIn("cdi", answer)
        self.assertIn("[project-real-time-road-accident-detection]", result.answer)
        self.assertIn("[project-openlegama-moroccan-legal-ai]", result.answer)
        self.assertNotIn("ai summarizer", answer)
        self.assertNotIn("meilleur que tous", answer.split("en revanche", 1)[-1])

    def test_expression_typo_is_understood_as_professional_experience(self):
        result = self.resolver.resolve("donne moi les expressions de Youssef")
        self.assertIsNotNone(result)
        answer = result.answer.lower()
        self.assertIn("expériences professionnelles", answer)
        self.assertIn("nextronic", answer)
        self.assertIn("fiverr", answer)
        self.assertIn("indépendant", answer)
        self.assertIn("cdi", answer)
        self.assertIn("[experience-education]", result.answer)

    def test_literal_quote_request_is_not_reinterpreted_as_experience(self):
        result = self.resolver._resolve_experience_overview(
            "donne moi les expressions ou citations favorites de Youssef", "fr"
        )
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
