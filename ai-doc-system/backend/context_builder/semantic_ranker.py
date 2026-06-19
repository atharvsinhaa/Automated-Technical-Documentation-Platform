"""
context_builder/semantic_ranker.py
────────────────────────────────────────────────────────────────
Ranks extracted context nodes by semantic relevance to the target.

Multi-signal scoring: centrality, lineage proximity, business
importance, type weight, service affinity.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Set

from .models import ContextNode


class SemanticRanker:
    """Ranks ContextNodes by multi-signal relevance."""

    # Node type importance weights
    TYPE_WEIGHTS = {
        "API_ENDPOINT":     1.0,
        "API_CALL":         0.9,
        "CONTROLLER":       0.9,
        "SERVICE":          0.85,
        "MICROSERVICE":     0.85,
        "ASYNC_FUNCTION":   0.8,
        "FUNCTION":         0.75,
        "METHOD":           0.75,
        "CLASS":            0.7,
        "REACT_COMPONENT":  0.7,
        "SQL_TABLE":        0.7,
        "MONGO_COLLECTION": 0.7,
        "SPARK_JOB":        0.65,
        "CONSTRUCTOR":      0.6,
        "INTERFACE":        0.6,
        "ENUM":             0.55,
        "MODULE":           0.5,
        "FILE":             0.45,
        "IMPORT":           0.3,
        "VARIABLE":         0.3,
        "CONSTANT":         0.3,
        "PROPERTY":         0.3,
        "DECORATOR":        0.25,
        "LAMBDA":           0.25,
    }

    def __init__(
        self,
        centrality_weight:  float = 0.30,
        proximity_weight:   float = 0.25,
        business_weight:    float = 0.20,
        type_weight:        float = 0.15,
        service_weight:     float = 0.10,
    ):
        self.w_centrality = centrality_weight
        self.w_proximity = proximity_weight
        self.w_business = business_weight
        self.w_type = type_weight
        self.w_service = service_weight

    def rank_nodes(
        self,
        nodes: List[ContextNode],
        target: Optional[ContextNode] = None,
        flow_node_ids: Optional[Set[str]] = None,
    ) -> List[ContextNode]:
        """
        Score and rank nodes by relevance.

        Args:
            nodes: List of context nodes to rank
            target: The target node (for service/domain affinity)
            flow_node_ids: IDs of nodes in business flows (for business importance)
        """
        if not nodes:
            return []

        target_service = target.service_boundary if target else None
        target_domain = target.business_domain if target else None
        flow_ids = flow_node_ids or set()

        for node in nodes:
            score = 0.0

            # 1. Centrality (PageRank)
            score += self.w_centrality * min(node.centrality_score, 1.0)

            # 2. Lineage proximity (inverse hop distance)
            if node.hop_distance > 0:
                score += self.w_proximity * (1.0 / node.hop_distance)
            else:
                score += self.w_proximity * 1.0

            # 3. Business importance (in a business flow?)
            if node.id in flow_ids:
                score += self.w_business * 1.0
            elif node.business_domain:
                score += self.w_business * 0.5

            # 4. Type weight
            type_w = self.TYPE_WEIGHTS.get(node.node_type, 0.4)
            score += self.w_type * type_w

            # 5. Service affinity
            if target_service and node.service_boundary == target_service:
                score += self.w_service * 1.0
            elif target_domain and node.business_domain == target_domain:
                score += self.w_service * 0.5

            node.relevance_score = round(score, 6)

        # Sort descending by relevance
        nodes.sort(key=lambda n: n.relevance_score, reverse=True)
        return nodes

    def deduplicate(self, nodes: List[ContextNode]) -> List[ContextNode]:
        """Remove duplicate nodes by ID."""
        seen: Set[str] = set()
        unique = []
        for n in nodes:
            if n.id not in seen:
                seen.add(n.id)
                unique.append(n)
        return unique

    def top_k(self, nodes: List[ContextNode], k: int = 50) -> List[ContextNode]:
        """Keep top K nodes after ranking."""
        return nodes[:k]
