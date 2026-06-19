"""
knowledge_graph/graph_stats.py
────────────────────────────────────────────────────────────────
Comprehensive graph analytics and reporting.

Generates:
  - Full statistics (node/edge counts, distributions)
  - Human-readable markdown reports
  - Service dependency maps
  - HLD architecture summaries
  - XML/JSON export of statistics

All processing is offline — zero external dependencies.
"""

from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from .models import (
    KGNode, KGEdge, KnowledgeGraph,
    BusinessFlow, ServiceCluster, LineageChain,
    KGNodeType, FlowSummary,
)
from .graph_optimizer import GraphProfile

try:
    from lxml import etree as ET
    _LXML = True
except ImportError:
    import xml.etree.ElementTree as ET
    _LXML = False


# ──────────────────────────────────────────────────────────────
#  GRAPH REPORT
# ──────────────────────────────────────────────────────────────

class GraphReport:
    """Container for comprehensive graph statistics."""

    def __init__(self):
        self.name:               str = ""
        self.generated_at:       str = ""
        self.node_count:         int = 0
        self.edge_count:         int = 0
        self.node_types:         Dict[str, int] = {}
        self.relation_types:     Dict[str, int] = {}
        self.language_dist:      Dict[str, int] = {}
        self.service_dist:       Dict[str, int] = {}
        self.avg_in_degree:      float = 0.0
        self.avg_out_degree:     float = 0.0
        self.max_in_degree:      int = 0
        self.max_out_degree:     int = 0
        self.max_in_node:        str = ""
        self.max_out_node:       str = ""
        self.connected_components: int = 0
        self.business_flow_count: int = 0
        self.service_cluster_count: int = 0
        self.lineage_chain_count: int = 0
        self.business_flows:     List[Dict] = []
        self.service_clusters:   List[Dict] = []
        self.hub_nodes:          List[Dict] = []
        self.complexity_stats:   Dict[str, float] = {}
        self.profile:            Optional[GraphProfile] = None

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "name":                 self.name,
            "generated_at":         self.generated_at,
            "node_count":           self.node_count,
            "edge_count":           self.edge_count,
            "node_types":           self.node_types,
            "relation_types":       self.relation_types,
            "language_distribution": self.language_dist,
            "service_distribution": self.service_dist,
            "degree_stats": {
                "avg_in":           self.avg_in_degree,
                "avg_out":          self.avg_out_degree,
                "max_in":           self.max_in_degree,
                "max_out":          self.max_out_degree,
                "max_in_node":      self.max_in_node,
                "max_out_node":     self.max_out_node,
            },
            "connected_components": self.connected_components,
            "business_flows":       self.business_flow_count,
            "service_clusters":     self.service_cluster_count,
            "lineage_chains":       self.lineage_chain_count,
            "hub_nodes":            self.hub_nodes[:20],
            "complexity_stats":     self.complexity_stats,
            "flow_details":         self.business_flows,
            "cluster_details":      self.service_clusters,
        }
        return d


# ══════════════════════════════════════════════════════════════
#  GRAPH STATISTICS
# ══════════════════════════════════════════════════════════════

class GraphStatistics:
    """
    Comprehensive graph analytics and reporting.

    Usage:
        stats = GraphStatistics()
        report = stats.compute_full_stats(kg)
        stats.generate_summary_report(kg, "outputs/stats.md")
        stats.export_stats_json(report, "outputs/stats.json")
    """

    def __init__(self, verbose: bool = True):
        self.verbose = verbose

    # ── Full Statistics ──────────────────────────────────────

    def compute_full_stats(
        self,
        kg: KnowledgeGraph,
        profile: Optional[GraphProfile] = None,
    ) -> GraphReport:
        """Compute comprehensive graph statistics."""
        t0 = time.time()
        report = GraphReport()

        report.name = kg.name
        report.generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        report.node_count = kg.node_count
        report.edge_count = kg.edge_count

        # Type distributions
        report.node_types = dict(Counter(
            n.node_type for n in kg.nodes.values()
        ))
        report.relation_types = dict(Counter(
            e.relation for e in kg.edges
        ))
        report.language_dist = dict(Counter(
            n.language for n in kg.nodes.values() if n.language
        ))
        report.service_dist = dict(Counter(
            n.service_boundary for n in kg.nodes.values() if n.service_boundary
        ))

        # Degree statistics
        if kg.node_count > 0:
            in_degrees = [n.in_degree for n in kg.nodes.values()]
            out_degrees = [n.out_degree for n in kg.nodes.values()]
            report.avg_in_degree = sum(in_degrees) / len(in_degrees)
            report.avg_out_degree = sum(out_degrees) / len(out_degrees)
            report.max_in_degree = max(in_degrees)
            report.max_out_degree = max(out_degrees)

            for n in kg.nodes.values():
                if n.in_degree == report.max_in_degree:
                    report.max_in_node = n.name
                if n.out_degree == report.max_out_degree:
                    report.max_out_node = n.name

        # Hub nodes (top 20 by total degree)
        sorted_nodes = sorted(
            kg.nodes.values(),
            key=lambda n: n.in_degree + n.out_degree,
            reverse=True,
        )
        report.hub_nodes = [
            {
                "name": n.name,
                "type": n.node_type,
                "in_degree": n.in_degree,
                "out_degree": n.out_degree,
                "file": n.file_path,
                "service": n.service_boundary or "",
            }
            for n in sorted_nodes[:20]
        ]

        # Business enrichments
        report.business_flow_count = len(kg.business_flows)
        report.service_cluster_count = len(kg.service_clusters)
        report.lineage_chain_count = len(kg.lineage_chains)

        # Flow details
        report.business_flows = [
            {
                "name": f.flow_name,
                "type": f.flow_type,
                "nodes": len(f.node_ids),
                "confidence": f.confidence,
            }
            for f in kg.business_flows
        ]

        # Cluster details
        report.service_clusters = [
            {
                "name": c.cluster_name,
                "method": c.detection_method,
                "files": len(c.file_paths),
                "languages": sorted(c.languages) if c.languages else [],
            }
            for c in kg.service_clusters
        ]

        # Complexity statistics
        scores = [n.complexity_score for n in kg.nodes.values() if n.complexity_score > 0]
        if scores:
            report.complexity_stats = {
                "avg": round(sum(scores) / len(scores), 4),
                "max": round(max(scores), 4),
                "min": round(min(scores), 4),
                "high_complexity_count": sum(1 for s in scores if s > 0.7),
            }

        # Profile
        report.profile = profile
        if profile:
            report.connected_components = profile.connected_components

        elapsed = time.time() - t0
        self._log(f"[stats] Computed in {elapsed:.2f}s")

        return report

    # ── Markdown Report ──────────────────────────────────────

    def generate_summary_report(
        self,
        kg: KnowledgeGraph,
        output_path: str,
        report: Optional[GraphReport] = None,
    ) -> str:
        """Generate a human-readable markdown report."""
        if report is None:
            report = self.compute_full_stats(kg)

        lines: List[str] = [
            f"# Knowledge Graph Report: {report.name}",
            "",
            f"*Generated: {report.generated_at}*",
            "",
            "## Overview",
            "",
            f"| Metric | Value |",
            f"|--------|-------|",
            f"| Total Nodes | **{report.node_count:,}** |",
            f"| Total Edges | **{report.edge_count:,}** |",
            f"| Business Flows | {report.business_flow_count} |",
            f"| Service Clusters | {report.service_cluster_count} |",
            f"| Lineage Chains | {report.lineage_chain_count} |",
            f"| Connected Components | {report.connected_components} |",
            "",
            "## Node Type Distribution",
            "",
            "| Type | Count | % |",
            "|------|-------|---|",
        ]
        for ntype, count in sorted(report.node_types.items(), key=lambda x: -x[1]):
            pct = count / max(report.node_count, 1) * 100
            lines.append(f"| {ntype} | {count:,} | {pct:.1f}% |")

        lines.extend([
            "",
            "## Relationship Distribution",
            "",
            "| Relation | Count | % |",
            "|----------|-------|---|",
        ])
        for rtype, count in sorted(report.relation_types.items(), key=lambda x: -x[1]):
            pct = count / max(report.edge_count, 1) * 100
            lines.append(f"| {rtype} | {count:,} | {pct:.1f}% |")

        lines.extend([
            "",
            "## Language Distribution",
            "",
            "| Language | Files |",
            "|----------|-------|",
        ])
        for lang, count in sorted(report.language_dist.items(), key=lambda x: -x[1]):
            lines.append(f"| {lang} | {count:,} |")

        lines.extend([
            "",
            "## Degree Statistics",
            "",
            f"| Metric | Value |",
            f"|--------|-------|",
            f"| Avg In-Degree | {report.avg_in_degree:.2f} |",
            f"| Avg Out-Degree | {report.avg_out_degree:.2f} |",
            f"| Max In-Degree | {report.max_in_degree} ({report.max_in_node}) |",
            f"| Max Out-Degree | {report.max_out_degree} ({report.max_out_node}) |",
            "",
        ])

        # Hub nodes
        if report.hub_nodes:
            lines.extend([
                "## Hub Nodes (Top 20 by Degree)",
                "",
                "| Name | Type | In | Out | Total | File |",
                "|------|------|----|----|-------|------|",
            ])
            for hub in report.hub_nodes:
                total = hub["in_degree"] + hub["out_degree"]
                lines.append(
                    f"| {hub['name']} | {hub['type']} | "
                    f"{hub['in_degree']} | {hub['out_degree']} | "
                    f"{total} | {hub.get('file', '')[:60]} |"
                )
            lines.append("")

        # Service clusters
        if report.service_clusters:
            lines.extend([
                "## Service Clusters",
                "",
                "| Service | Detection | Files | Languages |",
                "|---------|-----------|-------|-----------|",
            ])
            for cluster in report.service_clusters:
                langs = ", ".join(cluster.get("languages", []))
                lines.append(
                    f"| {cluster['name']} | {cluster['method']} | "
                    f"{cluster['files']} | {langs} |"
                )
            lines.append("")

        # Business flows
        if report.business_flows:
            lines.extend([
                "## Business Flows",
                "",
                "| Flow | Type | Nodes | Confidence |",
                "|------|------|-------|------------|",
            ])
            for flow in report.business_flows:
                lines.append(
                    f"| {flow['name']} | {flow['type']} | "
                    f"{flow['nodes']} | {flow['confidence']} |"
                )
            lines.append("")

        # Complexity
        if report.complexity_stats:
            lines.extend([
                "## Complexity Analysis",
                "",
                f"| Metric | Value |",
                f"|--------|-------|",
                f"| Average Complexity | {report.complexity_stats.get('avg', 0):.4f} |",
                f"| Max Complexity | {report.complexity_stats.get('max', 0):.4f} |",
                f"| High Complexity Nodes (>0.7) | {report.complexity_stats.get('high_complexity_count', 0)} |",
                "",
            ])

        md = "\n".join(lines)
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_text(md, encoding="utf-8")
        self._log(f"[stats] Report → {output_path}")
        return output_path

    # ── Service Dependency Map ───────────────────────────────

    def generate_service_map(
        self,
        kg: KnowledgeGraph,
        output_path: str,
    ) -> str:
        """Generate service-to-service dependency map JSON."""
        dep_map: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))

        for edge in kg.edges:
            src_node = kg.nodes.get(edge.from_id)
            tgt_node = kg.nodes.get(edge.to_id)
            if not src_node or not tgt_node:
                continue
            src_svc = src_node.service_boundary
            tgt_svc = tgt_node.service_boundary
            if src_svc and tgt_svc and src_svc != tgt_svc:
                dep_map[src_svc][tgt_svc] += 1

        data = {
            "name": kg.name,
            "services": sorted(set(
                list(dep_map.keys()) +
                [s for deps in dep_map.values() for s in deps]
            )),
            "dependencies": {
                src: dict(deps)
                for src, deps in sorted(dep_map.items())
            },
            "total_cross_service_edges": sum(
                sum(deps.values()) for deps in dep_map.values()
            ),
        }

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        self._log(f"[stats] Service map → {output_path}")
        return output_path

    # ── HLD Summary ──────────────────────────────────────────

    def generate_hld_summary(
        self,
        kg: KnowledgeGraph,
    ) -> str:
        """
        Generate a high-level architecture summary from graph structure.
        Useful as input to documentation generation.
        """
        stats = kg.stats()
        lines: List[str] = [
            f"# High-Level Design Summary: {kg.name}",
            "",
            "## Architecture Overview",
            "",
            f"The system consists of {stats['nodes']} components connected by "
            f"{stats['edges']} relationships across "
            f"{len(stats.get('languages', {}))} programming languages.",
            "",
        ]

        # Service overview
        if kg.service_clusters:
            lines.extend([
                "## Services",
                "",
            ])
            for cluster in kg.service_clusters:
                lines.append(
                    f"- **{cluster.cluster_name}**: "
                    f"{len(cluster.file_paths)} files, "
                    f"languages: {', '.join(sorted(cluster.languages)) if cluster.languages else 'N/A'}"
                )
            lines.append("")

        # API overview
        api_nodes = kg.nodes_by_type(KGNodeType.API_ENDPOINT)
        if api_nodes:
            lines.extend([
                "## API Endpoints",
                "",
            ])
            for api in api_nodes[:30]:
                lines.append(f"- `{api.name}` ({api.file_path})")
            if len(api_nodes) > 30:
                lines.append(f"- ... and {len(api_nodes) - 30} more")
            lines.append("")

        # Data stores
        sql_tables = kg.nodes_by_type(KGNodeType.SQL_TABLE)
        if sql_tables:
            lines.extend([
                "## Data Stores",
                "",
            ])
            for tbl in sql_tables:
                lines.append(f"- Table: `{tbl.name}`")
            lines.append("")

        # Business flows
        if kg.business_flows:
            lines.extend([
                "## Business Flows",
                "",
            ])
            for flow in kg.business_flows[:20]:
                lines.append(f"- **{flow.flow_name}** ({len(flow.node_ids)} steps)")
            lines.append("")

        return "\n".join(lines)

    # ── Export ────────────────────────────────────────────────

    def export_stats_json(
        self,
        report: GraphReport,
        output_path: str,
    ) -> str:
        """Export statistics as JSON."""
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report.to_dict(), f, indent=2, default=str, ensure_ascii=False)
        self._log(f"[stats] JSON → {output_path}")
        return output_path

    def export_stats_xml(
        self,
        report: GraphReport,
        output_path: str,
    ) -> str:
        """Export statistics as XML."""
        root = ET.Element("KnowledgeGraphStats")
        root.set("name", report.name)
        root.set("generated_at", report.generated_at)
        root.set("nodes", str(report.node_count))
        root.set("edges", str(report.edge_count))

        # Node types
        ntc = ET.SubElement(root, "NodeTypeCounts")
        for ntype, count in sorted(report.node_types.items(), key=lambda x: -x[1]):
            e = ET.SubElement(ntc, "Type")
            e.set("name", ntype)
            e.set("count", str(count))

        # Relation types
        rc = ET.SubElement(root, "RelationCounts")
        for rtype, count in sorted(report.relation_types.items(), key=lambda x: -x[1]):
            e = ET.SubElement(rc, "Relation")
            e.set("name", rtype)
            e.set("count", str(count))

        # Languages
        lc = ET.SubElement(root, "Languages")
        for lang, count in sorted(report.language_dist.items(), key=lambda x: -x[1]):
            e = ET.SubElement(lc, "Language")
            e.set("name", lang)
            e.set("count", str(count))

        # Write
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        if _LXML:
            ET.ElementTree(root).write(
                output_path, pretty_print=True,
                xml_declaration=True, encoding="utf-8",
            )
        else:
            raw = ET.tostring(root, encoding="unicode")
            Path(output_path).write_text(
                f'<?xml version="1.0" encoding="UTF-8"?>\n{raw}',
                encoding="utf-8",
            )

        self._log(f"[stats] XML → {output_path}")
        return output_path

    def _log(self, msg: str):
        if self.verbose:
            print(msg, flush=True)
