"""Privacy-safe in-memory operational metrics for Ask Youssef AI.

The portfolio assistant is public, so observability must not become a second data
store. This module deliberately records only aggregate counters and bounded
latency samples: no questions, answers, IP addresses, emails, tool inputs, or
conversation history are retained.

Metrics reset when the process restarts, which is appropriate for the current
single-instance portfolio deployment. A production service can later export the
same counters to OpenTelemetry/Prometheus without changing the chat contract.
"""
from __future__ import annotations

import math
import threading
import time
from collections import Counter, deque
from dataclasses import dataclass
from typing import Any


def _percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    pos = (len(ordered) - 1) * q
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return ordered[lo]
    weight = pos - lo
    return ordered[lo] + (ordered[hi] - ordered[lo]) * weight


@dataclass(frozen=True)
class TurnMetrics:
    language: str
    intent: str
    requires_retrieval: bool


class RuntimeTelemetry:
    """Thread-safe aggregate telemetry with a bounded latency window."""

    def __init__(self, max_latency_samples: int = 500) -> None:
        self._lock = threading.Lock()
        self._started_at = time.time()
        self._max_latency_samples = max(10, int(max_latency_samples))
        self._latencies_ms: deque[float] = deque(maxlen=self._max_latency_samples)
        self._requests = 0
        self._completed = 0
        self._errors = 0
        self._retrieval_required = 0
        self._retrieval_used = 0
        self._grounding_interventions = 0
        self._languages: Counter[str] = Counter()
        self._intents: Counter[str] = Counter()

    def record_request(self, route: Any) -> TurnMetrics:
        language = str(getattr(route, "language", "unknown") or "unknown")
        intent = str(getattr(route, "intent", "unknown") or "unknown")
        requires_retrieval = bool(getattr(route, "requires_retrieval", False))
        with self._lock:
            self._requests += 1
            self._languages[language] += 1
            self._intents[intent] += 1
            self._retrieval_required += int(requires_retrieval)
        return TurnMetrics(language, intent, requires_retrieval)

    def record_completed(
        self,
        *,
        latency_ms: float,
        retrieval_used: bool,
        grounding_intervened: bool,
    ) -> None:
        with self._lock:
            self._completed += 1
            self._retrieval_used += int(bool(retrieval_used))
            self._grounding_interventions += int(bool(grounding_intervened))
            if latency_ms >= 0:
                self._latencies_ms.append(float(latency_ms))

    def record_error(self, *, latency_ms: float | None = None) -> None:
        with self._lock:
            self._errors += 1
            if latency_ms is not None and latency_ms >= 0:
                self._latencies_ms.append(float(latency_ms))

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            latencies = list(self._latencies_ms)
            requests = self._requests
            completed = self._completed
            errors = self._errors
            required = self._retrieval_required
            used = self._retrieval_used
            interventions = self._grounding_interventions
            languages = dict(sorted(self._languages.items()))
            intents = dict(sorted(self._intents.items()))
            started_at = self._started_at

        return {
            "scope": "process_lifetime_aggregate",
            "privacy": "no prompts, answers, IPs, emails, or conversation history retained",
            "uptime_seconds": round(max(0.0, time.time() - started_at), 2),
            "requests": requests,
            "completed": completed,
            "errors": errors,
            "completion_rate": round(completed / requests, 4) if requests else 0.0,
            "retrieval": {
                "required_turns": required,
                "used_turns": used,
                "required_rate": round(required / requests, 4) if requests else 0.0,
                "used_rate": round(used / completed, 4) if completed else 0.0,
            },
            "grounding": {
                "interventions": interventions,
                "intervention_rate": round(interventions / completed, 4) if completed else 0.0,
            },
            "latency_ms": {
                "samples": len(latencies),
                "median": round(_percentile(latencies, 0.50), 2),
                "p95": round(_percentile(latencies, 0.95), 2),
                "max": round(max(latencies), 2) if latencies else 0.0,
            },
            "languages": languages,
            "intents": intents,
        }


TELEMETRY = RuntimeTelemetry()
