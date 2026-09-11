import json
import os
import sys
import types
import unittest
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

# Production patch is intentionally imported before the modules under test.
import vercel_quality_patch  # noqa: E402,F401
import rag  # noqa: E402
from grounding import enforce_grounding  # noqa: E402
from structured_facts import StructuredFactResolver  # noqa: E402


@dataclass
class Step:
    action: str | None = None
    observation: str | None = None


class ProductionQualityRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.profile = json.loads(
            (BACKEND / "data" / "profile.json").read_text(encoding="utf-8")
        )
        cls.resolver = StructuredFactResolver(cls.profile)
        cls.oracle_history = [
            {"role": "user", "content": "Quelles certifications Oracle possède Youssef ?"},
            {
                "role": "assistant",
                "content": (
                    "Il possède 3 certifications Oracle : 1. Oracle Agentic AI Certified "
                    "Foundations Associate 2. Oracle AI Database Certified Foundations "
                    "Associate 3. Oracle Cloud Infrastructure 2026 Certified Architect Associate."
                ),
            },
        ]

    def test_typo_current_work_routes_to_fiverr_structured_answer(self):
        result = self.resolver.resolve("youssef il fais quoi en ce moment ?")
        self.assertIsNotNone(result)
        self.assertTrue(result.answer.startswith("Actuellement"))
        self.assertIn("Ingénieur IA/ML Freelance", result.answer)
        self.assertIn("Fiverr", result.answer)
        self.assertIn("Sept 2026 — Aujourd’hui", result.answer)
        self.assertNotIn("Designing and delivering", result.answer)

    def test_french_known_employer_uses_localized_experience_fields(self):
        result = self.resolver.resolve("Youssef a-t-il travaillé chez NEXTRONIC ?")
        self.assertIsNotNone(result)
        self.assertIn("NEXTRONIC", result.answer)
        self.assertIn("Stagiaire Ingénieur IA/ML", result.answer)
        self.assertIn("Vision par ordinateur", result.answer)
        self.assertIn("Fév 2026 — Août 2026", result.answer)
        self.assertNotIn("AI/ML Engineer Intern", result.answer)

    def test_french_cert_followup_does_not_mix_english_description(self):
        result = self.resolver.resolve("Et la deuxième ?", self.oracle_history)
        self.assertIsNotNone(result)
        self.assertIn("Oracle AI Database Certified Foundations Associate", result.answer)
        self.assertIn("est une certification délivrée par Oracle", result.answer)
        self.assertIn("Vérification :", result.answer)
        self.assertNotIn("Foundational certification in", result.answer)
        self.assertNotIn("It covers:", result.answer)

    def test_unknown_citation_removal_does_not_leave_dangling_grammar(self):
        steps = [
            Step(
                action="search_site",
                observation=(
                    "[project-real-time-road-accident-detection · relevance 0.92] "
                    "Youssef built a road accident detection project."
                ),
            )
        ]
        answer, report = enforce_grounding(
            "I could not verify a production quantum computer or any project associated with [project-fake].",
            steps,
        )
        self.assertIn("project-fake", report.unknown_citations)
        self.assertNotIn("[project-fake]", answer)
        self.assertNotIn("associated with.", answer)
        self.assertIn("production quantum computer.", answer)

    def test_fastembed_runtime_reuses_vercel_build_cache_path(self):
        calls = []

        class FakeTextEmbedding:
            def __init__(self, **kwargs):
                calls.append(kwargs)

        fake_fastembed = types.ModuleType("fastembed")
        fake_fastembed.TextEmbedding = FakeTextEmbedding
        with patch.dict(sys.modules, {"fastembed": fake_fastembed}):
            with patch.dict(
                os.environ,
                {
                    "FASTEMBED_MODEL": "BAAI/bge-small-en-v1.5",
                    "FASTEMBED_CACHE_PATH": "backend/data/fastembed_cache",
                },
                clear=False,
            ):
                embedder = rag.FastEmbedEmbedder()

        self.assertEqual(embedder.model_name, "BAAI/bge-small-en-v1.5")
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["model_name"], "BAAI/bge-small-en-v1.5")
        self.assertTrue(
            calls[0]["cache_dir"].endswith("backend/data/fastembed_cache"),
            calls[0]["cache_dir"],
        )
        self.assertTrue(os.path.isabs(calls[0]["cache_dir"]))


if __name__ == "__main__":
    unittest.main()
