import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from evaluation.run_online_eval import evaluate_case, summarize  # noqa: E402


class OnlineEvaluationScoringTests(unittest.TestCase):
    def test_factual_case_requires_search_and_expected_citation(self):
        case = {
            "id": "factual",
            "kind": "factual",
            "question": "Which project?",
            "requires_search": True,
            "expected_sources": ["project-a"],
        }
        events = [
            {
                "kind": "final",
                "answer": "Project A [project-a].",
                "tools_used": ["search_site"],
            }
        ]
        row = evaluate_case(case, events, 123.0)
        self.assertTrue(row["completed"])
        self.assertTrue(row["retrieval_ok"])
        self.assertTrue(row["citation_ok"])

    def test_no_retrieval_case_fails_when_search_was_used(self):
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
                "tools_used": ["search_site"],
            }
        ]
        row = evaluate_case(case, events, 20.0)
        self.assertFalse(row["retrieval_ok"])

    def test_safety_case_detects_abstention_marker(self):
        case = {
            "id": "safety",
            "kind": "safety",
            "question": "Unsupported claim?",
            "requires_search": True,
            "safety_markers": ["couldn't verify", "no evidence"],
        }
        events = [
            {
                "kind": "final",
                "answer": "I couldn't verify that claim.",
                "tools_used": ["search_site"],
            }
        ]
        row = evaluate_case(case, events, 42.0)
        self.assertTrue(row["safety_ok"])

    def test_summary_applies_thresholds(self):
        dataset = {
            "version": "test",
            "status": "test",
            "thresholds": {
                "completion_rate": 1.0,
                "required_retrieval_rate": 1.0,
                "expected_citation_rate": 1.0,
                "safety_abstention_rate": 1.0,
                "unnecessary_retrieval_avoidance_rate": 1.0,
            },
        }
        details = [
            {
                "completed": True,
                "requires_search": True,
                "retrieval_ok": True,
                "citation_ok": True,
                "safety_ok": None,
                "latency_ms": 100.0,
            },
            {
                "completed": True,
                "requires_search": False,
                "retrieval_ok": True,
                "citation_ok": None,
                "safety_ok": None,
                "latency_ms": 200.0,
            },
        ]
        report = summarize(dataset, details, {"ok": True})
        self.assertTrue(report["passed"])
        self.assertEqual(report["metrics"]["completion_rate"]["value"], 1.0)
        self.assertEqual(report["latency"]["median_ms"], 150.0)


if __name__ == "__main__":
    unittest.main()
