"""Privacy-safe feedback aggregation for Ask Youssef AI.

Only fixed-category aggregate counters are retained. No prompts, answers,
conversation history, IP addresses, emails, free-text comments, or identifiers
are stored. The counters are process-local and reset on restart, matching the
current portfolio-scale deployment model.
"""
from __future__ import annotations

import threading
from collections import Counter
from typing import Any

_ALLOWED_RATINGS = {"up", "down"}
_ALLOWED_REASONS = {
    "helpful",
    "not_relevant",
    "incorrect",
    "missing_source",
    "too_long",
    "other",
}


class FeedbackStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._ratings: Counter[str] = Counter()
        self._reasons: Counter[str] = Counter()

    def record(self, rating: str, reason: str | None = None) -> None:
        rating = (rating or "").strip().lower()
        if rating not in _ALLOWED_RATINGS:
            raise ValueError("rating must be 'up' or 'down'")
        reason = (reason or "").strip().lower() or None
        if reason is not None and reason not in _ALLOWED_REASONS:
            raise ValueError("unsupported feedback reason")
        with self._lock:
            self._ratings[rating] += 1
            if reason:
                self._reasons[reason] += 1

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            up = int(self._ratings.get("up", 0))
            down = int(self._ratings.get("down", 0))
            reasons = dict(sorted(self._reasons.items()))
        total = up + down
        return {
            "scope": "process_lifetime_aggregate",
            "privacy": "aggregate fixed-category feedback only; no visitor content retained",
            "total": total,
            "up": up,
            "down": down,
            "helpful_rate": round(up / total, 4) if total else 0.0,
            "reasons": reasons,
        }


FEEDBACK = FeedbackStore()
