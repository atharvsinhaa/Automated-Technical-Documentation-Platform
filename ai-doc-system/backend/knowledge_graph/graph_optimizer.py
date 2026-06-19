"""
knowledge_graph/graph_optimizer.py
────────────────────────────────────────────────────────────────
Pre- and post-load graph optimization.

Pre-load optimizations (in-memory):
  - Orphan node removal
  - Edge deduplication
  - Property normalization
  - Degree recalculation

Post-load optimizations (Neo4j):
  - Duplicate node merge via APOC
  - Centrality pre-computation
  - Hub node identification

Graph profiling:
  - Degree distribution
  - Connected components
  - Relationship type distribution
  - Query performance estimates
"""

from __future__ import annotations

import math
from collections import Counter, defaultdict, deque
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from .models import KGNode, KGEdge, KnowledgeGraph, KGNodeType


# ──────────────────────────────────────────────────────────────
#  RESULT TYPES
# ──────────────────────────────────────────────────────────────

@dataclass
class OptimizationResult:
    """Result of pre-load optimization."""
    orphans_removed:     int = 0
    edges_deduplicated:  int = 0
    properties_cleaned:  int = 0
    final_node_count:    int = 0
    final_edge_count:    int = 0


@dataclass
class GraphProfile:
    """Comprehensive graph profile for performance analysis."""
    node_count:           int = 0
    edge_count:           int = 0
    connected_components: int = 0
    largest_component:    int = 0
    avg_degree:           float = 0.0
    max_in_degree:        int = 0
    max_out_degree:       int = 0
    max_in_node:          str = ""
    max_out_node:         str = ""
    density:              float = 0.0
    hub_nodes:            List[Dict[str, Any]] = field(default_factory=list)
    degree_distribution:  Dict[int, int] = field(default_factory=dict)
    type_distribution:    Dict[str, int] = field(default_factory=dict)
    relation_distribution: Dict[str, int] = field(default_factory=dict)
    language_distribution: Dict[str, int] = field(default_factory=dict)
    estimated_import_time_seconds: float = 0.0


# ══════════════════════════════════════════════════════════════
#  GRAPH OPTIMIZER
# ══════════════════════════════════════════════════════════════

class GraphOptimizer:
    """
    Pre- and post-load graph optimization.

    Usage:
        optimizer = GraphOptimizer()
        result = optimizer.optimize_pre_load(kg)
        profile = optimizer.generate_graph_profile(kg)
    """

    def __init__(self, verbose: bool = True):
        self.verbose = verbose

    # ── Pre-Load Optimization ────────────────────────────────

    def optimize_pre_load(
        self,
        kg: KnowledgeGraph,
        remove_orphans: bool = True,
        dedup_edges: bool = True,
        normalize_props: bool = True,
    ) -> OptimizationResult:
        """
        Optimize the in-memory graph before Neo4j loading.

        Modifications are in-place on the KnowledgeGraph.
        """
        result = OptimizationResult()
        self._log("[optimizer] Pre-load optimization…")

        # ── 1. Remove orphan nodes ───────────────────────────
        if remove_orphans:
            orphans = self._find_orphan_nodes(kg)
            for nid in orphans:
                del kg.nodes[nid]
            result.orphans_removed = len(orphans)
            if orphans:
                self._log(f"  → Removed {len(orphans)} orphan nodes")

        # ── 2. Deduplicate edges ─────────────────────────────
        if dedup_edges:
            before = len(kg.edges)
            unique_edges: Set[KGEdge] = set()
            for edge in kg.edges:
                unique_edges.add(edge)
            kg.edges = unique_edges
            result.edges_deduplicated = before - len(kg.edges)
            if result.edges_deduplicated:
                self._log(f"  → Deduplicated {result.edges_deduplicated} edges")

        # ── 3. Normalize properties ──────────────────────────
        if normalize_props:
            cleaned = self._normalize_properties(kg)
            result.properties_cleaned = cleaned
            if cleaned:
                self._log(f"  → Cleaned {cleaned} properties")

        # ── 4. Recalculate degrees ───────────────────────────
        self._recalculate_degrees(kg)

        # ── 5. Rebuild indexes ───────────────────────────────
        kg.rebuild_indexes()

        result.final_node_count = kg.node_count
        result.final_edge_count = kg.edge_count

        self._log(
            f"[optimizer] Final: {result.final_node_count} nodes, "
            f"{result.final_edge_count} edges"
        )

        return result

    def _find_orphan_nodes(self, kg: KnowledgeGraph) -> List[str]:
        """
        Find nodes with zero in+out degree.
        Exempt: FILE nodes (they may be empty but valid).
        """
        connected: Set[str] = set()
        for edge in kg.edges:
            connected.add(edge.from_id)
            connected.add(edge.to_id)

        orphans = []
        for nid, node in kg.nodes.items():
            if nid not in connected:
                if node.node_type not in (KGNodeType.FILE,):
                    orphans.append(nid)

        return orphans

    def _normalize_properties(self, kg: KnowledgeGraph) -> int:
        """Normalize node properties (truncation, null stripping)."""
        cleaned = 0
        for node in kg.nodes.values():
            # Truncate overlong strings
            if node.name and len(node.name) > 200:
                node.name = node.name[:200]
                cleaned += 1
            if node.docstring and len(node.docstring) > 500:
                node.docstring = node.docstring[:500]
                cleaned += 1
            if node.body_preview and len(node.body_preview) > 300:
                node.body_preview = node.body_preview[:300]
                cleaned += 1
            if node.return_type and len(node.return_type) > 100:
                node.return_type = node.return_type[:100]
                cleaned += 1

            # Strip empty string → None
            if node.docstring is not None and not node.docstring.strip():
                node.docstring = None
            if node.body_preview is not None and not node.body_preview.strip():
                node.body_preview = None

        return cleaned

    def _recalculate_degrees(self, kg: KnowledgeGraph):
        """Recalculate in/out degree for all nodes."""
        for node in kg.nodes.values():
            node.in_degree = 0
            node.out_degree = 0

        for edge in kg.edges:
            if edge.from_id in kg.nodes:
                kg.nodes[edge.from_id].out_degree += 1
            if edge.to_id in kg.nodes:
                kg.nodes[edge.to_id].in_degree += 1

    # ── Post-Load Optimization (Neo4j) ───────────────────────

    def generate_post_load_cypher(self, kg: KnowledgeGraph) -> str:
        """
        Generate APOC-powered post-load optimization Cypher.
        """
        lines: List[str] = [
            "// ============================================================",
            "// Post-Load Optimization",
            "// Run AFTER data loading",
            "// ============================================================",
            "",
            "// ── 1. Merge duplicate nodes by name+type ─────────────────",
            "// (Safe: only merges if same name, type, and file_path)",
            "CALL apoc.periodic.iterate(",
            "  'MATCH (n:CodeEntity)",
            "   WITH n.name AS name, n.node_type AS type, n.file_path AS fp,",
            "        collect(n) AS nodes",
            "   WHERE size(nodes) > 1",
            "   RETURN nodes',",
            "  'WITH nodes",
            "   CALL apoc.refactor.mergeNodes(nodes, {",
            "     properties: \"combine\",",
            "     mergeRels: true",
            "   }) YIELD node RETURN count(*)',",
            "  {batchSize: 100}",
            ");",
            "",
            "// ── 2. Pre-compute PageRank (if APOC GDS available) ───────",
            "// CALL gds.pageRank.write('kg_graph', {",
            "//   writeProperty: 'pagerank'",
            "// });",
            "",
            "// ── 3. Pre-compute Betweenness Centrality ─────────────────",
            "// CALL gds.betweenness.write('kg_graph', {",
            "//   writeProperty: 'betweenness'",
            "// });",
            "",
            "// ── 4. Warm up page cache ─────────────────────────────────",
            "CALL apoc.warmup.run(true, true, true);",
            "",
            "// ── 5. Compute summary statistics ─────────────────────────",
            "MATCH (n) RETURN labels(n) AS labels, count(n) AS cnt",
            "ORDER BY cnt DESC;",
            "",
            "MATCH ()-[r]->() RETURN type(r) AS rel, count(r) AS cnt",
            "ORDER BY cnt DESC;",
        ]

        return "\n".join(lines)

    # ── Graph Profiling ──────────────────────────────────────

    def generate_graph_profile(self, kg: KnowledgeGraph) -> GraphProfile:
        """
        Generate a comprehensive graph profile for performance analysis.
        """
        profile = GraphProfile()
        profile.node_count = kg.node_count
        profile.edge_count = kg.edge_count

        if kg.node_count == 0:
            return profile

        # ── Degree analysis ──────────────────────────────────
        in_degrees = [n.in_degree for n in kg.nodes.values()]
        out_degrees = [n.out_degree for n in kg.nodes.values()]
        total_degrees = [i + o for i, o in zip(in_degrees, out_degrees)]

        profile.avg_degree = sum(total_degrees) / len(total_degrees)
        profile.max_in_degree = max(in_degrees) if in_degrees else 0
        profile.max_out_degree = max(out_degrees) if out_degrees else 0

        # Find hub nodes
        for node in kg.nodes.values():
            if node.in_degree == profile.max_in_degree:
                profile.max_in_node = node.name
            if node.out_degree == profile.max_out_degree:
                profile.max_out_node = node.name

        # ── Degree distribution ──────────────────────────────
        profile.degree_distribution = dict(Counter(total_degrees))

        # ── Hub nodes (top 20 by total degree) ───────────────
        sorted_nodes = sorted(
            kg.nodes.values(),
            key=lambda n: n.in_degree + n.out_degree,
            reverse=True,
        )
        profile.hub_nodes = [
            {
                "id": n.id,
                "name": n.name,
                "type": n.node_type,
                "in_degree": n.in_degree,
                "out_degree": n.out_degree,
                "total_degree": n.in_degree + n.out_degree,
            }
            for n in sorted_nodes[:20]
        ]

        # ── Connected components ─────────────────────────────
        components = self._find_connected_components(kg)
        profile.connected_components = len(components)
        profile.largest_component = max(len(c) for c in components) if components else 0

        # ── Density ──────────────────────────────────────────
        n = kg.node_count
        if n > 1:
            profile.density = kg.edge_count / (n * (n - 1))
        else:
            profile.density = 0.0

        # ── Distributions ────────────────────────────────────
        profile.type_distribution = dict(
            Counter(n.node_type for n in kg.nodes.values())
        )
        profile.relation_distribution = dict(
            Counter(e.relation for e in kg.edges)
        )
        profile.language_distribution = dict(
            Counter(n.language for n in kg.nodes.values() if n.language)
        )

        # ── Import time estimate ─────────────────────────────
        # Rough: ~1000 nodes/sec, ~500 edges/sec with batching
        profile.estimated_import_time_seconds = (
            kg.node_count / 1000 + kg.edge_count / 500
        )

        self._log(
            f"[optimizer] Profile: {profile.node_count} nodes, "
            f"{profile.edge_count} edges, "
            f"{profile.connected_components} components, "
            f"avg degree {profile.avg_degree:.1f}, "
            f"density {profile.density:.6f}"
        )

        return profile

    def _find_connected_components(
        self,
        kg: KnowledgeGraph,
    ) -> List[Set[str]]:
        """Find connected components using BFS (undirected)."""
        visited: Set[str] = set()
        components: List[Set[str]] = []

        # Build undirected adjacency
        adj: Dict[str, Set[str]] = defaultdict(set)
        for edge in kg.edges:
            adj[edge.from_id].add(edge.to_id)
            adj[edge.to_id].add(edge.from_id)

        for node_id in kg.nodes:
            if node_id in visited:
                continue

            # BFS from this node
            component: Set[str] = set()
            queue = deque([node_id])
            visited.add(node_id)

            while queue:
                current = queue.popleft()
                component.add(current)
                for neighbor in adj.get(current, set()):
                    if neighbor not in visited and neighbor in kg.nodes:
                        visited.add(neighbor)
                        queue.append(neighbor)

            components.append(component)

        return components

    def _log(self, msg: str):
        if self.verbose:
            print(msg, flush=True)
