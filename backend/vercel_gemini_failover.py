"""Vercel-only fast failover policy for Gemini generation.

The core Gemini policy already switches to GEMINI_FALLBACK_MODEL when a quota
error occurs. On a 60-second serverless request window, transient primary-model
overload or a long provider timeout should trigger the same immediate fallback
instead of spending the remaining request budget retrying the same model.
"""
from __future__ import annotations

import agent as _agent

_original_is_quota = _agent._is_quota


def _should_fail_over(exc: Exception) -> bool:
    if _original_is_quota(exc):
        return True
    msg = str(exc).lower()
    return any(
        marker in msg
        for marker in (
            "503",
            "unavailable",
            "high demand",
            "overloaded",
            "timed out",
            "timeout",
            "deadline",
            "connection reset",
            "temporarily",
        )
    )


_agent._is_quota = _should_fail_over
