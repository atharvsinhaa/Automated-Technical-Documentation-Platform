"""
dependency_extractor/models.py
────────────────────────────────────────────────────────────────
Immutable graph data models.

Design:
  - GraphNode  = vertex in the dependency graph
  - GraphEdge  = directed edge between two vertices
  - DependencyGraph = the complete graph (nodes + edges + metadata)

Node IDs are deterministic slugs derived from (type, name, file).
This makes the XML output stable across runs — critical for Neo4j
MERGE operations (idempotent graph loading).
"""

from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set


# ──────────────────────────────────────────────────────────────
#  NODE TYPES  (what a vertex represents)
# ──────────────────────────────────────────────────────────────

class NodeType:
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
    API_ENDPOINT     = "API_ENDPOINT"     # backend route definition
    API_CALL         = "API_CALL"         # HTTP call site
    SQL_TABLE        = "SQL_TABLE"
    SQL_QUERY        = "SQL_QUERY"
    REACT_COMPONENT  = "REACT_COMPONENT"
    REACT_HOOK       = "REACT_HOOK"
    SPARK_JOB        = "SPARK_JOB"
    DATAFRAME        = "DATAFRAME"
    SERVICE          = "SERVICE"          # @Service, @Injectable, etc.
    REPOSITORY       = "REPOSITORY"       # @Repository
    CONTROLLER       = "CONTROLLER"       # @Controller, @RestController
    DECORATOR        = "DECORATOR"
    LAMBDA           = "LAMBDA"
    PACKAGE          = "PACKAGE"          # Java package / Python module path
    IMPORT           = "IMPORT"


# ──────────────────────────────────────────────────────────────
#  EDGE / RELATION TYPES  (what a directed edge represents)
# ──────────────────────────────────────────────────────────────

class RelationType:
    # File / module structure
    CONTAINS         = "CONTAINS"         # FILE → FUNCTION, CLASS → METHOD
    DEFINES          = "DEFINES"          # FILE → CLASS, MODULE → FUNCTION
    IMPORTS          = "IMPORTS"          # FILE → FILE  (import statement)
    EXPORTS          = "EXPORTS"          # FILE → SYMBOL

    # Call graph
    CALLS            = "CALLS"            # FUNCTION → FUNCTION
    INVOKES          = "INVOKES"          # METHOD → METHOD (same class)
    CALLS_API        = "CALLS_API"        # COMPONENT/FUNCTION → API_ENDPOINT
    USES_API         = "USES_API"         # FILE → API_ENDPOINT

    # Class hierarchy
    EXTENDS          = "EXTENDS"          # CLASS → CLASS
    IMPLEMENTS       = "IMPLEMENTS"       # CLASS → INTERFACE
    INSTANTIATES     = "INSTANTIATES"     # FUNCTION → CLASS (new / constructor)

    # SQL / data
    QUERIES_TABLE    = "QUERIES_TABLE"    # FUNCTION → SQL_TABLE (SELECT)
    WRITES_TABLE     = "WRITES_TABLE"     # FUNCTION → SQL_TABLE (INSERT/UPDATE)
    CREATES_TABLE    = "CREATES_TABLE"    # DDL → SQL_TABLE
    READS_FROM       = "READS_FROM"       # SPARK_JOB → DATAFRAME
    WRITES_TO        = "WRITES_TO"        # SPARK_JOB → DATAFRAME

    # Data flow
    DEPENDS_ON       = "DEPENDS_ON"       # generic cross-file dependency
    REFERENCES       = "REFERENCES"       # soft reference (body_preview hit)
    RETURNS          = "RETURNS"          # FUNCTION → TYPE
    FLOWS_TO         = "FLOWS_TO"         # data flow edge

    # React
    RENDERS          = "RENDERS"          # COMPONENT → COMPONENT (JSX)
    USES_HOOK        = "USES_HOOK"        # COMPONENT → REACT_HOOK

    # Service / annotation
    ANNOTATED_BY     = "ANNOTATED_BY"     # CLASS → DECORATOR/ANNOTATION
    DEPENDS_ON_SERVICE = "DEPENDS_ON_SERVICE"  # SERVICE → SERVICE


# ──────────────────────────────────────────────────────────────
#  ID GENERATION  (deterministic, slug-based)
# ──────────────────────────────────────────────────────────────

_SLUG_RE = re.compile(r"[^a-z0-9_]")


def _slug(text: str) -> str:
    return _SLUG_RE.sub("_", text.lower()).strip("_")


def make_node_id(node_type: str, name: str, context: str = "") -> str:
    """
    Deterministic stable ID for a graph node.

    Examples:
      make_node_id("FILE",     "app.py")                   → "file__app_py"
      make_node_id("FUNCTION", "get_users", "user_service.py") → "func__get_users__user_service_py"
      make_node_id("SQL_TABLE","users")                    → "sql_table__users"
    """
    prefix_map = {
        "FILE":           "file",
        "MODULE":         "mod",
        "CLASS":          "cls",
        "INTERFACE":      "iface",
        "ENUM":           "enum",
        "FUNCTION":       "func",
        "ASYNC_FUNCTION": "afunc",
        "METHOD":         "meth",
        "CONSTRUCTOR":    "ctor",
        "API_ENDPOINT":   "api",
        "API_CALL":       "apicall",
        "SQL_TABLE":      "tbl",
        "SQL_QUERY":      "qry",
        "REACT_COMPONENT":"comp",
        "REACT_HOOK":     "hook",
        "SPARK_JOB":      "spark",
        "DATAFRAME":      "df",
        "SERVICE":        "svc",
        "REPOSITORY":     "repo",
        "CONTROLLER":     "ctrl",
        "VARIABLE":       "var",
        "CONSTANT":       "const",
        "PROPERTY":       "prop",
        "DECORATOR":      "dec",
        "LAMBDA":         "lam",
        "PACKAGE":        "pkg",
        "IMPORT":         "imp",
    }
    prefix = prefix_map.get(node_type, "node")
    parts = [prefix, _slug(name)]
    if context:
        parts.append(_slug(context))
    return "__".join(p for p in parts if p)


# ──────────────────────────────────────────────────────────────
#  DATA CLASSES
# ──────────────────────────────────────────────────────────────

@dataclass
class GraphNode:
    id:           str
    node_type:    str
    name:         str
    language:     str         = ""
    file_path:    str         = ""
    start_line:   int         = 0
    end_line:     int         = 0
    parent_id:    Optional[str] = None

    # Enrichment
    docstring:    Optional[str] = None
    return_type:  Optional[str] = None
    is_async:     bool          = False
    is_exported:  bool          = False
    annotations:  List[str]     = field(default_factory=list)
    modifiers:    List[str]     = field(default_factory=list)
    params:       List[str]     = field(default_factory=list)
    body_preview: Optional[str] = None

    # Graph metadata
    in_degree:    int = 0
    out_degree:   int = 0

    def __hash__(self):
        return hash(self.id)

    def __eq__(self, other):
        return isinstance(other, GraphNode) and self.id == other.id


@dataclass
class GraphEdge:
    from_id:      str
    to_id:        str
    relation:     str
    weight:       float         = 1.0
    confidence:   str           = "high"    # high | medium | low
    evidence:     Optional[str] = None
    line_number:  Optional[int] = None

    def __hash__(self):
        return hash((self.from_id, self.to_id, self.relation))

    def __eq__(self, other):
        return (isinstance(other, GraphEdge) and
                self.from_id == other.from_id and
                self.to_id   == other.to_id   and
                self.relation == other.relation)


@dataclass
class DependencyGraph:
    name:     str
    source:   str                                 # path to combined XML
    nodes:    Dict[str, GraphNode]  = field(default_factory=dict)
    edges:    Set[GraphEdge]        = field(default_factory=set)
    errors:   List[str]             = field(default_factory=list)

    # Stats cache
    _stats: Optional[Dict] = field(default=None, repr=False)

    def add_node(self, node: GraphNode) -> GraphNode:
        if node.id not in self.nodes:
            self.nodes[node.id] = node
        return self.nodes[node.id]

    def add_edge(self, edge: GraphEdge) -> bool:
        """Add edge only if both endpoints exist. Returns True if added."""
        if edge.from_id not in self.nodes or edge.to_id not in self.nodes:
            return False
        if edge.from_id == edge.to_id:
            return False   # no self-loops
        self.edges.add(edge)
        self.nodes[edge.from_id].out_degree += 1
        self.nodes[edge.to_id].in_degree   += 1
        return True

    def safe_add_edge(self, from_id: str, to_id: str, relation: str,
                      confidence: str = "high", evidence: str = "",
                      weight: float = 1.0) -> bool:
        return self.add_edge(GraphEdge(
            from_id=from_id, to_id=to_id, relation=relation,
            confidence=confidence, evidence=evidence, weight=weight,
        ))

    @property
    def node_count(self) -> int:
        return len(self.nodes)

    @property
    def edge_count(self) -> int:
        return len(self.edges)

    def stats(self) -> Dict:
        from collections import Counter
        return {
            "nodes":          self.node_count,
            "edges":          self.edge_count,
            "node_types":     dict(Counter(n.node_type for n in self.nodes.values())),
            "relation_types": dict(Counter(e.relation for e in self.edges)),
        }
