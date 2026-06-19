"""
architecture_intelligence/models.py
────────────────────────────────────────────────────────────────
All data models for the Architecture Intelligence Engine.

Hierarchy:
    ArchitectureIntelligenceModel (root)
        ├── DomainModel
        ├── CapabilityModel
        │       └── BusinessCapability[]
        ├── ServiceModel
        │       └── ArchitecturalService[]
        ├── InformationModel
        │       ├── InformationAsset[]
        │       └── DataFlow[]
        ├── DeploymentModel
        │       └── DeploymentUnit[]
        ├── IntegrationModel
        │       └── IntegrationPoint[]
        └── NarrativeContext
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional


# ─────────────────────────────────────────────────────────────
# DOMAIN MODEL
# ─────────────────────────────────────────────────────────────

@dataclass
class DomainModel:
    primary_domain: str             # e.g. "Financial Services", "E-Commerce", "Healthcare IT"
    sub_domain: Optional[str]       # e.g. "Retail Banking", "Order Management", "EHR"
    bounded_contexts: List[str]     # e.g. ["Payments", "Customer Management", "Inventory"]
    business_functions: List[str]   # e.g. ["Process Payment", "Manage Orders", "Authenticate User"]
    domain_confidence: float        # 0.0 – 1.0
    domain_evidence: List[str]      # signals that drove the classification
    industry_vocabulary: List[str]  # domain terms found: ["invoice", "ledger", "premium", ...]
    core_information_assets: List[str] # semantically correct domain assets


# ─────────────────────────────────────────────────────────────
# CAPABILITY MODEL
# ─────────────────────────────────────────────────────────────

@dataclass
class BusinessCapability:
    name: str                       # Business-oriented: "Payment Processing", "Order Fulfillment"
    description: str                # 1–2 sentence explanation for a non-developer
    tier: str                       # "Core" | "Supporting" | "Generic"
    business_value: str             # why this capability matters to the business
    supporting_components: List[str]  # technical component names backing this capability
    related_bounded_context: Optional[str] = None
    confidence: float = 0.8         # 0.0 – 1.0


@dataclass
class CapabilityModel:
    core_capabilities: List[BusinessCapability]        # max 4
    supporting_capabilities: List[BusinessCapability]  # max 4
    generic_capabilities: List[BusinessCapability]     # max 3 (auth, logging, config)
    capability_map_description: str  # 1–2 sentences: "The system's capabilities are organized into..."


# ─────────────────────────────────────────────────────────────
# SERVICE MODEL
# ─────────────────────────────────────────────────────────────

@dataclass
class ServiceDependency:
    dependency: str
    source: str
    confidence: float

@dataclass
class ArchitecturalService:
    name: str                       # Architecture-level name: "Payment Gateway Service"
    service_type: str               # "Domain" | "Application" | "Infrastructure" | "Integration"
    responsibility: str             # 1-sentence responsibility statement
    capabilities_served: List[str]  # which BusinessCapability names this service supports
    dependencies: List[ServiceDependency] # other services this depends on
    consumers: List[str]            # services that consume this one
    layer: str                      # "Presentation" | "Application" | "Domain" | "Infrastructure"
    technology_notes: str           # brief tech context (language/framework)
    is_external: bool = False       # True if this is an external system/API


@dataclass
class ServiceModel:
    services: List[ArchitecturalService]
    interaction_summary: str        # "Services interact via..." — LLM-generated
    architecture_style: str         # "Layered Monolith" | "Modular Monolith" | "Microservices" | "Pipeline" | "Event-Driven"
    architecture_rationale: str     # Why this style was chosen


# ─────────────────────────────────────────────────────────────
# INFORMATION MODEL
# ─────────────────────────────────────────────────────────────

@dataclass
class InformationAsset:
    name: str                       # Business name: "Customer Record", "Payment Transaction"
    asset_type: str                 # "Master Data" | "Transactional" | "Reference" | "Derived" | "Event"
    description: str                # what this information represents
    lifecycle_stages: List[str]     # ["Created", "Validated", "Processed", "Archived"]
    produced_by: str                # service/component that creates it
    consumed_by: List[str]          # services/components that read it
    persistence: str                # "Persistent" | "Transient" | "Cached" | "Streamed"
    sensitivity: str                # "Public" | "Internal" | "Confidential" | "Restricted"
    confidence: float = 0.8         # 0.0 - 1.0
    evidence: List[str] = field(default_factory=list) # e.g. ["dependency_extractor", "graph_builder"]


@dataclass
class DataFlow:
    name: str                       # "Order Processing Flow", "Payment Authorization Flow"
    description: str                # what this flow represents in business terms
    stages: List[str]               # ordered business-level stages (no file paths)
    trigger: str                    # what initiates this flow
    outcome: str                    # business result when complete


@dataclass
class InformationModel:
    information_assets: List[InformationAsset]  # max 6
    primary_data_flows: List[DataFlow]           # max 3
    data_model_summary: str                      # LLM-generated description


# ─────────────────────────────────────────────────────────────
# DEPLOYMENT MODEL
# ─────────────────────────────────────────────────────────────

@dataclass
class DeploymentUnit:
    name: str
    unit_type: str          # "Application Server" | "Container" | "Serverless Function" | "CLI Tool" | "Library" | "Worker"
    hosted_services: List[str]
    runtime: str            # "Python", "JVM", "Node.js", "Docker", ...
    deployment_notes: str   # brief description


@dataclass
class DeploymentModel:
    hosting_model: str              # "Local" | "Cloud-Native" | "Hybrid" | "On-Premise" | "Serverless"
    deployment_units: List[DeploymentUnit]
    infrastructure_components: List[str]  # databases, queues, caches detected
    operational_notes: str          # LLM-generated: how this system is typically run


# ─────────────────────────────────────────────────────────────
# INTEGRATION MODEL
# ─────────────────────────────────────────────────────────────

@dataclass
class IntegrationPoint:
    name: str                       # descriptive name: "Payment Gateway Integration"
    direction: str                  # "Inbound" | "Outbound" | "Bidirectional"
    protocol: str                   # "REST" | "GraphQL" | "gRPC" | "Message Queue" | "Database" | "File"
    source: str
    target: str
    purpose: str                    # business purpose: "Process customer payments"
    data_exchanged: str             # what information moves: "Payment authorization request/response"
    is_external: bool = False


@dataclass
class IntegrationModel:
    integration_points: List[IntegrationPoint]  # max 8
    api_surface_summary: str        # summary of exposed API surface
    integration_narrative: str      # LLM-generated integration story


# ─────────────────────────────────────────────────────────────
# NARRATIVE CONTEXT (pre-computed for HLD generator)
# ─────────────────────────────────────────────────────────────

@dataclass
class NarrativeContext:
    executive_summary: str          # 2–3 paragraph executive narrative
    system_architecture_narrative: str   # 1–2 paragraphs on architecture approach
    module_descriptions: Dict[str, str]  # service_name → description paragraph
    deployment_narrative: str       # 1 paragraph on deployment approach
    integration_narrative: str      # 1 paragraph on integration approach
    technology_narrative: str       # 1 paragraph on technology choices
    document_theme: str             # "Platform", "Application", "Service", "Framework", "Tool"
    target_audience_framing: str    # how to frame this for the reader


# ─────────────────────────────────────────────────────────────
# ARCHITECTURE INTELLIGENCE MODEL (root model)
# ─────────────────────────────────────────────────────────────

@dataclass
class ArchitectureIntelligenceModel:
    repository_name: str
    domain: DomainModel
    capabilities: CapabilityModel
    services: ServiceModel
    information: InformationModel
    deployment: DeploymentModel
    integration: IntegrationModel
    narrative: NarrativeContext
    aim_version: str = "1.0"
    generation_metadata: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return asdict(self)
