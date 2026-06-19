"""
architecture_intelligence/deployment_analyzer.py
────────────────────────────────────────────────────────────────
Infer deployment model and runtime environment.

Builds DeploymentModel from SemanticIR metadata and
ArchitectureBlueprint deployment nodes using deterministic
infrastructure signal matching.
"""

from __future__ import annotations

import json
from typing import Dict, List, Optional

from backend.architecture_intelligence.models import (
    DeploymentModel,
    DeploymentUnit,
    ServiceModel,
)
from backend.semantic_ir.models import SemanticIR
from backend.architecture_extractor.models import ArchitectureBlueprint


# Infrastructure signal → hosting model mapping
_HOSTING_SIGNALS = [
    ({"kubernetes", "helm", "k8s"}, "Cloud-Native"),
    ({"lambda", "functions", "serverless", "cloud_functions"}, "Serverless"),
    ({"aws", "azure", "gcp", "cloud"}, "Cloud-Native"),
    ({"docker", "container", "podman"}, "Containerized"),
    ({"terraform", "pulumi", "cloudformation"}, "Cloud-Native"),
    ({"heroku", "vercel", "netlify", "railway"}, "Cloud-Managed"),
]

# Language → runtime mapping
_LANG_TO_RUNTIME = {
    "python": "Python",
    "java": "JVM",
    "kotlin": "JVM",
    "scala": "JVM",
    "javascript": "Node.js",
    "typescript": "Node.js",
    "go": "Go",
    "rust": "Rust",
    "ruby": "Ruby",
    "csharp": ".NET",
    "c#": ".NET",
    "php": "PHP",
}


class DeploymentAnalyzer:
    """Infer deployment model and runtime environment."""

    def __init__(self, llm_client=None):
        self.llm = llm_client

    def analyze(
        self,
        ir: SemanticIR,
        blueprint: ArchitectureBlueprint,
        services: ServiceModel,
    ) -> DeploymentModel:
        """Build DeploymentModel from infrastructure signals."""
        hosting_model = self._infer_hosting_model(ir, blueprint)
        units = self._build_deployment_units(services, ir, blueprint, hosting_model)
        infra = self._collect_infrastructure(ir, blueprint)
        notes = self._generate_operational_notes(
            hosting_model, units, infra, ir, services
        )

        return DeploymentModel(
            hosting_model=hosting_model,
            deployment_units=units,
            infrastructure_components=infra,
            operational_notes=notes,
        )

    def _infer_hosting_model(
        self, ir: SemanticIR, blueprint: ArchitectureBlueprint
    ) -> str:
        """Infer hosting model from infrastructure signals."""
        infra_lower = set(i.lower() for i in ir.infrastructure)
        framework_lower = set(f.lower() for f in ir.frameworks)
        all_signals = infra_lower | framework_lower

        # Also check imports/tools
        for tool in getattr(ir, "ai_ml_tools", []):
            all_signals.add(tool.lower())

        for sig_set, model in _HOSTING_SIGNALS:
            if sig_set & all_signals:
                return model

        # Check for web server frameworks (implies Application Server)
        web_frameworks = {"flask", "django", "fastapi", "express", "spring", "rails"}
        if web_frameworks & framework_lower:
            if not infra_lower:
                return "Local"
            return "On-Premise"

        # Check if blueprint has deployment nodes
        if blueprint.deployment_nodes:
            return "On-Premise"

        # Default: if it has a pipeline.py or CLI entrypoint
        return "Local"

    def _build_deployment_units(
        self,
        services: ServiceModel,
        ir: SemanticIR,
        blueprint: ArchitectureBlueprint,
        hosting_model: str,
    ) -> List[DeploymentUnit]:
        """Build deployment units from services."""
        units: List[DeploymentUnit] = []

        # Determine runtime from primary language
        runtime = "Python"  # default
        if ir.languages:
            primary_lang = ir.languages[0].lower()
            runtime = _LANG_TO_RUNTIME.get(primary_lang, primary_lang.capitalize())

        # Determine unit type
        has_api = len(ir.api_endpoints) > 0
        frameworks_lower = {f.lower() for f in ir.frameworks}
        messaging_lower = {m.lower() for m in ir.messaging_systems}
        languages_lower = {l.lower() for l in ir.languages}
        
        is_web_app = bool({"react", "vue", "next.js", "angular", "svelte"} & frameworks_lower) or bool({"html", "css", "javascript", "typescript"} & languages_lower)
        is_api = has_api or bool({"fastapi", "flask", "django", "express", "spring", "rails"} & frameworks_lower)
        is_background = bool({"celery", "kafka", "rabbitmq", "redis", "sidekiq"} & (frameworks_lower | messaging_lower))

        for svc in services.services:
            lower_name = svc.name.lower()
            if "knowledge" in lower_name or "graph" in lower_name:
                unit_type = "Neo4j Graph Store" if "neo4j" in runtime.lower() else "Knowledge Base"
            elif "understanding" in lower_name or "analysis" in lower_name:
                unit_type = "Processing Engine"
            elif "generation" in lower_name or "document" in lower_name:
                unit_type = "Document Generation Layer"
            elif "artifact" in lower_name or "storage" in lower_name:
                unit_type = "Artifact Repository"
            elif hosting_model == "Containerized" or hosting_model == "Cloud-Native":
                unit_type = "Container"
            elif hosting_model == "Serverless":
                unit_type = "Serverless Function"
            elif is_api:
                unit_type = "REST API Service"
            elif is_web_app:
                unit_type = "Web Application"
            elif is_background:
                unit_type = "Background Processor"
            else:
                unit_type = "CLI Tool"

            units.append(DeploymentUnit(
                name=svc.name.replace(" Service", ""),
                unit_type=unit_type,
                hosted_services=[svc.name],
                runtime=runtime,
                deployment_notes=f"Hosts {svc.name} ({svc.service_type} tier).",
            ))

        return units

    def _collect_infrastructure(
        self, ir: SemanticIR, blueprint: ArchitectureBlueprint
    ) -> List[str]:
        """Collect all infrastructure components."""
        infra = set()

        # Databases
        for db in ir.databases:
            infra.add(db)
            
        test_fixtures = {"customers", "orders", "users", "test", "mock"}
        for db in blueprint.databases:
            if db.name.lower() in test_fixtures or any(t in db.name.lower() for t in test_fixtures):
                continue
            infra.add(f"{db.name} ({db.type})")

        # Messaging
        for msg in ir.messaging_systems:
            infra.add(msg)

        # Infrastructure
        for i in ir.infrastructure:
            infra.add(i)

        return sorted(list(infra))

    def _generate_operational_notes(
        self,
        hosting_model: str,
        units: List[DeploymentUnit],
        infra: List[str],
        ir: SemanticIR,
        services: ServiceModel,
    ) -> str:
        """Generate operational notes."""
        if self.llm:
            try:
                return self._llm_operational_notes(
                    hosting_model, units, infra, ir, services
                )
            except Exception:
                pass

        return self._template_operational_notes(hosting_model, units, infra, ir)

    def _llm_operational_notes(
        self,
        hosting_model: str,
        units: List[DeploymentUnit],
        infra: List[str],
        ir: SemanticIR,
        services: ServiceModel,
    ) -> str:
        """LLM-generated operational notes."""
        system_prompt = (
            "You are a DevOps Architect. Write one brief paragraph about deployment. "
            "Respond with plain text only. Under 100 words."
        )
        user_prompt = (
            f"Describe the operational deployment model for this system.\n\n"
            f"HOSTING MODEL: {hosting_model}\n"
            f"INFRASTRUCTURE COMPONENTS: {infra}\n"
            f"SERVICES: {[s.name for s in services.services]}\n"
            f"LANGUAGES: {ir.languages}\n"
            f"DEPLOYMENT UNITS: {[u.name for u in units]}\n"
        )
        text = self.llm.generate(system_prompt, user_prompt, max_tokens=256, temperature=0.2)
        text = text.strip()

        if 30 < len(text) < 500:
            return text

        return self._template_operational_notes(hosting_model, units, infra, ir)

    def _template_operational_notes(
        self,
        hosting_model: str,
        units: List[DeploymentUnit],
        infra: List[str],
        ir: SemanticIR,
    ) -> str:
        """Template operational notes."""
        unit_types = set(u.unit_type for u in units)
        langs = ", ".join(ir.languages[:2]) if ir.languages else "standard"

        if hosting_model == "Local":
            return (
                f"The system is deployed locally as a {' / '.join(unit_types)} "
                f"running on {langs}. "
                + (f"It depends on {', '.join(infra[:3])} for data persistence. " if infra else "")
                + "No containerization or cloud deployment was detected."
            )
        elif hosting_model in ("Cloud-Native", "Containerized"):
            return (
                f"The system follows a {hosting_model.lower()} deployment model with "
                f"{len(units)} deployment units running on {langs}. "
                + (f"Infrastructure includes {', '.join(infra[:3])}. " if infra else "")
            )
        else:
            return (
                f"The system is deployed using a {hosting_model.lower()} model with "
                f"{len(units)} components running on {langs}."
            )
