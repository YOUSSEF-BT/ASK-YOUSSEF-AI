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

    def test_french_current_work_answer_is_localized(self):
        result = self.resolver.resolve("youssef il fait quoi maintenant ?")
        self.assertIsNotNone(result)
        self.assertIn("Ingénieur IA/ML Freelance", result.answer)
        self.assertIn("Sept 2026 — Aujourd’hui", result.answer)
        self.assertIn("Conception et réalisation", result.answer)
        self.assertIn("recherche une opportunité en CDI", result.answer)
        self.assertNotIn("Designing and delivering", result.answer)
        self.assertNotIn("RAG systems and LLM-powered applications", result.answer)

    def test_current_freelance_and_full_time_search_are_both_true(self):
        current = next(
            row for row in self.profile.get("work_experiences", [])
            if "present" in str(row.get("period", "")).lower()
        )
        self.assertIn("Freelance", current.get("role", ""))
        self.assertIs((self.profile.get("career_status") or {}).get("seeking_full_time"), True)


if __name__ == "__main__":
    unittest.main()
