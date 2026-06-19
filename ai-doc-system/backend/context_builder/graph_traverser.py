"""
context_builder/graph_traverser.py
────────────────────────────────────────────────────────────────
Intelligent graph traversal strategies for context extraction.

Wraps Neo4jClient with higher-level traversal methods that
produce ContextNode/ContextEdge objects.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Set, Tuple

from .models import ContextNode, ContextEdge
from .neo4j_client import Neo4jClient
from .utils import safe_str


def _dict_to_context_node(d: Dict, hop: int = 0) -> ContextNode:
    """Convert a raw node dict to a ContextNode."""
    tags = d.get("semantic_tags", [])
    if isinstance(tags, str):
        tags = [tags]
    params = d.get("params", [])
    if isinstance(params, str):
        params = [params]

    return ContextNode(
        id=d.get("id", ""),
        node_type=d.get("node_type", ""),
        name=d.get("name", ""),
        file_path=d.get("file_path", ""),
        language=d.get("language", ""),
        hop_distance=hop,
        service_boundary=d.get("service_boundary"),
        business_domain=d.get("business_domain"),
        centrality_score=float(d.get("centrality_score", 0)),
        community_id=d.get("community_id"),
        docstring=safe_str(d.get("docstring"), 200),
        params=params[:10] if params else [],
        return_type=d.get("return_type"),
        body_preview=safe_str(d.get("body_preview"), 200),
        semantic_tags=tags[:5] if tags else [],
        start_line=int(d.get("start_line", 0)),
        end_line=int(d.get("end_line", 0)),
    )


def _dict_to_context_edge(d: Dict) -> ContextEdge:
    """Convert a raw edge dict to a ContextEdge."""
    return ContextEdge(
        from_name=d.get("from_name", ""),
        to_name=d.get("to_name", ""),
        relation=d.get("relation", ""),
        from_id=d.get("from_id", ""),
        to_id=d.get("to_id", ""),
        evidence=safe_str(d.get("evidence"), 150),
        confidence=d.get("confidence", "high"),
    )


class GraphTraverser:
    """
    High-level graph traversal producing ContextNode/ContextEdge.

    All methods accept a node_id and return lightweight context objects.
    """

    def __init__(self, client: Neo4jClient, verbose: bool = True):
        self.client = client
        self.verbose = verbose

    def expand_neighborhood(
        self,
        node_id: str,
        depth: int = 2,
        rel_types: Optional[List[str]] = None,
        limit: int = 80,
    ) -> Tuple[List[ContextNode], List[ContextEdge]]:
        """BFS expansion around a node."""
        result = self.client.get_neighborhood(node_id, depth, rel_types, limit)

        nodes = [_dict_to_context_node(d, hop=1) for d in result.get("nodes", [])]
        edges = [_dict_to_context_edge(d) for d in result.get("edges", [])]

        # Deduplicate nodes by ID
        seen: Set[str] = set()
        unique_nodes = []
        for n in nodes:
            if n.id not in seen:
                seen.add(n.id)
                unique_nodes.append(n)

        return unique_nodes[:limit], edges[:limit * 2]

    def trace_upstream(
        self,
        node_id: str,
        max_depth: int = 3,
        limit: int = 30,
    ) -> List[ContextNode]:
        """Follow incoming edges — who calls / depends on this?"""
        raw = self.client.get_upstream(node_id, max_depth, limit)
        return [_dict_to_context_node(d, hop=1) for d in raw]

    def trace_downstream(
        self,
        node_id: str,
        max_depth: int = 3,
        limit: int = 30,
    ) -> List[ContextNode]:
        """Follow outgoing edges — what does this call / depend on?"""
        raw = self.client.get_downstream(node_id, max_depth, limit)
        return [_dict_to_context_node(d, hop=1) for d in raw]

    def extract_community(
        self,
        community_id: int,
        limit: int = 30,
    ) -> List[ContextNode]:
        """Get all nodes in the same community cluster."""
        raw = self.client.get_community(community_id, limit)
        return [_dict_to_context_node(d) for d in raw]

    def extract_service_members(
        self,
        service_name: str,
        limit: int = 50,
    ) -> List[ContextNode]:
        """Get all nodes in a service cluster."""
        raw = self.client.get_service_cluster(service_name, limit)
        return [_dict_to_context_node(d) for d in raw]

    def get_outgoing_edges(self, node_id: str, rel_types: Optional[List[str]] = None) -> List[ContextEdge]:
        """Get outgoing edges from a node."""
        raw = self.client.get_edges_from(node_id, rel_types)
        return [_dict_to_context_edge(d) for d in raw]

    def get_incoming_edges(self, node_id: str, rel_types: Optional[List[str]] = None) -> List[ContextEdge]:
        """Get incoming edges to a node."""
        raw = self.client.get_edges_to(node_id, rel_types)
        return [_dict_to_context_edge(d) for d in raw]
