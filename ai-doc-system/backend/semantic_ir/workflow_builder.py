"""
semantic_ir/workflow_builder.py
────────────────────────────────────────────────────────────────
KG-Grounded Workflow Builder.

Replaces the old version that returned a single hardcoded 7-step
workflow describing THIS platform's pipeline. Now extracts actual
business flows and lineage chains from the Knowledge Graph.

Backward compatibility: build(kg) returns List[IRWorkflow].
"""

from __future__ import annotations

from typing import List, Optional

from backend.semantic_ir.models import (
    IRComponent,
    IRWorkflow,
)


class WorkflowBuilder:

    def build(
        self,
        components: Optional[List[IRComponent]] = None,
        kg=None,
    ) -> List[IRWorkflow]:
        """
        Build workflow list from the Knowledge Graph.

        Args:
            components: List of IR components (used as fallback
                        to synthesize component-level workflow).
            kg: KnowledgeGraph instance. If provided, workflows
                are extracted from business flows and lineage chains.
                If None, synthesizes from component ordering.

        Returns:
            List of IRWorkflow instances.
        """
        if not components:
            components = []

        # ── Strategy 1: Use KG translator if KG is available ──
        if kg is not None:
            from backend.semantic_bridge.kg_to_ir_translator import (
                KGToIRTranslator,
            )
            translator = KGToIRTranslator(verbose=False)
            return translator._extract_workflows(kg)

        # ── Strategy 2: Synthesize from component list ────────
        return self._synthesize_from_components(components)

    def _synthesize_from_components(
        self,
        components: List[IRComponent],
    ) -> List[IRWorkflow]:
        """
        Fallback: create a generic workflow from component names
        ordered by their dependency chain.
        """
        if not components:
            return []

        # Try to build a dependency chain
        comp_map = {c.name: c for c in components}
        steps = []
        remaining = list(components)

        # Find root components (those that nothing depends on)
        depended_on = set()
        for c in components:
            depended_on.update(c.dependencies)

        roots = [c for c in components if c.name not in depended_on]
        if not roots:
            roots = [components[0]]

        visited = set()
        queue = list(roots)

        while queue:
            current = queue.pop(0)
            if current.name in visited:
                continue
            visited.add(current.name)
            steps.append(current.name)

            # Find components this one depends on or that depend on this one
            for c in components:
                if c.name not in visited:
                    if (
                        current.name in c.dependencies
                        or c.name in current.dependencies
                    ):
                        queue.append(c)

        # Add any remaining unvisited
        for c in components:
            if c.name not in visited:
                steps.append(c.name)

        return [
            IRWorkflow(
                name="Main Pipeline",
                steps=steps,
                workflow_type="generic",
                entry_point=steps[0] if steps else None,
                exit_points=[steps[-1]] if steps else [],
                description="System execution flow across components",
                confidence="low",
            )
        ]