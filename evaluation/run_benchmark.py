"""Deterministic quality benchmark for Ask Youssef AI.

This benchmark deliberately avoids network calls and LLM judging. It measures the
parts we can make reproducible in CI today:

- multilingual route classification,
- field-aware structured retrieval over the synchronized public profile,
- profile/manifest synchronization integrity,
- output grounding guardrails for invented metrics, links, emails, and citations.

It is a regression gate, not a claim of end-to-end answer accuracy. A separate
online evaluation can later score the deployed model itself.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from grounding import enforce_grounding  # noqa: E402
from retrieval.structured import StructuredProfileRetriever  # noqa: E402
from router import route_question  # noqa: E402


@dataclass
class EvidenceStep:
    action: str | None = None
    observation: str | None = None


@dataclass
class Metric:
    name: str
    value: float
    threshold: float

    @property
    def passed(self) -> bool:
        return self.value + 1e-12 >= self.threshold


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _route_eval(cases: list[dict[str, Any]]) -> tuple[float, list[dict[str, Any]]]:
    total = 0
    passed = 0
    details: list[dict[str, Any]] = []
    for case in cases:
        expected = case.get("expected_route")
        if not expected:
            continue
        total += 1
        route = route_question(case["question"])
        actual = {
            "language": route.language,
            "intent": route.intent,
            "requires_retrieval": route.requires_retrieval,
            "portfolio_scope": route.portfolio_scope,
        }
        ok = all(actual.get(key) == value for key, value in expected.items())
        passed += int(ok)
        details.append(
            {
                "id": case["id"],
                "passed": ok,
                "expected": expected,
                "actual": actual,
            }
        )
    return (passed / total if total else 1.0), details


def _is_relevant(hit: Any, target: dict[str, Any]) -> bool:
    sources = set(target.get("expected_sources") or [])
    entity_types = set(target.get("expected_entity_types") or [])
    source_ok = not sources or hit.meta.get("source") in sources
    type_ok = not entity_types or hit.meta.get("entity_type") in entity_types
    return source_ok and type_ok


def _retrieval_eval(
    cases: list[dict[str, Any]], retriever: StructuredProfileRetriever
) -> tuple[dict[str, float], list[dict[str, Any]]]:
    total = 0
    hit1 = 0
    hit3 = 0
    reciprocal_rank = 0.0
    details: list[dict[str, Any]] = []

    for case in cases:
        target = case.get("retrieval")
        if not target:
            continue
        total += 1
        hits = retriever.search(case["question"], k=5)
        relevant_rank: int | None = None
        for rank, hit in enumerate(hits, 1):
            if _is_relevant(hit, target):
                relevant_rank = rank
                break
        h1 = relevant_rank == 1
        h3 = relevant_rank is not None and relevant_rank <= 3
        hit1 += int(h1)
        hit3 += int(h3)
        if relevant_rank:
            reciprocal_rank += 1.0 / relevant_rank
        details.append(
            {
                "id": case["id"],
                "rank": relevant_rank,
                "hit_at_1": h1,
                "hit_at_3": h3,
                "top_hits": [
                    {
                        "rank": rank,
                        "source": hit.meta.get("source"),
                        "entity_type": hit.meta.get("entity_type"),
                        "heading": hit.meta.get("heading"),
                        "score": round(float(hit.score), 6),
                    }
                    for rank, hit in enumerate(hits[:3], 1)
                ],
            }
        )

    denominator = total or 1
    return (
        {
            "retrieval_hit_at_1": hit1 / denominator,
            "retrieval_hit_at_3": hit3 / denominator,
            "retrieval_mrr": reciprocal_rank / denominator,
        },
        details,
    )


def _grounding_case(case: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    observation = case.get("observation")
    steps = [EvidenceStep(action="search_site", observation=observation)] if observation else []
    original = case["answer"]
    guarded, report = enforce_grounding(original, steps)
    expected = case["expected"]

    if expected == "allow":
        ok = report.high_risk_supported and guarded == original
    elif expected == "abstain":
        ok = (
            "couldn't verify" in guarded
            and guarded != original
            and not report.high_risk_supported
        )
    elif expected == "sanitize_citation":
        ok = (
            guarded != original
            and not report.citation_integrity
            and all(f"[{c}]" not in guarded for c in report.unknown_citations)
            and any(f"[{source}]" in guarded for source in report.evidence_sources)
        )
    elif expected == "passthrough":
        ok = guarded == original and not report.has_search_evidence
    else:
        raise ValueError(f"Unknown grounding expectation: {expected}")

    return ok, {
        "id": case["id"],
        "passed": ok,
        "expected": expected,
        "guarded_answer": guarded,
        "report": {
            "has_search_evidence": report.has_search_evidence,
            "evidence_sources": list(report.evidence_sources),
            "valid_citations": list(report.valid_citations),
            "unknown_citations": list(report.unknown_citations),
            "unsupported_numbers": list(report.unsupported_numbers),
            "unsupported_urls": list(report.unsupported_urls),
            "unsupported_emails": list(report.unsupported_emails),
        },
    }


def _grounding_eval(cases: list[dict[str, Any]]) -> tuple[float, list[dict[str, Any]]]:
    details = []
    passed = 0
    for case in cases:
        ok, detail = _grounding_case(case)
        passed += int(ok)
        details.append(detail)
    return (passed / len(cases) if cases else 1.0), details


def _profile_integrity(profile: dict[str, Any], manifest: dict[str, Any]) -> tuple[float, dict[str, Any]]:
    checks = {
        "identity": bool((profile.get("identity") or {}).get("name")),
        "projects": len(profile.get("projects", [])) == int(manifest.get("projects", -1)),
        "skill_categories": len(profile.get("skill_categories", []))
        == int(manifest.get("skill_categories", -1)),
        "certifications": len(profile.get("certifications", []))
        == int(manifest.get("certifications", -1)),
        "work_experiences": len(profile.get("work_experiences", []))
        == int(manifest.get("work_experiences", -1)),
        "education_entries": len(profile.get("education", []))
        == int(manifest.get("education_entries", -1)),
    }
    passed = sum(int(v) for v in checks.values())
    return passed / len(checks), {"checks": checks, "manifest": manifest}


def run(dataset_path: Path, profile_path: Path, manifest_path: Path) -> dict[str, Any]:
    dataset = _load_json(dataset_path)
    profile = _load_json(profile_path)
    manifest = _load_json(manifest_path)
    thresholds = dataset.get("thresholds") or {}

    route_accuracy, route_details = _route_eval(dataset.get("cases") or [])
    retriever = StructuredProfileRetriever(profile)
    retrieval_metrics, retrieval_details = _retrieval_eval(
        dataset.get("cases") or [], retriever
    )
    grounding_rate, grounding_details = _grounding_eval(
        dataset.get("grounding_cases") or []
    )
    integrity_rate, integrity_details = _profile_integrity(profile, manifest)

    values = {
        "routing_accuracy": route_accuracy,
        **retrieval_metrics,
        "grounding_safety_rate": grounding_rate,
        "profile_integrity_rate": integrity_rate,
    }
    metrics = [
        Metric(name=name, value=float(value), threshold=float(thresholds.get(name, 0.0)))
        for name, value in values.items()
    ]
    report = {
        "benchmark_version": dataset.get("version"),
        "benchmark_status": dataset.get("status"),
        "scope": "deterministic regression; no LLM judge and no online model call",
        "structured_documents": retriever.count,
        "metrics": {
            metric.name: {
                "value": round(metric.value, 6),
                "threshold": metric.threshold,
                "passed": metric.passed,
            }
            for metric in metrics
        },
        "passed": all(metric.passed for metric in metrics),
        "details": {
            "routing": route_details,
            "retrieval": retrieval_details,
            "grounding": grounding_details,
            "profile_integrity": integrity_details,
        },
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="evaluation/dataset.json")
    parser.add_argument("--profile", default="backend/data/profile.json")
    parser.add_argument("--manifest", default="backend/data/site/manifest.json")
    parser.add_argument("--output", help="Optional path for the JSON report")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero if a threshold fails")
    args = parser.parse_args()

    report = run(Path(args.dataset), Path(args.profile), Path(args.manifest))
    text = json.dumps(report, indent=2, ensure_ascii=False)
    print(text)
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text + "\n", encoding="utf-8")
    return 1 if args.strict and not report["passed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
