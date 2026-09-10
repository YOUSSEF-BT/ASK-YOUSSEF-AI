import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from evaluation.run_online_eval import evaluate_case  # noqa: E402


class StructuredProfileEvaluationTests(unittest.TestCase):
    def test_structured_profile_counts_as_grounded_retrieval(self):
        case = {
            "id": "cert-count",
            "kind": "factual",
            "question": "How many certifications does he have?",
            "requires_search": True,
            "expected_sources": ["certifications"],
        }
        events = [
            {
                "kind": "final",
                "answer": "The portfolio lists 56 certifications [certifications].",
                "tools_used": ["structured_profile"],
            }
        ]
        row = evaluate_case(case, events, 5.0)
        self.assertTrue(row["retrieval_ok"])
        self.assertTrue(row["citation_ok"])

    def test_structured_profile_is_not_allowed_on_no_retrieval_case(self):
        case = {
            "id": "hello",
            "kind": "no-retrieval",
            "question": "Hello",
            "requires_search": False,
        }
        events = [
            {
                "kind": "final",
                "answer": "Hello!",
                "tools_used": ["structured_profile"],
            }
        ]
        row = evaluate_case(case, events, 5.0)
        self.assertFalse(row["retrieval_ok"])


if __name__ == "__main__":
    unittest.main()
