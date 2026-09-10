"""Compatibility layer for deterministic portfolio precision facts.

The implementation lives in ``precision_facts.py`` so the precision lane can
evolve independently from hybrid retrieval. This module keeps backward-compatible
aggregate vocabulary and normalizes structured project citations to the same
canonical source IDs used by the synchronized page corpus and public widget.
"""
from dataclasses import replace

import precision_facts as _precision

# Natural aggregate phrasing such as "public contact options" is semantically
# equivalent to "public contacts". Keep these generic nouns neutral so they do
# not turn a complete-set request into a filtered query.
_precision._COMMON.update({"option", "options"})

StructuredFactAnswer = _precision.StructuredFactAnswer


class StructuredFactResolver(_precision.StructuredFactResolver):
    """Precision resolver with canonical public source IDs.

    Structured project records store bare slugs (``openlegama-...``), while the
    page corpus and widget expose them as ``project-openlegama-...``. Normalizing
    here keeps exact structured answers, source cards, and RAG citations on one
    contract instead of maintaining two public citation namespaces.
    """

    def resolve(self, question, history=None):
        result = super().resolve(question, history)
        if result is None:
            return None

        answer = result.answer
        source = result.source
        for row in self.projects:
            slug = str(row.get("slug") or "").strip()
            if not slug:
                continue
            canonical = f"project-{slug}"
            answer = answer.replace(f"[{slug}]", f"[{canonical}]")
            if source == slug:
                source = canonical

        if answer == result.answer and source == result.source:
            return result
        return replace(result, answer=answer, source=source)


__all__ = ["StructuredFactAnswer", "StructuredFactResolver"]
