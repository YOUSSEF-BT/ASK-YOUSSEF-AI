"""Deployed-system smoke evaluation for Ask Youssef AI.

Unlike `run_benchmark.py`, this script talks to a running FastAPI deployment and
therefore exercises the real model, agent orchestration, retrieval tool, grounding
boundary, SSE transport, conversation history, and final-answer formatting together.

The evaluator intentionally uses deterministic checks only. It verifies behavior
we can observe reliably (completion, required retrieval, expected citations,
safety abstention, and avoiding unnecessary retrieval) and reports latency. It is
not an LLM judge and must not be described as semantic answer accuracy.
"""
from __future__ import annotations

import argparse
import json
import statistics
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


RETRYABLE_STATUS = {429, 500, 502, 503, 504}


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
        headers={"Accept": "application/json", "Origin": origin, "User-Agent": "ask-youssef-online-eval/1.0"},
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
            "User-Agent": "ask-youssef-online-eval/1.0",
        },
    )
    started = time.monotonic()
    events: list[dict[str, Any]] = []
    with urllib.request.urlopen(req, timeout=timeout) as response:
        # The backend emits one JSON object per `data:` SSE line. Ignore all
        # other fields so this remains compatible if event IDs are added later.
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


def evaluate_case(case: dict[str, Any], events: list[dict[str, Any]], latency_ms: float) -> dict[str, Any]:
    final = _final_event(events)
    answer = str((final or {}).get("answer") or "")
    tools = set((final or {}).get("tools_used") or [])
    completed = bool(final and answer.strip())
    requires_search = bool(case.get("requires_search"))
    retrieval_ok = ("search_site" in tools) if requires_search else ("search_site" not in tools)

    expected_sources = list(case.get("expected_sources") or [])
    citation_ok: bool | None = None
    if expected_sources:
        citation_ok = any(f"[{source}]" in answer for source in expected_sources)

    safety_ok: bool | None = None
    if case.get("kind") == "safety":
        lower = answer.lower()
        markers = [str(value).lower() for value in case.get("safety_markers") or []]
        safety_ok = bool(markers) and any(marker in lower for marker in markers)

    return {
        "id": case["id"],
        "kind": case.get("kind"),
        "question": case["question"],
        "history_turns": len(case.get("history") or []),
        "completed": completed,
        "requires_search": requires_search,
        "retrieval_ok": retrieval_ok,
        "expected_sources": expected_sources,
        "citation_ok": citation_ok,
        "safety_ok": safety_ok,
        "latency_ms": round(latency_ms, 2),
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
        "required_retrieval_rate": _rate(
            details, lambda row: bool(row.get("requires_search")), "retrieval_ok"
        ),
        "expected_citation_rate": _rate(
            details, lambda row: row.get("citation_ok") is not None, "citation_ok"
        ),
        "safety_abstention_rate": _rate(
            details, lambda row: row.get("safety_ok") is not None, "safety_ok"
        ),
        "unnecessary_retrieval_avoidance_rate": _rate(
            details, lambda row: not bool(row.get("requires_search")), "retrieval_ok"
        ),
    }
    metrics: dict[str, Any] = {}
    passed = True
    for name, value in values.items():
        threshold = float(thresholds.get(name, 0.0))
        metric_passed = value + 1e-12 >= threshold
        passed = passed and metric_passed
        metrics[name] = {
            "value": round(value, 6),
            "threshold": threshold,
            "passed": metric_passed,
        }

    return {
        "evaluation_version": dataset.get("version"),
        "evaluation_status": dataset.get("status"),
        "scope": "deployed-system deterministic smoke checks; not semantic answer accuracy",
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
            detail = evaluate_case(case, events, latency_ms)
            detail["retry_count"] = retry_count
        except Exception as exc:  # record the failure so the full run is inspectable
            detail = {
                "id": case["id"],
                "kind": case.get("kind"),
                "question": case["question"],
                "history_turns": len(case.get("history") or []),
                "completed": False,
                "requires_search": bool(case.get("requires_search")),
                "retrieval_ok": False,
                "expected_sources": list(case.get("expected_sources") or []),
                "citation_ok": False if case.get("expected_sources") else None,
                "safety_ok": False if case.get("kind") == "safety" else None,
                "latency_ms": 0.0,
                "tools_used": [],
                "answer": "",
                "event_kinds": [],
                "retry_count": retries,
                "error": f"{type(exc).__name__}: {exc}",
            }
        details.append(detail)
        print(
            "  completion={completed} retrieval={retrieval_ok} citation={citation_ok} "
            "safety={safety_ok} latency_ms={latency_ms}".format(**detail),
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
    parser.add_argument(
        "--delay",
        type=float,
        default=11.0,
        help="Seconds between cases; default respects the deployed per-IP minute limit",
    )
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