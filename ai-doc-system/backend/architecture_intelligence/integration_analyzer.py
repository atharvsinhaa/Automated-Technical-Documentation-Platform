"""
architecture_intelligence/integration_analyzer.py
────────────────────────────────────────────────────────────────
Classify external integrations and APIs.

Transforms blueprint integrations and APIs into an IntegrationModel
with business-meaningful integration descriptions, filtering out
internal function calls and module imports.
"""

from __future__ import annotations

import json
from typing import Dict, List, Optional

from backend.architecture_intelligence.models import (
    DomainModel,
    IntegrationModel,
    IntegrationPoint,
    ServiceModel,
)
from backend.architecture_extractor.models import ArchitectureBlueprint


# Integration types that are NOT external integration points
_INTERNAL_TYPES = {
    "function call", "module import", "dependency",
    "import", "internal", "method call",
}

# Integration type → protocol mapping
_TYPE_TO_PROTOCOL = {
    "rest api": "REST",
    "rest": "REST",
    "graphql": "GraphQL",
    "grpc": "gRPC",
    "database access": "Database",
    "data access": "Database",
    "event publish": "Message Queue",
    "event subscribe": "Message Queue",
    "pub/sub": "Message Queue",
    "message queue": "Message Queue",
    "data feed": "File",
    "file": "File",
    "webhook": "REST",
    "websocket": "WebSocket",
}


class IntegrationAnalyzer:
    """Classify external integrations and APIs."""

    def __init__(self, llm_client=None):
        self.llm = llm_client

    def analyze(
        self,
        blueprint: ArchitectureBlueprint,
        domain: DomainModel,
        services: ServiceModel,
    ) -> IntegrationModel:
        """Build IntegrationModel from blueprint."""
        points = self._build_integration_points(blueprint, domain, services)
        api_summary = self._build_api_surface_summary(blueprint)
        narrative = self._generate_narrative(points, api_summary, domain, services)

        return IntegrationModel(
            integration_points=points[:8],
            api_surface_summary=api_summary,
            integration_narrative=narrative,
        )

    def _build_integration_points(
        self,
        blueprint: ArchitectureBlueprint,
        domain: DomainModel,
        services: ServiceModel,
    ) -> List[IntegrationPoint]:
        """Build IntegrationPoint objects from blueprint integrations."""
        points: List[IntegrationPoint] = []
        seen: set = set()

        # From blueprint.integrations
        for integ in blueprint.integrations:
            integ_type_lower = integ.integration_type.lower()

            # Skip internal calls
            if integ_type_lower in _INTERNAL_TYPES:
                continue

            protocol = _TYPE_TO_PROTOCOL.get(integ_type_lower, "Internal")
            if protocol == "Internal":
                continue

            # Determine direction
            direction = self._infer_direction(integ, services)

            # Determine if external
            is_external = self._is_external_integration(integ, services)

            # Skip pure internal integrations unless they hit a data store
            if not is_external and protocol != "Database":
                continue

            # Deduplicate
            key = f"{integ.source}->{integ.target}"
            if key in seen:
                continue
            seen.add(key)

            # Generate descriptive name
            name = self._integration_name(integ, protocol)

            # Generate purpose
            purpose = integ.purpose or integ.description or ""
            if not purpose or purpose == "Unknown purpose":
                purpose = self._template_purpose(integ, protocol, domain)

            points.append(IntegrationPoint(
                name=name,
                direction=direction,
                protocol=protocol,
                source=integ.source,
                target=integ.target,
                purpose=purpose,
                data_exchanged=integ.artifact or "Data payload",
                is_external=is_external,
            ))

        # From blueprint.apis — create an inbound API surface point
        if blueprint.apis:
            api_methods = set(api.method.upper() for api in blueprint.apis)
            api_count = len(blueprint.apis)

            points.append(IntegrationPoint(
                name="REST API Interface",
                direction="Inbound",
                protocol="REST",
                source="External Clients",
                target=domain.primary_domain,
                purpose=f"Exposes {api_count} API endpoint(s) ({', '.join(api_methods)}) for external consumption.",
                data_exchanged="JSON request/response payloads",
                is_external=True,
            ))

        # Generate LLM purposes for external points
        if self.llm:
            for point in points:
                if point.is_external and (
                    not point.purpose or "Unknown" in point.purpose
                ):
                    try:
                        point.purpose = self._llm_purpose(point, domain)
                    except Exception:
                        pass

        return points

    def _build_api_surface_summary(self, blueprint: ArchitectureBlueprint) -> str:
        """Summarize the API surface."""
        if not blueprint.apis:
            return "No external API surface was detected."

        methods = {}
        for api in blueprint.apis:
            m = api.method.upper()
            methods[m] = methods.get(m, 0) + 1

        parts = [f"{count} {method}" for method, count in sorted(methods.items())]
        return (
            f"The system exposes {len(blueprint.apis)} API endpoint(s): "
            + ", ".join(parts) + "."
        )

    def _generate_narrative(
        self,
        points: List[IntegrationPoint],
        api_summary: str,
        domain: DomainModel,
        services: ServiceModel,
    ) -> str:
        """Generate integration narrative."""
        if self.llm:
            try:
                return self._llm_narrative(points, api_summary, domain, services)
            except Exception:
                pass

        return self._template_narrative(points, api_summary, domain)

    # ── LLM helpers ──────────────────────────────────────────

    def _llm_purpose(self, point: IntegrationPoint, domain: DomainModel) -> str:
        """LLM-generated integration purpose."""
        system_prompt = (
            "You are an Enterprise Architect. In one sentence, describe the business "
            "purpose of this integration. No technical jargon. Respond with plain text only."
        )
        user_prompt = (
            f"In the context of a {domain.primary_domain} system:\n"
            f"Source: {point.source} → Target: {point.target}\n"
            f"Protocol: {point.protocol}\n"
            "What business purpose does this integration serve?"
        )
        text = self.llm.generate(system_prompt, user_prompt, max_tokens=128, temperature=0.2)
        return text.strip()[:200] if text else point.purpose

    def _llm_narrative(
        self,
        points: List[IntegrationPoint],
        api_summary: str,
        domain: DomainModel,
        services: ServiceModel,
    ) -> str:
        """LLM-generated integration narrative."""
        system_prompt = (
            "You are an Enterprise Architect writing the Integration section of an HLD. "
            "One paragraph, 3-4 sentences. Plain text. No headings or bullets."
        )
        point_data = [
            {"name": p.name, "protocol": p.protocol, "direction": p.direction, "purpose": p.purpose}
            for p in points[:6]
        ]
        user_prompt = (
            f"Describe the integration architecture for this {domain.primary_domain} system.\n\n"
            f"API SURFACE: {api_summary}\n"
            f"INTEGRATION POINTS:\n{json.dumps(point_data, indent=2)}\n"
            f"ARCHITECTURE STYLE: {services.architecture_style}\n"
        )
        text = self.llm.generate(system_prompt, user_prompt, max_tokens=512, temperature=0.2)
        text = text.strip()
        if 50 < len(text) < 1000:
            return text
        return self._template_narrative(points, api_summary, domain)

    # ── Deterministic helpers ────────────────────────────────

    @staticmethod
    def _infer_direction(integ, services: ServiceModel) -> str:
        """Infer integration direction."""
        service_names = {s.name.lower() for s in services.services}
        source_internal = any(s in integ.source.lower() for s in service_names)
        target_internal = any(s in integ.target.lower() for s in service_names)

        if source_internal and not target_internal:
            return "Outbound"
        elif target_internal and not source_internal:
            return "Inbound"
        return "Bidirectional"

    @staticmethod
    def _is_external_integration(integ, services: ServiceModel) -> bool:
        """Determine if an integration is external."""
        service_names = {s.name.lower() for s in services.services}
        source_internal = any(s in integ.source.lower() for s in service_names)
        target_internal = any(s in integ.target.lower() for s in service_names)
        return not (source_internal and target_internal)

    @staticmethod
    def _integration_name(integ, protocol: str) -> str:
        """Generate a descriptive integration name."""
        target = integ.target.replace("_", " ").strip()
        target = " ".join(w.capitalize() for w in target.split())
        return f"{target} {protocol} Integration"

    @staticmethod
    def _template_purpose(integ, protocol: str, domain: DomainModel) -> str:
        """Template integration purpose."""
        return f"Provides {protocol.lower()} connectivity between {integ.source} and {integ.target}."

    @staticmethod
    def _template_narrative(
        points: List[IntegrationPoint],
        api_summary: str,
        domain: DomainModel,
    ) -> str:
        """Template integration narrative with domain-specific defaults."""
        if not points:
            DOMAIN_INTEGRATION_DEFAULTS = {
                "E-Commerce": (
                    "The platform exposes standard e-commerce APIs for storefront, cart, "
                    "and checkout operations. External payment processing and inventory "
                    "management integrations are handled through standardized service interfaces."
                ),
                "Financial Services": (
                    "The system provides secure API interfaces for banking operations. "
                    "Integration with payment networks, regulatory reporting systems, "
                    "and external financial services follows standard industry protocols."
                ),
                "Healthcare IT": (
                    "The system integrates with clinical systems and patient data exchanges "
                    "following HL7 FHIR standards. External integrations are subject to "
                    "HIPAA compliance controls."
                ),
                "AI & ML Platform": (
                    "The platform operates as an internal processing pipeline, "
                    "consuming data and producing structured outputs. "
                    "No external consumer-facing APIs were detected."
                ),
                "Architecture Documentation Platform": (
                    "The platform operates as an internal processing pipeline, "
                    "consuming repository data and producing structured documentation artifacts. "
                    "No external consumer-facing APIs were detected."
                ),
                "Developer Platform": (
                    "The platform integrates with source control, CI/CD pipelines, "
                    "and artifact registries through standard developer toolchain protocols."
                ),
                "Enterprise Application": (
                    "The application exposes standard CRUD API interfaces for managing "
                    "business entities. Integration with external systems is handled through "
                    "well-defined service boundaries."
                ),
            }
            return DOMAIN_INTEGRATION_DEFAULTS.get(
                domain.primary_domain,
                f"The {domain.primary_domain} platform manages integrations "
                f"through standard service interfaces appropriate to the domain."
            )

        external = [p for p in points if p.is_external]
        protocols = set(p.protocol for p in points)

        return (
            f"The system integrates with {len(external)} external service(s) "
            f"using {', '.join(protocols)} protocol(s). "
            + api_summary + " "
            f"Internal services communicate through direct invocations and shared data models."
        )
