"""Vercel production language policy hardening.

The core agent already asks Gemini to match the visitor language, but wording such
as "when practical" still allowed occasional English drift on Arabic factual
questions.  This patch runs before backend.app builds the shared agent and makes
the output-language contract explicit without adding a second model call.
"""
from __future__ import annotations

import agent as _agent

_OLD_RULE = (
    "- Match the visitor's language when practical: English, French, or Arabic. "
    "Keep technical names unchanged where appropriate."
)
_NEW_RULE = (
    "- ALWAYS answer in the language of the visitor's CURRENT question: English, French, "
    "or Arabic. This is a hard output contract, not a preference. If the current question "
    "is Arabic, the Final Answer prose must be in Arabic script; technical product names, "
    "model names, code identifiers and citations may remain in Latin script. If the prompt "
    "contains a conversation wrapper and a 'Follow-up:' line, determine the response language "
    "from that current follow-up rather than from the English wrapper or older turns."
)

if _OLD_RULE not in _agent.AGENTIC_RAG_PROMPT:
    raise RuntimeError("Expected agent language rule was not found; review language patch wiring")

_agent.AGENTIC_RAG_PROMPT = _agent.AGENTIC_RAG_PROMPT.replace(_OLD_RULE, _NEW_RULE, 1)
