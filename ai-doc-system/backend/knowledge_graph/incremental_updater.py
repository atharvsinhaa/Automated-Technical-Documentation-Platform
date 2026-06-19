"""
knowledge_graph/incremental_updater.py
────────────────────────────────────────────────────────────────
Incremental Graph Update Engine.

Compares a new graph build against a previous partition manifest
and generates delta Cypher (add/modify/delete) instead of a full
rebuild. Critical for enterprise-scale repositories where only a
fraction of files change between builds.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from .models import (
    KnowledgeGraph, KGNode, KGEdge,
    GraphPartition, PartitionManifest, DeltaOperation,
    KGNodeType,
)


class IncrementalUpdater:
    """
    Generates delta operations by comparing graph builds.

    Usage:
        updater = IncrementalUpdater()
        deltas = updater.compute_delta(kg, new_partitions, old_manifest)
        updater.generate_delta_cypher(deltas, output_path)
    """

    def __init__(self, verbose: bool = True):
        self.verbose = verbose

    def load_previous_manifest(self, manifest_path: str) -> Optional[PartitionManifest]:
        """Load a previously saved partition manifest."""
        path = Path(manifest_path)
        if not path.exists():
            self._log("[incremental] No previous manifest found — full build required.")
            return None

        data = json.loads(path.read_text(encoding="utf-8"))

        partitions = []
        for pd in data.get("partitions", []):
            partitions.append(GraphPartition(
                partition_id=pd["partition_id"],
                partition_name=pd["partition_name"],
                strategy=pd["strategy"],
                node_ids=set(),  # IDs not stored in manifest
                edge_count=pd.get("edge_count", 0),
                content_hash=pd.get("content_hash", ""),
                root_path=pd.get("root_path", ""),
                cross_partition_edge_count=pd.get("cross_partition_edge_count", 0),
            ))

        manifest = PartitionManifest(
            graph_name=data.get("graph_name", ""),
            total_nodes=data.get("total_nodes", 0),
            total_edges=data.get("total_edges", 0),
            partition_strategy=data.get("partition_strategy", "auto"),
            partitions=partitions,
            cross_partition_edges=data.get("cross_partition_edges", 0),
            build_timestamp=data.get("build_timestamp", ""),
        )
        self._log(
            f"[incremental] Loaded manifest: {len(partitions)} partitions, "
            f"{manifest.total_nodes} nodes"
        )
        return manifest

    def compute_delta(
        self,
        kg: KnowledgeGraph,
        new_partitions: List[GraphPartition],
        old_manifest: Optional[PartitionManifest],
    ) -> List[DeltaOperation]:
        """
        Compare new partitions against old manifest.

        Returns a list of DeltaOperations (add/modify/delete).
        If old_manifest is None, all nodes/edges are 'add'.
        """
        if old_manifest is None:
            # Full add — everything is new
            deltas: List[DeltaOperation] = []
            for node in kg.nodes.values():
                deltas.append(DeltaOperation(
                    op_type="add",
                    entity_type="node",
                    target_id=node.id,
                    payload=node.to_props_dict(),
                ))
            for edge in kg.edges:
                deltas.append(DeltaOperation(
                    op_type="add",
                    entity_type="edge",
                    target_id=f"{edge.from_id}->{edge.to_id}:{edge.relation}",
                    payload=edge.to_props_dict() | {
                        "from_id": edge.from_id,
                        "to_id": edge.to_id,
                        "relation": edge.relation,
                    },
                ))
            self._log(f"[incremental] Full build: {len(deltas)} operations (no prior manifest)")
            return deltas

        # Compare partition hashes
        old_hashes: Dict[str, str] = {
            p.partition_id: p.content_hash for p in old_manifest.partitions
        }
        old_partition_ids = set(old_hashes.keys())
        new_partition_ids = set(p.partition_id for p in new_partitions)

        changed_partitions: List[GraphPartition] = []
        unchanged_count = 0
        new_count = 0
        deleted_partition_ids = old_partition_ids - new_partition_ids

        for p in new_partitions:
            old_hash = old_hashes.get(p.partition_id)
            if old_hash is None:
                # New partition
                changed_partitions.append(p)
                new_count += 1
            elif old_hash != p.content_hash:
                # Changed partition
                changed_partitions.append(p)
            else:
                unchanged_count += 1

        self._log(
            f"[incremental] Partitions: {unchanged_count} unchanged, "
            f"{len(changed_partitions)} changed, {new_count} new, "
            f"{len(deleted_partition_ids)} deleted"
        )

        # Build delta operations for changed partitions
        deltas: List[DeltaOperation] = []

        for p in changed_partitions:
            for nid in p.node_ids:
                node = kg.nodes.get(nid)
                if node:
                    deltas.append(DeltaOperation(
                        op_type="add",  # MERGE is idempotent
                        entity_type="node",
                        target_id=node.id,
                        payload=node.to_props_dict(),
                    ))

            # Edges within the changed partition
            for edge in kg.edges:
                if edge.from_id in p.node_ids or edge.to_id in p.node_ids:
                    deltas.append(DeltaOperation(
                        op_type="add",
                        entity_type="edge",
                        target_id=f"{edge.from_id}->{edge.to_id}:{edge.relation}",
                        payload=edge.to_props_dict() | {
                            "from_id": edge.from_id,
                            "to_id": edge.to_id,
                            "relation": edge.relation,
                        },
                    ))

        # Deleted partitions → delete all nodes in those partitions
        # (We don't have the node IDs from old manifest, so we generate
        #  a partition-level delete marker)
        for pid in deleted_partition_ids:
            deltas.append(DeltaOperation(
                op_type="delete",
                entity_type="partition",
                target_id=pid,
            ))

        self._log(f"[incremental] Generated {len(deltas)} delta operations")
        return deltas

    def generate_delta_cypher(
        self,
        deltas: List[DeltaOperation],
        output_path: str,
        batch_size: int = 500,
    ) -> str:
        """
        Generate delta Cypher containing only the changes.

        Uses MERGE for add/modify (idempotent) and
        MATCH + DELETE for deletions.
        """
        lines = [
            "// ============================================================",
            "// DELTA Cypher — Incremental Graph Update",
            f"// Operations: {len(deltas)}",
            "// ============================================================",
            "",
        ]

        # Group node adds
        node_adds = [d for d in deltas if d.entity_type == "node" and d.op_type == "add"]
        edge_adds = [d for d in deltas if d.entity_type == "edge" and d.op_type == "add"]
        deletes = [d for d in deltas if d.op_type == "delete"]

        if node_adds:
            lines.append(f"// ── Node MERGE ({len(node_adds)} nodes) ────────────")
            for i in range(0, len(node_adds), batch_size):
                chunk = node_adds[i:i + batch_size]
                lines.append(":begin")
                for d in chunk:
                    payload = d.payload or {}
                    node_type = payload.get("node_type", "CodeEntity")
                    labels = ":".join(KGNodeType.neo4j_labels(node_type))
                    nid = payload.get("id", d.target_id)
                    lines.append(
                        f"MERGE (n:{labels} {{id: '{_esc(nid)}'}}) "
                        f"SET n.name = '{_esc(payload.get('name', '')[:200])}', "
                        f"n.node_type = '{_esc(node_type)}';"
                    )
                lines.append(":commit")
                lines.append("")

        if edge_adds:
            lines.append(f"// ── Edge MERGE ({len(edge_adds)} edges) ────────────")
            for i in range(0, len(edge_adds), batch_size):
                chunk = edge_adds[i:i + batch_size]
                lines.append(":begin")
                for d in chunk:
                    payload = d.payload or {}
                    rel = (payload.get("relation", "DEPENDS_ON")).replace(" ", "_")
                    lines.append(
                        f"MATCH (a {{id: '{_esc(payload.get('from_id', ''))}'}}),"
                        f" (b {{id: '{_esc(payload.get('to_id', ''))}'}}) "
                        f"MERGE (a)-[:{rel}]->(b);"
                    )
                lines.append(":commit")
                lines.append("")

        if deletes:
            lines.append(f"// ── Deletes ({len(deletes)}) ──────────────────────")
            lines.append(":begin")
            for d in deletes:
                if d.entity_type == "partition":
                    lines.append(f"// Partition deleted: {d.target_id}")
                    lines.append(
                        f"// To remove: MATCH (n) WHERE n.partition_id = '{_esc(d.target_id)}' "
                        f"DETACH DELETE n;"
                    )
                else:
                    lines.append(
                        f"MATCH (n {{id: '{_esc(d.target_id)}'}}) DETACH DELETE n;"
                    )
            lines.append(":commit")
            lines.append("")

        lines.append("// Delta complete.")

        cypher = "\n".join(lines)
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_text(cypher, encoding="utf-8")

        kb = Path(output_path).stat().st_size / 1024
        self._log(f"[incremental] Delta Cypher → {output_path}  ({kb:.1f} KB)")

        return output_path

    def _log(self, msg: str):
        if self.verbose:
            print(msg, flush=True)


import re
_CTRL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")

def _esc(s: str) -> str:
    if s is None:
        return ""
    s = _CTRL_RE.sub("", str(s))
    return s.replace("\\", "\\\\").replace("'", "\\'")
