"""
architecture_intelligence/aim_builder.py
────────────────────────────────────────────────────────────────
Orchestrates all AIE sub-components into a complete
ArchitectureIntelligenceModel.

Pipeline:
    Stage 1: Domain Classification
    Stage 2: Capability Modeling
    Stage 3: Service Architecture
    Stage 4: Information Modeling
    Stage 5: Deployment Analysis
    Stage 6: Integration Analysis
    Stage 7: Narrative Generation
"""

from __future__ import annotations

import time
from typing import Dict, Optional

from backend.architecture_intelligence.models import ArchitectureIntelligenceModel
from backend.architecture_intelligence.domain_classifier import DomainClassifier
from backend.architecture_intelligence.capability_modeler import CapabilityModeler
from backend.architecture_intelligence.service_architect import ServiceArchitect
from backend.architecture_intelligence.information_modeler import InformationModeler
from backend.architecture_intelligence.deployment_analyzer import DeploymentAnalyzer
from backend.architecture_intelligence.integration_analyzer import IntegrationAnalyzer
from backend.architecture_intelligence.narrative_engine import NarrativeEngine

from backend.semantic_ir.models import SemanticIR
from backend.architecture_extractor.models import ArchitectureBlueprint


class AIMBuilder:
    """
    Orchestrates the Architecture Intelligence Engine pipeline.

    Each stage feeds the next — order matters.
    """

    def __init__(
        self,
        llm_client=None,
        verbose: bool = True,
    ):
        self.llm = llm_client
        self.verbose = verbose

        self.domain_classifier = DomainClassifier(llm_client)
        self.capability_modeler = CapabilityModeler(llm_client)
        self.service_architect = ServiceArchitect(llm_client)
        self.information_modeler = InformationModeler(llm_client)
        self.deployment_analyzer = DeploymentAnalyzer(llm_client)
        self.integration_analyzer = IntegrationAnalyzer(llm_client)
        self.narrative_engine = NarrativeEngine(llm_client)

    def build(
        self,
        semantic_ir: SemanticIR,
        blueprint: ArchitectureBlueprint,
        repository_name: str = "Unknown",
    ) -> ArchitectureIntelligenceModel:
        """
        Build a complete ArchitectureIntelligenceModel from
        SemanticIR + ArchitectureBlueprint.

        Stage order matters — each stage feeds the next.
        """
        t_start = time.time()

        # Stage 1: Domain Classification
        self._log("[AIE] Stage 1/7: Domain Classification...")
        domain = self.domain_classifier.classify(semantic_ir, blueprint)
        self._log(f"  → Domain: {domain.primary_domain} (confidence: {domain.domain_confidence:.2f})")

        # Stage 2: Capability Modeling
        self._log("[AIE] Stage 2/7: Capability Modeling...")
        capabilities = self.capability_modeler.model(blueprint, domain)
        self._log(
            f"  → {len(capabilities.core_capabilities)} core, "
            f"{len(capabilities.supporting_capabilities)} supporting, "
            f"{len(capabilities.generic_capabilities)} generic capabilities"
        )

        # Stage 3: Service Architecture
        self._log("[AIE] Stage 3/7: Service Architecture...")
        services = self.service_architect.architect(capabilities, blueprint, domain)
        self._log(
            f"  → {len(services.services)} services, "
            f"style: {services.architecture_style}"
        )

        # Stage 4: Information Modeling
        self._log("[AIE] Stage 4/7: Information Modeling...")
        information = self.information_modeler.model(blueprint, domain, capabilities)
        self._log(
            f"  → {len(information.information_assets)} assets, "
            f"{len(information.primary_data_flows)} flows"
        )

        # Stage 5: Deployment Analysis
        self._log("[AIE] Stage 5/7: Deployment Analysis...")
        deployment = self.deployment_analyzer.analyze(semantic_ir, blueprint, services)
        self._log(
            f"  → Hosting: {deployment.hosting_model}, "
            f"{len(deployment.deployment_units)} units"
        )

        # Stage 6: Integration Analysis
        self._log("[AIE] Stage 6/7: Integration Analysis...")
        integration = self.integration_analyzer.analyze(blueprint, domain, services)
        self._log(f"  → {len(integration.integration_points)} integration points")

        # Stage 7: Narrative Generation
        self._log("[AIE] Stage 7/7: Narrative Generation...")
        narrative = self.narrative_engine.generate(
            domain=domain,
            capabilities=capabilities,
            services=services,
            information=information,
            deployment=deployment,
            integration=integration,
            languages=semantic_ir.languages,
            frameworks=semantic_ir.frameworks,
            databases=semantic_ir.databases,
            ai_ml_tools=getattr(semantic_ir, "ai_ml_tools", []),
        )

        elapsed = time.time() - t_start
        self._log(f"[AIE] Complete ({elapsed:.1f}s)")

        return ArchitectureIntelligenceModel(
            repository_name=repository_name,
            domain=domain,
            capabilities=capabilities,
            services=services,
            information=information,
            deployment=deployment,
            integration=integration,
            narrative=narrative,
            generation_metadata={
                "llm_used": self.llm.model_name() if self.llm else "deterministic",
                "domain_confidence": domain.domain_confidence,
                "generation_time_seconds": round(elapsed, 2),
                "languages": semantic_ir.languages,
                "frameworks": semantic_ir.frameworks,
                "databases": semantic_ir.databases,
                "ai_ml_tools": getattr(semantic_ir, "ai_ml_tools", []),
            },
        )

    def _log(self, msg: str) -> None:
        """Log a message if verbose mode is enabled."""
        if self.verbose:
            print(msg, flush=True)
