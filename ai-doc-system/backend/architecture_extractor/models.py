import json
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict

@dataclass
class ArchitectureService:
    name: str
    purpose: str
    layer: str = "Application"
    responsibilities: List[str] = field(default_factory=list)
    inputs: List[str] = field(default_factory=list)
    outputs: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    consumers: List[str] = field(default_factory=list)
    complexity_score: str = "1/5"
    confidence_score: str = "0%"

@dataclass
class ArchitectureCapability:
    name: str
    description: str
    confidence: str = "high"
    supporting_components: List[str] = field(default_factory=list)
    supporting_workflows: List[str] = field(default_factory=list)
    supporting_relationships: List[str] = field(default_factory=list)

@dataclass
class ArchitectureArtifact:
    name: str
    description: str
    producer: str
    consumers: List[str]
    artifact_type: str

@dataclass
class ArchitectureService:
    name: str
    purpose: str
    layer: str = "Application"
    responsibilities: List[str] = field(default_factory=list)
    inputs: List[str] = field(default_factory=list)
    outputs: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    consumers: List[str] = field(default_factory=list)
    complexity_score: str = "1/5"
    confidence_score: str = "0%"

@dataclass
class ArchitectureComponent:
    name: str
    parent_service: Optional[str]
    description: str
    technologies: List[str] = field(default_factory=list)
    responsibilities: List[str] = field(default_factory=list)
    interfaces: List[str] = field(default_factory=list)

@dataclass
class ArchitectureWorkflow:
    name: str
    description: str
    workflow_type: str
    trigger: str
    business_goal: str
    steps: List[str] = field(default_factory=list)
    inputs: List[str] = field(default_factory=list)
    outputs: List[str] = field(default_factory=list)
    participants: List[str] = field(default_factory=list)

@dataclass
class ArchitectureDataFlow:
    source: str
    sink: str
    producer_service: str
    consumer_service: str
    evidence: str
    name: str = ""
    steps: List[str] = field(default_factory=list)
    description: Optional[str] = None

@dataclass
class ArchitectureAPI:
    method: str
    path: str
    handler: str
    service: Optional[str]
    description: Optional[str] = None

@dataclass
class ArchitectureDatabase:
    name: str
    type: str
    operations: List[str] = field(default_factory=list)
    accessed_by: List[str] = field(default_factory=list)

@dataclass
class ArchitectureIntegration:
    source: str
    target: str
    integration_type: str # API, Event, Pub/Sub, Data
    description: Optional[str] = None
    purpose: str = "Unknown purpose"
    artifact: str = "Control flow / Default payload"
    confidence: str = "medium"

@dataclass
class ArchitectureDeploymentNode:
    node_type: str # Container, Serverless, VM, etc.
    name: str
    services_hosted: List[str] = field(default_factory=list)

@dataclass
class SecurityBoundary:
    name: str
    zone_type: str # Public, DMZ, Internal, Restricted
    components_included: List[str] = field(default_factory=list)
    description: Optional[str] = None

@dataclass
class ArchitectureBlueprint:
    repository_type: str
    architecture_pattern: Optional[str] = None
    architecture_pattern_confidence: Optional[str] = None
    architecture_pattern_evidence: Optional[str] = None
    capabilities: List[ArchitectureCapability] = field(default_factory=list)
    artifacts: List[ArchitectureArtifact] = field(default_factory=list)
    services: List[ArchitectureService] = field(default_factory=list)
    workflows: List[ArchitectureWorkflow] = field(default_factory=list)
    data_flows: List[ArchitectureDataFlow] = field(default_factory=list)
    apis: List[ArchitectureAPI] = field(default_factory=list)
    databases: List[ArchitectureDatabase] = field(default_factory=list)
    integrations: List[ArchitectureIntegration] = field(default_factory=list)
    components: List[ArchitectureComponent] = field(default_factory=list)
    deployment_nodes: List[ArchitectureDeploymentNode] = field(default_factory=list)
    security_boundaries: List[SecurityBoundary] = field(default_factory=list)
    
    metadata: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)
