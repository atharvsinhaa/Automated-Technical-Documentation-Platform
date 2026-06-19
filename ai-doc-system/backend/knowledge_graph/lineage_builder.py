"""
knowledge_graph/lineage_builder.py
────────────────────────────────────────────────────────────────
Builds complete lineage chains across the knowledge graph.

Lineage types:
  - API lineage:    endpoint → handler → business logic → data stores
  - SQL lineage:    function → table read/write chains
  - Data lineage:   Spark source → transformations → sink
  - Import lineage: transitive import closure

All chains are stored as LineageChain objects and can be
materialized as graph edges for traversal optimization.
"""

from __future__ import annotations

import re
from collections import defaultdict, deque
from typing import Dict, List, Optional, Set, Tuple

from .models import (
    KGNode, KGEdge, KnowledgeGraph, LineageChain,
    KGNodeType, KGRelationType, make_kg_node_id,
)


# ══════════════════════════════════════════════════════════════
#  LINEAGE BUILDER
# ══════════════════════════════════════════════════════════════

class LineageBuilder:
    """
    Builds lineage chains across the knowledge graph.

    Usage:
        builder = LineageBuilder()
        api_chains = builder.build_api_lineage(kg)
        sql_chains = builder.build_sql_lineage(kg)
        data_chains = builder.build_data_flow_lineage(kg)
        builder.enrich_graph_with_lineage(kg, api_chains + sql_chains)
    """

    def __init__(self, verbose: bool = True, max_chain_depth: int = 15):
        self.verbose = verbose
        self.max_chain_depth = max_chain_depth

    # ── API Lineage ──────────────────────────────────────────

    def build_api_lineage(
        self,
        kg: KnowledgeGraph,
        max_chains_per_endpoint: int = 50,
    ) -> List[LineageChain]:
        """
        Trace lineage from API endpoints through handler chains
        to data stores (SQL tables, DataFrames, etc.).

        Uses BFS with visited tracking (not backtracking DFS)
        to avoid combinatorial explosion on dense call graphs.

        Returns ordered chains: [endpoint → handler → ... → table]
        """
        chains: List[LineageChain] = []

        target_types = {KGNodeType.SQL_TABLE, KGNodeType.DATAFRAME, KGNodeType.MONGO_COLLECTION, KGNodeType.EVENT_BUS}
        follow_relations = {
            KGRelationType.CALLS, KGRelationType.INVOKES,
            KGRelationType.QUERIES_TABLE, KGRelationType.WRITES_TABLE,
            KGRelationType.READS_FROM, KGRelationType.WRITES_TO,
            KGRelationType.DEPENDS_ON, KGRelationType.READS_COLLECTION,
            KGRelationType.WRITES_COLLECTION, KGRelationType.PUBLISHES_TO_TOPIC,
            KGRelationType.CALLS_API, KGRelationType.INVOKES_SERVICE,
        }

        # Find all API endpoint nodes
        api_nodes = kg.nodes_by_type(KGNodeType.API_ENDPOINT)

        for api_node in api_nodes:
            # Find handlers (nodes that DEFINE this endpoint)
            handlers = []
            for edge in kg.incoming_edges(api_node.id):
                if edge.relation in (KGRelationType.DEFINES, KGRelationType.EXPOSES_API):
                    handlers.append(edge.from_id)

            if not handlers:
                continue

            # BFS from handlers to find reachable data sinks
            visited: Set[str] = {api_node.id}
            visited.update(handlers)
            # parent map for path reconstruction
            parent: Dict[str, Tuple[str, str]] = {}  # child → (parent, relation)
            queue = deque(handlers)

            sinks_found: List[str] = []
            depth = 0
            level_queue = list(handlers)

            while level_queue and depth < self.max_chain_depth:
                next_level: List[str] = []
                for node_id in level_queue:
                    for edge in kg.outgoing_edges(node_id):
                        if edge.to_id in visited:
                            continue
                        if edge.relation not in follow_relations:
                            continue
                        visited.add(edge.to_id)
                        parent[edge.to_id] = (node_id, edge.relation)
                        next_level.append(edge.to_id)

                        target_node = kg.nodes.get(edge.to_id)
                        if target_node and target_node.node_type in target_types:
                            sinks_found.append(edge.to_id)
                level_queue = next_level
                depth += 1

            # Reconstruct paths from API endpoint to each sink
            ep_chains = 0
            for sink_id in sinks_found:
                if ep_chains >= max_chains_per_endpoint:
                    break
                # Walk back from sink to handler
                path_rev = [sink_id]
                rels_rev = []
                current = sink_id
                while current in parent:
                    p, rel = parent[current]
                    path_rev.append(p)
                    rels_rev.append(rel)
                    current = p

                path = [api_node.id] + list(reversed(path_rev))
                rels = [KGRelationType.DEFINES] + list(reversed(rels_rev))

                chain_id = make_kg_node_id(
                    "DATA_PIPELINE", f"api_{len(chains)}"
                )
                chains.append(LineageChain(
                    chain_id=chain_id,
                    chain_type="api",
                    ordered_node_ids=path,
                    hop_relations=rels,
                    confidence="high" if len(path) <= 5 else "medium",
                    description=f"API lineage: {api_node.name} → {kg.nodes.get(sink_id, KGNode(id='', node_type='', name='?')).name}",
                ))
                ep_chains += 1

        self._log(f"[lineage] API lineage: {len(chains)} chains")
        return chains

    # ── SQL Lineage ──────────────────────────────────────────

    def build_sql_lineage(
        self,
        kg: KnowledgeGraph,
    ) -> List[LineageChain]:
        """
        Trace SQL lineage: which functions read/write which tables,
        and through what call paths.

        Returns chains: [function → ... → table]
        """
        chains: List[LineageChain] = []

        # Find all SQL table nodes
        table_nodes = kg.nodes_by_type(KGNodeType.SQL_TABLE)

        for table_node in table_nodes:
            # Find all nodes that directly touch this table
            for edge in kg.incoming_edges(table_node.id):
                if edge.relation in (
                    KGRelationType.QUERIES_TABLE,
                    KGRelationType.WRITES_TABLE,
                    KGRelationType.CREATES_TABLE,
                    KGRelationType.READS_FROM,
                    KGRelationType.READS_COLLECTION,
                    KGRelationType.WRITES_COLLECTION,
                ):
                    accessor_id = edge.from_id
                    accessor_node = kg.nodes.get(accessor_id)
                    if not accessor_node:
                        continue

                    # Trace backwards: who calls this accessor?
                    reverse_path = self._trace_backwards(
                        kg, accessor_id,
                        follow_relations={
                            KGRelationType.CALLS, KGRelationType.INVOKES,
                            KGRelationType.CONTAINS, KGRelationType.DEFINES,
                            KGRelationType.CALLS_API, KGRelationType.INVOKES_SERVICE,
                        },
                        max_depth=self.max_chain_depth,
                    )

                    # Build chain: [caller chain] → accessor → table
                    full_path = list(reversed(reverse_path)) + [table_node.id]
                    rels = ["CALLS"] * (len(full_path) - 2) + [edge.relation]

                    chain_id = make_kg_node_id(
                        "DATA_PIPELINE",
                        f"sql_{table_node.name}_{len(chains)}",
                    )
                    chains.append(LineageChain(
                        chain_id=chain_id,
                        chain_type="sql",
                        ordered_node_ids=full_path,
                        hop_relations=rels,
                        confidence=edge.confidence,
                        description=(
                            f"SQL lineage to table '{table_node.name}' "
                            f"via {accessor_node.name}"
                        ),
                    ))

        self._log(f"[lineage] SQL lineage: {len(chains)} chains")
        return chains

    # ── Data Flow Lineage ────────────────────────────────────

    def build_data_flow_lineage(
        self,
        kg: KnowledgeGraph,
    ) -> List[LineageChain]:
        """
        Trace Spark/DataFrame lineage: source → transformation → sink.
        """
        chains: List[LineageChain] = []

        # Find Spark job nodes
        spark_nodes = kg.nodes_by_type(KGNodeType.SPARK_JOB)

        for spark_node in spark_nodes:
            # Find data sources (READS_FROM edges)
            sources = []
            sinks = []
            for edge in kg.outgoing_edges(spark_node.id):
                if edge.relation in (KGRelationType.READS_FROM, KGRelationType.READS_COLLECTION, KGRelationType.SUBSCRIBES_TO_TOPIC):
                    sources.append(edge.to_id)
                elif edge.relation in (KGRelationType.WRITES_TO, KGRelationType.WRITES_COLLECTION, KGRelationType.PUBLISHES_TO_TOPIC):
                    sinks.append(edge.to_id)

            # Build chains: source → spark_job → sink
            for src in sources:
                for sink in sinks:
                    chain_id = make_kg_node_id(
                        "DATA_PIPELINE",
                        f"spark_{spark_node.name}_{len(chains)}",
                    )
                    chains.append(LineageChain(
                        chain_id=chain_id,
                        chain_type="data",
                        ordered_node_ids=[src, spark_node.id, sink],
                        hop_relations=[
                            KGRelationType.READS_FROM,
                            KGRelationType.WRITES_TO,
                        ],
                        confidence="high",
                        description=(
                            f"Data pipeline: {kg.nodes.get(src, KGNode(id='', node_type='', name='?')).name} "
                            f"→ {spark_node.name} → "
                            f"{kg.nodes.get(sink, KGNode(id='', node_type='', name='?')).name}"
                        ),
                    ))

            # If no sinks but has sources, still record partial chain
            if sources and not sinks:
                for src in sources:
                    chain_id = make_kg_node_id(
                        "DATA_PIPELINE",
                        f"spark_read_{spark_node.name}_{len(chains)}",
                    )
                    chains.append(LineageChain(
                        chain_id=chain_id,
                        chain_type="data",
                        ordered_node_ids=[src, spark_node.id],
                        hop_relations=[KGRelationType.READS_FROM],
                        confidence="medium",
                        description=f"Spark read: {spark_node.name}",
                    ))

        self._log(f"[lineage] Data flow lineage: {len(chains)} chains")
        return chains

    # ── Import Lineage ───────────────────────────────────────

    def build_import_lineage(
        self,
        kg: KnowledgeGraph,
    ) -> Dict[str, List[str]]:
        """
        Build transitive import closure for each file.

        Returns:
            Dict[file_node_id → [transitively_imported_file_ids]]
        """
        # Build direct import graph
        import_graph: Dict[str, Set[str]] = defaultdict(set)
        for edge in kg.edges:
            if edge.relation == KGRelationType.IMPORTS:
                import_graph[edge.from_id].add(edge.to_id)

        # Compute transitive closure via BFS
        closures: Dict[str, List[str]] = {}

        for file_id in import_graph:
            visited: Set[str] = set()
            queue = deque(import_graph[file_id])
            visited.update(queue)

            while queue:
                current = queue.popleft()
                for dep in import_graph.get(current, set()):
                    if dep not in visited:
                        visited.add(dep)
                        queue.append(dep)

            closures[file_id] = sorted(visited)

        self._log(
            f"[lineage] Import lineage: {len(closures)} files, "
            f"avg depth {sum(len(v) for v in closures.values()) / max(len(closures), 1):.1f}"
        )
        return closures

    # ── Graph Enrichment ─────────────────────────────────────

    def enrich_graph_with_lineage(
        self,
        kg: KnowledgeGraph,
        chains: List[LineageChain],
    ) -> int:
        """
        Add materialized lineage edges to the graph.

        Creates FEEDS_DATA_TO edges between non-adjacent nodes
        in lineage chains to enable single-hop traversal.

        Returns count of edges added.
        """
        added = 0

        for chain in chains:
            if len(chain.ordered_node_ids) < 2:
                continue

            source = chain.ordered_node_ids[0]
            sink = chain.ordered_node_ids[-1]

            if source == sink:
                continue

            # Add FEEDS_DATA_TO edge from source to sink
            if kg.safe_add_edge(
                from_id=source,
                to_id=sink,
                relation=KGRelationType.FEEDS_DATA_TO,
                confidence=chain.confidence,
                evidence=chain.description or f"Lineage: {chain.chain_type}",
                lineage_type=chain.chain_type,
                business_context=chain.description,
            ):
                added += 1

        self._log(f"[lineage] Added {added} FEEDS_DATA_TO edges")
        return added

    # ── DFS helper ───────────────────────────────────────────

    def _dfs_lineage(
        self,
        kg: KnowledgeGraph,
        current_id: str,
        visited: Set[str],
        path: List[str],
        rels: List[str],
        target_types: Set[str],
        follow_relations: Set[str],
        chains: List[LineageChain],
        chain_type: str,
        chain_counter: int,
    ):
        """DFS to find paths to target node types."""
        if len(path) > self.max_chain_depth:
            return

        current_node = kg.nodes.get(current_id)
        if current_node and current_node.node_type in target_types and len(path) > 2:
            # Found a complete chain
            chain_id = make_kg_node_id(
                "DATA_PIPELINE",
                f"{chain_type}_{chain_counter + len(chains)}",
            )
            chains.append(LineageChain(
                chain_id=chain_id,
                chain_type=chain_type,
                ordered_node_ids=list(path),
                hop_relations=list(rels),
                confidence="high" if len(path) <= 5 else "medium",
                description=f"{chain_type} lineage ({len(path)} hops)",
            ))
            return  # don't go deeper past a target

        for edge in kg.outgoing_edges(current_id):
            if edge.to_id in visited:
                continue
            if edge.relation not in follow_relations:
                continue

            visited.add(edge.to_id)
            path.append(edge.to_id)
            rels.append(edge.relation)

            self._dfs_lineage(
                kg, edge.to_id, visited, path, rels,
                target_types, follow_relations, chains,
                chain_type, chain_counter,
            )

            path.pop()
            rels.pop()
            visited.discard(edge.to_id)

    def _trace_backwards(
        self,
        kg: KnowledgeGraph,
        start_id: str,
        follow_relations: Set[str],
        max_depth: int = 10,
    ) -> List[str]:
        """
        Trace backwards from a node following incoming edges.
        Returns the reverse path (start → ... → root).
        """
        path = [start_id]
        current = start_id
        visited: Set[str] = {start_id}
        depth = 0

        while depth < max_depth:
            incoming = kg.incoming_edges(current)
            best_edge: Optional[KGEdge] = None

            for edge in incoming:
                if edge.from_id in visited:
                    continue
                if edge.relation in follow_relations:
                    # Prefer CALLS over CONTAINS/DEFINES
                    if best_edge is None:
                        best_edge = edge
                    elif edge.relation == KGRelationType.CALLS:
                        best_edge = edge

            if best_edge is None:
                break

            path.append(best_edge.from_id)
            visited.add(best_edge.from_id)
            current = best_edge.from_id
            depth += 1

        return path

    def _log(self, msg: str):
        if self.verbose:
            print(msg, flush=True)
