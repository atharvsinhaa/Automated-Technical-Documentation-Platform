"""
architecture_intelligence/__init__.py
────────────────────────────────────────────────────────────────
Architecture Intelligence Engine (AIE).

Transforms raw SemanticIR + ArchitectureBlueprint into an
ArchitectureIntelligenceModel (AIM) with domain-aware,
consulting-grade narratives.

Public API:
    from backend.architecture_intelligence import AIMBuilder
    from backend.architecture_intelligence.models import ArchitectureIntelligenceModel
"""

from backend.architecture_intelligence.aim_builder import AIMBuilder
from backend.architecture_intelligence.models import ArchitectureIntelligenceModel

__all__ = ["AIMBuilder", "ArchitectureIntelligenceModel"]
