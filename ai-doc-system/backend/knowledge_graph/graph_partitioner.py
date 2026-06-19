"""
knowledge_graph/graph_partitioner.py
────────────────────────────────────────────────────────────────
Enterprise Graph Partitioning Engine.

Splits a KnowledgeGraph into bounded partitions by service,
directory, domain, or fixed-size chunks. Generates partition
manifests for incremental updates and streaming ingestion.
"""

from __future__ import annotations

import csv
import json
import time
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Set

from .models import (
    KnowledgeGraph, KGNode, KGEdge, KGNodeType,
    GraphPartition, PartitionManifest,
)


class GraphPartitioner:
    """
    Partitions a KnowledgeGraph into bounded chunks.

    Strategies:
      - service:   One partition per service_boundary
      - directory: One partition per top-level directory
      - domain:    One partition per business_domain
      - fixed:     Fixed-size chunks of N nodes
      - auto:      Service if boundaries detected, else directory
    """

    def __init__(
        self,
        strategy: str = "auto",
        max_partition_size: int = 10_000,
        verbose: bool = True,
    ):
        self.strategy = strategy
        self.max_partition_size = max_partition_size
        self.verbose = verbose

    def partition(self, kg: KnowledgeGraph) -> List[GraphPartition]:
        """Partition the graph using the configured strategy."""
        t0 = time.time()
        strategy = self._resolve_strategy(kg)
        self._log(f"[partitioner] Strategy: {strategy}")

        if strategy == "service":
            partitions = kg.partition_by_service()
        elif strategy == "directory":
            partitions = kg.partition_by_directory(depth=1)
        elif strategy == "domain":
            partitions = self._partition_by_domain(kg)
        elif strategy == "fixed":
            partitions = self._partition_fixed_size(kg)
        else:
            partitions = kg.partition_by_service()

        # Split oversized partitions
        final = []
        for p in partitions:
            if len(p.node_ids) > self.max_partition_size:
                splits = self._split_partition(p, kg)
                final.extend(splits)
            else:
                final.append(p)

        # Compute cross-partition edge counts
        node_to_part: Dict[str, str] = {}
        for p in final:
            for nid in p.node_ids:
                node_to_part[nid] = p.partition_id

        for p in final:
            cross = sum(
                1 for e in kg.edges
                if e.from_id in p.node_ids and e.to_id not in p.node_ids
            )
            p.cross_partition_edge_count = cross

        elapsed = time.time() - t0
        self._log(
            f"[partitioner] Created {len(final)} partitions "
            f"(total {kg.node_count} nodes) in {elapsed:.2f}s"
        )
        for p in final:
            self._log(
                f"  [{p.partition_name}] {len(p.node_ids)} nodes, "
                f"{p.edge_count} edges, {p.cross_partition_edge_count} cross-edges"
            )

        return final

    def build_manifest(
        self,
        kg: KnowledgeGraph,
        partitions: List[GraphPartition],
    ) -> PartitionManifest:
        """Build a partition manifest for the graph."""
        import datetime
        cross_edges = kg.cross_partition_edges(partitions)

        manifest = PartitionManifest(
            graph_name=kg.name,
            total_nodes=kg.node_count,
            total_edges=kg.edge_count,
            partition_strategy=self.strategy,
            partitions=partitions,
            cross_partition_edges=len(cross_edges),
            build_timestamp=datetime.datetime.now().isoformat(),
        )
        return manifest

    def export_partitions(
        self,
        kg: KnowledgeGraph,
        partitions: List[GraphPartition],
        output_dir: str,
    ) -> str:
        """
        Export each partition as separate CSV files + manifest.

        Structure:
          output_dir/
            partitions/
              partition_manifest.json
              <partition_name>/
                nodes.csv
                edges.csv
                partition_stats.json
              cross_partition_edges.csv
        """
        t0 = time.time()
        part_dir = Path(output_dir) / "partitions"
        part_dir.mkdir(parents=True, exist_ok=True)

        # Export each partition
        for p in partitions:
            p_dir = part_dir / p.partition_name.replace("/", "_")
            p_dir.mkdir(parents=True, exist_ok=True)

            # Nodes CSV
            self._write_nodes_csv(kg, p.node_ids, str(p_dir / "nodes.csv"))

            # Edges CSV (intra-partition only)
            intra_edges = [
                e for e in kg.edges
                if e.from_id in p.node_ids and e.to_id in p.node_ids
            ]
            self._write_edges_csv(intra_edges, str(p_dir / "edges.csv"))

            # Partition stats
            stats = {
                "partition_id": p.partition_id,
                "partition_name": p.partition_name,
                "strategy": p.strategy,
                "node_count": len(p.node_ids),
                "edge_count": p.edge_count,
                "content_hash": p.content_hash,
                "cross_partition_edge_count": p.cross_partition_edge_count,
            }
            (p_dir / "partition_stats.json").write_text(
                json.dumps(stats, indent=2), encoding="utf-8"
            )

        # Cross-partition edges
        cross_edges = kg.cross_partition_edges(partitions)
        self._write_edges_csv(
            cross_edges, str(part_dir / "cross_partition_edges.csv")
        )

        # Manifest
        manifest = self.build_manifest(kg, partitions)
        (part_dir / "partition_manifest.json").write_text(
            json.dumps(manifest.to_dict(), indent=2), encoding="utf-8"
        )

        elapsed = time.time() - t0
        self._log(
            f"[partitioner] Exported {len(partitions)} partitions "
            f"+ {len(cross_edges)} cross edges in {elapsed:.2f}s"
        )
        return str(part_dir)

    # ── Internal helpers ─────────────────────────────────────

    def _resolve_strategy(self, kg: KnowledgeGraph) -> str:
        """Auto-detect the best partition strategy."""
        if self.strategy != "auto":
            return self.strategy
        # If service boundaries are detected, use service
        has_svc = any(n.service_boundary for n in kg.nodes.values())
        if has_svc:
            return "service"
        return "directory"

    def _partition_by_domain(self, kg: KnowledgeGraph) -> List[GraphPartition]:
        """Partition by business_domain."""
        groups: Dict[str, Set[str]] = defaultdict(set)
        for nid, node in kg.nodes.items():
            key = node.business_domain or "__unclassified__"
            groups[key].add(nid)

        partitions = []
        for domain, nids in groups.items():
            p = GraphPartition(
                partition_id=f"domain_{domain}",
                partition_name=domain,
                strategy="domain",
                node_ids=nids,
            )
            p.content_hash = kg._hash_node_ids(nids)
            p.edge_count = sum(
                1 for e in kg.edges
                if e.from_id in nids and e.to_id in nids
            )
            partitions.append(p)
        return partitions

    def _partition_fixed_size(self, kg: KnowledgeGraph) -> List[GraphPartition]:
        """Partition into fixed-size chunks."""
        all_ids = list(kg.nodes.keys())
        partitions = []
        for i in range(0, len(all_ids), self.max_partition_size):
            chunk = set(all_ids[i:i + self.max_partition_size])
            idx = i // self.max_partition_size
            p = GraphPartition(
                partition_id=f"chunk_{idx:04d}",
                partition_name=f"chunk_{idx:04d}",
                strategy="fixed",
                node_ids=chunk,
            )
            p.content_hash = kg._hash_node_ids(chunk)
            p.edge_count = sum(
                1 for e in kg.edges
                if e.from_id in chunk and e.to_id in chunk
            )
            partitions.append(p)
        return partitions

    def _split_partition(
        self, partition: GraphPartition, kg: KnowledgeGraph,
    ) -> List[GraphPartition]:
        """Split an oversized partition into sub-partitions."""
        ids = list(partition.node_ids)
        splits = []
        for i in range(0, len(ids), self.max_partition_size):
            chunk = set(ids[i:i + self.max_partition_size])
            idx = i // self.max_partition_size
            p = GraphPartition(
                partition_id=f"{partition.partition_id}_sub{idx}",
                partition_name=f"{partition.partition_name}_sub{idx}",
                strategy=partition.strategy,
                node_ids=chunk,
            )
            p.content_hash = kg._hash_node_ids(chunk)
            p.edge_count = sum(
                1 for e in kg.edges
                if e.from_id in chunk and e.to_id in chunk
            )
            splits.append(p)
        return splits

    def _write_nodes_csv(self, kg: KnowledgeGraph, node_ids: Set[str], path: str):
        """Write partition nodes to CSV."""
        headers = [
            "id", "node_type", "name", "language", "file_path",
            "start_line", "end_line", "is_async", "is_exported",
            "in_degree", "out_degree", "complexity_score",
            "service_boundary", "business_domain", "community_id",
            "semantic_chunk", "centrality_score", "labels",
        ]
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f, quoting=csv.QUOTE_ALL)
            writer.writerow(headers)
            for nid in sorted(node_ids):
                node = kg.nodes.get(nid)
                if not node:
                    continue
                labels = ":".join(KGNodeType.neo4j_labels(node.node_type))
                writer.writerow([
                    node.id, node.node_type, (node.name or "")[:200],
                    node.language, node.file_path,
                    node.start_line, node.end_line,
                    str(node.is_async).lower(), str(node.is_exported).lower(),
                    node.in_degree, node.out_degree, node.complexity_score,
                    node.service_boundary or "", node.business_domain or "",
                    node.community_id if node.community_id is not None else "",
                    (node.semantic_chunk or "")[:500],
                    node.centrality_score,
                    labels,
                ])

    def _write_edges_csv(self, edges: List[KGEdge], path: str):
        """Write edges to CSV."""
        headers = [
            "from_id", "to_id", "relation", "weight",
            "confidence", "evidence", "lineage_type", "business_context",
        ]
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f, quoting=csv.QUOTE_ALL)
            writer.writerow(headers)
            for edge in edges:
                writer.writerow([
                    edge.from_id, edge.to_id, edge.relation,
                    edge.weight, edge.confidence,
                    (edge.evidence or "")[:250],
                    edge.lineage_type or "",
                    (edge.business_context or "")[:300],
                ])

    def _log(self, msg: str):
        if self.verbose:
            print(msg, flush=True)
