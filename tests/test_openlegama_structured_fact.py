import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from structured_facts import StructuredFactResolver  # noqa: E402


class OpenLegaMaStructuredFactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        profile = json.loads((BACKEND / "data" / "profile.json").read_text(encoding="utf-8"))
        cls.resolver = StructuredFactResolver(profile)

    def test_controlled_rag_question_is_resolved_from_project_data(self):
        result = self.resolver.resolve(
            "Explique brièvement le Controlled RAG utilisé dans OpenLegaMa."
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.tool, "structured_profile")
        self.assertIn("OpenLegaMa", result.answer)
        self.assertIn("Controlled RAG", result.answer)
        self.assertIn("textes juridiques officiels", result.answer)
        self.assertIn("s’abstient", result.answer)
        self.assertIn("[project-openlegama-moroccan-legal-ai]", result.answer)

    def test_generic_openlegama_question_still_uses_hybrid_retrieval(self):
        self.assertIsNone(self.resolver.resolve("Tell me about OpenLegaMa"))


if __name__ == "__main__":
    unittest.main()
