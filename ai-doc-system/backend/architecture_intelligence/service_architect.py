"""
architecture_intelligence/service_architect.py
────────────────────────────────────────────────────────────────
Organize capabilities into architectural services.

Transforms CapabilityModel into ServiceModel — mapping each
business capability to an architectural service with correct
names, layers, types, and interaction descriptions.
"""

from __future__ import annotations

import json
from typing import Dict, List, Optional

from backend.architecture_intelligence.models import (
    ArchitecturalService,
    CapabilityModel,
    DomainModel,
    ServiceModel,
    BusinessCapability,
    ServiceDependency,
)
from backend.architecture_extractor.models import ArchitectureBlueprint


# Layer mapping based on service type
_TYPE_TO_LAYER = {
    "Domain":        "Domain",
    "Application":   "Application",
    "Infrastructure":"Infrastructure",
    "Integration":   "Infrastructure",
    # AIM tier values
    "Core":          "Domain",
    "Supporting":    "Application",
    "Generic":       "Infrastructure",
}

VALID_LAYERS = {"Domain", "Application", "Infrastructure", "Presentation"}

# Domains where pipeline architecture is a valid default
_PIPELINE_DOMAINS = {
    "Data Platform", "AI & ML Platform", "Developer Platform",
    "Architecture Documentation Platform",
}


class ServiceArchitect:
    """Organize capabilities into architectural services."""

    def __init__(self, llm_client=None):
        self.llm = llm_client

    def architect(
        self,
        capabilities: CapabilityModel,
        blueprint: ArchitectureBlueprint,
        domain: DomainModel,
    ) -> ServiceModel:
        """Build ServiceModel from CapabilityModel."""
        services: List[ArchitecturalService] = []

        # Core capabilities → Domain services
        for cap in capabilities.core_capabilities:
            services.append(self._cap_to_service(cap, "Domain", blueprint, domain))

        # Supporting capabilities → Application services
        for cap in capabilities.supporting_capabilities:
            services.append(self._cap_to_service(cap, "Application", blueprint, domain))

        # Generic capabilities → Infrastructure services
        for cap in capabilities.generic_capabilities:
            services.append(self._cap_to_service(cap, "Infrastructure", blueprint, domain))

        # Derive dependencies from blueprint integrations
        self._derive_dependencies(services, blueprint)

        # Determine architecture style and rationale
        architecture_style, architecture_rationale = self._infer_architecture_style(services, blueprint, domain)

        # Generate interaction summary
        interaction_summary = self._generate_interaction_summary(
            services, architecture_style, domain
        )

        return ServiceModel(
            services=services,
            interaction_summary=interaction_summary,
            architecture_style=architecture_style,
            architecture_rationale=architecture_rationale,
        )

    def _cap_to_service(
        self,
        cap: BusinessCapability,
        service_type: str,
        blueprint: ArchitectureBlueprint,
        domain: DomainModel,
    ) -> ArchitecturalService:
        """Convert a BusinessCapability to an ArchitecturalService."""
        # Derive service name
        name = cap.name
        if not name.endswith("Service"):
            name = f"{name} Service"

        # Layer ALWAYS comes from service_type mapping — never from capability name
        layer = _TYPE_TO_LAYER.get(service_type, "Application")
        if layer not in VALID_LAYERS:
            layer = "Application"

        # Derive technology notes from blueprint services
        tech_notes = self._find_technology_notes(cap, blueprint)

        return ArchitecturalService(
            name=name,
            service_type=service_type,
            responsibility=cap.description,
            capabilities_served=[cap.name],
            dependencies=[],
            consumers=[],
            layer=layer,
            technology_notes=tech_notes,
            is_external=False,
        )

    def _find_technology_notes(
        self, cap: BusinessCapability, blueprint: ArchitectureBlueprint
    ) -> str:
        """Find technology context for a capability from the blueprint."""
        components = cap.supporting_components or []
        techs = set()

        for srv in blueprint.services:
            srv_lower = srv.name.lower()
            for comp in components:
                if comp.lower() in srv_lower or srv_lower in comp.lower():
                    # Pull technology info from metadata if available
                    for cat in ['languages', 'frameworks', 'databases', 'messaging_systems']:
                        for tech in blueprint.metadata.get(cat, []):
                            techs.add(tech)

        if not techs:
            return ""

        return ", ".join(list(techs)[:3])

    def _derive_dependencies(
        self,
        services: List[ArchitecturalService],
        blueprint: ArchitectureBlueprint,
    ) -> None:
        """Derive service dependencies from blueprint integrations."""
        service_names = {s.name.lower(): s for s in services}

        for integ in blueprint.integrations:
            source_lower = integ.source.lower()
            target_lower = integ.target.lower()

            source_svc = None
            target_svc = None

            for sname, sobj in service_names.items():
                if any(comp.lower() in source_lower for comp in (sobj.capabilities_served or [sname])):
                    source_svc = sobj
                if any(comp.lower() in target_lower for comp in (sobj.capabilities_served or [sname])):
                    target_svc = sobj

            if source_svc and target_svc and source_svc != target_svc:
                if not any(d.dependency == target_svc.name for d in source_svc.dependencies):
                    source_svc.dependencies.append(ServiceDependency(
                        dependency=target_svc.name,
                        source="blueprint_integration_extraction",
                        confidence=0.95
                    ))
                if source_svc.name not in target_svc.consumers:
                    target_svc.consumers.append(source_svc.name)
                    
        # Heuristic fallback: if no dependencies were mapped, and we have multiple core services, chain them.
        has_deps = any(len(s.dependencies) > 0 for s in services)
        if not has_deps:
            core_services = [s for s in services if s.service_type == "Domain"]
            if len(core_services) > 1:
                # If we suspect a pipeline, chain them
                for i in range(len(core_services) - 1):
                    src = core_services[i]
                    tgt = core_services[i+1]
                    if not any(d.dependency == tgt.name for d in src.dependencies):
                        src.dependencies.append(ServiceDependency(
                            dependency=tgt.name,
                            source="heuristic_pipeline_inference",
                            confidence=0.72
                        ))
                    if src.name not in tgt.consumers:
                        tgt.consumers.append(src.name)

    def _infer_architecture_style(
        self,
        services: List[ArchitecturalService],
        blueprint: ArchitectureBlueprint,
        domain: DomainModel,
    ) -> tuple[str, str]:
        """Infer architecture style deterministically and provide a rationale."""
        svc_count = len(services)
        total_deps = sum(len(s.dependencies) for s in services)

        # 1. Check explicit pattern from blueprint (strongest evidence)
        if blueprint.architecture_pattern:
            pattern = blueprint.architecture_pattern.lower()
            if "microservice" in pattern:
                return "Microservices Architecture", "Services are independently deployable components with defined API contracts."
            if "event" in pattern:
                return "Event-Driven Architecture", "Services communicate asynchronously via events and message queues."
            if "pipeline" in pattern or "etl" in pattern:
                return "Pipeline Architecture", "Data transforms sequentially through processing stages."
            if "monolith" in pattern:
                return "Modular Monolith", "Functionality organized into modules within a single deployment unit."

        # 2. Check messaging systems — strong indicator of event-driven
        has_events = any(
            integ.integration_type.lower() in ("event publish", "event subscribe", "pub/sub", "message queue")
            for integ in blueprint.integrations
        )
        if has_events and svc_count >= 3:
            return "Event-Driven Architecture", "Messaging infrastructure detected — services communicate asynchronously."

        # 3. Simple two-tier systems
        if svc_count <= 2:
            return "Layered Architecture", "Simple two-tier separation of concerns."

        # 4. High service count with distributed dependencies
        if svc_count >= 6 and total_deps >= 6:
            return "Microservices Architecture", "High service count with distributed dependencies suggests independently deployable services."

        # 5. Domain-based pipeline check — only for domains where pipeline is natural
        if domain.primary_domain in _PIPELINE_DOMAINS:
            # Verify linear chain structure
            chain_services = sum(
                1 for s in services
                if len(s.dependencies) <= 1 and len(s.consumers) <= 1
            )
            if chain_services >= svc_count * 0.7:
                return "Pipeline Architecture", "Data transformation domain with sequential processing stages."

        # 6. Default: Modular Monolith for 3-5 services, SOA for 6+
        if svc_count <= 5:
            return "Modular Monolith", "Multiple cohesive modules deployed as a single unit with clear capability boundaries."

        return "Service-Oriented Architecture", "Multiple services with defined responsibilities and interfaces."

    def _generate_interaction_summary(
        self,
        services: List[ArchitecturalService],
        architecture_style: str,
        domain: DomainModel,
    ) -> str:
        """Generate service interaction summary."""
        if self.llm:
            try:
                return self._llm_interaction_summary(services, architecture_style, domain)
            except Exception:
                pass

        return self._template_interaction_summary(services, architecture_style, domain)

    def _llm_interaction_summary(
        self,
        services: List[ArchitecturalService],
        architecture_style: str,
        domain: DomainModel,
    ) -> str:
        """LLM-generated interaction summary."""
        system_prompt = (
            "You are a Solution Architect. Write a concise service interaction description.\n"
            "One paragraph. No bullet points. Technical but accessible.\n"
            "Respond with plain text only."
        )

        svc_data = [
            {"name": s.name, "type": s.service_type, "responsibility": s.responsibility}
            for s in services
        ]

        user_prompt = (
            f"Describe how these services interact in a {domain.primary_domain} system.\n\n"
            f"SERVICES:\n{json.dumps(svc_data, indent=2)}\n\n"
            f"DETECTED ARCHITECTURE STYLE: {architecture_style}\n\n"
            "Write a single paragraph (3-5 sentences) describing:\n"
            "1. The overall interaction pattern\n"
            "2. How data flows between services\n"
            "3. Any integration or orchestration mechanisms"
        )

        text = self.llm.generate(system_prompt, user_prompt, max_tokens=512, temperature=0.2)
        text = text.strip()

        # Basic validation
        if len(text) < 50 or len(text) > 1000:
            return self._template_interaction_summary(services, architecture_style, domain)

        return text

    def _template_interaction_summary(
        self,
        services: List[ArchitecturalService],
        architecture_style: str,
        domain: DomainModel,
    ) -> str:
        """Deterministic interaction summary template."""
        svc_names = [s.name for s in services[:4]]
        domain_svc = [s.name for s in services if s.service_type == "Domain"]

        return (
            f"The system follows a {architecture_style} pattern with "
            f"{len(services)} architectural services. "
            f"Domain services ({', '.join(domain_svc[:3]) or 'core services'}) "
            f"handle primary business logic, while supporting and infrastructure services "
            f"provide cross-cutting capabilities. "
            f"Services communicate through internal method invocations and shared data models."
        )
