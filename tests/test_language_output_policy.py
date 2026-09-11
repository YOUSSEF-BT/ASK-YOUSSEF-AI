from __future__ import annotations

import importlib
import sys
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


class StrictLanguageOutputPolicyTests(unittest.TestCase):
    def test_vercel_entrypoint_wires_language_patch_before_backend(self):
        source = (ROOT / "app.py").read_text(encoding="utf-8")
        language_pos = source.index("import vercel_language_patch")
        backend_pos = source.index("import backend.app as _backend")
        self.assertLess(language_pos, backend_pos)

    def test_generated_answer_policy_is_mandatory_for_arabic(self):
        import agent

        importlib.import_module("vercel_language_patch")
        prompt = agent.AGENTIC_RAG_PROMPT
        self.assertIn("ALWAYS answer in the language of the visitor's CURRENT question", prompt)
        self.assertIn("Final Answer prose must be in Arabic script", prompt)
        self.assertIn("determine the response language from that current follow-up", prompt)
        self.assertNotIn("Match the visitor's language when practical", prompt)


if __name__ == "__main__":
    unittest.main()
