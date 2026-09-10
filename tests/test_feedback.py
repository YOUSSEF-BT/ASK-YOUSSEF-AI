import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from feedback import FeedbackStore  # noqa: E402


class FeedbackStoreTests(unittest.TestCase):
    def test_records_positive_and_negative_feedback(self):
        store = FeedbackStore()
        store.record("up", "helpful")
        store.record("down", "incorrect")
        snapshot = store.snapshot()
        self.assertEqual(snapshot["total"], 2)
        self.assertEqual(snapshot["up"], 1)
        self.assertEqual(snapshot["down"], 1)
        self.assertEqual(snapshot["helpful_rate"], 0.5)
        self.assertEqual(snapshot["reasons"]["helpful"], 1)
        self.assertEqual(snapshot["reasons"]["incorrect"], 1)

    def test_rejects_free_form_or_unknown_categories(self):
        store = FeedbackStore()
        with self.assertRaises(ValueError):
            store.record("maybe")
        with self.assertRaises(ValueError):
            store.record("down", "this is a long private comment")

    def test_snapshot_contains_no_visitor_payload_fields(self):
        store = FeedbackStore()
        store.record("up")
        snapshot = store.snapshot()
        forbidden = {"question", "answer", "email", "ip", "history", "comment"}
        self.assertFalse(forbidden & set(snapshot))


if __name__ == "__main__":
    unittest.main()
