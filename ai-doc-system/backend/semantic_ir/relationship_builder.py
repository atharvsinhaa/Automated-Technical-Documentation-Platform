"""
semantic_ir/relationship_builder.py
────────────────────────────────────────────────────────────────
KG-Grounded Relationship Builder.

Replaces the old version that returned 5 hardcoded relationship
edges describing THIS platform's pipeline. Now extracts actual
inter-component relationships from the Knowledge Graph.

Backward compatibility: build(components, kg) returns
List[IRRelationship].
"""

from __future__ import annotations

from typing import List, Optional

from backend.semantic_ir.models import (
    IRComponent,
    IRRelationship,
)


class RelationshipBuilder:

    def build(
        self,
        components: Optional[List[IRComponent]] = None,
        kg=None,
    ) -> List[IRRelationship]:
        """
        Build relationship list from the Knowledge Graph.

        Args:
            components: List of IR components (needed to map
                        node-level edges to component-level).
            kg: KnowledgeGraph instance. If provided, relationships
                are extracted from graph edges. If None, synthesizes
                from component dependency lists.

        Returns:
            List of IRRelationship instances.
        """
        if not components:
            components = []

        # ── Strategy 1: Use KG translator if KG is available ──
        if kg is not None:
            from backend.semantic_bridge.kg_to_ir_translator import (
                KGToIRTranslator,
            )
            translator = KGToIRTranslator(verbose=False)
            return translator._extract_relationships(kg, components)

        # ── Strategy 2: Synthesize from component dependencies ─
        return self._synthesize_from_dependencies(components)

    def _synthesize_from_dependencies(
        self,
        components: List[IRComponent],
    ) -> List[IRRelationship]:
        """
        Fallback: create relationships from component.dependencies
        fields (which may have been populated by directory-based
        import analysis).
        """
        relationships = []
        comp_names = {c.name for c in components}

        for comp in components:
            for dep in comp.dependencies:
                if dep in comp_names:
                    relationships.append(IRRelationship(
                        source=comp.name,
                        target=dep,
                        relationship_type="DEPENDS_ON",
                        confidence="low",
                    ))

        return relationships