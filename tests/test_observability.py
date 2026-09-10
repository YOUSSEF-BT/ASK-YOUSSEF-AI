import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from observability import RuntimeTelemetry  # noqa: E402


class RuntimeTelemetryTests(unittest.TestCase):
    def test_records_aggregate_request_and_completion_metrics(self):
        telemetry = RuntimeTelemetry(max_latency_samples=20)
        route = SimpleNamespace(language="fr", intent="projects", requires_retrieval=True)
        telemetry.record_request(route)
        telemetry.record_completed(
            latency_ms=120.0,
            retrieval_used=True,
            grounding_intervened=False,
        )
        snapshot = telemetry.snapshot()

        self.assertEqual(snapshot["requests"], 1)
        self.assertEqual(snapshot["completed"], 1)
        self.assertEqual(snapshot["errors"], 0)
        self.assertEqual(snapshot["retrieval"]["required_turns"], 1)
        self.assertEqual(snapshot["retrieval"]["used_turns"], 1)
        self.assertEqual(snapshot["languages"], {"fr": 1})
        self.assertEqual(snapshot["intents"], {"projects": 1})
        self.assertEqual(snapshot["latency_ms"]["median"], 120.0)

    def test_grounding_intervention_and_error_are_counted(self):
        telemetry = RuntimeTelemetry()
        telemetry.record_request(
            SimpleNamespace(language="en", intent="experience", requires_retrieval=True)
        )
        telemetry.record_completed(
            latency_ms=250.0,
            retrieval_used=True,
            grounding_intervened=True,
        )
        telemetry.record_error(latency_ms=500.0)
        snapshot = telemetry.snapshot()

        self.assertEqual(snapshot["grounding"]["interventions"], 1)
        self.assertEqual(snapshot["errors"], 1)
        self.assertEqual(snapshot["latency_ms"]["samples"], 2)
        self.assertEqual(snapshot["latency_ms"]["max"], 500.0)

    def test_latency_window_is_bounded(self):
        telemetry = RuntimeTelemetry(max_latency_samples=10)
        for i in range(20):
            telemetry.record_completed(
                latency_ms=float(i),
                retrieval_used=False,
                grounding_intervened=False,
            )
        snapshot = telemetry.snapshot()
        self.assertEqual(snapshot["latency_ms"]["samples"], 10)
        self.assertEqual(snapshot["latency_ms"]["max"], 19.0)

    def test_snapshot_exposes_privacy_contract_not_user_content(self):
        telemetry = RuntimeTelemetry()
        snapshot = telemetry.snapshot()
        self.assertIn("no prompts", snapshot["privacy"])
        self.assertNotIn("questions", snapshot)
        self.assertNotIn("answers", snapshot)
        self.assertNotIn("ips", snapshot)


if __name__ == "__main__":
    unittest.main()
