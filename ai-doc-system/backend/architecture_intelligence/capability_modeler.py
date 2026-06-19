"""
architecture_intelligence/capability_modeler.py
────────────────────────────────────────────────────────────────
Map technical components to business capabilities.

Transforms raw ArchitectureCapability objects into a tiered
CapabilityModel with business-meaningful names and descriptions.

Tiers:
    Core       — directly delivers business value (max 4)
    Supporting — enables core capabilities (max 4)
    Generic    — cross-cutting concerns: auth, logging, config (max 3)
"""

from __future__ import annotations

import json
import re
from typing import Dict, List, Optional, Set

from backend.architecture_intelligence.models import (
    BusinessCapability,
    CapabilityModel,
    DomainModel,
)
from backend.architecture_extractor.models import (
    ArchitectureBlueprint,
    ArchitectureCapability,
)


# Technical terms that must NOT appear in business capability names
FORBIDDEN_NAME_TERMS = {
    "class", "module", "engine", "extractor", "builder", "parser",
    "handler", "factory", "registry", "manager", "util", "helper",
    "impl", "abstract", "base", "mixin", "adapter", "wrapper",
    "component", "node", "context", "spec", "generator",
    "root", "core", "main", "system",
}

# Patterns that indicate generic/cross-cutting concerns
GENERIC_PATTERNS = {
    "auth", "authentication", "authorization", "login", "security",
    "logging", "log", "monitor", "observability", "metric",
    "config", "configuration", "settings", "environment",
    "cache", "caching", "session",
    "error", "exception", "retry",
    "health", "heartbeat", "ping",
}


class CapabilityModeler:
    """Map technical components to tiered business capabilities."""

    def __init__(self, llm_client=None):
        self.llm = llm_client

    def model(
        self,
        blueprint: ArchitectureBlueprint,
        domain: DomainModel,
    ) -> CapabilityModel:
        """
        Transform blueprint capabilities into a tiered CapabilityModel.
        """
        raw_caps = getattr(blueprint, "capabilities", []) or []

        if not raw_caps:
            # Build capabilities from services if none exist
            raw_caps = self._caps_from_services(blueprint)

        # Step 1: Classify each capability into a tier
        classified = self._classify_tiers(raw_caps, domain)

        # Step 2: Generate business names and descriptions
        core = []
        supporting = []
        generic = []

        for cap, tier in classified:
            biz_cap = self._to_business_capability(cap, tier, domain)
            if tier == "Core":
                core.append(biz_cap)
            elif tier == "Supporting":
                supporting.append(biz_cap)
            else:
                generic.append(biz_cap)

        # Enforce limits
        core = core[:4]
        supporting = supporting[:4]
        generic = generic[:3]

        # Generate capability map description
        cap_desc = self._generate_capability_map_description(
            core, supporting, generic, domain
        )

        return CapabilityModel(
            core_capabilities=core,
            supporting_capabilities=supporting,
            generic_capabilities=generic,
            capability_map_description=cap_desc,
        )

    def _caps_from_services(
        self, blueprint: ArchitectureBlueprint
    ) -> List[ArchitectureCapability]:
        """Build synthetic capabilities from services when none exist."""
        caps = []
        source_items = blueprint.services if blueprint.services else blueprint.components
        for item in source_items:
            name = getattr(item, "name", "Core Component")
            desc = getattr(item, "purpose", getattr(item, "description", ""))
            caps.append(
                ArchitectureCapability(
                    name=name,
                    description=desc,
                    supporting_components=[name],
                )
            )
        
        # If absolutely nothing is found, create a single generic capability
        if not caps:
            caps.append(
                ArchitectureCapability(
                    name="Core Processing",
                    description="Main application processing logic",
                    supporting_components=["main"],
                )
            )
            
        return caps

    def _classify_tiers(
        self,
        caps: List[ArchitectureCapability],
        domain: DomainModel,
    ) -> List[tuple]:
        """Classify each capability into Core, Supporting, or Generic."""
        domain_vocab = set(w.lower() for w in domain.industry_vocabulary)
        domain_contexts = set(c.lower() for c in domain.bounded_contexts)
        result = []

        for cap in caps:
            cap_lower = cap.name.lower()
            desc_lower = (cap.description or "").lower()
            combined = cap_lower + " " + desc_lower

            # Check for generic patterns first
            if any(pat in combined for pat in GENERIC_PATTERNS):
                result.append((cap, "Generic"))
                continue

            # Check for domain vocabulary overlap → Core
            domain_match = any(v in combined for v in domain_vocab)
            context_match = any(c in combined for c in domain_contexts)

            if domain_match or context_match:
                result.append((cap, "Core"))
            else:
                # Check component count — heavily referenced = Core
                comp_count = len(getattr(cap, "supporting_components", []))
                if comp_count >= 3:
                    result.append((cap, "Core"))
                else:
                    result.append((cap, "Supporting"))

        # Guarantee at least one Core capability to prevent pipeline failure
        has_core = any(tier == "Core" for _, tier in result)
        if not has_core and result:
            # Promote the first non-generic capability to Core, or the first overall
            promoted = False
            for i, (cap, tier) in enumerate(result):
                if tier == "Supporting":
                    result[i] = (cap, "Core")
                    promoted = True
                    break
            if not promoted:
                result[0] = (result[0][0], "Core")

        return result

    def _to_business_capability(
        self,
        cap: ArchitectureCapability,
        tier: str,
        domain: DomainModel,
    ) -> BusinessCapability:
        """Convert a raw capability to a BusinessCapability with LLM or template."""
        supporting_components = getattr(cap, "supporting_components", []) or []

        if self.llm:
            try:
                return self._llm_business_capability(cap, tier, domain, supporting_components)
            except Exception:
                pass

        # Deterministic fallback
        return self._template_business_capability(cap, tier, domain, supporting_components)

    def _llm_business_capability(
        self,
        cap: ArchitectureCapability,
        tier: str,
        domain: DomainModel,
        supporting_components: List[str],
    ) -> BusinessCapability:
        """Use LLM to generate business capability name and description."""
        system_prompt = (
            "You are an Enterprise Business Architect.\n"
            "You translate software component groupings into business capability language.\n"
            "Respond ONLY with valid JSON. No markdown. No explanation."
        )

        user_prompt = (
            "Transform these technical components into a business capability.\n\n"
            f"REPOSITORY DOMAIN: {domain.primary_domain}"
            + (f" — {domain.sub_domain}" if domain.sub_domain else "")
            + f"\nBOUNDED CONTEXTS: {domain.bounded_contexts}\n\n"
            f"TECHNICAL COMPONENT:\n"
            f"  Name: {cap.name}\n"
            f"  Description: {cap.description}\n"
            f"  Supporting components: {supporting_components[:5]}\n\n"
            "Respond with:\n"
            "{\n"
            '  "business_name": "<Business-oriented capability name, 2-4 words>",\n'
            '  "description": "<1-2 sentences, no technical jargon, under 200 chars>",\n'
            f'  "tier": "{tier}",\n'
            '  "business_value": "<1 sentence: why does the business need this?>",\n'
            '  "confidence": 0.0-1.0\n'
            "}\n\n"
            "Rules:\n"
            "- business_name must NOT contain: class, module, engine, extractor, builder, parser, handler\n"
            "- description must be understandable by a non-developer\n"
        )

        raw = self.llm.generate(system_prompt, user_prompt, max_tokens=512, temperature=0.2)

        # Parse JSON
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned
            cleaned = cleaned.rsplit("```", 1)[0]
        data = json.loads(cleaned)

        # Validate
        biz_name = data.get("business_name", cap.name)
        if any(term in biz_name.lower() for term in FORBIDDEN_NAME_TERMS):
            biz_name = self._clean_name(cap.name, domain)

        description = data.get("description", "")
        if len(description) > 200:
            description = description[:197] + "..."

        confidence = float(data.get("confidence", 0.7))
        if confidence < 0.6:
            biz_name = self._clean_name(cap.name, domain)
            description, _ = self._template_description(cap, tier, biz_name, domain)

        return BusinessCapability(
            name=biz_name,
            description=description or self._template_description(cap, tier, biz_name, domain)[0],
            tier=tier,
            business_value=data.get("business_value", f"Enables {tier.lower()} {domain.primary_domain} operations."),
            supporting_components=supporting_components,
            related_bounded_context=domain.bounded_contexts[0] if domain.bounded_contexts else None,
            confidence=confidence,
        )

    def _template_business_capability(
        self,
        cap: ArchitectureCapability,
        tier: str,
        domain: DomainModel,
        supporting_components: List[str],
    ) -> BusinessCapability:
        """Deterministic business capability with meaningful description."""
        clean_name = self._clean_name(cap.name, domain)
        description, business_value = self._template_description(cap, tier, clean_name, domain)

        return BusinessCapability(
            name=clean_name,
            description=description,
            tier=tier,
            business_value=business_value,
            supporting_components=supporting_components,
            related_bounded_context=domain.bounded_contexts[0] if domain.bounded_contexts else None,
            confidence=0.7,
        )

    def _clean_name(self, raw_name: str, domain: DomainModel) -> str:
        """Clean a raw capability name into a business-friendly name."""
        # Insert space before capital letters (CamelCase split)
        name = re.sub(r'([a-z])([A-Z])', r'\1 \2', raw_name)
        
        # Remove common suffixes
        for suffix in ["Service", "Module", "Engine", "Manager", "Handler", "Builder", "Extractor", "Generator", "Analysis"]:
            name = name.replace(suffix, "").strip()

        # Remove underscores and clean up
        name = name.replace("_", " ").strip()

        # Title case
        name = " ".join(w.capitalize() for w in name.split())

        # If name is too short or too technical, derive from domain
        if len(name) < 4 or any(t in name.lower() for t in FORBIDDEN_NAME_TERMS):
            # Try to map to the first business function if available
            if domain.business_functions:
                return domain.business_functions[0]
            return f"{domain.primary_domain} Processing"

        # Check if the name partially matches a domain business function to map it fully
        for func in domain.business_functions:
            if name.lower() in func.lower() or func.lower() in name.lower():
                return func

        return name

    def _template_description(self, cap: ArchitectureCapability, tier: str, clean_name: str, domain: DomainModel = None) -> tuple:
        """Generate a domain-grounded description and business value for a capability."""
        desc = cap.description or ""
        if desc and len(desc) > 10 and not any(t in desc.lower() for t in FORBIDDEN_NAME_TERMS):
            return desc[:200], f"Enables {tier.lower()} {domain.primary_domain if domain else 'platform'} operations."

        name = clean_name.lower()
        domain_ctx = (domain.sub_domain or domain.primary_domain) if domain else "the platform"

        # Find the most relevant business function for this capability
        relevant_func = None
        if domain and domain.business_functions:
            for func in domain.business_functions:
                func_words = set(func.lower().split())
                cap_words = set(name.split())
                if func_words & cap_words:  # Any word overlap
                    relevant_func = func
                    break

        if tier == "Core" and relevant_func:
            description = (
                f"Enables the {relevant_func} business function by "
                f"providing {name} operations across the {domain_ctx} platform."
            )
            business_value = (
                f"Directly supports {domain.primary_domain if domain else 'business'} revenue and customer experience "
                f"through {name}."
            )
        elif tier == "Core":
            if "management" in name:
                target = name.replace("management", "").strip()
                description = f"Manages {target} operations including creation, modification, and lifecycle tracking within the {domain_ctx} domain."
            elif "processing" in name:
                target = name.replace("processing", "").strip()
                description = f"Processes {target} events and workflows, transforming inputs into business outcomes for the {domain_ctx} domain."
            else:
                description = (
                    f"Provides core {name} capabilities that deliver "
                    f"direct business value in the {domain_ctx} domain."
                )
            business_value = f"Core business capability required for {domain.primary_domain if domain else 'platform'} operations."
        elif tier == "Supporting":
            description = (
                f"Supports the {domain_ctx} platform by enabling "
                f"{name} across all core business processes."
            )
            business_value = "Enables core capabilities to function reliably and efficiently."
        else:  # Generic
            description = (
                f"Provides cross-cutting {name} services used by all "
                f"other platform components."
            )
            business_value = "Infrastructure capability shared across the platform."

        return description, business_value

    def _generate_capability_map_description(
        self,
        core: List[BusinessCapability],
        supporting: List[BusinessCapability],
        generic: List[BusinessCapability],
        domain: DomainModel,
    ) -> str:
        """Generate a 1-2 sentence capability map description."""
        total = len(core) + len(supporting) + len(generic)
        core_names = ", ".join(c.name for c in core[:3])

        return (
            f"The system's capabilities are organized into {total} functional areas. "
            f"Core capabilities — {core_names} — deliver direct business value, "
            f"supported by {len(supporting)} enabling services and "
            f"{len(generic)} cross-cutting infrastructure concerns."
        )
