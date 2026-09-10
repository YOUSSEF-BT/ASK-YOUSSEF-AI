import sys
import unittest
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from grounding import enforce_grounding, verify_grounding  # noqa: E402


@dataclass
class Step:
    action: str | None = None
    observation: str | None = None


EVIDENCE = (
    "[project-real-time-road-accident-detection · relevance 0.92] "
    "YOLOv11s achieved 86.68% precision and 91.56% recall at 31.5 FPS. || "
    "[skills · relevance 0.61] Computer Vision skills include YOLOv11 and OpenCV."
)


class GroundingVerifierTests(unittest.TestCase):
    def setUp(self):
        self.steps = [Step(action="search_site", observation=EVIDENCE)]

    def test_supported_metric_passes_and_gets_real_source(self):
        answer, report = enforce_grounding(
            "The image benchmark reports 86.68% precision.", self.steps
        )
        self.assertTrue(report.high_risk_supported)
        self.assertIn("[project-real-time-road-accident-detection]", answer)

    def test_unsupported_metric_is_blocked(self):
        answer, report = enforce_grounding(
            "The system achieved 99.99% precision.", self.steps
        )
        self.assertFalse(report.high_risk_supported)
        self.assertIn("couldn't verify", answer)
        self.assertNotIn("99.99%", answer)

    def test_supported_citation_is_preserved(self):
        answer, report = enforce_grounding(
            "It uses YOLOv11s. [project-real-time-road-accident-detection]", self.steps
        )
        self.assertEqual(answer, "It uses YOLOv11s. [project-real-time-road-accident-detection]")
        self.assertEqual(
            report.valid_citations,
            ("project-real-time-road-accident-detection",),
        )

    def test_unknown_citation_is_reported(self):
        report = verify_grounding("Claim [made-up-source]", self.steps)
        self.assertEqual(report.unknown_citations, ("made-up-source",))

    def test_non_retrieval_turn_is_left_unchanged(self):
        answer, report = enforce_grounding("Hello! How can I help?", [])
        self.assertEqual(answer, "Hello! How can I help?")
        self.assertFalse(report.has_search_evidence)


if __name__ == "__main__":
    unittest.main()
