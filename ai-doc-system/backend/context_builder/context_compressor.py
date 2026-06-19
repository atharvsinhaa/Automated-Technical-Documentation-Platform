"""
context_builder/context_compressor.py
────────────────────────────────────────────────────────────────
Assembles all context sections and compresses to fit within
the token budget. Deduplicates, groups, and trims intelligently.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from .models import (
    ContextResult, ContextNode, ContextEdge, ContextQuery,
    ArchitectureContext, BusinessContext, TelecomContext,
    LineageContext, WorkflowContext,
)
from .token_estimator import TokenEstimator
from .semantic_ranker import SemanticRanker


class ContextCompressor:
    """
    Assembles all context sections and compresses to budget.
    """

    def __init__(self, verbose: bool = True):
        self.verbose = verbose
        self.estimator = TokenEstimator()
        self.ranker = SemanticRanker()

    def compress(
        self,
        query: ContextQuery,
        target_node: Optional[ContextNode],
        architecture: ArchitectureContext,
        business: BusinessContext,
        telecom: TelecomContext,
        lineage: LineageContext,
        workflow: WorkflowContext,
        neighbors: List[ContextNode],
        edges: List[ContextEdge],
        source_code: Optional[str],
        related_functions: List[Dict],
    ) -> ContextResult:
        """
        Assemble and compress all context into a ContextResult.
        """
        budget = query.token_budget

        # 1. Deduplicate neighbors
        neighbors = self.ranker.deduplicate(neighbors)

        # 2. Rank neighbors
        flow_ids = set()
        for f in business.flows:
            fn = f.get("flow_name", "")
            if fn:
                flow_ids.add(fn)
        neighbors = self.ranker.rank_nodes(neighbors, target_node, flow_ids)

        # 3. Build the result
        result = ContextResult(
            query=query,
            target_node=target_node,
            architecture=architecture,
            business=business,
            telecom=telecom,
            lineage=lineage,
            workflow=workflow,
            neighbors=neighbors,
            edges=edges,
            source_code=source_code,
            related_functions=related_functions,
            node_count=len(neighbors) + (1 if target_node else 0),
            edge_count=len(edges),
        )

        # 4. Estimate tokens and trim if needed
        result_dict = result.to_dict()
        estimated = self.estimator.estimate_dict_tokens(result_dict)

        if estimated > budget:
            if self.verbose:
                print(f"[compressor] Over budget: {estimated} > {budget} tokens. Trimming…")

            # Trim neighbors first (lowest priority)
            max_neighbors = max(5, len(neighbors) // 2)
            while estimated > budget and max_neighbors > 3:
                result.neighbors = result.neighbors[:max_neighbors]
                result_dict = result.to_dict()
                estimated = self.estimator.estimate_dict_tokens(result_dict)
                max_neighbors = max_neighbors // 2

            # Trim edges
            max_edges = max(10, len(edges) // 2)
            while estimated > budget and max_edges > 5:
                result.edges = result.edges[:max_edges]
                result_dict = result.to_dict()
                estimated = self.estimator.estimate_dict_tokens(result_dict)
                max_edges = max_edges // 2

            # Trim related functions
            if estimated > budget and result.related_functions:
                result.related_functions = result.related_functions[:3]
                result_dict = result.to_dict()
                estimated = self.estimator.estimate_dict_tokens(result_dict)

            # Trim source code
            if estimated > budget and result.source_code:
                lines = result.source_code.split("\n")
                half = max(20, len(lines) // 2)
                result.source_code = "\n".join(lines[:half]) + "\n... [truncated]"
                result_dict = result.to_dict()
                estimated = self.estimator.estimate_dict_tokens(result_dict)

            if self.verbose:
                print(f"[compressor] After trimming: {estimated} tokens")

        result.estimated_tokens = estimated

        if self.verbose:
            print(
                f"[compressor] Context: {result.node_count} nodes, "
                f"{result.edge_count} edges, ~{estimated} tokens"
            )

        return result
