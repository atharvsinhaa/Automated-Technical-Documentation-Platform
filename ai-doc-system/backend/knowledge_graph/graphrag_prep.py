"""
knowledge_graph/graphrag_prep.py
────────────────────────────────────────────────────────────────
Enterprise GraphRAG Preparation Layer.

Computes network centrality (PageRank approximation), builds
hierarchical semantic text chunks, and generates retrieval indexes
for offline vector embedding and hybrid GraphRAG queries.

All computation is pure Python — no external ML deps required.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Set

from .models import (
    KnowledgeGraph, KGNode,
    KGNodeType, KGRelationType,
)


class GraphRAGPrep:
    """
    Prepares graph nodes for semantic retrieval and embedding.

    Usage:
        prep = GraphRAGPrep()
        prep.prepare(kg)
    """

    def __init__(
        self,
        embedding_model: str = "intfloat/multilingual-e5-large",
        pagerank_iterations: int = 20,
        pagerank_damping: float = 0.85,
        verbose: bool = True,
    ):
        self.embedding_model = embedding_model
        self.pagerank_iterations = pagerank_iterations
        self.pagerank_damping = pagerank_damping
        self.verbose = verbose

    def prepare(self, kg: KnowledgeGraph) -> int:
        """
        Full preparation pass:
        1. Compute PageRank centrality
        2. Build hierarchical semantic chunks
        3. Set embedding model marker

        Returns the number of nodes prepared.
        """
        # Step 1: PageRank
        scores = self._compute_pagerank(kg)

        # Apply scores
        max_score = max(scores.values()) if scores else 1.0
        if max_score == 0:
            max_score = 1.0

        for nid, score in scores.items():
            node = kg.nodes.get(nid)
            if node:
                node.centrality_score = round(score / max_score, 6)

        # Step 2: Build semantic chunks
        prepared = 0
        for node in kg.nodes.values():
            chunk = self._build_hierarchical_chunk(node, kg)
            if chunk:
                node.semantic_chunk = chunk
                node.embedding_model = self.embedding_model
                prepared += 1

        if self.verbose:
            print(f"[graphrag] Prepared {prepared} nodes for semantic embedding.")
            top_5 = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:5]
            for nid, score in top_5:
                name = kg.nodes[nid].name if nid in kg.nodes else nid
                print(f"  Top PageRank: {name} = {score:.4f}")

        return prepared

    def generate_retrieval_indexes(
        self, kg: KnowledgeGraph, output_dir: str,
    ):
        """
        Generate retrieval index files for GraphRAG:
          - chunk_index.json: flat list of (node_id, chunk_text, centrality)
          - neighborhood_index.json: 2-hop neighborhood summaries
        """
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)

        # Chunk index
        chunk_index = []
        for node in kg.nodes.values():
            if not node.semantic_chunk:
                continue
            chunk_index.append({
                "node_id": node.id,
                "node_type": node.node_type,
                "name": node.name,
                "file_path": node.file_path,
                "chunk_text": node.semantic_chunk,
                "centrality": node.centrality_score,
                "language": node.language,
            })

        (out / "chunk_index.json").write_text(
            json.dumps(chunk_index, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )

        # Neighborhood index (2-hop summary for top nodes)
        neighborhood_index = []
        top_nodes = sorted(
            kg.nodes.values(),
            key=lambda n: n.centrality_score,
            reverse=True,
        )[:200]  # Top 200 by centrality

        for node in top_nodes:
            neighbors_1 = self._get_neighborhood(node.id, kg, depth=1)
            neighbors_2 = self._get_neighborhood(node.id, kg, depth=2)

            summary = self._build_neighborhood_summary(node, neighbors_1, neighbors_2, kg)
            neighborhood_index.append({
                "node_id": node.id,
                "name": node.name,
                "node_type": node.node_type,
                "centrality": node.centrality_score,
                "hop1_count": len(neighbors_1),
                "hop2_count": len(neighbors_2),
                "neighborhood_summary": summary,
            })

        (out / "neighborhood_index.json").write_text(
            json.dumps(neighborhood_index, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )

        if self.verbose:
            print(
                f"[graphrag] Indexes: chunk={len(chunk_index)} entries, "
                f"neighborhood={len(neighborhood_index)} entries → {out}"
            )

    # ── PageRank ─────────────────────────────────────────────

    def _compute_pagerank(self, kg: KnowledgeGraph) -> Dict[str, float]:
        """
        Approximate PageRank via power iteration.
        Pure Python — no numpy/networkx required.
        """
        N = len(kg.nodes)
        if N == 0:
            return {}

        d = self.pagerank_damping
        node_ids = list(kg.nodes.keys())
        scores: Dict[str, float] = {nid: 1.0 / N for nid in node_ids}

        # Precompute outgoing counts
        out_count: Dict[str, int] = defaultdict(int)
        for edge in kg.edges:
            out_count[edge.from_id] += 1

        # Power iteration
        for iteration in range(self.pagerank_iterations):
            new_scores: Dict[str, float] = {}
            dangling_sum = sum(
                scores[nid] for nid in node_ids if out_count[nid] == 0
            )

            for nid in node_ids:
                rank = (1.0 - d) / N + d * dangling_sum / N

                # Incoming contributions
                for edge in kg.incoming_edges(nid):
                    from_id = edge.from_id
                    if from_id in scores and out_count[from_id] > 0:
                        rank += d * scores[from_id] / out_count[from_id]

                new_scores[nid] = rank

            scores = new_scores

        return scores

    # ── Chunk Building ───────────────────────────────────────

    def _build_hierarchical_chunk(self, node: KGNode, kg: KnowledgeGraph) -> str:
        """
        Build a hierarchical semantic text chunk for a node.

        Structure:
          [Type] Name (Language)
          File: path
          Description: docstring
          Called by: ...
          Calls: ...
          Service: boundary
          Domain: business_domain
          Tags: semantic_tags
        """
        parts: List[str] = []

        # Identity
        parts.append(f"[{node.node_type}] {node.name}")
        if node.language:
            parts.append(f"Language: {node.language}")
        if node.file_path:
            parts.append(f"File: {node.file_path}")

        # Description
        if node.docstring:
            parts.append(f"Description: {node.docstring[:300]}")
        if node.body_preview:
            parts.append(f"Preview: {node.body_preview[:200]}")

        # Parameters
        if node.params:
            parts.append(f"Parameters: {', '.join(node.params[:10])}")
        if node.return_type:
            parts.append(f"Returns: {node.return_type}")

        # Relationship context
        callers = []
        for edge in kg.incoming_edges(node.id):
            if edge.relation in (KGRelationType.CALLS, KGRelationType.CALLS_API):
                caller = kg.nodes.get(edge.from_id)
                if caller:
                    callers.append(caller.name)
        if callers:
            parts.append(f"Called by: {', '.join(callers[:10])}")

        callees = []
        for edge in kg.outgoing_edges(node.id):
            if edge.relation in (KGRelationType.CALLS, KGRelationType.CALLS_API):
                callee = kg.nodes.get(edge.to_id)
                if callee:
                    callees.append(callee.name)
        if callees:
            parts.append(f"Calls: {', '.join(callees[:10])}")

        # Business context
        if node.service_boundary:
            parts.append(f"Service: {node.service_boundary}")
        if node.business_domain:
            parts.append(f"Domain: {node.business_domain}")

        # Tags
        if node.semantic_tags:
            parts.append(f"Tags: {', '.join(node.semantic_tags[:10])}")

        return " | ".join(parts) if parts else ""

    # ── Neighborhood ─────────────────────────────────────────

    def _get_neighborhood(
        self, node_id: str, kg: KnowledgeGraph, depth: int = 1,
    ) -> Set[str]:
        """Get node IDs within N hops (BFS)."""
        visited: Set[str] = set()
        frontier = {node_id}

        for _ in range(depth):
            next_frontier: Set[str] = set()
            for nid in frontier:
                for edge in kg.outgoing_edges(nid):
                    if edge.to_id not in visited:
                        next_frontier.add(edge.to_id)
                for edge in kg.incoming_edges(nid):
                    if edge.from_id not in visited:
                        next_frontier.add(edge.from_id)
            visited |= frontier
            frontier = next_frontier - visited

        visited |= frontier
        visited.discard(node_id)
        return visited

    def _build_neighborhood_summary(
        self, node: KGNode,
        neighbors_1: Set[str], neighbors_2: Set[str],
        kg: KnowledgeGraph,
    ) -> str:
        """Build a text summary of a node's neighborhood."""
        from collections import Counter
        types_1 = Counter(
            kg.nodes[nid].node_type for nid in neighbors_1 if nid in kg.nodes
        )
        types_2 = Counter(
            kg.nodes[nid].node_type for nid in neighbors_2 if nid in kg.nodes
        )

        parts = [f"{node.name} ({node.node_type})"]
        parts.append(f"1-hop: {len(neighbors_1)} neighbors ({dict(types_1.most_common(5))})")
        parts.append(f"2-hop: {len(neighbors_2)} neighbors ({dict(types_2.most_common(5))})")

        # Notable neighbors
        notable = []
        for nid in list(neighbors_1)[:5]:
            n = kg.nodes.get(nid)
            if n:
                notable.append(f"{n.name}({n.node_type})")
        if notable:
            parts.append(f"Notable: {', '.join(notable)}")

        return " | ".join(parts)
