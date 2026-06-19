"""
document_generator/summarizer.py
────────────────────────────────────────────────────────────────
Documentation Compression Layer.

Produces trimmed ArchitectureBlueprint and LLDModel that prioritise
architecturally significant artifacts over raw completeness.

HLD target: 5–6 pages
LLD target: 10–15 pages

Tuning constants (adjust to taste):
  HLD_TOP_SERVICES      – max services to retain in full detail
  HLD_TOP_WORKFLOWS     – max workflows to retain
  HLD_TOP_INTEGRATIONS  – max integrations to retain
  LLD_TOP_CLASSES       – max classes rendered with full detail
  LLD_TOP_SEQUENCES     – max sequence flows to retain
"""

from __future__ import annotations

import copy
from dataclasses import replace
from typing import List, Set, Tuple

from backend.architecture_extractor.models import (
    ArchitectureBlueprint,
    ArchitectureService,
    ArchitectureWorkflow,
    ArchitectureIntegration,
    ArchitectureDataFlow,
)
from backend.object_model_extractor.models import (
    LLDModel,
    LLDClass,
    LLDSequenceFlow,
)

# ── Tuning constants ───────────────────────────────────────────
HLD_TOP_CAPABILITIES: int = 5
HLD_TOP_SERVICES: int = 4
HLD_TOP_ARTIFACTS: int = 6
HLD_TOP_WORKFLOWS: int = 1
HLD_TOP_INTEGRATIONS: int = 6
LLD_TOP_CLASSES: int = 30
LLD_TOP_SEQUENCES: int = 5


def _service_score(srv: ArchitectureService) -> float:
    """Score service to retain top architectural components."""
    centrality = len(srv.dependencies) + len(srv.consumers)
    
    important_names = {
        "Repository Intelligence Service",
        "Knowledge Graph Service",
        "Context Builder Service",
        "LLM Orchestrator Service",
        "Document Generator Service"
    }
    architectural_importance = 10 if srv.name in important_names else 0
    external_boundary_weight = 5 if any(x in srv.name.lower() for x in ['gateway', 'proxy', 'api']) else 0
    
    return centrality * 0.5 + architectural_importance * 0.3 + external_boundary_weight * 0.2


def _class_score(cls: LLDClass) -> int:
    """Structural richness: more relationships & methods = more important."""
    return (
        len(cls.dependencies)
        + len(cls.composition)
        + len(cls.aggregation)
        + len(cls.methods)
        + len(cls.inherits_from) * 2   # inheritance is architecturally significant
        + len(cls.implements) * 2
    )


class DocumentationSummarizer:
    """
    Compresses ArchitectureBlueprint and LLDModel to documentation-ready sizes.

    Produces new model objects — source models are never mutated.
    Raw JSON exports in pipeline.py should use the original models.
    """

    # ──────────────────────────────────────────────────────────
    #  HLD Compression
    # ──────────────────────────────────────────────────────────

    def summarize_hld(
        self,
        blueprint: ArchitectureBlueprint,
        top_capabilities: int = 5,
        top_services: int = 4,
        top_workflows: int = 1,
        top_integrations: int = 10,
        top_artifacts: int = 6,
    ) -> ArchitectureBlueprint:
        """
        Return a trimmed ArchitectureBlueprint focused on the most
        architecturally central services, workflows, and integrations.
        """
        # ── 1. Rank and select top services ───────────────────
        ranked_services = sorted(
            blueprint.services, key=_service_score, reverse=True
        )
        selected_services = []
        for srv in ranked_services[:top_services]:
            srv_copy = copy.copy(srv)
            if len(srv_copy.dependencies) > 5:
                srv_copy.dependencies = srv_copy.dependencies[:5] + ["Additional relationships omitted for clarity."]
            if len(srv_copy.consumers) > 5:
                srv_copy.consumers = srv_copy.consumers[:5] + ["Additional relationships omitted for clarity."]
            selected_services.append(srv_copy)
            
        selected_names: Set[str] = {s.name for s in selected_services}

        # ── 2. Filter workflows by participant overlap ─────────
        ranked_workflows = sorted(
            blueprint.workflows,
            key=lambda w: (
                # Business workflows first, then technical
                0 if getattr(w, "workflow_type", "") == "business" else 1,
                # More participants = more architectural breadth
                -len(w.participants),
            ),
        )
        filtered_workflows: List[ArchitectureWorkflow] = []
        for wf in ranked_workflows:
            if len(filtered_workflows) >= top_workflows:
                break
            # Include if it has participants overlapping selected services,
            # or if it has steps (even with no named participants)
            participants_set = set(wf.participants)
            if participants_set & selected_names or wf.steps:
                filtered_workflows.append(wf)

        # ── 3. Retain discovered external boundaries ───────────
        filtered_integrations = []
        for intg in blueprint.integrations:
            if getattr(intg, "integration_type", "") in ["Module Import", "Function Call"]:
                continue
            if getattr(intg, "purpose", "") in ["Module Import", "Function Call"]:
                continue
            filtered_integrations.append(intg)
            
        filtered_integrations = filtered_integrations[:top_integrations]

        # ── 4. Annotate metadata so generators can surface it ──
        meta = dict(blueprint.metadata)
        meta["summarizer"] = {
            "total_services": len(blueprint.services),
            "shown_services": len(selected_services),
            "total_workflows": len(blueprint.workflows),
            "shown_workflows": len(filtered_workflows),
            "total_integrations": len(blueprint.integrations),
            "shown_integrations": len(filtered_integrations),
        }

        # ── 5. Build and return trimmed blueprint ──────────────
        
        caps = getattr(blueprint, "capabilities", [])[:top_capabilities]
        arts = getattr(blueprint, "artifacts", [])[:top_artifacts]
        
        trimmed_bp = ArchitectureBlueprint(
            repository_type=blueprint.repository_type,
            architecture_pattern=blueprint.architecture_pattern,
            services=selected_services,
            components=blueprint.components,        # kept as-is (compact)
            capabilities=caps,
            artifacts=arts,
            workflows=filtered_workflows,
            data_flows=blueprint.data_flows,        # typically small
            apis=blueprint.apis,                    # kept as-is
            databases=blueprint.databases,          # kept as-is
            integrations=filtered_integrations,
            deployment_nodes=blueprint.deployment_nodes,
            security_boundaries=blueprint.security_boundaries,
            metadata=meta,
        )
        
        return trimmed_bp


    # ──────────────────────────────────────────────────────────
    #  LLD Compression
    # ──────────────────────────────────────────────────────────

    def summarize_lld(
        self,
        model: LLDModel,
        top_classes: int = LLD_TOP_CLASSES,
        top_sequences: int = LLD_TOP_SEQUENCES,
    ) -> LLDModel:
        """
        Return a trimmed LLDModel focused on architecturally significant
        classes and sequence flows.

        Utility/helper classes (score == 0) are grouped and surfaced
        via metadata so the generator can render a compact summary table.
        """
        # ── 1. Rank classes ────────────────────────────────────
        ranked_classes = sorted(
            model.classes, key=_class_score, reverse=True
        )

        core_classes = ranked_classes[:top_classes]
        utility_classes = ranked_classes[top_classes:]

        core_names: Set[str] = {c.name for c in core_classes}

        # ── 2. Filter sequence flows to those referencing core classes ──
        # A step that contains any core class name is considered relevant.
        def _flow_is_relevant(flow: LLDSequenceFlow) -> bool:
            text = " ".join(flow.steps + [flow.name, flow.trigger or ""]).lower()
            return (
                any(name.lower() in text for name in core_names)
                or not core_names
                or "sql" in text
                or "lineage" in text
                or "database" in text
                or "external" in text
            )

        ranked_flows = model.sequence_flows  # already ordered by extraction
        filtered_flows = [f for f in ranked_flows if _flow_is_relevant(f)]
        filtered_flows = filtered_flows[:top_sequences]

        # ── 3. Build metadata for generators ──────────────────
        meta = dict(model.metadata)
        meta["summarizer"] = {
            "total_classes": len(model.classes),
            "shown_classes": len(core_classes),
            "utility_classes": [c.name for c in utility_classes],
            "total_sequences": len(model.sequence_flows),
            "shown_sequences": len(filtered_flows),
        }

        # ── 4. Return trimmed model ────────────────────────────
        return LLDModel(
            repository_type=model.repository_type,
            classes=core_classes,
            interfaces=model.interfaces,    # always fully included
            design_patterns=model.design_patterns,
            algorithms=model.algorithms,
            database_objects=model.database_objects,
            sequence_flows=filtered_flows,
            error_paths=model.error_paths,
            # NEW fields — pass through without compression
            api_specs=getattr(model, 'api_specs', []),
            modules=getattr(model, 'modules', []),
            components=getattr(model, 'components', []),
            dependencies=getattr(model, 'dependencies', []),
            external_integrations=getattr(model, 'external_integrations', []),
            deployment_units=getattr(model, 'deployment_units', []),
            security=getattr(model, 'security', None),
            configuration=getattr(model, 'configuration', None),
            system_overview=getattr(model, 'system_overview', ''),
            data_type_tables=getattr(model, 'data_type_tables', []),
            data_types=getattr(model, 'data_types', []),
            enum_types=getattr(model, 'enum_types', []),
            type_aliases=getattr(model, 'type_aliases', []),
            metadata=meta,
        )
