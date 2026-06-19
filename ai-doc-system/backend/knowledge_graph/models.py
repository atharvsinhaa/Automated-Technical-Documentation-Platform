"""
knowledge_graph/models.py
────────────────────────────────────────────────────────────────
Enterprise Knowledge Graph data models.

Extends Component 3's GraphNode/GraphEdge with KG-specific
enrichments for business-aware documentation, lineage, and
GraphRAG retrieval.

Design:
  - KGNode     = enriched graph vertex (code entity + business context)
  - KGEdge     = enriched directed edge (with lineage + data flow)
  - KnowledgeGraph  = complete enriched graph
  - BusinessFlow    = named sequence of nodes forming a business operation
  - ServiceCluster  = microservice boundary grouping
  - LineageChain    = ordered traversal path (API→Fn→SQL)

All IDs are compatible with Component 3's deterministic slug scheme
so MERGE operations remain idempotent across pipeline re-runs.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple
from collections import defaultdict


# ──────────────────────────────────────────────────────────────
#  NODE TYPES  (superset of Component 3 NodeType)
# ──────────────────────────────────────────────────────────────

class KGNodeType:
    """All node labels used in the knowledge graph."""

    # ── Code entities (from Component 3) ──────────────────────
    FILE             = "FILE"
    MODULE           = "MODULE"
    CLASS            = "CLASS"
    INTERFACE        = "INTERFACE"
    ENUM             = "ENUM"
    FUNCTION         = "FUNCTION"
    ASYNC_FUNCTION   = "ASYNC_FUNCTION"
    METHOD           = "METHOD"
    CONSTRUCTOR      = "CONSTRUCTOR"
    VARIABLE         = "VARIABLE"
    CONSTANT         = "CONSTANT"
    PROPERTY         = "PROPERTY"
    ASSIGNMENT       = "ASSIGNMENT"
    API_ENDPOINT     = "API_ENDPOINT"
    API_CALL         = "API_CALL"
    SQL_TABLE        = "SQL_TABLE"
    SQL_QUERY        = "SQL_QUERY"
    REACT_COMPONENT  = "REACT_COMPONENT"
    REACT_HOOK       = "REACT_HOOK"
    SPARK_JOB        = "SPARK_JOB"
    DATAFRAME        = "DATAFRAME"
    SERVICE          = "SERVICE"
    REPOSITORY       = "REPOSITORY"
    CONTROLLER       = "CONTROLLER"
    DECORATOR        = "DECORATOR"
    LAMBDA           = "LAMBDA"
    PACKAGE          = "PACKAGE"
    IMPORT           = "IMPORT"

    # ── Business / KG-enriched (Component 4 additions) ────────
    BUSINESS_FLOW    = "BUSINESS_FLOW"
    SERVICE_CLUSTER  = "SERVICE_CLUSTER"
    DATA_PIPELINE    = "DATA_PIPELINE"
    MODULE_BOUNDARY  = "MODULE_BOUNDARY"

    # ── Mongo/NoSQL (Component 4 semantic additions) ──────────
    MONGO_COLLECTION = "MONGO_COLLECTION"
    BSON_SCHEMA      = "BSON_SCHEMA"
    MONGO_QUERY      = "MONGO_QUERY"
    MONGO_PIPELINE   = "MONGO_PIPELINE"
    DOCUMENT_MODEL   = "DOCUMENT_MODEL"

    # ── Business Semantics (Component 4 semantic additions) ───
    BUSINESS_CAPABILITY = "BUSINESS_CAPABILITY"
    DOMAIN              = "DOMAIN"
    WORKFLOW            = "WORKFLOW"
    BUSINESS_EVENT      = "BUSINESS_EVENT"
    DOMAIN_SERVICE      = "DOMAIN_SERVICE"
    CAPABILITY_GROUP    = "CAPABILITY_GROUP"

    # ── Architecture HLD (Component 4 semantic additions) ─────
    MICROSERVICE      = "MICROSERVICE"
    BOUNDED_CONTEXT   = "BOUNDED_CONTEXT"
    DOMAIN_LAYER      = "DOMAIN_LAYER"
    INFRA_COMPONENT   = "INFRA_COMPONENT"
    EVENT_BUS         = "EVENT_BUS"

    # ── Label hierarchy mapping (for Neo4j multi-label) ───────
    LABEL_HIERARCHY: Dict[str, List[str]] = {
        # Code entities
        "FILE":             ["CodeEntity", "File"],
        "MODULE":           ["CodeEntity", "Module"],
        "CLASS":            ["CodeEntity", "Class"],
        "INTERFACE":        ["CodeEntity", "Interface"],
        "ENUM":             ["CodeEntity", "Enum"],
        "FUNCTION":         ["CodeEntity", "Function"],
        "ASYNC_FUNCTION":   ["CodeEntity", "AsyncFunction"],
        "METHOD":           ["CodeEntity", "Method"],
        "CONSTRUCTOR":      ["CodeEntity", "Constructor"],
        "VARIABLE":         ["CodeEntity", "Variable"],
        "CONSTANT":         ["CodeEntity", "Constant"],
        "PROPERTY":         ["CodeEntity", "Property"],
        "ASSIGNMENT":       ["CodeEntity", "Assignment"],
        "DECORATOR":        ["CodeEntity", "Decorator"],
        "LAMBDA":           ["CodeEntity", "Lambda"],
        "IMPORT":           ["CodeEntity", "Import"],
        "PACKAGE":          ["CodeEntity", "Package"],
        # API entities
        "API_ENDPOINT":     ["CodeEntity", "APIEndpoint"],
        "API_CALL":         ["CodeEntity", "APICall"],
        # Data entities
        "SQL_TABLE":        ["DataEntity", "SQLTable"],
        "SQL_QUERY":        ["DataEntity", "SQLQuery"],
        "DATAFRAME":        ["DataEntity", "DataFrame"],
        # Frontend entities
        "REACT_COMPONENT":  ["CodeEntity", "ReactComponent"],
        "REACT_HOOK":       ["CodeEntity", "ReactHook"],
        # Infrastructure entities
        "SPARK_JOB":        ["CodeEntity", "SparkJob"],
        "SERVICE":          ["CodeEntity", "Service"],
        "REPOSITORY":       ["CodeEntity", "Repository"],
        "CONTROLLER":       ["CodeEntity", "Controller"],
        # Business entities (Component 4)
        "BUSINESS_FLOW":    ["BusinessEntity", "BusinessFlow"],
        "SERVICE_CLUSTER":  ["BusinessEntity", "ServiceCluster"],
        "DATA_PIPELINE":    ["BusinessEntity", "DataPipeline"],
        "MODULE_BOUNDARY":  ["BusinessEntity", "ModuleBoundary"],
        
        # Mongo/NoSQL entities
        "MONGO_COLLECTION": ["DataEntity", "MongoCollection", "NoSQL"],
        "BSON_SCHEMA":      ["DataEntity", "BsonSchema", "NoSQL"],
        "MONGO_QUERY":      ["DataEntity", "MongoQuery", "NoSQL"],
        "MONGO_PIPELINE":   ["DataEntity", "MongoPipeline", "NoSQL"],
        "DOCUMENT_MODEL":   ["DataEntity", "DocumentModel", "NoSQL"],

        # True Business Semantics
        "BUSINESS_CAPABILITY": ["BusinessEntity", "BusinessCapability"],
        "DOMAIN":              ["BusinessEntity", "Domain"],
        "WORKFLOW":            ["BusinessEntity", "Workflow"],
        "BUSINESS_EVENT":      ["BusinessEntity", "BusinessEvent"],
        "DOMAIN_SERVICE":      ["BusinessEntity", "DomainService"],
        "CAPABILITY_GROUP":    ["BusinessEntity", "CapabilityGroup"],

        # Architecture (HLD)
        "MICROSERVICE":      ["ArchitectureEntity", "Microservice"],
        "BOUNDED_CONTEXT":   ["ArchitectureEntity", "BoundedContext"],
        "DOMAIN_LAYER":      ["ArchitectureEntity", "DomainLayer"],
        "INFRA_COMPONENT":   ["ArchitectureEntity", "InfraComponent"],
        "EVENT_BUS":         ["ArchitectureEntity", "EventBus"],
    }

    @classmethod
    def neo4j_labels(cls, node_type: str) -> List[str]:
        """Return Neo4j labels for a given node type."""
        return cls.LABEL_HIERARCHY.get(node_type, ["CodeEntity", node_type])

    @classmethod
    def all_types(cls) -> List[str]:
        """Return all known node types."""
        return list(cls.LABEL_HIERARCHY.keys())


# ──────────────────────────────────────────────────────────────
#  RELATION TYPES  (superset of Component 3 RelationType)
# ──────────────────────────────────────────────────────────────

class KGRelationType:
    """All relationship types used in the knowledge graph."""

    # ── Structural (from Component 3) ─────────────────────────
    CONTAINS           = "CONTAINS"
    DEFINES            = "DEFINES"
    IMPORTS            = "IMPORTS"
    EXPORTS            = "EXPORTS"

    # ── Call graph ────────────────────────────────────────────
    CALLS              = "CALLS"
    INVOKES            = "INVOKES"
    CALLS_API          = "CALLS_API"
    USES_API           = "USES_API"
    RETURNS_RESPONSE   = "RETURNS_RESPONSE"
    ACCEPTS_PAYLOAD    = "ACCEPTS_PAYLOAD"
    RETURNS_PAYLOAD    = "RETURNS_PAYLOAD"

    # ── Class hierarchy / Control Flow ───────────────────────
    EXTENDS            = "EXTENDS"
    IMPLEMENTS         = "IMPLEMENTS"
    INSTANTIATES       = "INSTANTIATES"
    CONTROL_FLOW       = "CONTROL_FLOW"
    EXECUTES_AFTER     = "EXECUTES_AFTER"
    INVOKES_METHOD     = "INVOKES_METHOD"
    RETURNS_TO         = "RETURNS_TO"

    # ── SQL / data ───────────────────────────────────────────
    QUERIES_TABLE      = "QUERIES_TABLE"
    WRITES_TABLE       = "WRITES_TABLE"
    CREATES_TABLE      = "CREATES_TABLE"
    READS_FROM         = "READS_FROM"
    WRITES_TO          = "WRITES_TO"
    
    # ── NoSQL / Mongo ────────────────────────────────────────
    READS_COLLECTION      = "READS_COLLECTION"
    WRITES_COLLECTION     = "WRITES_COLLECTION"
    AGGREGATES_COLLECTION = "AGGREGATES_COLLECTION"
    LOOKUP_COLLECTION     = "LOOKUP_COLLECTION"
    UPDATES_DOCUMENT      = "UPDATES_DOCUMENT"
    INDEXES_COLLECTION    = "INDEXES_COLLECTION"

    # ── Data flow & Events ───────────────────────────────────
    DEPENDS_ON         = "DEPENDS_ON"
    REFERENCES         = "REFERENCES"
    RETURNS            = "RETURNS"
    FLOWS_TO           = "FLOWS_TO"
    TRANSFORMS         = "TRANSFORMS"
    FILTERS            = "FILTERS"
    AGGREGATES         = "AGGREGATES"
    JOINS_WITH         = "JOINS_WITH"
    ENRICHES           = "ENRICHES"
    STREAMS_TO         = "STREAMS_TO"
    PRODUCES_EVENT     = "PRODUCES_EVENT"
    CONSUMES_EVENT     = "CONSUMES_EVENT"
    PUBLISHES_TO_TOPIC = "PUBLISHES_TO_TOPIC"
    SUBSCRIBES_TO_TOPIC = "SUBSCRIBES_TO_TOPIC"

    # ── React ────────────────────────────────────────────────
    RENDERS            = "RENDERS"
    USES_HOOK          = "USES_HOOK"

    # ── Annotation / service ─────────────────────────────────
    ANNOTATED_BY       = "ANNOTATED_BY"
    DEPENDS_ON_SERVICE = "DEPENDS_ON_SERVICE"

    # ── Business / KG-enriched (Component 4 additions) ────────
    BELONGS_TO_SERVICE     = "BELONGS_TO_SERVICE"
    PARTICIPATES_IN_FLOW   = "PARTICIPATES_IN_FLOW"
    FEEDS_DATA_TO          = "FEEDS_DATA_TO"
    TRIGGERS_ASYNC         = "TRIGGERS_ASYNC"
    EXPOSES_API            = "EXPOSES_API"
    INVOKES_API            = "INVOKES_API"
    OWNS_MODULE            = "OWNS_MODULE"
    INTERACTS_WITH_SERVICE = "INTERACTS_WITH_SERVICE"
    INVOKES_SERVICE        = "INVOKES_SERVICE"
    TRIGGERS_WORKFLOW      = "TRIGGERS_WORKFLOW"

    # ── Architecture mapping (Phase 2 additions) ──────────────
    PUBLISHES_TO           = "PUBLISHES_TO"
    SUBSCRIBES_FROM        = "SUBSCRIBES_FROM"
    MAPS_TO                = "MAPS_TO"


    @classmethod
    def all_types(cls) -> List[str]:
        """Return all known relation types."""
        return [
            v for k, v in vars(cls).items()
            if not k.startswith("_") and isinstance(v, str) and k == k.upper()
        ]


# ──────────────────────────────────────────────────────────────
#  ID GENERATION  (compatible with Component 3)
# ──────────────────────────────────────────────────────────────

_SLUG_RE = re.compile(r"[^a-z0-9_]")


def _slug(text: str) -> str:
    return _SLUG_RE.sub("_", text.lower()).strip("_")


def make_kg_node_id(node_type: str, name: str, context: str = "") -> str:
    """
    Deterministic stable ID for a knowledge graph node.
    Compatible with Component 3's make_node_id scheme.
    """
    prefix_map = {
        "FILE":             "file",
        "MODULE":           "mod",
        "CLASS":            "cls",
        "INTERFACE":        "iface",
        "ENUM":             "enum",
        "FUNCTION":         "func",
        "ASYNC_FUNCTION":   "afunc",
        "METHOD":           "meth",
        "CONSTRUCTOR":      "ctor",
        "API_ENDPOINT":     "api",
        "API_CALL":         "apicall",
        "SQL_TABLE":        "tbl",
        "SQL_QUERY":        "qry",
        "REACT_COMPONENT":  "comp",
        "REACT_HOOK":       "hook",
        "SPARK_JOB":        "spark",
        "DATAFRAME":        "df",
        "SERVICE":          "svc",
        "REPOSITORY":       "repo",
        "CONTROLLER":       "ctrl",
        "VARIABLE":         "var",
        "CONSTANT":         "const",
        "PROPERTY":         "prop",
        "DECORATOR":        "dec",
        "LAMBDA":           "lam",
        "PACKAGE":          "pkg",
        "IMPORT":           "imp",
        # Component 4 additions
        "BUSINESS_FLOW":    "flow",
        "SERVICE_CLUSTER":  "cluster",
        "DATA_PIPELINE":    "pipeline",
        "MODULE_BOUNDARY":  "boundary",
        "MONGO_COLLECTION": "mongo",
        "BSON_SCHEMA":      "bson",
        "MONGO_QUERY":      "mquery",
        "MONGO_PIPELINE":   "mpipeline",
        "DOCUMENT_MODEL":   "docmodel",
        "BUSINESS_CAPABILITY": "bizcap",
        "DOMAIN":           "domain",
        "WORKFLOW":         "workflow",
        "BUSINESS_EVENT":   "bizevent",
        "DOMAIN_SERVICE":   "domainsvc",
        "CAPABILITY_GROUP": "capgrp",
        "MICROSERVICE":     "msvc",
        "BOUNDED_CONTEXT":  "bcontext",
        "DOMAIN_LAYER":     "layer",
        "INFRA_COMPONENT":  "infra",
        "EVENT_BUS":        "ebus",
    }
    prefix = prefix_map.get(node_type, "node")
    parts = [prefix, _slug(name)]
    if context:
        parts.append(_slug(context))
    return "__".join(p for p in parts if p)


# ──────────────────────────────────────────────────────────────
#  DATA CLASSES — KG-Enriched Node
# ──────────────────────────────────────────────────────────────

@dataclass
class KGNode:
    """
    Knowledge Graph node — enriched vertex with business context.

    Compatible with Component 3's GraphNode but adds:
      - service_boundary: which microservice owns this node
      - business_domain:  business domain tag (auth, payments, etc.)
      - complexity_score: 0.0–1.0 normalized complexity
      - semantic_tags:    auto-discovered semantic labels
      - community_id:     cluster/community from graph analysis
    """
    id:               str
    node_type:        str
    name:             str
    language:         str         = ""
    file_path:        str         = ""
    start_line:       int         = 0
    end_line:         int         = 0
    parent_id:        Optional[str] = None

    # Component 3 enrichment
    docstring:        Optional[str] = None
    return_type:      Optional[str] = None
    is_async:         bool          = False
    is_exported:      bool          = False
    annotations:      List[str]     = field(default_factory=list)
    modifiers:        List[str]     = field(default_factory=list)
    params:           List[str]     = field(default_factory=list)
    body_preview:     Optional[str] = None

    # Degree (from Component 3)
    in_degree:        int = 0
    out_degree:       int = 0

    # ── Component 4 KG enrichments ───────────────────────────
    service_boundary: Optional[str] = None
    business_domain:  Optional[str] = None
    complexity_score: float         = 0.0
    semantic_tags:    List[str]     = field(default_factory=list)
    community_id:     Optional[int] = None
    
    # ── GraphRAG Metadata (Component 4 semantic additions) ───
    semantic_chunk:   Optional[str] = None
    centrality_score: float         = 0.0
    embedding_model:  Optional[str] = None

    def __hash__(self):
        return hash(self.id)

    def __eq__(self, other):
        return isinstance(other, KGNode) and self.id == other.id

    @property
    def neo4j_labels(self) -> List[str]:
        """Get Neo4j multi-labels for this node."""
        return KGNodeType.neo4j_labels(self.node_type)

    @property
    def neo4j_label_string(self) -> str:
        """Get Neo4j label string like ':CodeEntity:Function'."""
        return ":" + ":".join(self.neo4j_labels)

    def to_props_dict(self) -> Dict[str, Any]:
        """Convert node to a property dictionary for Cypher."""
        props: Dict[str, Any] = {
            "id":              self.id,
            "name":            (self.name or "")[:200],
            "language":        self.language,
            "file_path":       self.file_path,
            "start_line":      self.start_line,
            "end_line":        self.end_line,
            "is_async":        self.is_async,
            "is_exported":     self.is_exported,
            "in_degree":       self.in_degree,
            "out_degree":      self.out_degree,
            "node_type":       self.node_type,
            "complexity_score": self.complexity_score,
        }
        if self.docstring:
            props["docstring"] = self.docstring[:500]
        if self.return_type:
            props["return_type"] = self.return_type[:100]
        if self.body_preview:
            props["body_preview"] = self.body_preview[:300]
        if self.parent_id:
            props["parent_id"] = self.parent_id
        if self.annotations:
            props["annotations"] = self.annotations[:20]
        if self.params:
            props["params"] = self.params[:30]
        if self.modifiers:
            props["modifiers"] = self.modifiers[:20]
        if self.service_boundary:
            props["service_boundary"] = self.service_boundary
        if self.business_domain:
            props["business_domain"] = self.business_domain
        if self.semantic_tags:
            props["semantic_tags"] = self.semantic_tags[:10]
        if self.community_id is not None:
            props["community_id"] = self.community_id
        if self.semantic_chunk:
            props["semantic_chunk"] = self.semantic_chunk
        if self.centrality_score:
            props["centrality_score"] = self.centrality_score
        if self.embedding_model:
            props["embedding_model"] = self.embedding_model
        return props


# ──────────────────────────────────────────────────────────────
#  DATA CLASSES — KG-Enriched Edge
# ──────────────────────────────────────────────────────────────

@dataclass
class KGEdge:
    """
    Knowledge Graph edge — enriched directed relationship.

    Extends Component 3's GraphEdge with:
      - lineage_type:        what kind of lineage this edge participates in
      - data_flow_direction: upstream/downstream indicator
      - business_context:    human-readable context for documentation
    """
    from_id:          str
    to_id:            str
    relation:         str
    weight:           float         = 1.0
    confidence:       str           = "high"      # high | medium | low
    evidence:         Optional[str] = None
    line_number:      Optional[int] = None

    # ── Component 4 KG enrichments ───────────────────────────
    lineage_type:        Optional[str] = None     # api | sql | data | import
    data_flow_direction: Optional[str] = None     # upstream | downstream
    business_context:    Optional[str] = None

    def __hash__(self):
        return hash((self.from_id, self.to_id, self.relation))

    def __eq__(self, other):
        return (isinstance(other, KGEdge) and
                self.from_id  == other.from_id and
                self.to_id    == other.to_id   and
                self.relation == other.relation)

    def to_props_dict(self) -> Dict[str, Any]:
        """Convert edge to a property dictionary for Cypher."""
        props: Dict[str, Any] = {
            "confidence": self.confidence,
            "weight":     self.weight,
        }
        if self.evidence:
            props["evidence"] = (self.evidence or "")[:250]
        if self.line_number is not None:
            props["line_number"] = self.line_number
        if self.lineage_type:
            props["lineage_type"] = self.lineage_type
        if self.data_flow_direction:
            props["data_flow_direction"] = self.data_flow_direction
        if self.business_context:
            props["business_context"] = (self.business_context or "")[:300]
        return props


# ──────────────────────────────────────────────────────────────
#  BUSINESS FLOW — named operation path
# ──────────────────────────────────────────────────────────────

@dataclass
class FlowSummary:
    """Human-readable summary of a business flow."""
    flow_id:        str
    flow_name:      str
    description:    str
    entry_point:    str              # API endpoint or trigger
    exit_points:    List[str]        # data stores or response
    node_count:     int
    languages:      List[str]
    services:       List[str]
    tables_touched: List[str]


@dataclass
class BusinessFlow:
    """
    A named sequence of connected nodes representing a
    business operation (e.g., 'User Registration Flow').

    Traces from API endpoint → handler → business logic
    → data access → response/side-effects.
    """
    flow_id:          str
    flow_name:        str
    flow_type:        str             # api_flow | data_flow | event_flow
    entry_node_id:    str
    node_ids:         List[str]       = field(default_factory=list)
    edge_relations:   List[str]       = field(default_factory=list)
    confidence:       str             = "high"
    description:      Optional[str]   = None

    def to_kg_node(self) -> KGNode:
        """Create a virtual BUSINESS_FLOW node for the graph."""
        return KGNode(
            id=self.flow_id,
            node_type=KGNodeType.BUSINESS_FLOW,
            name=self.flow_name,
            language="multi",
            docstring=self.description,
            semantic_tags=[self.flow_type],
        )


# ──────────────────────────────────────────────────────────────
#  SERVICE CLUSTER — microservice boundary
# ──────────────────────────────────────────────────────────────

@dataclass
class ServiceCluster:
    """
    A group of files/classes belonging to a single microservice
    or logical module boundary.
    """
    cluster_id:       str
    cluster_name:     str
    detection_method: str              # directory | annotation | package | config
    root_path:        str              # directory root
    file_paths:       List[str]        = field(default_factory=list)
    node_ids:         List[str]        = field(default_factory=list)
    languages:        Set[str]         = field(default_factory=set)
    api_endpoints:    List[str]        = field(default_factory=list)
    tables_accessed:  List[str]        = field(default_factory=list)
    confidence:       str              = "high"

    def to_kg_node(self) -> KGNode:
        """Create a virtual SERVICE_CLUSTER node for the graph."""
        return KGNode(
            id=self.cluster_id,
            node_type=KGNodeType.SERVICE_CLUSTER,
            name=self.cluster_name,
            language=",".join(sorted(self.languages)) if self.languages else "multi",
            file_path=self.root_path,
            docstring=f"Service: {self.cluster_name} ({len(self.file_paths)} files)",
            semantic_tags=[self.detection_method],
        )


# ──────────────────────────────────────────────────────────────
#  LINEAGE CHAIN — ordered traversal path
# ──────────────────────────────────────────────────────────────

@dataclass
class LineageChain:
    """
    An ordered path through the graph representing data lineage,
    API call chain, or import dependency chain.
    """
    chain_id:         str
    chain_type:       str              # api | sql | data | import
    ordered_node_ids: List[str]        = field(default_factory=list)
    hop_relations:    List[str]        = field(default_factory=list)
    confidence:       str              = "high"
    description:      Optional[str]    = None

    @property
    def depth(self) -> int:
        return len(self.ordered_node_ids)

    @property
    def source_id(self) -> Optional[str]:
        return self.ordered_node_ids[0] if self.ordered_node_ids else None

    @property
    def sink_id(self) -> Optional[str]:
        return self.ordered_node_ids[-1] if self.ordered_node_ids else None


# ──────────────────────────────────────────────────────────────
#  GRAPH PARTITION — bounded chunk of the graph
# ──────────────────────────────────────────────────────────────

@dataclass
class GraphPartition:
    """
    Represents a bounded sub-section of the knowledge graph,
    partitioned by service, directory, or domain.
    """
    partition_id:     str
    partition_name:   str
    strategy:         str              # service | directory | domain | fixed
    node_ids:         Set[str]         = field(default_factory=set)
    edge_count:       int              = 0
    content_hash:     str              = ""        # SHA-256 for incremental diff
    root_path:        str              = ""
    timestamp:        str              = ""
    cross_partition_edge_count: int    = 0


@dataclass
class PartitionManifest:
    """
    Registry of all partitions in a graph build.
    Tracks state for incremental updates.
    """
    graph_name:           str
    total_nodes:          int              = 0
    total_edges:          int              = 0
    partition_strategy:   str              = "auto"
    partitions:           List[GraphPartition] = field(default_factory=list)
    cross_partition_edges: int             = 0
    build_timestamp:      str              = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "graph_name":           self.graph_name,
            "total_nodes":          self.total_nodes,
            "total_edges":          self.total_edges,
            "partition_strategy":   self.partition_strategy,
            "cross_partition_edges": self.cross_partition_edges,
            "build_timestamp":      self.build_timestamp,
            "partitions": [
                {
                    "partition_id":   p.partition_id,
                    "partition_name": p.partition_name,
                    "strategy":       p.strategy,
                    "node_count":     len(p.node_ids),
                    "edge_count":     p.edge_count,
                    "content_hash":   p.content_hash,
                    "root_path":      p.root_path,
                    "cross_partition_edge_count": p.cross_partition_edge_count,
                }
                for p in self.partitions
            ],
        }


@dataclass
class DeltaOperation:
    """
    Represents one incremental change operation.
    """
    op_type:    str              # add | modify | delete
    entity_type: str             # node | edge
    target_id:  str
    payload:    Optional[Dict[str, Any]] = None


# ──────────────────────────────────────────────────────────────
#  KNOWLEDGE GRAPH — complete enriched graph
# ──────────────────────────────────────────────────────────────

@dataclass
class KnowledgeGraph:
    """
    Complete enterprise knowledge graph with business-aware
    enrichments, lineage, and service boundaries.
    """
    name:             str
    source:           str                                   # path to input XML
    nodes:            Dict[str, KGNode]   = field(default_factory=dict)
    edges:            Set[KGEdge]         = field(default_factory=set)
    errors:           List[str]           = field(default_factory=list)

    # Business enrichments
    business_flows:   List[BusinessFlow]      = field(default_factory=list)
    service_clusters: List[ServiceCluster]    = field(default_factory=list)
    lineage_chains:   List[LineageChain]      = field(default_factory=list)

    # Adjacency indexes (built post-load)
    _outgoing:  Dict[str, List[KGEdge]] = field(default_factory=lambda: defaultdict(list), repr=False)
    _incoming:  Dict[str, List[KGEdge]] = field(default_factory=lambda: defaultdict(list), repr=False)

    # Stats cache
    _stats: Optional[Dict] = field(default=None, repr=False)

    # ── Mutation ─────────────────────────────────────────────

    def add_node(self, node: KGNode) -> KGNode:
        """Add a node (deduplicates by ID)."""
        if node.id not in self.nodes:
            self.nodes[node.id] = node
        return self.nodes[node.id]

    def add_edge(self, edge: KGEdge) -> bool:
        """Add edge only if both endpoints exist. Returns True if added."""
        if edge.from_id not in self.nodes or edge.to_id not in self.nodes:
            return False
        if edge.from_id == edge.to_id:
            return False  # no self-loops
        if edge in self.edges:
            return False  # already exists
        self.edges.add(edge)
        self._outgoing[edge.from_id].append(edge)
        self._incoming[edge.to_id].append(edge)
        self.nodes[edge.from_id].out_degree += 1
        self.nodes[edge.to_id].in_degree   += 1
        self._stats = None  # invalidate cache
        return True

    def safe_add_edge(
        self,
        from_id: str,
        to_id: str,
        relation: str,
        confidence: str = "high",
        evidence: str = "",
        weight: float = 1.0,
        lineage_type: Optional[str] = None,
        business_context: Optional[str] = None,
    ) -> bool:
        """Safe edge addition with all parameters."""
        return self.add_edge(KGEdge(
            from_id=from_id, to_id=to_id, relation=relation,
            confidence=confidence, evidence=evidence, weight=weight,
            lineage_type=lineage_type, business_context=business_context,
        ))

    # ── Traversal ────────────────────────────────────────────

    def outgoing_edges(self, node_id: str) -> List[KGEdge]:
        """Get all outgoing edges from a node."""
        return self._outgoing.get(node_id, [])

    def incoming_edges(self, node_id: str) -> List[KGEdge]:
        """Get all incoming edges to a node."""
        return self._incoming.get(node_id, [])

    def neighbors(self, node_id: str, direction: str = "out") -> List[str]:
        """Get neighbor node IDs (out, in, or both)."""
        result = []
        if direction in ("out", "both"):
            result.extend(e.to_id for e in self._outgoing.get(node_id, []))
        if direction in ("in", "both"):
            result.extend(e.from_id for e in self._incoming.get(node_id, []))
        return result

    def nodes_by_type(self, node_type: str) -> List[KGNode]:
        """Get all nodes of a specific type."""
        return [n for n in self.nodes.values() if n.node_type == node_type]

    def edges_by_relation(self, relation: str) -> List[KGEdge]:
        """Get all edges of a specific relation type."""
        return [e for e in self.edges if e.relation == relation]

    def subgraph(self, node_ids: Set[str]) -> "KnowledgeGraph":
        """Extract a subgraph containing only the specified nodes and their connecting edges."""
        sub = KnowledgeGraph(name=f"{self.name}_subgraph", source=self.source)
        for nid in node_ids:
            if nid in self.nodes:
                sub.add_node(self.nodes[nid])
        for edge in self.edges:
            if edge.from_id in node_ids and edge.to_id in node_ids:
                sub.add_edge(edge)
        return sub

    # ── Partitioning ─────────────────────────────────────────

    def partition_by_service(self) -> List[GraphPartition]:
        """
        Partition the graph by service boundary.
        Nodes without a service_boundary go into a '__default__' partition.
        """
        groups: Dict[str, Set[str]] = defaultdict(set)
        for nid, node in self.nodes.items():
            key = node.service_boundary or "__default__"
            groups[key].add(nid)

        partitions = []
        for svc_name, nids in groups.items():
            p = GraphPartition(
                partition_id=_slug(f"svc_{svc_name}"),
                partition_name=svc_name,
                strategy="service",
                node_ids=nids,
            )
            p.content_hash = self._hash_node_ids(nids)
            # Count intra-partition edges
            p.edge_count = sum(
                1 for e in self.edges
                if e.from_id in nids and e.to_id in nids
            )
            partitions.append(p)

        return partitions

    def partition_by_directory(self, depth: int = 1) -> List[GraphPartition]:
        """
        Partition the graph by top-level directory.
        `depth` controls how many path segments to use as the key.
        """
        groups: Dict[str, Set[str]] = defaultdict(set)
        for nid, node in self.nodes.items():
            fp = node.file_path or ""
            parts = fp.split("/")
            key = "/".join(parts[:depth]) if len(parts) >= depth else "__root__"
            groups[key].add(nid)

        partitions = []
        for dir_name, nids in groups.items():
            p = GraphPartition(
                partition_id=_slug(f"dir_{dir_name}"),
                partition_name=dir_name,
                strategy="directory",
                node_ids=nids,
                root_path=dir_name,
            )
            p.content_hash = self._hash_node_ids(nids)
            p.edge_count = sum(
                1 for e in self.edges
                if e.from_id in nids and e.to_id in nids
            )
            partitions.append(p)

        return partitions

    def compute_content_hash(self) -> str:
        """Compute a SHA-256 hash of the full graph for change detection."""
        return self._hash_node_ids(set(self.nodes.keys()))

    def _hash_node_ids(self, node_ids: Set[str]) -> str:
        """Hash a set of node IDs deterministically."""
        h = hashlib.sha256()
        for nid in sorted(node_ids):
            node = self.nodes.get(nid)
            if node:
                h.update(f"{nid}|{node.node_type}|{node.name}|{node.file_path}".encode())
        return h.hexdigest()[:16]

    def rebuild_indexes(self):
        """Rebuild adjacency indexes from edges set."""
        self._outgoing = defaultdict(list)
        self._incoming = defaultdict(list)
        for edge in self.edges:
            self._outgoing[edge.from_id].append(edge)
            self._incoming[edge.to_id].append(edge)

    # ── Properties ───────────────────────────────────────────

    @property
    def node_count(self) -> int:
        return len(self.nodes)

    @property
    def edge_count(self) -> int:
        return len(self.edges)

    def stats(self) -> Dict:
        """Compute and cache basic graph statistics."""
        if self._stats is None:
            from collections import Counter
            self._stats = {
                "nodes":            self.node_count,
                "edges":            self.edge_count,
                "node_types":       dict(Counter(n.node_type for n in self.nodes.values())),
                "relation_types":   dict(Counter(e.relation for e in self.edges)),
                "languages":        dict(Counter(n.language for n in self.nodes.values() if n.language)),
                "business_flows":   len(self.business_flows),
                "service_clusters": len(self.service_clusters),
                "lineage_chains":   len(self.lineage_chains),
            }
        return self._stats

    def cross_partition_edges(self, partitions: List[GraphPartition]) -> List[KGEdge]:
        """Find edges that span across different partitions."""
        node_to_partition: Dict[str, str] = {}
        for p in partitions:
            for nid in p.node_ids:
                node_to_partition[nid] = p.partition_id

        cross = []
        for edge in self.edges:
            src_p = node_to_partition.get(edge.from_id)
            tgt_p = node_to_partition.get(edge.to_id)
            if src_p and tgt_p and src_p != tgt_p:
                cross.append(edge)
        return cross

    # ── Serialization ────────────────────────────────────────

    @classmethod
    def from_dict(cls, data: Dict) -> "KnowledgeGraph":
        """
        Load a KnowledgeGraph from a dict (parsed from JSON).

        Expected JSON structure:
            {
                "metadata": {"name": "...", "node_count": ..., ...},
                "nodes": [{"id": ..., "node_type": ..., "name": ..., ...}, ...],
                "edges": [{"from_id": ..., "to_id": ..., "relation": ..., ...}, ...],
            }
        """
        meta = data.get("metadata", {})
        name = meta.get("name", "loaded_graph")

        kg = cls(name=name, source="json")

        # Parse nodes
        for nd in data.get("nodes", []):
            node = KGNode(
                id=nd.get("id", ""),
                node_type=nd.get("node_type", nd.get("type", "")),
                name=nd.get("name", ""),
                language=nd.get("language", ""),
                file_path=nd.get("file_path", ""),
                start_line=nd.get("start_line", 0),
                end_line=nd.get("end_line", 0),
                is_async=nd.get("is_async", False),
                is_exported=nd.get("is_exported", False),
                in_degree=0,
                out_degree=0,
                parent_id=nd.get("parent_id"),
                return_type=nd.get("return_type"),
                docstring=nd.get("docstring"),
                body_preview=nd.get("body_preview"),
                params=nd.get("params", []),
                annotations=nd.get("annotations", []),
                modifiers=nd.get("modifiers", []),
                service_boundary=nd.get("service_boundary"),
                business_domain=nd.get("business_domain"),
                complexity_score=nd.get("complexity_score", 0),
                semantic_tags=nd.get("semantic_tags", []),
                community_id=nd.get("community_id"),
            )
            if node.id:
                kg.nodes[node.id] = node

        # Parse edges
        for ed in data.get("edges", []):
            edge = KGEdge(
                from_id=ed.get("from_id", ""),
                to_id=ed.get("to_id", ""),
                relation=ed.get("relation", ""),
                weight=float(ed.get("weight", 1.0)),
                confidence=ed.get("confidence", "high"),
                evidence=ed.get("evidence"),
                line_number=ed.get("line_number"),
                lineage_type=ed.get("lineage_type"),
                business_context=ed.get("business_context"),
            )
            if edge.from_id and edge.to_id:
                kg.add_edge(edge)

        return kg

