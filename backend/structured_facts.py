"""Compatibility import for the deterministic precision-facts resolver.

The implementation lives in ``precision_facts.py`` so the structured fact lane
can evolve independently from the general hybrid retrieval stack.
"""
from precision_facts import StructuredFactAnswer, StructuredFactResolver

__all__ = ["StructuredFactAnswer", "StructuredFactResolver"]
