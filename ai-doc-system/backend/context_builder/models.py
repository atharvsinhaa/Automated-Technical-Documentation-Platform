"""
context_builder/models.py
────────────────────────────────────────────────────────────────
Data models for the Enterprise Context Builder (Component 5).

Defines the query specification, intermediate context structures,
and the final LLM-ready prompt payload.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ──────────────────────────────────────────────────────────────
#  INPUT: What the user is asking about
# ──────────────────────────────────────────────────────────────

@dataclass
class ContextQuery:
    """
    Specifies what context to extract from the knowledge graph.

    At least one of the target fields must be set.
    """
    # ── Target identifiers (set one or more) ─────────────────
    target_file:    Optional[str] = None     # e.g. "billing_service.py"
    service:        Optional[str] = None     # e.g. "BillingService"
    api:            Optional[str] = None     # e.g. "/api/v1/recharge"
    workflow:       Optional[str] = None     # e.g. "Recharge Flow"
    domain:         Optional[str] = None     # e.g. "Charging & Billing"
    module:         Optional[str] = None     # e.g. "auth"
    node_id:        Optional[str] = None     # direct node ID

    # ── Traversal parameters ─────────────────────────────────
    depth:          int   = 2                # max hop distance
    token_budget:   int   = 8000             # max estimated tokens in output
    include_source: bool  = True             # include source code?

    # ── Prompt generation ────────────────────────────────────
    prompt_type:    Optional[str] = None     # documentation|hld|lld|code-comment|architecture|business

    @property
    def has_target(self) -> bool:
        return any([
            self.target_file, self.service, self.api,
            self.workflow, self.domain, self.module, self.node_id,
        ])

    @property
    def target_description(self) -> str:
        """Human-readable description of the query target."""
        parts = []
        if self.target_file: parts.append(f"file={self.target_file}")
        if self.service:     parts.append(f"service={self.service}")
        if self.api:         parts.append(f"api={self.api}")
        if self.workflow:    parts.append(f"workflow={self.workflow}")
        if self.domain:      parts.append(f"domain={self.domain}")
        if self.module:      parts.append(f"module={self.module}")
        if self.node_id:     parts.append(f"node_id={self.node_id}")
        return ", ".join(parts) or "unspecified"


# ──────────────────────────────────────────────────────────────
#  INTERMEDIATE: Lightweight context representations
# ──────────────────────────────────────────────────────────────

@dataclass
class ContextNode:
    """Lightweight node for context — no full graph data."""
    id:              str
    node_type:       str
    name:            str
    file_path:       str            = ""
    language:        str            = ""
    relevance_score: float          = 0.0
    hop_distance:    int            = 0
    summary:         str            = ""
    service_boundary: Optional[str] = None
    business_domain: Optional[str]  = None
    centrality_score: float         = 0.0
    community_id:    Optional[int]  = None
    docstring:       Optional[str]  = None
    params:          List[str]      = field(default_factory=list)
    return_type:     Optional[str]  = None
    body_preview:    Optional[str]  = None
    semantic_tags:   List[str]      = field(default_factory=list)
    start_line:      int            = 0
    end_line:        int            = 0

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "id": self.id,
            "type": self.node_type,
            "name": self.name,
        }
        if self.file_path:       d["file_path"] = self.file_path
        if self.language:        d["language"] = self.language
        if self.summary:         d["summary"] = self.summary
        if self.service_boundary: d["service"] = self.service_boundary
        if self.business_domain: d["domain"] = self.business_domain
        if self.docstring:       d["docstring"] = self.docstring[:200]
        if self.params:          d["params"] = self.params[:10]
        if self.return_type:     d["return_type"] = self.return_type
        if self.semantic_tags:   d["tags"] = self.semantic_tags[:5]
        d["relevance"] = round(self.relevance_score, 4)
        return d


@dataclass
class ContextEdge:
    """Lightweight edge for context."""
    from_name:  str
    to_name:    str
    relation:   str
    from_id:    str     = ""
    to_id:      str     = ""
    evidence:   str     = ""
    confidence: str     = "high"

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "from": self.from_name,
            "to": self.to_name,
            "relation": self.relation,
        }
        if self.evidence:
            d["evidence"] = self.evidence[:150]
        return d


# ──────────────────────────────────────────────────────────────
#  CONTEXT SECTION MODELS
# ──────────────────────────────────────────────────────────────

@dataclass
class ArchitectureContext:
    """Architecture-level context for the target."""
    service:            Optional[str]      = None
    bounded_context:    Optional[str]      = None
    architecture_layer: Optional[str]      = None
    microservice:       Optional[str]      = None
    event_buses:        List[Dict]         = field(default_factory=list)
    data_pipelines:     List[str]          = field(default_factory=list)
    inter_service_deps: List[Dict]         = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {}
        if self.service:            d["service"] = self.service
        if self.bounded_context:    d["bounded_context"] = self.bounded_context
        if self.architecture_layer: d["layer"] = self.architecture_layer
        if self.microservice:       d["microservice"] = self.microservice
        if self.event_buses:        d["event_buses"] = self.event_buses
        if self.data_pipelines:     d["data_pipelines"] = self.data_pipelines
        if self.inter_service_deps: d["service_dependencies"] = self.inter_service_deps
        return d


@dataclass
class BusinessContext:
    """Business-level context."""
    flows:           List[Dict]     = field(default_factory=list)
    capabilities:    List[str]      = field(default_factory=list)
    workflow_steps:  List[str]      = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {}
        if self.flows:          d["business_flows"] = self.flows
        if self.capabilities:   d["capabilities"] = self.capabilities
        if self.workflow_steps: d["workflow_steps"] = self.workflow_steps
        return d


@dataclass
class TelecomContext:
    """Telecom domain context."""
    domain:         Optional[str]   = None
    sub_domain:     Optional[str]   = None
    tmf_apis:       List[str]       = field(default_factory=list)
    related_nodes:  List[str]       = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {}
        if self.domain:        d["telecom_domain"] = self.domain
        if self.sub_domain:    d["sub_domain"] = self.sub_domain
        if self.tmf_apis:      d["tmf_apis"] = self.tmf_apis
        if self.related_nodes: d["related_telecom_nodes"] = self.related_nodes
        return d


@dataclass
class LineageContext:
    """Data lineage context."""
    sql_tables:        List[Dict]   = field(default_factory=list)
    mongo_collections: List[Dict]   = field(default_factory=list)
    api_lineage:       List[Dict]   = field(default_factory=list)
    event_lineage:     List[Dict]   = field(default_factory=list)
    import_chain:      List[str]    = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {}
        if self.sql_tables:        d["sql_tables"] = self.sql_tables
        if self.mongo_collections: d["mongo_collections"] = self.mongo_collections
        if self.api_lineage:       d["api_lineage"] = self.api_lineage
        if self.event_lineage:     d["event_lineage"] = self.event_lineage
        if self.import_chain:      d["import_chain"] = self.import_chain
        return d


@dataclass
class WorkflowContext:
    """Workflow execution context."""
    workflow_name:  Optional[str]   = None
    steps:          List[Dict]      = field(default_factory=list)
    entry_point:    Optional[str]   = None
    exit_points:    List[str]       = field(default_factory=list)
    control_flow:   List[Dict]      = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {}
        if self.workflow_name: d["workflow_name"] = self.workflow_name
        if self.steps:         d["steps"] = self.steps
        if self.entry_point:   d["entry_point"] = self.entry_point
        if self.exit_points:   d["exit_points"] = self.exit_points
        if self.control_flow:  d["control_flow"] = self.control_flow
        return d


# ──────────────────────────────────────────────────────────────
#  OUTPUT: Full assembled context
# ──────────────────────────────────────────────────────────────

@dataclass
class ContextResult:
    """The complete assembled context for a target."""
    # ── Target ───────────────────────────────────────────────
    query:              ContextQuery
    target_node:        Optional[ContextNode]     = None

    # ── Semantic sections ────────────────────────────────────
    architecture:       ArchitectureContext        = field(default_factory=ArchitectureContext)
    business:           BusinessContext            = field(default_factory=BusinessContext)
    telecom:            TelecomContext             = field(default_factory=TelecomContext)
    lineage:            LineageContext             = field(default_factory=LineageContext)
    workflow:           WorkflowContext            = field(default_factory=WorkflowContext)

    # ── Graph neighborhood ───────────────────────────────────
    neighbors:          List[ContextNode]          = field(default_factory=list)
    edges:              List[ContextEdge]          = field(default_factory=list)

    # ── Source code ──────────────────────────────────────────
    source_code:        Optional[str]              = None
    related_functions:  List[Dict]                 = field(default_factory=list)

    # ── Metadata ─────────────────────────────────────────────
    estimated_tokens:   int                        = 0
    node_count:         int                        = 0
    edge_count:         int                        = 0

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a compact JSON-safe dictionary."""
        result: Dict[str, Any] = {
            "target": self.target_node.to_dict() if self.target_node else {},
            "query": {
                "target": self.query.target_description,
                "depth": self.query.depth,
                "token_budget": self.query.token_budget,
            },
        }

        # Add non-empty sections
        arch = self.architecture.to_dict()
        if arch: result["architecture"] = arch

        biz = self.business.to_dict()
        if biz: result["business"] = biz

        tel = self.telecom.to_dict()
        if tel: result["telecom"] = tel

        lin = self.lineage.to_dict()
        if lin: result["lineage"] = lin

        wf = self.workflow.to_dict()
        if wf: result["workflow"] = wf

        if self.neighbors:
            result["semantic_neighbors"] = [
                n.to_dict() for n in self.neighbors[:30]
            ]

        if self.edges:
            result["relationships"] = [
                e.to_dict() for e in self.edges[:50]
            ]

        if self.source_code:
            result["source_code"] = self.source_code

        if self.related_functions:
            result["related_functions"] = self.related_functions[:15]

        result["metadata"] = {
            "estimated_tokens": self.estimated_tokens,
            "nodes_extracted": self.node_count,
            "edges_extracted": self.edge_count,
        }

        return result


# ──────────────────────────────────────────────────────────────
#  OUTPUT: LLM-ready prompt
# ──────────────────────────────────────────────────────────────

@dataclass
class PromptPayload:
    """Final LLM-ready prompt with context."""
    prompt_type:      str
    system_prompt:    str
    user_prompt:      str
    context_json:     Dict[str, Any]    = field(default_factory=dict)
    estimated_tokens: int               = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "prompt_type": self.prompt_type,
            "system_prompt": self.system_prompt,
            "user_prompt": self.user_prompt,
            "context": self.context_json,
            "estimated_tokens": self.estimated_tokens,
        }
