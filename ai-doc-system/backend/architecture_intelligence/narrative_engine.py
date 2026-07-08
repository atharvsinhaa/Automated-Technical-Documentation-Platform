"""
architecture_intelligence/narrative_engine.py
────────────────────────────────────────────────────────────────
LLM-powered narrative generation with strict grounding.

Generates all consultant-grade text for the HLD using LLM
with validation and deterministic fallbacks.

Design principles:
    1. Every LLM call receives only structured, pre-computed evidence
    2. Every prompt specifies output format and length limits
    3. Temperature = 0.2 for all narrative calls
    4. Each section is generated in a separate LLM call
    5. Full deterministic template fallback when LLM is unavailable
"""

from __future__ import annotations

import json
from typing import Dict, List, Optional

from backend.architecture_intelligence.models import (
    CapabilityModel,
    DeploymentModel,
    DomainModel,
    InformationModel,
    IntegrationModel,
    NarrativeContext,
    ServiceModel,
)
from backend.architecture_intelligence.prompt_templates import (
    EXECUTIVE_SUMMARY_SYSTEM,
    EXECUTIVE_SUMMARY_USER,
    SYSTEM_ARCHITECTURE_SYSTEM,
    SYSTEM_ARCHITECTURE_USER,
    MODULE_DESCRIPTION_SYSTEM,
    MODULE_DESCRIPTION_USER,
    DEPLOYMENT_NARRATIVE_SYSTEM,
    DEPLOYMENT_NARRATIVE_USER,
    TECHNOLOGY_NARRATIVE_SYSTEM,
    TECHNOLOGY_NARRATIVE_USER,
)
from backend.architecture_intelligence.domain_taxonomy import DOMAIN_TAXONOMY


# ─────────────────────────────────────────────────────────────
# Forbidden terms in LLM-generated narrative
# ─────────────────────────────────────────────────────────────

FORBIDDEN_TERMS = [
    # Implementation artifacts
    ".py", ".js", ".ts", ".java", "import ", "class ", "def ", "function ",
    # Internal model names
    "ArchitectureBlueprint", "SemanticIR", "IRComponent", "ArchitectureService",
    "CapabilityModel", "BusinessCapability", "ParsedFile", "ParsedProject",
    "LanguageSpec", "ParserRegistry", "BatchRunner",
    # Anti-patterns
    "as an AI", "I cannot", "I don't have", "based on the provided",
    "as a language model",
]


class NarrativeEngine:
    """Generate consulting-grade narratives for HLD sections."""

    def __init__(self, llm_client=None):
        self.llm = llm_client

    def generate(
        self,
        domain: DomainModel,
        capabilities: CapabilityModel,
        services: ServiceModel,
        information: InformationModel,
        deployment: DeploymentModel,
        integration: IntegrationModel,
        languages: List[str],
        frameworks: List[str],
        databases: List[str],
        ai_ml_tools: List[str],
    ) -> NarrativeContext:
        """Generate all narrative sections."""
        # Determine document theme from domain taxonomy
        taxonomy = DOMAIN_TAXONOMY.get(domain.primary_domain, {})
        document_theme = taxonomy.get("document_theme", "System")

        executive_summary = self._generate_executive_summary(
            domain, capabilities, services, information, languages, frameworks, databases, ai_ml_tools
        )

        system_architecture = self._generate_system_architecture(
            domain, capabilities, services
        )

        module_descriptions = self._generate_module_descriptions(
            domain, services
        )

        deployment_narrative = self._generate_deployment_narrative(
            deployment, languages
        )

        integration_narrative = self._generate_integration_narrative(
            integration, domain
        )

        technology_narrative = self._generate_technology_narrative(
            domain, services, languages, frameworks, databases, ai_ml_tools
        )

        return NarrativeContext(
            executive_summary=executive_summary,
            system_architecture_narrative=system_architecture,
            module_descriptions=module_descriptions,
            deployment_narrative=deployment_narrative,
            integration_narrative=integration_narrative,
            technology_narrative=technology_narrative,
            document_theme=document_theme,
            target_audience_framing=(
                "This document is intended for technical leads, solution architects, "
                "and business stakeholders."
            ),
        )

    # ─────────────────────────────────────────────────────────
    # EXECUTIVE SUMMARY
    # ─────────────────────────────────────────────────────────

    def _generate_executive_summary(
        self,
        domain: DomainModel,
        capabilities: CapabilityModel,
        services: ServiceModel,
        information: InformationModel,
        languages: List[str],
        frameworks: List[str],
        databases: List[str],
        ai_ml_tools: List[str],
    ) -> str:
        """Generate executive summary."""
        if self.llm:
            try:
                text = self._llm_executive_summary(
                    domain, capabilities, services, information,
                    languages, frameworks, databases, ai_ml_tools
                )
                if self._validate_narrative(text, "executive_summary"):
                    return text
                # Retry once
                text = self._llm_executive_summary(
                    domain, capabilities, services, information,
                    languages, frameworks, databases, ai_ml_tools
                )
                if self._validate_narrative(text, "executive_summary"):
                    return text
            except Exception:
                pass

        return self._template_executive_summary(
            domain, capabilities, services, information, languages, frameworks, databases, ai_ml_tools
        )

    def _llm_executive_summary(
        self,
        domain: DomainModel,
        capabilities: CapabilityModel,
        services: ServiceModel,
        information: InformationModel,
        languages: List[str],
        frameworks: List[str],
        databases: List[str],
    ) -> str:
        """LLM-generated executive summary."""
        system_prompt = EXECUTIVE_SUMMARY_SYSTEM.format(domain=domain.primary_domain)

        core_caps = "\n".join(
            f"- {cap.name}: {cap.description}"
            for cap in capabilities.core_capabilities
        )
        supporting_caps = "\n".join(
            f"- {cap.name}"
            for cap in capabilities.supporting_capabilities
        )
        info_assets = "\n".join(
            f"- {asset.name} ({asset.asset_type})"
            for asset in information.information_assets[:4]
        )

        user_prompt = EXECUTIVE_SUMMARY_USER.format(
            domain=domain.primary_domain,
            sub_domain=domain.sub_domain or "General",
            architecture_style=services.architecture_style,
            business_functions=domain.business_functions,
            core_capabilities=core_caps or "Not identified",
            supporting_capabilities=supporting_caps or "Not identified",
            information_assets=info_assets or "Not identified",
            languages=languages,
            frameworks=frameworks,
            databases=databases,
        )

        return self.llm.generate(system_prompt, user_prompt, max_tokens=1024, temperature=0.2)

    def _template_executive_summary(
        self, domain, capabilities, services, information,
        languages, frameworks, databases, ai_ml_tools
    ) -> str:
        domain_name = domain.primary_domain or "Enterprise"
        sub = f" ({domain.sub_domain})" if domain.sub_domain else ""
        lang_str = ", ".join(languages[:3]) if languages else "Unknown"
        fw_str   = ", ".join(frameworks[:2]) if frameworks else "standard libraries"
        db_str   = ", ".join(databases[:2]) if databases else ""
        style    = getattr(services, "architecture_style", "") or "Modular"
        biz_fns  = ", ".join(domain.business_functions[:3]) if domain.business_functions else ""
        contexts = ", ".join(domain.bounded_contexts[:3]) if domain.bounded_contexts else ""

        core_caps = capabilities.core_capabilities or []
        cap_str = "; ".join(
            f"{c.name} ({c.description[:60].rstrip('.')})"
            for c in core_caps[:3]
        ) if core_caps else "core platform capabilities"

        p1 = (
            f"This document describes the architecture of a {domain_name}{sub} system "
            f"implemented in {lang_str} using {fw_str}. "
            f"The system delivers {len(core_caps)} primary business capability(ies): {cap_str}."
        )
        p2 = (
            f"The platform supports {biz_fns or 'core business operations'} "
            + (f"across {contexts} bounded contexts. " if contexts else "")
            + f"It is organized into {len(services.services)} architectural service(s) "
            f"following a {style} pattern."
            + (f" Data is persisted across {db_str}." if db_str else "")
        )

        rationale = getattr(services, "architecture_rationale", "") or ""
        p3 = (
            f"The architecture follows {style.lower()}, "
            f"enabling {(domain.business_functions[0].lower() if domain.business_functions else 'core operations')} "
            f"with maintainability and extensibility as primary design goals."
        )
        if rationale:
            p3 += f" {rationale}"

        return f"{p1}\n\n{p2}\n\n{p3}"

    def _generate_system_architecture(
        self,
        domain: DomainModel,
        capabilities: CapabilityModel,
        services: ServiceModel,
    ) -> str:
        """Generate system architecture narrative."""
        if self.llm:
            try:
                text = self._llm_system_architecture(domain, capabilities, services)
                if self._validate_narrative(text, "system_architecture"):
                    return text
            except Exception:
                pass

        return self._template_system_architecture(domain, capabilities, services)

    def _llm_system_architecture(
        self,
        domain: DomainModel,
        capabilities: CapabilityModel,
        services: ServiceModel,
    ) -> str:
        """LLM-generated system architecture narrative."""
        layers = list(set(s.layer for s in services.services))
        core_svc = [s.name for s in services.services if s.service_type == "Domain"]

        user_prompt = SYSTEM_ARCHITECTURE_USER.format(
            architecture_style=services.architecture_style,
            layers=layers,
            service_count=len(services.services),
            capability_summary=capabilities.capability_map_description,
            core_services=core_svc,
        )

        return self.llm.generate(
            SYSTEM_ARCHITECTURE_SYSTEM, user_prompt,
            max_tokens=512, temperature=0.2
        )

    def _template_system_architecture(
        self,
        domain: DomainModel,
        capabilities: CapabilityModel,
        services: ServiceModel,
    ) -> str:
        """Deterministic system architecture narrative."""
        layers = sorted(set(s.layer for s in services.services))
        core_svc = [s.name for s in services.services if s.service_type == "Domain"]

        return (
            f"The system follows a {services.architecture_style} architectural pattern, "
            f"organizing {len(services.services)} services across "
            f"{', '.join(layers)} layer{'s' if len(layers) > 1 else ''}. "
            + capabilities.capability_map_description + " "
            f"Domain services — {', '.join(core_svc[:3])} — form the backbone of the system, "
            f"supported by application and infrastructure services that provide "
            f"cross-cutting capabilities."
        )

    # ─────────────────────────────────────────────────────────
    # MODULE DESCRIPTIONS
    # ─────────────────────────────────────────────────────────

    def _generate_module_descriptions(
        self,
        domain: DomainModel,
        services: ServiceModel,
    ) -> Dict[str, str]:
        """Generate per-module description paragraphs."""
        descriptions: Dict[str, str] = {}

        for svc in services.services:
            if self.llm:
                try:
                    text = self._llm_module_description(domain, svc)
                    if self._validate_narrative(text, "module"):
                        descriptions[svc.name] = text.strip()
                        continue
                except Exception:
                    pass

            # Template fallback — meaningful three-sentence description
            descriptions[svc.name] = self._template_module_description(domain, svc)

        return descriptions

    def _template_module_description(self, domain: DomainModel, svc) -> str:
        """Generate a meaningful module description without LLM."""
        domain_ctx = domain.sub_domain or domain.primary_domain

        # Sentence 1: What this service is responsible for
        responsibility = svc.responsibility.rstrip('.')
        s1 = f"The {svc.name} is the {svc.service_type.lower()} component responsible for {responsibility.lower() if responsibility[0].isupper() else responsibility}"

        # Sentence 2: What layer it operates in and why
        layer_descriptions = {
            "Domain": "This service contains the core business rules and domain logic",
            "Application": "This service coordinates between domain components and external consumers",
            "Infrastructure": "This service provides foundational technical capabilities to the platform",
            "Presentation": "This service manages user-facing interactions and request handling",
        }
        s2 = layer_descriptions.get(svc.layer, f"This service operates in the {svc.layer} layer")

        # Sentence 3: Dependencies or consumers
        dep_names = [d.dependency for d in svc.dependencies] if svc.dependencies else []
        if dep_names:
            dep_str = ", ".join(dep_names[:2])
            s3 = f"It depends on {dep_str} to fulfill its responsibilities within the {domain_ctx} platform."
        elif svc.consumers:
            cons_str = ", ".join(svc.consumers[:2])
            s3 = f"It is consumed by {cons_str} as part of the overall service architecture."
        else:
            s3 = f"It operates as a self-contained component within the {domain_ctx} platform."

        return f"{s1}. {s2}. {s3}"

    def _llm_module_description(self, domain: DomainModel, svc) -> str:
        """LLM-generated module description."""
        user_prompt = MODULE_DESCRIPTION_USER.format(
            service_name=svc.name,
            service_type=svc.service_type,
            responsibility=svc.responsibility,
            capabilities_served=svc.capabilities_served,
            layer=svc.layer,
            technology_notes=svc.technology_notes or "Not specified",
            domain=domain.primary_domain,
        )

        return self.llm.generate(
            MODULE_DESCRIPTION_SYSTEM, user_prompt,
            max_tokens=256, temperature=0.2
        )

    # ─────────────────────────────────────────────────────────
    # DEPLOYMENT NARRATIVE
    # ─────────────────────────────────────────────────────────

    def _generate_deployment_narrative(
        self,
        deployment: DeploymentModel,
        languages: List[str],
    ) -> str:
        """Generate deployment narrative."""
        if self.llm:
            try:
                user_prompt = DEPLOYMENT_NARRATIVE_USER.format(
                    hosting_model=deployment.hosting_model,
                    deployment_units=[u.name for u in deployment.deployment_units],
                    infrastructure=deployment.infrastructure_components,
                    languages=languages,
                )
                text = self.llm.generate(
                    DEPLOYMENT_NARRATIVE_SYSTEM, user_prompt,
                    max_tokens=256, temperature=0.2
                )
                if self._validate_narrative(text, "deployment"):
                    return text.strip()
            except Exception:
                pass

        return deployment.operational_notes

    # ─────────────────────────────────────────────────────────
    # TECHNOLOGY NARRATIVE
    # ─────────────────────────────────────────────────────────

    def _generate_technology_narrative(
        self,
        domain: DomainModel,
        services: ServiceModel,
        languages: List[str],
        frameworks: List[str],
        databases: List[str],
        ai_ml_tools: List[str],
    ) -> str:
        """Generate technology narrative."""
        if self.llm:
            try:
                user_prompt = TECHNOLOGY_NARRATIVE_USER.format(
                    domain=domain.primary_domain,
                    languages=languages,
                    frameworks=frameworks,
                    databases=databases,
                    ai_ml_tools=ai_ml_tools,
                    architecture_style=services.architecture_style,
                )
                text = self.llm.generate(
                    TECHNOLOGY_NARRATIVE_SYSTEM, user_prompt,
                    max_tokens=256, temperature=0.2
                )
                if self._validate_narrative(text, "technology"):
                    return text.strip()
            except Exception:
                pass

        # Template fallback
        lang_str = ", ".join(languages[:3]) if languages else "standard languages"
        db_str = ", ".join(databases[:2]) if databases else "standard storage"
        fw_str = ", ".join(frameworks[:3]) if frameworks else "common frameworks"

        return (
            f"The technology stack is built on {lang_str}, leveraging {fw_str} "
            f"for application logic and {db_str} for data persistence. "
            f"This combination provides a solid foundation for the "
            f"{domain.primary_domain} system's requirements."
        )

    # ─────────────────────────────────────────────────────────
    # VALIDATION
    # ─────────────────────────────────────────────────────────

    @staticmethod
    def _validate_narrative(text: str, section: str) -> bool:
        """Validate LLM-generated narrative text."""
        if not text or not text.strip():
            return False

        text_lower = text.lower()

        # Check forbidden terms
        for term in FORBIDDEN_TERMS:
            if term.lower() in text_lower:
                return False

        # Section-specific validation
        if section == "executive_summary":
            # Must be 2-3 paragraphs
            paragraphs = [p.strip() for p in text.strip().split("\n\n") if p.strip()]
            if len(paragraphs) < 2 or len(paragraphs) > 4:
                return False
            # Word count: 200-500
            word_count = len(text.split())
            if word_count < 100 or word_count > 600:
                return False

        elif section == "system_architecture":
            word_count = len(text.split())
            if word_count < 30 or word_count > 300:
                return False

        elif section == "module":
            word_count = len(text.split())
            if word_count < 15 or word_count > 200:
                return False

        return True

    # ─────────────────────────────────────────────────────────
    # INTEGRATION NARRATIVE (P1 fix)
    # ─────────────────────────────────────────────────────────

    def _generate_integration_narrative(
        self,
        integration,
        domain: DomainModel,
    ) -> str:
        """Generate integration narrative using LLM when available, falling back to analyzer's version."""
        if self.llm and integration.integration_points:
            try:
                points_data = [
                    {"name": ip.name, "protocol": ip.protocol, "purpose": ip.purpose}
                    for ip in integration.integration_points[:5]
                ]
                system_prompt = (
                    "You are an Enterprise Architect writing the Integration section of an HLD. "
                    "One paragraph, 3-4 sentences. Plain text. No headings or bullets."
                )
                user_prompt = (
                    f"Describe the integration architecture for this {domain.primary_domain} system.\n\n"
                    f"INTEGRATION POINTS:\n{points_data}\n"
                    f"API SURFACE: {integration.api_surface_summary}\n"
                )
                text = self.llm.generate(system_prompt, user_prompt, max_tokens=256, temperature=0.2)
                if self._validate_narrative(text, "integration"):
                    return text.strip()
            except Exception:
                pass
        return integration.integration_narrative
