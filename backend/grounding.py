"""Deterministic final-answer grounding checks for portfolio responses.

The LLM already receives strict instructions to stay within retrieved evidence.
This module adds a second, model-independent boundary at the output layer. It
tracks which portfolio sources were actually returned by search, validates
source citations, and blocks unsupported high-risk literals such as invented
metrics, dates/numbers, URLs, or email addresses.

It deliberately does not pretend to prove full semantic entailment. That belongs
in the evaluation layer (and can later use a dedicated verifier model). The goal
here is a cheap production guard against the most damaging factual failures.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable

_SOURCE_WITH_SCORE = re.compile(r"\[([^\]\n]+?)\s*·\s*relevance\s+[0-9.]+\]", re.I)
_SIMPLE_SOURCE = re.compile(r"\[([A-Za-z0-9_.:-][A-Za-z0-9_.:/-]{1,120})\]")
_URL = re.compile(r"https?://[^\s)\]>]+", re.I)
_EMAIL = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
_NUMBER = re.compile(r"(?<![\w])\d+(?:[.,]\d+)*(?:\s?%|\s?FPS)?", re.I)


def _norm_literal(value: str) -> str:
    return re.sub(r"\s+", "", value.lower().replace(",", ""))


def _search_observations(steps: Iterable[Any]) -> list[str]:
    outputs: list[str] = []
    for step in steps:
        if getattr(step, "action", None) != "search_site":
            continue
        observation = getattr(step, "observation", None)
        if observation:
            outputs.append(str(observation))
    return outputs


def evidence_sources(steps: Iterable[Any]) -> list[str]:
    """Return source slugs in retrieval order, de-duplicated."""
    found: list[str] = []
    for observation in _search_observations(steps):
        for match in _SOURCE_WITH_SCORE.finditer(observation):
            source = match.group(1).strip()
            if source and source not in found:
                found.append(source)
        # Scripted/offline fallback can expose compact [source] references.
        if not _SOURCE_WITH_SCORE.search(observation):
            for match in _SIMPLE_SOURCE.finditer(observation):
                source = match.group(1).strip()
                if source and source not in found:
                    found.append(source)
    return found


def _answer_citations(answer: str) -> list[str]:
    return [m.group(1).strip() for m in _SIMPLE_SOURCE.finditer(answer or "")]


def _unsupported_literals(answer: str, evidence: str) -> tuple[list[str], list[str], list[str]]:
    # Citations like [project-foo] and [1] are metadata, not factual numbers.
    answer_no_cites = _SIMPLE_SOURCE.sub("", answer or "")
    ev_norm = _norm_literal(evidence)

    unsupported_numbers: list[str] = []
    for value in _NUMBER.findall(answer_no_cites):
        if _norm_literal(value) not in ev_norm and value not in unsupported_numbers:
            unsupported_numbers.append(value)

    unsupported_urls = [u for u in _URL.findall(answer_no_cites) if u not in evidence]
    unsupported_emails = [e for e in _EMAIL.findall(answer_no_cites) if e.lower() not in evidence.lower()]
    return unsupported_numbers, unsupported_urls, unsupported_emails


@dataclass(frozen=True)
class GroundingReport:
    has_search_evidence: bool
    evidence_sources: tuple[str, ...]
    valid_citations: tuple[str, ...]
    unknown_citations: tuple[str, ...]
    unsupported_numbers: tuple[str, ...]
    unsupported_urls: tuple[str, ...]
    unsupported_emails: tuple[str, ...]

    @property
    def high_risk_supported(self) -> bool:
        return not (self.unsupported_numbers or self.unsupported_urls or self.unsupported_emails)


def verify_grounding(answer: str, steps: Iterable[Any]) -> GroundingReport:
    observations = _search_observations(steps)
    sources = evidence_sources(steps)
    citations = _answer_citations(answer)
    source_set = set(sources)
    valid = [c for c in citations if c in source_set]
    unknown = [c for c in citations if c not in source_set]
    numbers, urls, emails = _unsupported_literals(answer, "\n".join(observations))
    return GroundingReport(
        has_search_evidence=bool(observations),
        evidence_sources=tuple(sources),
        valid_citations=tuple(dict.fromkeys(valid)),
        unknown_citations=tuple(dict.fromkeys(unknown)),
        unsupported_numbers=tuple(numbers),
        unsupported_urls=tuple(urls),
        unsupported_emails=tuple(emails),
    )


def enforce_grounding(answer: str, steps: Iterable[Any]) -> tuple[str, GroundingReport]:
    """Return a guarded answer plus its verification report.

    No search evidence means no post-hoc claim of grounding is made; the answer is
    left alone (useful for greetings/clarifying turns/contact confirmations). When
    search was used, unsupported high-risk literals trigger a conservative
    abstention. Otherwise at least one real retrieved-source citation is ensured.
    """
    report = verify_grounding(answer, steps)
    if not report.has_search_evidence:
        return answer, report

    if not report.high_risk_supported:
        sources = ", ".join(f"[{s}]" for s in report.evidence_sources[:3])
        safe = (
            "I couldn't verify that exact detail from the portfolio evidence returned "
            "for this question, so I won't present it as a fact."
        )
        if sources:
            safe += f" Retrieved sources: {sources}."
        return safe, report

    if report.valid_citations or not report.evidence_sources:
        return answer, report

    sources = ", ".join(f"[{s}]" for s in report.evidence_sources[:3])
    return f"{answer.rstrip()}\n\nSources: {sources}", report
