import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from evaluation.run_online_eval import evaluate_case, summarize  # noqa: E402

KNOWN = {"project-a", "public-links", "skills", "certifications"}


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
        row = evaluate_case(case, events, 123.0, known_sources=KNOWN)
        self.assertTrue(row["completed"])
        self.assertTrue(row["retrieval_ok"])
        self.assertTrue(row["citation_ok"])
        self.assertTrue(row["citation_integrity_ok"])

    def test_required_answer_literals_are_enforced(self):
        case = {
            "id": "email",
            "kind": "factual",
            "question": "What is Youssef's public email?",
            "requires_search": True,
            "expected_sources": ["public-links"],
            "expected_answer_contains": ["bt.youssef.369@gmail.com"],
        }
        events = [
            {
                "kind": "final",
                "answer": "Email: bt.youssef.369@gmail.com [public-links].",
                "tools_used": ["search_site"],
            }
        ]
        row = evaluate_case(case, events, 80.0, known_sources=KNOWN)
        self.assertTrue(row["answer_contains_ok"])

        events[0]["answer"] = "Please use LinkedIn [public-links]."
        row = evaluate_case(case, events, 80.0, known_sources=KNOWN)
        self.assertFalse(row["answer_contains_ok"])

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
        row = evaluate_case(case, events, 20.0, known_sources=KNOWN)
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
        row = evaluate_case(case, events, 42.0, known_sources=KNOWN)
        self.assertTrue(row["safety_ok"])

    def test_all_required_sources_must_be_present(self):
        case = {
            "id": "multi-source",
            "kind": "factual",
            "question": "Summarize evidence",
            "requires_search": True,
            "required_sources": ["project-a", "skills"],
        }
        events = [{
            "kind": "final",
            "answer": "Evidence [project-a].",
            "tools_used": ["search_site"],
        }]
        row = evaluate_case(case, events, 10.0, known_sources=KNOWN)
        self.assertFalse(row["required_sources_ok"])
        events[0]["answer"] = "Evidence [project-a] [skills]."
        row = evaluate_case(case, events, 10.0, known_sources=KNOWN)
        self.assertTrue(row["required_sources_ok"])

    def test_forbidden_content_and_citation_integrity_are_checked(self):
        case = {
            "id": "adversarial",
            "kind": "factual",
            "question": "Test",
            "requires_search": True,
            "forbidden_answer_contains": ["invented employer"],
        }
        events = [{
            "kind": "final",
            "answer": "invented employer [fake-source]",
            "tools_used": ["search_site"],
        }]
        row = evaluate_case(case, events, 10.0, known_sources=KNOWN)
        self.assertFalse(row["forbidden_answer_ok"])
        self.assertFalse(row["citation_integrity_ok"])
        self.assertIn("fake-source", row["unknown_citations"])

    def test_sse_error_event_means_case_did_not_complete(self):
        case = {
            "id": "error",
            "kind": "factual",
            "question": "Question",
            "requires_search": True,
        }
        events = [
            {"kind": "error", "message": "Rate limit exceeded"},
            {"kind": "final", "answer": "Partial answer", "tools_used": ["search_site"]},
        ]
        row = evaluate_case(case, events, 12.0, known_sources=KNOWN)
        self.assertFalse(row["completed"])
        self.assertEqual(row["error_messages"], ["Rate limit exceeded"])

    def test_summary_applies_thresholds(self):
        dataset = {
            "version": "test",
            "status": "test",
            "thresholds": {
                "completion_rate": 1.0,
                "required_retrieval_rate": 1.0,
                "expected_citation_rate": 1.0,
                "citation_integrity_rate": 1.0,
                "expected_answer_contains_rate": 1.0,
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
                "required_sources_ok": None,
                "answer_contains_ok": True,
                "answer_contains_any_ok": None,
                "forbidden_answer_ok": None,
                "safety_ok": None,
                "citation_integrity_ok": True,
                "latency_ok": None,
                "latency_ms": 100.0,
            },
            {
                "completed": True,
                "requires_search": False,
                "retrieval_ok": True,
                "citation_ok": None,
                "required_sources_ok": None,
                "answer_contains_ok": None,
                "answer_contains_any_ok": None,
                "forbidden_answer_ok": None,
                "safety_ok": None,
                "citation_integrity_ok": True,
                "latency_ok": None,
                "latency_ms": 200.0,
            },
        ]
        report = summarize(dataset, details, {"ok": True})
        self.assertTrue(report["passed"])
        self.assertEqual(report["metrics"]["completion_rate"]["value"], 1.0)
        self.assertEqual(report["metrics"]["expected_answer_contains_rate"]["value"], 1.0)
        self.assertEqual(report["metrics"]["citation_integrity_rate"]["value"], 1.0)
        self.assertEqual(report["latency"]["median_ms"], 150.0)


if __name__ == "__main__":
    unittest.main()
