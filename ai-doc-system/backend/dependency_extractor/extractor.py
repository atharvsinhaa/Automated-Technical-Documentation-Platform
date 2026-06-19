"""
dependency_extractor/extractor.py
────────────────────────────────────────────────────────────────
DependencyExtractor — single entry point that orchestrates
the entire Component 3 pipeline.
"""

from __future__ import annotations
from pathlib import Path
from .xml_loader   import load
from .graph_builder import GraphBuilder
from .exporter     import export_xml
from .neo4j_exporter import export_cypher
from .models       import DependencyGraph


class DependencyExtractor:
    """
    Usage:
        extractor = DependencyExtractor(project_name="airtel")

        graph = extractor.extract(
            combined_xml   = "enterprise_combined.xml",
            output_xml     = "graph_dependencies.xml",
            output_cypher  = "graph.cypher",    # optional
        )
    """

    def __init__(self, project_name: str = "project", verbose: bool = True):
        self.project_name = project_name
        self.verbose      = verbose

    def extract(
        self,
        combined_xml:  str,
        output_xml:    str  = "graph_dependencies.xml",
        output_cypher: str  = "",   # empty = skip
    ) -> DependencyGraph:

        self._log(f"=== Dependency Extractor: {self.project_name} ===")

        # ── 1. Load ───────────────────────────────────────────
        self._log(f"[1/3] Loading combined XML…")
        project = load(combined_xml)
        project.name = self.project_name
        self._log(f"      {len(project.files)} files, "
                  f"{sum(len(f.symbols) for f in project.files)} symbols, "
                  f"{len(project.dependencies)} c2-deps, "
                  f"{len(project.sql_tables)} sql-tables")

        # ── 2. Build graph ────────────────────────────────────
        self._log(f"[2/3] Building dependency graph…")
        builder = GraphBuilder(verbose=self.verbose)
        graph   = builder.build(project)
        graph.name   = self.project_name
        graph.source = combined_xml

        # Print stats
        stats = graph.stats()
        self._log(f"\n  Node types:")
        for nt, cnt in sorted(stats["node_types"].items(), key=lambda x: -x[1]):
            self._log(f"    {nt:<25} {cnt}")
        self._log(f"\n  Relation types:")
        for rt, cnt in sorted(stats["relation_types"].items(), key=lambda x: -x[1]):
            self._log(f"    {rt:<30} {cnt}")

        # ── 3. Export ─────────────────────────────────────────
        self._log(f"\n[3/3] Exporting…")
        export_xml(graph, output_xml)

        if output_cypher:
            export_cypher(graph, output_cypher)

        if graph.errors:
            self._log(f"\n  Warnings ({len(graph.errors)}):")
            for e in graph.errors[:5]:
                self._log(f"    • {e}")

        self._log(f"\n  Total nodes : {graph.node_count}")
        self._log(f"  Total edges : {graph.edge_count}")
        self._log(f"  XML output  : {output_xml}")

        return graph

    def _log(self, msg: str):
        if self.verbose:
            print(msg, flush=True)
