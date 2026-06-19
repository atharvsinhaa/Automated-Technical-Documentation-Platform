"""
knowledge_graph/streaming_pipeline.py
────────────────────────────────────────────────────────────────
Enterprise Streaming Graph Pipeline.

Orchestrates the full enterprise graph processing flow with:
  - Memory-bounded processing
  - Partition-aware enrichment and export
  - Streaming Neo4j ingestion
  - Incremental delta support
  - Partitioned output generation

Replaces the monolithic "load all → enrich all → export all"
pattern with a scalable, partition-at-a-time pipeline.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Dict, List, Optional

from .models import (
    KnowledgeGraph, GraphPartition, PartitionManifest,
    KGNodeType,
)
from .graph_loader import GraphXMLLoader
from .graph_builder import KnowledgeGraphBuilder
from .graph_optimizer import GraphOptimizer
from .graph_partitioner import GraphPartitioner
from .incremental_updater import IncrementalUpdater
from .cypher_generator import CypherGenerator
from .apoc_loader import APOCLoader
from .graph_stats import GraphStatistics
from .graph_schema import KGSchema
from .business_mapper import BusinessMapper
from .mongodb_extractor import MongoDBExtractor
from .telecom_ontology import TelecomOntologyMapper
from .cross_language_linker import CrossLanguageLinker
from .architecture_mapper import ArchitectureMapper
from .graphrag_prep import GraphRAGPrep


class StreamingGraphPipeline:
    """
    Enterprise streaming graph pipeline.

    Usage:
        pipeline = StreamingGraphPipeline(
            partition_strategy="auto",
            max_partition_size=10000,
        )
        pipeline.run(
            input_path="graph_dependencies.xml",
            output_dir="outputs/knowledge_graph/",
        )
    """

    def __init__(
        self,
        partition_strategy: str = "auto",
        max_partition_size: int = 10_000,
        batch_size: int = 500,
        incremental: bool = False,
        optimize: bool = True,
        generate_stats: bool = True,
        verbose: bool = True,
    ):
        self.partition_strategy = partition_strategy
        self.max_partition_size = max_partition_size
        self.batch_size = batch_size
        self.incremental = incremental
        self.optimize = optimize
        self.generate_stats = generate_stats
        self.verbose = verbose

    def run(
        self,
        input_path: str,
        output_dir: str,
        neo4j_uri: str = "",
        neo4j_user: str = "neo4j",
        neo4j_pass: str = "password",
        neo4j_db: str = "neo4j",
    ) -> Dict:
        """
        Run the full streaming pipeline.

        Returns a summary dict with counts and timing.
        """
        t_start = time.time()
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)

        if self.verbose:
            print("\n" + "="*60)
            print("  Enterprise Streaming Graph Pipeline")
            print("="*60 + "\n")

        # ── Step 1: Load XML ─────────────────────────────────
        self._log("[1/8] Loading graph XML…")
        loader = GraphXMLLoader(verbose=self.verbose)
        kg = loader.load(input_path)
        self._log(f"  Loaded: {kg.node_count} nodes, {kg.edge_count} edges")

        # ── Step 2: Optimize ─────────────────────────────────
        if self.optimize:
            self._log("[2/8] Optimizing graph…")
            optimizer = GraphOptimizer(verbose=self.verbose)
            optimizer.optimize_pre_load(kg)

        # ── Step 3: Enrich ───────────────────────────────────
        self._log("[3/8] Enriching with Enterprise Semantics…")
        self._enrich(kg)

        # ── Step 4: Partition ────────────────────────────────
        self._log("[4/8] Partitioning graph…")
        partitioner = GraphPartitioner(
            strategy=self.partition_strategy,
            max_partition_size=self.max_partition_size,
            verbose=self.verbose,
        )
        partitions = partitioner.partition(kg)
        manifest = partitioner.build_manifest(kg, partitions)

        # ── Step 5: Incremental diff (optional) ──────────────
        deltas = None
        if self.incremental:
            self._log("[5/8] Computing incremental delta…")
            updater = IncrementalUpdater(verbose=self.verbose)
            old_manifest = updater.load_previous_manifest(
                str(out / "partitions" / "partition_manifest.json")
            )
            deltas = updater.compute_delta(kg, partitions, old_manifest)

            if old_manifest and all(d.op_type == "add" and d.entity_type == "partition" 
                                    for d in deltas if d.op_type == "delete"):
                # Check if delta is substantially smaller than full
                unchanged = sum(
                    1 for p in partitions
                    if any(
                        op.partition_id == p.partition_id and op.content_hash == p.content_hash
                        for op in (old_manifest.partitions if old_manifest else [])
                    )
                )
                self._log(f"  {unchanged} partitions unchanged")

            # Write delta Cypher
            updater.generate_delta_cypher(
                deltas, str(out / "delta_update.cypher"), self.batch_size
            )
        else:
            self._log("[5/8] Skipping incremental (full build)")

        # ── Step 6: Export partitions ────────────────────────
        self._log("[6/8] Exporting partitioned outputs…")
        partitioner.export_partitions(kg, partitions, str(out))

        # Also generate full Cypher + CSV for backward compatibility
        cypher_gen = CypherGenerator(batch_size=self.batch_size, verbose=self.verbose)
        cypher_gen.generate_full(kg, str(out))

        apoc = APOCLoader(verbose=self.verbose)
        apoc.generate_csv_export(kg, str(out / "csv"))
        apoc.generate_json_export(kg, str(out))
        apoc.generate_apoc_import_script(
            kg, str(out / "apoc_import.cypher"),
            csv_dir=str(out / "csv"),
            json_path=str(out / "knowledge_graph.json"),
        )

        # Generate segmented Neo4j batch files
        self._generate_batch_cypher(kg, partitions, str(out / "neo4j_batches"))

        # ── Step 7: Post-load scripts ────────────────────────
        self._log("[7/8] Generating post-load optimizations…")
        optimizer = GraphOptimizer(verbose=self.verbose)
        post_load = optimizer.generate_post_load_cypher(kg)
        (out / "post_load_optimize.cypher").write_text(post_load, encoding="utf-8")

        mem = apoc.estimate_memory_requirements(kg)

        # ── Step 8: Statistics & Reports ─────────────────────
        if self.generate_stats:
            self._log("[8/8] Generating statistics…")
            self._generate_stats(kg, partitions, str(out))
        else:
            self._log("[8/8] Skipping stats")

        # ── Step 9: Optional Neo4j Push ──────────────────────
        if neo4j_uri:
            self._log(f"[neo4j] Streaming push to {neo4j_uri}…")
            self._push_to_neo4j(kg, partitions, neo4j_uri, neo4j_user, neo4j_pass, neo4j_db)

        # ── Summary ──────────────────────────────────────────
        elapsed = time.time() - t_start
        summary = {
            "nodes": kg.node_count,
            "edges": kg.edge_count,
            "partitions": len(partitions),
            "business_flows": len(kg.business_flows),
            "service_clusters": len(kg.service_clusters),
            "lineage_chains": len(kg.lineage_chains),
            "cross_partition_edges": manifest.cross_partition_edges,
            "elapsed_seconds": round(elapsed, 2),
            "memory_heap": mem["recommended_heap"],
            "memory_pagecache": mem["recommended_pagecache"],
        }

        if self.verbose:
            print(f"\n{'='*60}")
            print(f"  Streaming Pipeline Complete")
            print(f"  {'─'*40}")
            print(f"  Nodes:              {summary['nodes']:,}")
            print(f"  Edges:              {summary['edges']:,}")
            print(f"  Partitions:         {summary['partitions']}")
            print(f"  Business Flows:     {summary['business_flows']}")
            print(f"  Service Clusters:   {summary['service_clusters']}")
            print(f"  Lineage Chains:     {summary['lineage_chains']}")
            print(f"  Cross-Part. Edges:  {summary['cross_partition_edges']}")
            print(f"  Time:               {elapsed:.2f}s")
            print(f"  Output:             {out}/")
            print(f"{'='*60}\n")

            print("  Generated structure:")
            for p in sorted(out.rglob("*")):
                if p.is_file():
                    kb = p.stat().st_size / 1024
                    rel = p.relative_to(out)
                    print(f"    {rel}  ({kb:.1f} KB)")
            print()

        return summary

    # ── Enrichment pipeline ──────────────────────────────────

    def _enrich(self, kg: KnowledgeGraph):
        """Run the full multi-phase semantic enrichment."""
        builder = KnowledgeGraphBuilder(verbose=self.verbose)
        kg = builder.build(kg)

        TelecomOntologyMapper(verbose=self.verbose).map_ontology(kg)
        MongoDBExtractor(verbose=self.verbose).extract(kg)
        CrossLanguageLinker(verbose=self.verbose).link(kg)
        ArchitectureMapper(verbose=self.verbose).map_architecture(kg)
        GraphRAGPrep(verbose=self.verbose).prepare(kg)

    # ── Batch Cypher generation ──────────────────────────────

    def _generate_batch_cypher(
        self,
        kg: KnowledgeGraph,
        partitions: List[GraphPartition],
        output_dir: str,
    ):
        """Generate segmented Cypher batches for Neo4j ingestion."""
        batch_dir = Path(output_dir)
        batch_dir.mkdir(parents=True, exist_ok=True)

        # Schema batch (always first)
        schema = KGSchema.generate_full_schema_script()
        (batch_dir / "batch_000_schema.cypher").write_text(schema, encoding="utf-8")

        batch_manifest = {
            "total_batches": 0,
            "order": ["batch_000_schema.cypher"],
        }

        cypher_gen = CypherGenerator(batch_size=self.batch_size, verbose=False)

        batch_idx = 1
        for p in partitions:
            sub = kg.subgraph(p.node_ids)
            batch_name = f"batch_{batch_idx:03d}_{p.partition_name.replace('/', '_')}.cypher"
            data_script = cypher_gen._generate_data_script(sub)
            (batch_dir / batch_name).write_text(data_script, encoding="utf-8")
            batch_manifest["order"].append(batch_name)
            batch_idx += 1

        # Cross-partition edges
        cross_edges = kg.cross_partition_edges(partitions)
        if cross_edges:
            cross_name = f"batch_{batch_idx:03d}_cross_partition.cypher"
            cross_lines = ["// Cross-partition edges", ""]
            edges_by_rel: Dict[str, list] = {}
            for e in cross_edges:
                edges_by_rel.setdefault(e.relation, []).append(e)
            for rel_type, edges in edges_by_rel.items():
                for batch_lines in cypher_gen._generate_edge_unwind_batches(edges, rel_type):
                    cross_lines.extend(batch_lines)
            (batch_dir / cross_name).write_text("\n".join(cross_lines), encoding="utf-8")
            batch_manifest["order"].append(cross_name)
            batch_idx += 1

        batch_manifest["total_batches"] = batch_idx
        (batch_dir / "batch_manifest.json").write_text(
            json.dumps(batch_manifest, indent=2), encoding="utf-8"
        )

        self._log(f"[streaming] Generated {batch_idx} Neo4j batch files → {batch_dir}")

    # ── Statistics ───────────────────────────────────────────

    def _generate_stats(
        self,
        kg: KnowledgeGraph,
        partitions: List[GraphPartition],
        output_dir: str,
    ):
        """Generate all statistics and reports."""
        out = Path(output_dir)
        stats_dir = out / "graph_stats"
        stats_dir.mkdir(parents=True, exist_ok=True)

        optimizer = GraphOptimizer(verbose=self.verbose)
        stats_gen = GraphStatistics(verbose=self.verbose)

        profile = optimizer.generate_graph_profile(kg)
        report = stats_gen.compute_full_stats(kg, profile=profile)

        stats_gen.export_stats_json(report, str(stats_dir / "graph_stats.json"))
        stats_gen.generate_summary_report(kg, str(stats_dir / "graph_stats.md"), report=report)
        stats_gen.generate_service_map(kg, str(stats_dir / "service_map.json"))
        stats_gen.export_stats_xml(report, str(stats_dir / "graph_stats.xml"))

        # Also write to top-level for backward compat
        stats_gen.export_stats_json(report, str(out / "graph_stats.json"))
        stats_gen.generate_service_map(kg, str(out / "service_map.json"))

        # Business flows
        if kg.business_flows:
            mapper = BusinessMapper(verbose=self.verbose)
            flow_summaries = mapper.generate_flow_summaries(kg, kg.business_flows)
            flows_data = [
                {"flow_id": s.flow_id, "flow_name": s.flow_name,
                 "description": s.description, "entry_point": s.entry_point,
                 "exit_points": s.exit_points, "node_count": s.node_count,
                 "languages": s.languages, "services": s.services,
                 "tables_touched": s.tables_touched}
                for s in flow_summaries
            ]
            for path in [out / "business_flows.json", out / "workflows" / "business_flows.json"]:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(flows_data, indent=2, ensure_ascii=False), encoding="utf-8")

        # Lineage
        if kg.lineage_chains:
            lineage_dir = out / "lineage"
            lineage_dir.mkdir(parents=True, exist_ok=True)
            chains_data = [
                {"chain_id": c.chain_id, "chain_type": c.chain_type,
                 "depth": c.depth, "confidence": c.confidence,
                 "description": c.description,
                 "source": c.source_id, "sink": c.sink_id}
                for c in kg.lineage_chains
            ]
            (lineage_dir / "lineage_chains.json").write_text(
                json.dumps(chains_data, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            (out / "lineage_chains.json").write_text(
                json.dumps(chains_data, indent=2, ensure_ascii=False), encoding="utf-8"
            )

        # HLD
        hld = stats_gen.generate_hld_summary(kg)
        (out / "hld_summary.md").write_text(hld, encoding="utf-8")

        # Service clusters
        svc_dir = out / "service_clusters"
        svc_dir.mkdir(parents=True, exist_ok=True)
        (svc_dir / "service_map.json").write_text(
            (out / "service_map.json").read_text(encoding="utf-8"), encoding="utf-8"
        )

        # GraphRAG indexes
        self._generate_graphrag_indexes(kg, str(out))

    def _generate_graphrag_indexes(self, kg: KnowledgeGraph, output_dir: str):
        """Generate GraphRAG retrieval index files."""
        out = Path(output_dir)

        # Chunk index
        chunk_index = []
        for node in kg.nodes.values():
            if node.semantic_chunk:
                chunk_index.append({
                    "node_id": node.id,
                    "node_type": node.node_type,
                    "name": node.name,
                    "chunk_text": node.semantic_chunk,
                    "centrality": node.centrality_score,
                })

        (out / "chunk_index.json").write_text(
            json.dumps(chunk_index, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
        self._log(f"[graphrag] Chunk index: {len(chunk_index)} entries → {out / 'chunk_index.json'}")

    # ── Neo4j push ───────────────────────────────────────────

    def _push_to_neo4j(
        self,
        kg: KnowledgeGraph,
        partitions: List[GraphPartition],
        uri: str, user: str, password: str, db: str,
    ):
        """Stream partitions to Neo4j."""
        from .neo4j_exporter import Neo4jExporter
        with Neo4jExporter(
            uri=uri, user=user, password=password,
            database=db, batch_size=self.batch_size,
            verbose=self.verbose,
        ) as exporter:
            exporter.push_schema()
            for p in partitions:
                sub = kg.subgraph(p.node_ids)
                self._log(f"  Pushing partition '{p.partition_name}' ({len(p.node_ids)} nodes)…")
                exporter.push(sub, mode="full")

    def _log(self, msg: str):
        if self.verbose:
            print(msg, flush=True)
