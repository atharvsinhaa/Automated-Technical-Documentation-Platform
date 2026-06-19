import json
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict

@dataclass
class LLDMethod:
    name: str
    signature: str
    description: Optional[str] = None
    parameters: List[str] = field(default_factory=list)
    return_type: Optional[str] = None

@dataclass
class LLDClass:
    name: str
    file_path: str
    description: Optional[str] = None
    inherits_from: List[str] = field(default_factory=list)
    implements: List[str] = field(default_factory=list)
    constructors: List[LLDMethod] = field(default_factory=list)
    methods: List[LLDMethod] = field(default_factory=list)
    fields: List[str] = field(default_factory=list)
    composition: List[str] = field(default_factory=list)
    aggregation: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list) # classes it depends on

@dataclass
class LLDInterface:
    name: str
    file_path: str
    description: Optional[str] = None
    methods: List[LLDMethod] = field(default_factory=list)

@dataclass
class LLDDesignPattern:
    pattern_name: str
    components_involved: List[str] = field(default_factory=list)
    description: str = ""
    confidence: str = "Low"

@dataclass
class LLDAlgorithm:
    name: str
    location: str
    description: str
    complexity: Optional[str] = None
    steps: List[str] = field(default_factory=list)

@dataclass
class LLDDatabaseObject:
    name: str
    type: str # Table, View, Collection
    fields: List[str] = field(default_factory=list)
    relationships: List[str] = field(default_factory=list)

@dataclass
class LLDSequenceFlow:
    name: str
    trigger: str
    steps: List[str] = field(default_factory=list)
    description: Optional[str] = None

@dataclass
class LLDErrorPath:
    source: str
    error_type: str
    handler: str
    recovery_strategy: Optional[str] = None
    trigger: str = "Unknown"
    affected_component: str = "Unknown"
    impact: str = "Unknown"
    severity: str = "Unknown"


@dataclass
class LLDFieldDef:
    name: str
    type_str: str                   # "str", "Optional[int]", "List[str]"
    default_value: Optional[str] = None
    is_optional: bool = False
    description: str = ""


@dataclass
class LLDDataType:
    """A structured data type (dataclass, TypedDict, NamedTuple, Pydantic model)."""
    name: str
    kind: str                       # "dataclass" | "TypedDict" | "NamedTuple" | "Pydantic" | "class"
    fields: List[LLDFieldDef] = field(default_factory=list)
    description: str = ""
    file_path: str = ""


@dataclass
class LLDEnumType:
    """An enumeration type."""
    name: str
    members: List[str] = field(default_factory=list)   # "STATUS_ACTIVE = 'active'"
    description: str = ""
    file_path: str = ""


@dataclass
class LLDTypeAlias:
    """A type alias (e.g. UserId = int, Payload = Dict[str, Any])."""
    name: str
    alias_for: str
    file_path: str = ""


# ── NEW: API Specification ─────────────────────────────────────────
@dataclass
class LLDAPISpec:
    path: str                         # "/api/orders"
    method: str                       # "POST"
    service: str                      # "OrderService"
    description: str = ""
    request_body: List[str] = field(default_factory=list)   # field names
    response_body: List[str] = field(default_factory=list)  # field names
    auth_required: bool = False
    error_codes: List[str] = field(default_factory=list)    # ["400", "404", "500"]


# ── NEW: Module Design ────────────────────────────────────────────
@dataclass
class LLDModule:
    name: str                         # "Order Management"
    package_path: str                 # "backend/order/"
    responsibility: str               # "Handles order lifecycle"
    classes_contained: List[str] = field(default_factory=list)
    interfaces_contained: List[str] = field(default_factory=list)
    depends_on_modules: List[str] = field(default_factory=list)
    exposed_apis: List[str] = field(default_factory=list)   # endpoint paths
    tech_evidence: List[str] = field(default_factory=list)


# ── NEW: Component (for Component Architecture) ───────────────────
@dataclass
class LLDComponent:
    name: str
    component_type: str               # "Service" | "Repository" | "Controller" | "Model" | "Utility"
    layer: str                        # "Presentation" | "Application" | "Domain" | "Infrastructure"
    purpose: str = ""
    consumes: List[str] = field(default_factory=list)
    produces: List[str] = field(default_factory=list)
    artifacts: List[str] = field(default_factory=list)
    depends_on: List[str] = field(default_factory=list)
    technology: str = ""              # "FastAPI", "SQLAlchemy", etc.
    tech_evidence: List[str] = field(default_factory=list)


# ── NEW: Dependency Edge ──────────────────────────────────────────
@dataclass
class LLDDependency:
    source: str                       # component name
    target: str                       # component name
    dependency_type: str              # "Data Dependency" | "Service Dependency" | "API Dependency" | "Infrastructure Dependency" | "Runtime Dependency"
    is_circular: bool = False
    strength: str = "Medium"
    purpose: str = ""

@dataclass
class LLDCircularDependency:
    cycle_path: List[str] = field(default_factory=list)
    root_cause: str = ""
    affected_files: List[str] = field(default_factory=list)
    affected_classes: List[str] = field(default_factory=list)
    recommended_refactor: str = ""

@dataclass
class LLDEntryPoint:
    name: str
    evidence: List[str] = field(default_factory=list)


# ── NEW: External Integration ─────────────────────────────────────
@dataclass
class LLDExternalIntegration:
    name: str                         # "Stripe Payment Gateway"
    integration_type: str             # "REST API" | "Database" | "Message Queue" | "File System"
    direction: str                    # "Inbound" | "Outbound" | "Bidirectional"
    endpoint_or_dsn: str              # URL, connection string pattern
    used_by_components: List[str] = field(default_factory=list)
    auth_mechanism: str = ""          # "API Key" | "OAuth2" | "Basic Auth" | ""
    data_format: str = ""             # "JSON" | "XML" | "Binary" | ""


# ── NEW: Deployment Unit (LLD-level, more detailed than HLD) ─────
@dataclass
class LLDDeploymentUnit:
    name: str
    unit_type: str
    entry_point: Optional[str] = None
    hosts_components: List[str] = field(default_factory=list)
    runtime: Optional[str] = None
    exposed_ports: List[int] = field(default_factory=list)
    environment_variables: List[str] = field(default_factory=list)

@dataclass
class LLDSecurityDesign:
    mechanisms: List[str] = field(default_factory=list)
    description: Optional[str] = None
    detected_evidence: List[str] = field(default_factory=list)

@dataclass
class LLDConfigDesign:
    environment_variables: List[str] = field(default_factory=list)
    config_files: List[str] = field(default_factory=list)
    description: Optional[str] = None


# ── NEW: Typed Field for schema columns ───────────────────────────
@dataclass
class LLDTableColumn:
    name: str
    data_type: str              # "VARCHAR(255)", "INTEGER", "BOOLEAN", "TIMESTAMP"
    is_primary_key: bool = False
    is_foreign_key: bool = False
    is_nullable: bool = True
    default_value: Optional[str] = None
    references: Optional[str] = None  # "users.id"

# ── NEW: Data Type / Table Schema ─────────────────────────────────
@dataclass
class LLDDataTypeTable:
    name: str                           # "users", "OrderLine", "PaymentRecord"
    source_type: str                    # "SQL Table" | "ORM Model" | "Dataclass" | "TypedDict" | "Pydantic Model" | "NoSQL Collection"
    file_path: str = ""
    columns: List[LLDTableColumn] = field(default_factory=list)
    indexes: List[str] = field(default_factory=list)      # ["idx_users_email", "idx_created_at"]
    constraints: List[str] = field(default_factory=list)  # ["UNIQUE(email)", "CHECK(age > 0)"]
    description: str = ""
    relationships: List[str] = field(default_factory=list)  # ["users.id → orders.user_id"]

@dataclass
class LLDModel:
    repository_type: str
    architecture_pattern: Optional[str] = None
    architecture_pattern_confidence: Optional[str] = None
    architecture_pattern_evidence: Optional[str] = None

    # Existing fields (keep exactly as-is)
    classes: List[LLDClass] = field(default_factory=list)
    interfaces: List[LLDInterface] = field(default_factory=list)
    design_patterns: List[LLDDesignPattern] = field(default_factory=list)
    algorithms: List[LLDAlgorithm] = field(default_factory=list)
    database_objects: List[LLDDatabaseObject] = field(default_factory=list)
    sequence_flows: List[LLDSequenceFlow] = field(default_factory=list)
    error_paths: List[LLDErrorPath] = field(default_factory=list)

    # NEW fields
    api_specs: List[LLDAPISpec] = field(default_factory=list)
    modules: List[LLDModule] = field(default_factory=list)
    components: List[LLDComponent] = field(default_factory=list)
    dependencies: List[LLDDependency] = field(default_factory=list)
    circular_dependencies: List[LLDCircularDependency] = field(default_factory=list)
    entry_points: List[LLDEntryPoint] = field(default_factory=list)
    external_integrations: List[LLDExternalIntegration] = field(default_factory=list)
    deployment_units: List[LLDDeploymentUnit] = field(default_factory=list)
    security: Optional[LLDSecurityDesign] = None
    configuration: Optional[LLDConfigDesign] = None
    data_type_tables: List[LLDDataTypeTable] = field(default_factory=list)
    
    # Section 15: Data Types and Tables
    data_types: List[LLDDataType] = field(default_factory=list)
    enum_types: List[LLDEnumType] = field(default_factory=list)
    type_aliases: List[LLDTypeAlias] = field(default_factory=list)
    
    system_overview: Optional[str] = None

    metadata: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)
