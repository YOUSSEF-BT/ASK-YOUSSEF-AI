"""Compatibility import for the deterministic precision-facts resolver.

The implementation lives in ``precision_facts.py`` so the structured fact lane
can evolve independently from the general hybrid retrieval stack. Keep a small
backward-compatible aggregate vocabulary here while older callers import this
module name.
"""
import precision_facts as _precision

# Natural aggregate phrasing such as "public contact options" is semantically
# equivalent to "public contacts". Keep these generic nouns neutral so they do
# not turn a complete-set request into a filtered query.
_precision._COMMON.update({"option", "options"})

StructuredFactAnswer = _precision.StructuredFactAnswer
StructuredFactResolver = _precision.StructuredFactResolver

__all__ = ["StructuredFactAnswer", "StructuredFactResolver"]
