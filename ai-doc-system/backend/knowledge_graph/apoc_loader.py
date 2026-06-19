"""
knowledge_graph/apoc_loader.py
────────────────────────────────────────────────────────────────
APOC-optimized batch import utilities.

Generates:
  - apoc.periodic.iterate() wrapped import scripts
  - CSV export for LOAD CSV
  - JSON export for apoc.load.json()
  - APOC XML import scripts
  - Memory requirement estimates

All outputs are offline-ready — no live Neo4j connection required
during generation.
"""

from __future__ import annotations

import csv
import json
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .models import KGNode, KGEdge, KnowledgeGraph, KGNodeType


# ══════════════════════════════════════════════════════════════
#  APOC LOADER
# ══════════════════════════════════════════════════════════════

class APOCLoader:
    """
    APOC-optimized batch import generator.

    Usage:
        loader = APOCLoader()
        loader.generate_csv_export(kg, "outputs/csv/")
        loader.generate_json_export(kg, "outputs/json/")
        loader.generate_apoc_import_script(kg, "outputs/apoc_import.cypher")
    """

    def __init__(self, verbose: bool = True):
        self.verbose = verbose

    # ── CSV Export ────────────────────────────────────────────

    def generate_csv_export(
        self,
        kg: KnowledgeGraph,
        output_dir: str,
    ) -> Tuple[str, str]:
        """
        Export nodes and edges as CSV files for LOAD CSV import.

        This is the fastest import method for very large graphs.

        Returns:
            (nodes_csv_path, edges_csv_path)
        """
        t0 = time.time()
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)

        # ── Nodes CSV ────────────────────────────────────────
        nodes_path = str(out / "nodes.csv")
        node_headers = [
            "id", "node_type", "name", "language", "file_path",
            "start_line", "end_line", "is_async", "is_exported",
            "in_degree", "out_degree", "complexity_score",
            "service_boundary", "business_domain", "community_id",
            "docstring", "return_type", "body_preview",
            "parent_id", "labels",
        ]

        with open(nodes_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f, quoting=csv.QUOTE_ALL)
            writer.writerow(node_headers)

            for node in kg.nodes.values():
                labels = ":".join(KGNodeType.neo4j_labels(node.node_type))
                writer.writerow([
                    node.id,
                    node.node_type,
                    (node.name or "")[:200],
                    node.language,
                    node.file_path,
                    node.start_line,
                    node.end_line,
                    str(node.is_async).lower(),
                    str(node.is_exported).lower(),
                    node.in_degree,
                    node.out_degree,
                    node.complexity_score,
                    node.service_boundary or "",
                    node.business_domain or "",
                    node.community_id if node.community_id is not None else "",
                    (node.docstring or "")[:500],
                    (node.return_type or "")[:100],
                    (node.body_preview or "")[:300],
                    node.parent_id or "",
                    labels,
                ])

        # ── Edges CSV ────────────────────────────────────────
        edges_path = str(out / "edges.csv")
        edge_headers = [
            "from_id", "to_id", "relation", "weight",
            "confidence", "evidence", "lineage_type",
            "business_context",
        ]

        with open(edges_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f, quoting=csv.QUOTE_ALL)
            writer.writerow(edge_headers)

            for edge in kg.edges:
                writer.writerow([
                    edge.from_id,
                    edge.to_id,
                    edge.relation,
                    edge.weight,
                    edge.confidence,
                    (edge.evidence or "")[:250],
                    edge.lineage_type or "",
                    (edge.business_context or "")[:300],
                ])

        nodes_kb = Path(nodes_path).stat().st_size / 1024
        edges_kb = Path(edges_path).stat().st_size / 1024
        elapsed = time.time() - t0

        self._log(
            f"[apoc] CSV export: nodes={nodes_path} ({nodes_kb:.1f} KB), "
            f"edges={edges_path} ({edges_kb:.1f} KB)  ({elapsed:.2f}s)"
        )

        return nodes_path, edges_path

    # ── JSON Export ───────────────────────────────────────────

    def generate_json_export(
        self,
        kg: KnowledgeGraph,
        output_dir: str,
    ) -> str:
        """
        Export graph as JSON for apoc.load.json() import.

        Returns path to the JSON file.
        """
        t0 = time.time()
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)

        json_path = str(out / "knowledge_graph.json")

        data = {
            "metadata": {
                "name": kg.name,
                "node_count": kg.node_count,
                "edge_count": kg.edge_count,
                "stats": kg.stats(),
            },
            "nodes": [
                node.to_props_dict()
                for node in kg.nodes.values()
            ],
            "edges": [
                edge.to_props_dict() | {
                    "from_id": edge.from_id,
                    "to_id": edge.to_id,
                    "relation": edge.relation,
                }
                for edge in kg.edges
            ],
        }

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str, ensure_ascii=False)

        kb = Path(json_path).stat().st_size / 1024
        elapsed = time.time() - t0
        self._log(f"[apoc] JSON export: {json_path}  ({kb:.1f} KB)  ({elapsed:.2f}s)")

        return json_path

    # ── APOC Import Script ───────────────────────────────────

    def generate_apoc_import_script(
        self,
        kg: KnowledgeGraph,
        output_path: str,
        csv_dir: Optional[str] = None,
        json_path: Optional[str] = None,
    ) -> str:
        """
        Generate APOC-powered import Cypher script.

        Supports:
          - LOAD CSV with apoc.periodic.iterate()
          - apoc.load.json()
          - apoc.import.xml()
        """
        lines: List[str] = [
            "// ============================================================",
            f"// APOC Import Script: {kg.name}",
            f"// Nodes: {kg.node_count}   Edges: {kg.edge_count}",
            "// Requires: Neo4j 5.x with APOC Core",
            "// ============================================================",
            "",
        ]

        # ── Option 1: CSV Import ─────────────────────────────
        if csv_dir:
            lines.extend(self._csv_import_script(csv_dir))
            lines.append("")

        # ── Option 2: JSON Import ────────────────────────────
        if json_path:
            lines.extend(self._json_import_script(json_path))
            lines.append("")

        # ── Option 3: XML Import ─────────────────────────────
        if kg.source:
            lines.extend(self._xml_import_script(kg.source))
            lines.append("")

        script = "\n".join(lines)
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_text(script, encoding="utf-8")
        self._log(f"[apoc] Import script → {output_path}")
        return output_path

    def _csv_import_script(self, csv_dir: str) -> List[str]:
        """Generate LOAD CSV + apoc.periodic.iterate() import."""
        return [
            "// ── CSV Import with APOC Batch Processing ─────────────────",
            "",
            "// Step 1: Import nodes (parallel batching)",
            "CALL apoc.periodic.iterate(",
            f"  'LOAD CSV WITH HEADERS FROM \"file:///{csv_dir}/nodes.csv\" AS row RETURN row',",
            "  'WITH row",
            "   CALL apoc.merge.node(",
            "     split(row.labels, \":\"),",
            "     {id: row.id},",
            "     {",
            "       name: row.name,",
            "       language: row.language,",
            "       file_path: row.file_path,",
            "       node_type: row.node_type,",
            "       start_line: toInteger(row.start_line),",
            "       end_line: toInteger(row.end_line),",
            "       is_async: row.is_async = \"true\",",
            "       is_exported: row.is_exported = \"true\",",
            "       complexity_score: toFloat(row.complexity_score),",
            "       service_boundary: row.service_boundary,",
            "       business_domain: row.business_domain,",
            "       docstring: row.docstring,",
            "       body_preview: row.body_preview",
            "     },",
            "     {}",
            "   ) YIELD node RETURN count(*)',",
            "  {batchSize: 1000, parallel: true}",
            ");",
            "",
            "// Step 2: Import edges (parallel batching)",
            "CALL apoc.periodic.iterate(",
            f"  'LOAD CSV WITH HEADERS FROM \"file:///{csv_dir}/edges.csv\" AS row RETURN row',",
            "  'WITH row",
            "   MATCH (a {id: row.from_id}), (b {id: row.to_id})",
            "   CALL apoc.merge.relationship(",
            "     a, row.relation, {}, {",
            "       confidence: row.confidence,",
            "       weight: toFloat(row.weight),",
            "       evidence: row.evidence",
            "     }, b, {}",
            "   ) YIELD rel RETURN count(*)',",
            "  {batchSize: 1000, parallel: false}",
            ");",
        ]

    def _json_import_script(self, json_path: str) -> List[str]:
        """Generate apoc.load.json() import script."""
        return [
            "// ── JSON Import with APOC ──────────────────────────────────",
            "",
            "// Import nodes from JSON",
            f"CALL apoc.load.json('file:///{json_path}') YIELD value",
            "UNWIND value.nodes AS node",
            "CALL apoc.merge.node(",
            "  ['CodeEntity'],",
            "  {id: node.id},",
            "  node,",
            "  {}",
            ") YIELD node AS n",
            "RETURN count(n);",
            "",
            "// Import edges from JSON",
            f"CALL apoc.load.json('file:///{json_path}') YIELD value",
            "UNWIND value.edges AS edge",
            "MATCH (a {id: edge.from_id}), (b {id: edge.to_id})",
            "CALL apoc.merge.relationship(",
            "  a, edge.relation, {},",
            "  {confidence: edge.confidence, weight: edge.weight, evidence: edge.evidence},",
            "  b, {}",
            ") YIELD rel",
            "RETURN count(rel);",
        ]

    def _xml_import_script(self, xml_path: str) -> List[str]:
        """Generate apoc.import.xml() import script."""
        return [
            "// ── XML Import with APOC ───────────────────────────────────",
            f"// Source: {xml_path}",
            "",
            "// Direct XML import (for small-to-medium graphs)",
            f"CALL apoc.import.xml('file:///{xml_path}', {{",
            "  relType: 'relation',",
            "  label: 'type'",
            "});",
        ]

    # ── Memory Estimation ────────────────────────────────────

    def estimate_memory_requirements(
        self,
        kg: KnowledgeGraph,
    ) -> Dict[str, str]:
        """
        Estimate Neo4j heap and pagecache requirements based on
        graph size.

        Returns human-readable configuration recommendations.
        """
        # Rough estimates:
        # - Each node: ~500 bytes in memory
        # - Each relationship: ~200 bytes in memory
        # - Index overhead: ~30% additional

        node_bytes = kg.node_count * 500
        edge_bytes = kg.edge_count * 200
        index_overhead = (node_bytes + edge_bytes) * 0.3
        total_bytes = node_bytes + edge_bytes + index_overhead

        # Convert to MB/GB
        total_mb = total_bytes / (1024 * 1024)
        heap_mb = max(512, int(total_mb * 1.5))
        pagecache_mb = max(256, int(total_mb * 0.8))

        recommendations = {
            "estimated_data_size": f"{total_mb:.0f} MB",
            "recommended_heap": f"{heap_mb} MB",
            "recommended_pagecache": f"{pagecache_mb} MB",
            "neo4j_conf": (
                f"server.memory.heap.initial_size={heap_mb}m\n"
                f"server.memory.heap.max_size={heap_mb}m\n"
                f"server.memory.pagecache.size={pagecache_mb}m"
            ),
            "node_count": str(kg.node_count),
            "edge_count": str(kg.edge_count),
        }

        self._log(
            f"[apoc] Memory estimate: heap={heap_mb}MB, "
            f"pagecache={pagecache_mb}MB (data ~{total_mb:.0f}MB)"
        )

        return recommendations

    def _log(self, msg: str):
        if self.verbose:
            print(msg, flush=True)
