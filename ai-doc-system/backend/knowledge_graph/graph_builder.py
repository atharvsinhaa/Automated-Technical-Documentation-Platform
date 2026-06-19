"""
knowledge_graph/graph_builder.py
────────────────────────────────────────────────────────────────
Core orchestrator — takes loaded XML data and produces a
semantically enriched enterprise knowledge graph.

Pipeline phases:
  1. Service boundary detection
  2. Business flow extraction
  3. Community detection (label propagation)
  4. Complexity scoring
  5. Semantic tagging
  6. Virtual node/edge creation
  7. Lineage enrichment

All processing is offline — zero LLM, zero cloud.
"""

from __future__ import annotations

import time
from collections import Counter, defaultdict
from typing import Dict, List, Optional, Set, Tuple

from .models import (
    KGNode, KGEdge, KnowledgeGraph,
    BusinessFlow, ServiceCluster, LineageChain,
    KGNodeType, KGRelationType, make_kg_node_id,
)
from .business_mapper import BusinessMapper
from .lineage_builder import LineageBuilder


# ══════════════════════════════════════════════════════════════
#  KNOWLEDGE GRAPH BUILDER
# ══════════════════════════════════════════════════════════════

class KnowledgeGraphBuilder:
    """
    Semantic enrichment orchestrator for the knowledge graph.

    Takes a loaded KnowledgeGraph (from GraphXMLLoader) and
    enriches it with business flows, service clusters, lineage,
    community detection, and complexity scoring.

    Usage:
        builder = KnowledgeGraphBuilder()
        enriched_kg = builder.build(kg)
    """

    def __init__(self, verbose: bool = True):
        self.verbose = verbose
        self._mapper = BusinessMapper(verbose=verbose)
        self._lineage = LineageBuilder(verbose=verbose)

    def build(self, kg: KnowledgeGraph) -> KnowledgeGraph:
        """
        Run the full enrichment pipeline on a loaded KnowledgeGraph.

        Returns the same KnowledgeGraph object, mutated in-place
        with business enrichments added.
        """
        t0 = time.time()
        self._log(f"\n{'='*60}")
        self._log(f"  Knowledge Graph Builder: {kg.name}")
        self._log(f"  Input: {kg.node_count} nodes, {kg.edge_count} edges")
        self._log(f"{'='*60}\n")

        # ── Phase 1: Service Boundary Detection ──────────────
        self._log("[Phase 1/7] Detecting service boundaries…")
        t1 = time.time()
        clusters = self._mapper.detect_service_boundaries(kg)
        kg.service_clusters = clusters

        # Apply ownership to nodes
        ownership = self._mapper.map_module_ownership(kg, clusters)
        self._log(f"  → {len(clusters)} clusters, {len(ownership)} nodes owned  ({time.time()-t1:.2f}s)")

        # ── Phase 2: Business Flow Extraction ────────────────
        self._log("[Phase 2/7] Extracting business flows…")
        t2 = time.time()
        flows = self._mapper.extract_business_flows(kg)
        kg.business_flows = flows
        self._log(f"  → {len(flows)} flows  ({time.time()-t2:.2f}s)")

        # ── Phase 3: Community Detection ─────────────────────
        self._log("[Phase 3/7] Running community detection…")
        t3 = time.time()
        communities = self._detect_communities(kg)
        self._log(f"  → {len(set(communities.values()))} communities  ({time.time()-t3:.2f}s)")

        # ── Phase 4: Complexity Scoring ──────────────────────
        self._log("[Phase 4/7] Computing complexity scores…")
        t4 = time.time()
        self._compute_complexity(kg)
        self._log(f"  → Scored {kg.node_count} nodes  ({time.time()-t4:.2f}s)")

        # ── Phase 5: Semantic Tagging ────────────────────────
        self._log("[Phase 5/7] Applying semantic tags…")
        t5 = time.time()
        self._mapper.apply_semantic_tags(kg)
        tagged = sum(1 for n in kg.nodes.values() if n.semantic_tags)
        self._log(f"  → Tagged {tagged} nodes  ({time.time()-t5:.2f}s)")

        # ── Phase 6: Virtual Nodes & Edges ───────────────────
        self._log("[Phase 6/7] Creating virtual business nodes…")
        t6 = time.time()
        virtual_added = self._create_virtual_entities(kg)
        self._log(f"  → {virtual_added} virtual entities  ({time.time()-t6:.2f}s)")

        # ── Phase 7: Lineage Enrichment ──────────────────────
        self._log("[Phase 7/7] Building lineage chains…")
        t7 = time.time()
        api_chains = self._lineage.build_api_lineage(kg)
        sql_chains = self._lineage.build_sql_lineage(kg)
        data_chains = self._lineage.build_data_flow_lineage(kg)
        import_lineage = self._lineage.build_import_lineage(kg)

        all_chains = api_chains + sql_chains + data_chains
        kg.lineage_chains = all_chains

        lineage_edges = self._lineage.enrich_graph_with_lineage(kg, all_chains)
        self._log(
            f"  → {len(all_chains)} chains, {lineage_edges} edges  ({time.time()-t7:.2f}s)"
        )

        elapsed = time.time() - t0
        self._log(f"\n{'='*60}")
        self._log(f"  Enrichment complete in {elapsed:.2f}s")
        self._log(f"  Final: {kg.node_count} nodes, {kg.edge_count} edges")
        self._log(f"  Flows: {len(kg.business_flows)}")
        self._log(f"  Clusters: {len(kg.service_clusters)}")
        self._log(f"  Lineage chains: {len(kg.lineage_chains)}")
        self._log(f"{'='*60}\n")

        return kg

    # ── Community Detection (Label Propagation) ──────────────

    def _detect_communities(
        self,
        kg: KnowledgeGraph,
        max_iterations: int = 20,
    ) -> Dict[str, int]:
        """
        Lightweight label propagation for community detection.

        Pure Python — no external ML dependency.
        Assigns community_id to each node based on densely
        connected clusters.
        """
        # Initialize: each node is its own community
        labels: Dict[str, int] = {}
        node_ids = list(kg.nodes.keys())
        for i, nid in enumerate(node_ids):
            labels[nid] = i

        # Iterative label propagation
        changed = True
        iteration = 0

        while changed and iteration < max_iterations:
            changed = False
            iteration += 1

            for nid in node_ids:
                # Collect neighbor labels
                neighbor_labels: List[int] = []

                for edge in kg.outgoing_edges(nid):
                    if edge.to_id in labels:
                        neighbor_labels.append(labels[edge.to_id])
                for edge in kg.incoming_edges(nid):
                    if edge.from_id in labels:
                        neighbor_labels.append(labels[edge.from_id])

                if not neighbor_labels:
                    continue

                # Majority vote
                label_counts = Counter(neighbor_labels)
                majority_label = label_counts.most_common(1)[0][0]

                if labels[nid] != majority_label:
                    labels[nid] = majority_label
                    changed = True

        # Normalize community IDs to sequential integers
        unique_labels = sorted(set(labels.values()))
        label_map = {old: new for new, old in enumerate(unique_labels)}
        normalized: Dict[str, int] = {
            nid: label_map[lab] for nid, lab in labels.items()
        }

        # Apply to nodes
        for nid, community_id in normalized.items():
            if nid in kg.nodes:
                kg.nodes[nid].community_id = community_id

        return normalized

    # ── Complexity Scoring ───────────────────────────────────

    def _compute_complexity(self, kg: KnowledgeGraph):
        """
        Compute a 0.0–1.0 complexity score for each node based on:
          - In/out degree
          - Body preview length (proxy for cyclomatic complexity)
          - Cross-service edge count
          - Number of parameters
        """
        # Compute max values for normalization
        max_degree = max(
            (n.in_degree + n.out_degree for n in kg.nodes.values()),
            default=1,
        )
        max_body = max(
            (len(n.body_preview or "") for n in kg.nodes.values()),
            default=1,
        )
        max_params = max(
            (len(n.params) for n in kg.nodes.values()),
            default=1,
        )

        if max_degree == 0:
            max_degree = 1

        for node in kg.nodes.values():
            # Degree factor (0–1)
            degree_factor = (node.in_degree + node.out_degree) / max_degree

            # Body complexity factor (0–1)
            body_len = len(node.body_preview or "")
            body_factor = body_len / max_body if max_body > 0 else 0

            # Parameter count factor (0–1)
            param_factor = len(node.params) / max_params if max_params > 0 else 0

            # Cross-service factor (0 or 0.2)
            cross_svc = 0.0
            if node.service_boundary:
                for edge in kg.outgoing_edges(node.id):
                    target = kg.nodes.get(edge.to_id)
                    if target and target.service_boundary and \
                       target.service_boundary != node.service_boundary:
                        cross_svc = 0.2
                        break

            # Weighted combination
            score = (
                0.35 * degree_factor +
                0.25 * body_factor +
                0.15 * param_factor +
                0.25 * cross_svc
            )
            node.complexity_score = round(min(score, 1.0), 4)

    # ── Virtual Entity Creation ──────────────────────────────

    def _create_virtual_entities(self, kg: KnowledgeGraph) -> int:
        """
        Create virtual BUSINESS_FLOW and SERVICE_CLUSTER nodes
        and link them to participating nodes.
        """
        added = 0

        # Create service cluster virtual nodes
        for cluster in kg.service_clusters:
            cluster_node = cluster.to_kg_node()
            if kg.add_node(cluster_node):
                added += 1

            # Link files to their service cluster
            for node_id in cluster.node_ids:
                if kg.safe_add_edge(
                    from_id=node_id,
                    to_id=cluster_node.id,
                    relation=KGRelationType.BELONGS_TO_SERVICE,
                    confidence=cluster.confidence,
                    evidence=f"Part of service '{cluster.cluster_name}'",
                    business_context=f"Service: {cluster.cluster_name}",
                ):
                    added += 1

        # Create business flow virtual nodes
        for flow in kg.business_flows:
            flow_node = flow.to_kg_node()
            if kg.add_node(flow_node):
                added += 1

            # Link participating nodes to the flow
            for node_id in flow.node_ids:
                if kg.safe_add_edge(
                    from_id=node_id,
                    to_id=flow_node.id,
                    relation=KGRelationType.PARTICIPATES_IN_FLOW,
                    confidence=flow.confidence,
                    evidence=f"Participates in '{flow.flow_name}'",
                    business_context=f"Flow: {flow.flow_name}",
                ):
                    added += 1

        return added

    def _log(self, msg: str):
        if self.verbose:
            print(msg, flush=True)
