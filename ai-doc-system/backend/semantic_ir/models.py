"""
semantic_ir/models.py
────────────────────────────────────────────────────────────────
Enhanced Semantic IR models for enterprise-grade HLD/LLD generation.

These models represent the intermediate representation between
the Knowledge Graph (rich, graph-shaped data) and the document
generators (which need linear, structured data).
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict


# ──────────────────────────────────────────────────────────────
#  COMPONENT — an architectural unit (service, module, layer)
# ──────────────────────────────────────────────────────────────

@dataclass
class IRComponent:
    name: str
    component_type: str
    description: str

    # File membership
    files: List[str] = field(default_factory=list)

    # What this component depends on (other component names)
    dependencies: List[str] = field(default_factory=list)

    # Architecture enrichment
    layer: Optional[str] = None               # Presentation / Application / Domain / Infrastructure
    service_boundary: Optional[str] = None    # microservice name
    business_domain: Optional[str] = None     # e.g. "Charging & Billing"
    languages: List[str] = field(default_factory=list)

    # Key classes/functions inside this component
    key_classes: List[str] = field(default_factory=list)
    key_functions: List[str] = field(default_factory=list)

    # API endpoints exposed by this component
    api_endpoints: List[str] = field(default_factory=list)

    # Data stores accessed by this component
    data_stores: List[str] = field(default_factory=list)

    # Complexity and confidence
    complexity_score: float = 0.0
    confidence: str = "high"


# ──────────────────────────────────────────────────────────────
#  RELATIONSHIP — a directed connection between components
# ──────────────────────────────────────────────────────────────

@dataclass
class IRRelationship:
    source: str
    target: str
    relationship_type: str

    # Enrichment
    evidence: Optional[str] = None
    confidence: str = "high"
    data_flow_direction: Optional[str] = None  # upstream / downstream


# ──────────────────────────────────────────────────────────────
#  WORKFLOW — a named execution sequence
# ──────────────────────────────────────────────────────────────

@dataclass
class IRWorkflow:
    name: str
    steps: List[str]

    # Enrichment
    workflow_type: str = "generic"   # api_flow / data_flow / event_flow / generic
    entry_point: Optional[str] = None
    exit_points: List[str] = field(default_factory=list)
    description: Optional[str] = None
    confidence: str = "high"


# ──────────────────────────────────────────────────────────────
#  API ENDPOINT — an HTTP route definition
# ──────────────────────────────────────────────────────────────

@dataclass
class IRApiEndpoint:
    path: str
    method: str = "GET"
    handler_function: Optional[str] = None
    handler_file: Optional[str] = None
    service: Optional[str] = None
    description: Optional[str] = None
    request_model: Optional[str] = None
    response_model: Optional[str] = None


# ──────────────────────────────────────────────────────────────
#  DATA STORE — a database table, collection, or cache
# ──────────────────────────────────────────────────────────────

@dataclass
class IRDataStore:
    name: str
    store_type: str = "sql_table"  # sql_table / mongo_collection / cache / dataframe
    accessed_by: List[str] = field(default_factory=list)
    operations: List[str] = field(default_factory=list)  # SELECT / INSERT / UPDATE / DELETE


# ──────────────────────────────────────────────────────────────
#  REQUEST FLOW — traces a request lifecycle end-to-end
# ──────────────────────────────────────────────────────────────

@dataclass
class IRRequestFlow:
    name: str
    entry_point: str                               # API endpoint or trigger
    steps: List[str] = field(default_factory=list)  # ordered node names
    exit_point: Optional[str] = None               # response or data store
    flow_type: str = "api_flow"                    # api_flow / event_flow / data_flow
    description: Optional[str] = None


# ──────────────────────────────────────────────────────────────
#  ERROR PATH — traces exception/error handling
# ──────────────────────────────────────────────────────────────

@dataclass
class IRErrorPath:
    source_function: str
    error_handler: str
    error_type: Optional[str] = None
    recovery_strategy: Optional[str] = None


# ──────────────────────────────────────────────────────────────
#  SEMANTIC IR — the complete intermediate representation
# ──────────────────────────────────────────────────────────────

@dataclass
class SemanticIR:
    repository_type: str

    # Core structures
    components: List[IRComponent] = field(default_factory=list)
    relationships: List[IRRelationship] = field(default_factory=list)
    workflows: List[IRWorkflow] = field(default_factory=list)

    # Architecture enrichment
    api_endpoints: List[IRApiEndpoint] = field(default_factory=list)
    data_stores: List[IRDataStore] = field(default_factory=list)
    request_flows: List[IRRequestFlow] = field(default_factory=list)
    error_paths: List[IRErrorPath] = field(default_factory=list)

    # Metadata
    languages: List[str] = field(default_factory=list)
    frameworks: List[str] = field(default_factory=list)
    databases: List[str] = field(default_factory=list)
    messaging_systems: List[str] = field(default_factory=list)
    infrastructure: List[str] = field(default_factory=list)
    ai_ml_tools: List[str] = field(default_factory=list)
    code_analysis_tools: List[str] = field(default_factory=list)
    architecture_pattern: Optional[str] = None  # microservices / monolith / modular / etc.
    architecture_pattern_confidence: Optional[str] = None
    architecture_pattern_evidence: Optional[str] = None
    service_count: int = 0
    metadata: Dict = field(default_factory=dict)