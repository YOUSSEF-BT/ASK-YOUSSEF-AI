import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "backend" / "app.py").read_text(encoding="utf-8")


class PublicApiHardeningTests(unittest.TestCase):
    def test_history_roles_are_strictly_user_or_assistant(self):
        self.assertIn('role: Literal["user", "assistant"]', APP)

    def test_history_list_has_a_hard_item_bound(self):
        self.assertIn("MAX_HISTORY_ITEMS", APP)
        self.assertIn("Field(default_factory=list, max_length=MAX_HISTORY_ITEMS)", APP)

    def test_runtime_exceptions_are_not_streamed_verbatim(self):
        self.assertIn("def _safe_runtime_error", APP)
        self.assertIn("I couldn't complete that request just now", APP)
        self.assertNotIn("message = str(exc)", APP)
        self.assertIn("runtime failure", APP)

    def test_origin_guard_runs_before_empty_question_reply(self):
        origin_pos = APP.index("if not _origin_allowed(request):", APP.index('def chat('))
        empty_pos = APP.index("if not question:", APP.index('def chat('))
        self.assertLess(origin_pos, empty_pos)

    def test_internal_reasoning_payload_is_not_streamed(self):
        self.assertNotIn('prompt=ev.data["prompt"]', APP)
        self.assertNotIn('text=ev.data["text"]', APP)


if __name__ == "__main__":
    unittest.main()
