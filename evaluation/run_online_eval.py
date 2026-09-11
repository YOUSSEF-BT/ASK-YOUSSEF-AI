"""Deployed-system deterministic evaluation for Ask Youssef AI.

This script talks to a running FastAPI deployment and therefore exercises the
real model, orchestration, retrieval, grounding, SSE transport, history and final
formatting together. It deliberately avoids LLM-as-a-judge scoring: every gate is
an observable deterministic contract.
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


RETRYABLE_STATUS = {429, 500, 502, 503, 504}
RETRIEVAL_TOOLS = {"search_site", "structured_profile"}
_SIMPLE_CITATION = re.compile(r"\[([A-Za-z0-9_.:-][A-Za-z0-9_.:/-]{1,120})\]")
_BRACKETED = re.compile(r"\[([^\]\n]{1,180})\]")
_SOURCEISH = (
    "project-", "skills", "certifications", "experience-education",
    "public-links", "career-status", "structured-profile", "relevance",
)


def _json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    pos = (len(ordered) - 1) * percentile
    lower = int(pos)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = pos - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def _request_json(url: str, *, origin: str, timeout: float) -> dict[str, Any]:
    req = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "Origin": origin, "User-Agent": "ask-youssef-online-eval/2.0"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _chat_once(
    api_url: str,
    question: str,
    *,
    history: list[dict[str, str]] | None,
    origin: str,
    timeout: float,
) -> tuple[list[dict[str, Any]], float]:
    payload = json.dumps({"question": question, "history": history or []}).encode("utf-8")
    req = urllib.request.Request(
        api_url.rstrip("/") + "/chat",
        data=payload,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
            "Origin": origin,
            "User-Agent": "ask-youssef-online-eval/2.0",
        },
    )
    started = time.monotonic()
    events: list[dict[str, Any]] = []
    with urllib.request.urlopen(req, timeout=timeout) as response:
        for raw in response:
            line = raw.decode("utf-8", errors="replace").strip()
            if not line.startswith("data:"):
                continue
            value = line[5:].strip()
            if not value:
                continue
            try:
                event = json.loads(value)
            except json.JSONDecodeError:
                continue
            if isinstance(event, dict):
                events.append(event)
    return events, (time.monotonic() - started) * 1000.0


def chat(
    api_url: str,
    question: str,
    *,
    history: list[dict[str, str]] | None = None,
    origin: str,
    timeout: float,
    retries: int,
) -> tuple[list[dict[str, Any]], float, int]:
    last_exc: Exception | None = None
    for attempt in range(retries + 1):
        try:
            events, latency_ms = _chat_once(
                api_url,
                question,
                history=history,
                origin=origin,
                timeout=timeout,
            )
            return events, latency_ms, attempt
        except urllib.error.HTTPError as exc:
            last_exc = exc
            if exc.code not in RETRYABLE_STATUS or attempt >= retries:
                raise
            retry_after = exc.headers.get("Retry-After")
            try:
                wait = max(2.0, float(retry_after)) if retry_after else min(12.0 * (attempt + 1), 30.0)
            except ValueError:
                wait = min(12.0 * (attempt + 1), 30.0)
            time.sleep(wait)
        except (urllib.error.URLError, TimeoutError) as exc:
            last_exc = exc
            if attempt >= retries:
                raise
            time.sleep(min(5.0 * (attempt + 1), 15.0))
    if last_exc:
        raise last_exc
    raise RuntimeError("Online evaluation request failed without an exception")


def _final_event(events: list[dict[str, Any]]) -> dict[str, Any] | None:
    for event in reversed(events):
        if event.get("kind") == "final":
            return event
    return None


def _error_messages(events: list[dict[str, Any]]) -> list[str]:
    return [str(event.get("message") or "") for event in events if event.get("kind") == "error"]


def _citation_integrity(answer: str, known_sources: set[str]) -> tuple[bool, list[str], list[str]]:
    unknown: list[str] = []
    malformed: list[str] = []
    for match in _BRACKETED.finditer(answer or ""):
        whole = match.group(0)
        content = match.group(1).strip()
        simple = _SIMPLE_CITATION.fullmatch(whole)
        if simple:
            slug = simple.group(1)
            if known_sources and slug not in known_sources:
                unknown.append(slug)
            continue
        low = content.lower()
        # Markdown link labels and ordinary prose brackets are not citations.
        # Only source-looking malformed bracket groups are an integrity problem.
        if "·" in content or any(token in low for token in _SOURCEISH):
            malformed.append(content)
    return not unknown and not malformed, list(dict.fromkeys(unknown)), list(dict.fromkeys(malformed))


def evaluate_case(
    case: dict[str, Any],
    events: list[dict[str, Any]],
    latency_ms: float,
    *,
    known_sources: set[str],
) -> dict[str, Any]:
    final = _final_event(events)
    answer = str((final or {}).get("answer") or "")
    tools = set((final or {}).get("tools_used") or [])
    errors = _error_messages(events)
    completed = bool(final and answer.strip() and not errors)
    requires_search = bool(case.get("requires_search"))
    used_retrieval = bool(tools & RETRIEVAL_TOOLS)
    retrieval_ok = used_retrieval if requires_search else not used_retrieval

    expected_sources = list(case.get("expected_sources") or [])
    citation_ok: bool | None = None
    if expected_sources:
        citation_ok = any(f"[{source}]" in answer for source in expected_sources)

    required_sources = list(case.get("required_sources") or [])
    required_sources_ok: bool | None = None
    if required_sources:
        required_sources_ok = all(f"[{source}]" in answer for source in required_sources)

    expected_answer_contains = [str(value) for value in case.get("expected_answer_contains") or []]
    answer_contains_ok: bool | None = None
    if expected_answer_contains:
        lower_answer = answer.lower()
        answer_contains_ok = all(value.lower() in lower_answer for value in expected_answer_contains)

    expected_answer_contains_any = [str(value) for value in case.get("expected_answer_contains_any") or []]
    answer_contains_any_ok: bool | None = None
    if expected_answer_contains_any:
        lower_answer = answer.lower()
        answer_contains_any_ok = any(value.lower() in lower_answer for value in expected_answer_contains_any)

    forbidden_answer_contains = [str(value) for value in case.get("forbidden_answer_contains") or []]
    forbidden_answer_ok: bool | None = None
    if forbidden_answer_contains:
        lower_answer = answer.lower()
        forbidden_answer_ok = all(value.lower() not in lower_answer for value in forbidden_answer_contains)

    safety_ok: bool | None = None
    if case.get("kind") == "safety":
        lower = answer.lower()
        markers = [str(value).lower() for value in case.get("safety_markers") or []]
        safety_ok = bool(markers) and any(marker in lower for marker in markers)

    citation_integrity_ok, unknown_citations, malformed_citations = _citation_integrity(answer, known_sources)

    max_latency_ms = case.get("max_latency_ms")
    latency_ok: bool | None = None
    if max_latency_ms is not None:
        latency_ok = latency_ms <= float(max_latency_ms)

    return {
        "id": case["id"],
        "kind": case.get("kind"),
        "question": case["question"],
        "history_turns": len(case.get("history") or []),
        "completed": completed,
        "error_messages": errors,
        "requires_search": requires_search,
        "retrieval_ok": retrieval_ok,
        "expected_sources": expected_sources,
        "citation_ok": citation_ok,
        "required_sources": required_sources,
        "required_sources_ok": required_sources_ok,
        "expected_answer_contains": expected_answer_contains,
        "answer_contains_ok": answer_contains_ok,
        "expected_answer_contains_any": expected_answer_contains_any,
        "answer_contains_any_ok": answer_contains_any_ok,
        "forbidden_answer_contains": forbidden_answer_contains,
        "forbidden_answer_ok": forbidden_answer_ok,
        "safety_ok": safety_ok,
        "citation_integrity_ok": citation_integrity_ok,
        "unknown_citations": unknown_citations,
        "malformed_citations": malformed_citations,
        "latency_ms": round(latency_ms, 2),
        "max_latency_ms": max_latency_ms,
        "latency_ok": latency_ok,
        "tools_used": sorted(tools),
        "answer": answer,
        "event_kinds": [str(event.get("kind")) for event in events],
    }


def _rate(details: list[dict[str, Any]], predicate, field: str) -> float:
    selected = [row for row in details if predicate(row)]
    if not selected:
        return 1.0
    return sum(bool(row[field]) for row in selected) / len(selected)


def summarize(dataset: dict[str, Any], details: list[dict[str, Any]], health: dict[str, Any]) -> dict[str, Any]:
    thresholds = dataset.get("thresholds") or {}
    latencies = [float(row["latency_ms"]) for row in details if row.get("completed")]
    values = {
        "completion_rate": _rate(details, lambda _: True, "completed"),
        "required_retrieval_rate": _rate(details, lambda row: bool(row.get("requires_search")), "retrieval_ok"),
        "expected_citation_rate": _rate(details, lambda row: row.get("citation_ok") is not None, "citation_ok"),
        "required_source_rate": _rate(details, lambda row: row.get("required_sources_ok") is not None, "required_sources_ok"),
        "expected_answer_contains_rate": _rate(details, lambda row: row.get("answer_contains_ok") is not None, "answer_contains_ok"),
        "expected_answer_contains_any_rate": _rate(details, lambda row: row.get("answer_contains_any_ok") is not None, "answer_contains_any_ok"),
        "forbidden_answer_absence_rate": _rate(details, lambda row: row.get("forbidden_answer_ok") is not None, "forbidden_answer_ok"),
        "safety_abstention_rate": _rate(details, lambda row: row.get("safety_ok") is not None, "safety_ok"),
        "citation_integrity_rate": _rate(details, lambda _: True, "citation_integrity_ok"),
        "latency_budget_rate": _rate(details, lambda row: row.get("latency_ok") is not None, "latency_ok"),
        "unnecessary_retrieval_avoidance_rate": _rate(details, lambda row: not bool(row.get("requires_search")), "retrieval_ok"),
    }
    metrics: dict[str, Any] = {}
    passed = True
    for name, value in values.items():
        threshold = float(thresholds.get(name, 0.0))
        metric_passed = value + 1e-12 >= threshold
        passed = passed and metric_passed
        metrics[name] = {"value": round(value, 6), "threshold": threshold, "passed": metric_passed}

    return {
        "evaluation_version": dataset.get("version"),
        "evaluation_status": dataset.get("status"),
        "scope": "deployed-system deterministic QA checks; not semantic answer accuracy",
        "health": health,
        "metrics": metrics,
        "latency": {
            "count": len(latencies),
            "median_ms": round(statistics.median(latencies), 2) if latencies else 0.0,
            "p95_ms": round(_percentile(latencies, 0.95), 2) if latencies else 0.0,
            "max_ms": round(max(latencies), 2) if latencies else 0.0,
        },
        "passed": passed,
        "cases": details,
    }


def run(
    dataset: dict[str, Any],
    api_url: str,
    *,
    origin: str,
    timeout: float,
    retries: int,
    delay: float,
) -> dict[str, Any]:
    health = _request_json(api_url.rstrip("/") + "/health", origin=origin, timeout=timeout)
    if not health.get("ok"):
        raise RuntimeError(f"Deployment is not ready: {health}")
    page_payload = _request_json(api_url.rstrip("/") + "/pages", origin=origin, timeout=timeout)
    known_sources = {
        str(page.get("source")) for page in page_payload.get("pages", [])
        if isinstance(page, dict) and page.get("source")
    }

    details: list[dict[str, Any]] = []
    cases = list(dataset.get("cases") or [])
    for index, case in enumerate(cases):
        if index and delay > 0:
            time.sleep(delay)
        print(f"[{index + 1}/{len(cases)}] {case['id']}: {case['question']}", flush=True)
        try:
            events, latency_ms, retry_count = chat(
                api_url,
                case["question"],
                history=list(case.get("history") or []),
                origin=origin,
                timeout=timeout,
                retries=retries,
            )
            detail = evaluate_case(case, events, latency_ms, known_sources=known_sources)
            detail["retry_count"] = retry_count
        except Exception as exc:
            expected_terms = [str(value) for value in case.get("expected_answer_contains") or []]
            expected_any = [str(value) for value in case.get("expected_answer_contains_any") or []]
            forbidden = [str(value) for value in case.get("forbidden_answer_contains") or []]
            detail = {
                "id": case["id"], "kind": case.get("kind"), "question": case["question"],
                "history_turns": len(case.get("history") or []), "completed": False,
                "error_messages": [f"{type(exc).__name__}: {exc}"],
                "requires_search": bool(case.get("requires_search")), "retrieval_ok": False,
                "expected_sources": list(case.get("expected_sources") or []),
                "citation_ok": False if case.get("expected_sources") else None,
                "required_sources": list(case.get("required_sources") or []),
                "required_sources_ok": False if case.get("required_sources") else None,
                "expected_answer_contains": expected_terms,
                "answer_contains_ok": False if expected_terms else None,
                "expected_answer_contains_any": expected_any,
                "answer_contains_any_ok": False if expected_any else None,
                "forbidden_answer_contains": forbidden,
                "forbidden_answer_ok": False if forbidden else None,
                "safety_ok": False if case.get("kind") == "safety" else None,
                "citation_integrity_ok": False, "unknown_citations": [], "malformed_citations": [],
                "latency_ms": 0.0, "max_latency_ms": case.get("max_latency_ms"),
                "latency_ok": False if case.get("max_latency_ms") is not None else None,
                "tools_used": [], "answer": "", "event_kinds": [], "retry_count": retries,
            }
        details.append(detail)
        print(
            "  completion={completed} retrieval={retrieval_ok} citation={citation_ok} "
            "required_sources={required_sources_ok} contains={answer_contains_ok} any={answer_contains_any_ok} "
            "forbidden={forbidden_answer_ok} safety={safety_ok} integrity={citation_integrity_ok} "
            "latency_ms={latency_ms} errors={error_messages}".format(**detail),
            flush=True,
        )

    return summarize(dataset, details, health)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-url", required=True, help="Base URL of the deployed FastAPI service")
    parser.add_argument("--origin", default="https://youssef-bt.github.io")
    parser.add_argument("--dataset", default="evaluation/online_cases.json")
    parser.add_argument("--output", default="online-eval-report.json")
    parser.add_argument("--timeout", type=float, default=150.0)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--delay", type=float, default=11.0, help="Seconds between cases")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    dataset = _json(Path(args.dataset))
    report = run(
        dataset,
        args.api_url,
        origin=args.origin.rstrip("/"),
        timeout=max(10.0, args.timeout),
        retries=max(0, args.retries),
        delay=max(0.0, args.delay),
    )
    text = json.dumps(report, indent=2, ensure_ascii=False)
    print(text)
    Path(args.output).write_text(text + "\n", encoding="utf-8")
    return 1 if args.strict and not report["passed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
