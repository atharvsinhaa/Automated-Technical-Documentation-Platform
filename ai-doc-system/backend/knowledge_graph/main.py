#!/usr/bin/env python3
"""
knowledge_graph/main.py
────────────────────────────────────────────────────────────────
Component 4 CLI — Neo4j Knowledge Graph Builder

Full pipeline: load XML → enrich → optimize → export → (optional) push

Usage:
  python -m backend.knowledge_graph.main \\
    --input  backend/outputs/graph_dependencies.xml \\
    --output backend/outputs/knowledge_graph/ \\
    --stats \\
    --optimize

  # With Neo4j push:
  python -m backend.knowledge_graph.main \\
    --input  backend/outputs/graph_dependencies.xml \\
    --output backend/outputs/knowledge_graph/ \\
    --neo4j  bolt://localhost:7687 \\
    --neo4j-user neo4j \\
    --neo4j-pass password

  # With APOC CSV export:
  python -m backend.knowledge_graph.main \\
    --input  backend/outputs/graph_dependencies.xml \\
    --output backend/outputs/knowledge_graph/ \\
    --csv \\
    --json
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

# Ensure the parent package is importable when running as __main__
sys.path.insert(0, str(Path(__file__).parent.parent))

from knowledge_graph.graph_loader import GraphXMLLoader
from knowledge_graph.graph_builder import KnowledgeGraphBuilder
from knowledge_graph.graph_schema import KGSchema
from knowledge_graph.cypher_generator import CypherGenerator
from knowledge_graph.apoc_loader import APOCLoader
from knowledge_graph.graph_optimizer import GraphOptimizer
from knowledge_graph.graph_indexer import GraphIndexer
from knowledge_graph.graph_stats import GraphStatistics
from knowledge_graph.business_mapper import BusinessMapper
from knowledge_graph.mongodb_extractor import MongoDBExtractor
from knowledge_graph.telecom_ontology import TelecomOntologyMapper
from knowledge_graph.cross_language_linker import CrossLanguageLinker
from knowledge_graph.architecture_mapper import ArchitectureMapper
from knowledge_graph.graphrag_prep import GraphRAGPrep



# ── Telecom Domain Gating ────────────────────────────────────

_TELECOM_KEYWORDS = {
    "telecom", "telco", "oss", "bss", "cdr", "billing",
    "charging", "provisioning", "subscriber", "mediation",
    "inventory", "nms", "ems", "sdn", "nfv", "vnf",
    "volte", "imsi", "msisdn", "diameter", "radius",
    "tmf", "etsi", "3gpp", "lte", "5g", "ran",
    "core_network", "packet_gateway", "pgw", "sgw",
    "mme", "hss", "pcrf", "ocs", "ofcs",
    "rating", "tariff", "roaming", "interconnect",
    "sim", "esim", "ussd", "sms_gateway",
    "network_function", "service_order", "catalog",
}


def _detect_telecom_confidence(kg) -> float:
    """
    Score how likely this repository is telecom-related.

    Returns a float 0.0–1.0:
        >= 0.3 → telecom ontology should be applied
        <  0.3 → skip telecom ontology

    Checks: node names, service cluster names, file paths,
    annotations, and docstrings.
    """
    hits = 0
    total_checked = 0

    # Check node names
    for node in kg.nodes.values():
        total_checked += 1
        name_lower = node.name.lower()
        for kw in _TELECOM_KEYWORDS:
            if kw in name_lower:
                hits += 1
                break

    # Check service cluster names
    for cluster in kg.service_clusters:
        total_checked += 1
        name_lower = cluster.cluster_name.lower()
        for kw in _TELECOM_KEYWORDS:
            if kw in name_lower:
                hits += 1
                break

    if total_checked == 0:
        return 0.0

    return min(1.0, hits / max(total_checked * 0.05, 1))


def main():

    p = argparse.ArgumentParser(
        description="Component 4: Neo4j Knowledge Graph Builder (Enterprise Edition)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic: generate Cypher scripts
  python -m knowledge_graph.main --input graph_dependencies.xml --output kg/

  # Full: optimize, enrich, generate stats
  python -m knowledge_graph.main --input graph.xml --output kg/ --stats --optimize

  # Enterprise Streaming Pipeline (partitioned + scalable)
  python -m knowledge_graph.main --input graph.xml --output kg/ --streaming-pipeline --optimize --stats

  # Incremental update (delta only)
  python -m knowledge_graph.main --input graph.xml --output kg/ --streaming-pipeline --incremental

  # With Neo4j live push
  python -m knowledge_graph.main --input graph.xml --output kg/ --neo4j bolt://localhost:7687
        """,
    )

    # Input/Output
    p.add_argument("--input", required=True,
                   help="Path to graph_dependencies.xml (Component 3 output)")
    p.add_argument("--output", default="outputs/knowledge_graph/",
                   help="Output directory for generated files")
    p.add_argument("--project", default="",
                   help="Project name (default: from XML)")

    # Processing options
    p.add_argument("--optimize", action="store_true",
                   help="Run pre-load graph optimization")
    p.add_argument("--stats", action="store_true",
                   help="Generate statistics and reports")
    p.add_argument("--streaming", action="store_true",
                   help="Use memory-efficient streaming loader (limited fidelity)")

    # Enterprise Streaming Pipeline
    p.add_argument("--streaming-pipeline", action="store_true",
                   help="Use enterprise streaming pipeline (partitioned + scalable)")
    p.add_argument("--partition-strategy", default="auto",
                   choices=["auto", "service", "directory", "domain", "fixed"],
                   help="Partition strategy for streaming pipeline (default: auto)")
    p.add_argument("--incremental", action="store_true",
                   help="Generate delta-only output (requires previous manifest)")
    p.add_argument("--memory-limit", type=int, default=0,
                   help="Memory limit in MB for streaming pipeline (0=unlimited)")
    p.add_argument("--partition-size", type=int, default=10000,
                   help="Max nodes per partition (default: 10000)")

    # Export options
    p.add_argument("--csv", action="store_true",
                   help="Export CSV files for LOAD CSV import")
    p.add_argument("--json", action="store_true",
                   help="Export JSON for apoc.load.json()")
    p.add_argument("--simple-cypher", action="store_true",
                   help="Generate simple MERGE Cypher (backward compatible)")

    # Neo4j options
    p.add_argument("--neo4j", default="",
                   help="Neo4j bolt URI for live push (e.g., bolt://localhost:7687)")
    p.add_argument("--neo4j-user", default="neo4j")
    p.add_argument("--neo4j-pass", default="password")
    p.add_argument("--neo4j-db", default="neo4j",
                   help="Neo4j database name")
    p.add_argument("--batch-size", type=int, default=500,
                   help="Batch size for Cypher operations")

    # Other
    p.add_argument("--quiet", action="store_true")

    args = p.parse_args()
    verbose = not args.quiet

    # ── Enterprise Streaming Pipeline Path ───────────────────
    if args.streaming_pipeline:
        from knowledge_graph.streaming_pipeline import StreamingGraphPipeline
        pipeline = StreamingGraphPipeline(
            partition_strategy=args.partition_strategy,
            max_partition_size=args.partition_size,
            batch_size=args.batch_size,
            incremental=args.incremental,
            optimize=args.optimize,
            generate_stats=args.stats,
            verbose=verbose,
        )
        pipeline.run(
            input_path=args.input,
            output_dir=args.output,
            neo4j_uri=args.neo4j,
            neo4j_user=args.neo4j_user,
            neo4j_pass=args.neo4j_pass,
            neo4j_db=args.neo4j_db,
        )
        return

    # ── Legacy Pipeline (backward compatible) ────────────────
    t_start = time.time()
    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)

    if verbose:
        print("\n" + "="*60)
        print("  Component 4: Neo4j Knowledge Graph Builder")
        print("="*60 + "\n")

    # ── Step 1: Load XML ─────────────────────────────────────

    if verbose:
        print("[1/6] Loading graph XML…")

    loader = GraphXMLLoader(verbose=verbose)
    if args.streaming:
        kg = loader.load_streaming(args.input)
    else:
        kg = loader.load(args.input)

    if args.project:
        kg.name = args.project

    if verbose:
        print(f"  Loaded: {kg.node_count} nodes, {kg.edge_count} edges\n")

    # ── Step 2: Optimize (optional) ──────────────────────────

    if args.optimize:
        if verbose:
            print("[2/6] Optimizing graph…")
        optimizer = GraphOptimizer(verbose=verbose)
        opt_result = optimizer.optimize_pre_load(kg)
        if verbose:
            print(f"  Orphans removed: {opt_result.orphans_removed}")
            print(f"  Edges deduped: {opt_result.edges_deduplicated}")
            print(f"  Final: {opt_result.final_node_count} nodes, "
                  f"{opt_result.final_edge_count} edges\n")
    else:
        if verbose:
            print("[2/6] Skipping optimization (use --optimize)\n")

    # ── Step 3: Enrich ───────────────────────────────────────

    if verbose:
        print("[3/6] Enriching with Enterprise Semantics…")

    # 3.1 Base Builder (BusinessFlows, Lineage, etc.)
    builder = KnowledgeGraphBuilder(verbose=verbose)
    kg = builder.build(kg)

    # 3.2 Telecom Ontology Mapping (gated — only for telecom repos)
    telecom_confidence = _detect_telecom_confidence(kg)
    if telecom_confidence >= 0.3:
        if verbose:
            print(f"  Telecom domain detected (confidence={telecom_confidence:.2f}), applying ontology…")
        telecom = TelecomOntologyMapper(verbose=verbose)
        telecom.map_ontology(kg)
    else:
        if verbose:
            print(f"  Telecom domain not detected (confidence={telecom_confidence:.2f}), skipping ontology")

    # 3.3 MongoDB & Data Inference
    mongo = MongoDBExtractor(verbose=verbose)
    mongo.extract(kg)

    # 3.4 Cross-Language Linking
    cross = CrossLanguageLinker(verbose=verbose)
    cross.link(kg)

    # 3.5 Architecture (HLD/LLD) Mapping
    arch = ArchitectureMapper(verbose=verbose)
    arch.map_architecture(kg)

    # 3.6 GraphRAG Preparation
    rag = GraphRAGPrep(verbose=verbose)
    rag.prepare(kg)

    # ── Step 4: Generate Cypher ──────────────────────────────

    if verbose:
        print("[4/6] Generating Cypher scripts…")

    cypher_gen = CypherGenerator(batch_size=args.batch_size, verbose=verbose)
    cypher_files = cypher_gen.generate_full(kg, str(out_dir))

    if args.simple_cypher:
        cypher_gen.generate_simple_cypher(kg, str(out_dir / "graph_simple.cypher"))

    if verbose:
        print()

    # ── Step 5: Additional exports ───────────────────────────

    if verbose:
        print("[5/6] Additional exports…")

    apoc = APOCLoader(verbose=verbose)

    if args.csv:
        csv_dir = str(out_dir / "csv")
        apoc.generate_csv_export(kg, csv_dir)

    if args.json:
        apoc.generate_json_export(kg, str(out_dir))

    # Always generate APOC import script
    apoc.generate_apoc_import_script(
        kg,
        str(out_dir / "apoc_import.cypher"),
        csv_dir=str(out_dir / "csv") if args.csv else None,
        json_path=str(out_dir / "knowledge_graph.json") if args.json else None,
    )

    # Memory estimates
    mem = apoc.estimate_memory_requirements(kg)

    # Post-load optimization script
    optimizer = GraphOptimizer(verbose=verbose)
    post_load = optimizer.generate_post_load_cypher(kg)
    post_load_path = str(out_dir / "post_load_optimize.cypher")
    Path(post_load_path).write_text(post_load, encoding="utf-8")

    if verbose:
        print()

    # ── Step 6: Statistics & Reports ─────────────────────────

    if args.stats:
        if verbose:
            print("[6/6] Generating statistics…")

        stats_gen = GraphStatistics(verbose=verbose)

        # Graph profile
        profile = optimizer.generate_graph_profile(kg)

        # Full report
        report = stats_gen.compute_full_stats(kg, profile=profile)

        # Export stats
        stats_gen.export_stats_json(report, str(out_dir / "graph_stats.json"))
        stats_gen.generate_summary_report(kg, str(out_dir / "graph_stats.md"), report=report)
        stats_gen.generate_service_map(kg, str(out_dir / "service_map.json"))
        stats_gen.export_stats_xml(report, str(out_dir / "graph_stats.xml"))

        # Business flow summaries
        if kg.business_flows:
            mapper = BusinessMapper(verbose=verbose)
            flow_summaries = mapper.generate_flow_summaries(kg, kg.business_flows)
            import json
            flows_path = str(out_dir / "business_flows.json")
            with open(flows_path, "w", encoding="utf-8") as f:
                json.dump(
                    [{"flow_id": s.flow_id, "flow_name": s.flow_name,
                      "description": s.description, "entry_point": s.entry_point,
                      "exit_points": s.exit_points, "node_count": s.node_count,
                      "languages": s.languages, "services": s.services,
                      "tables_touched": s.tables_touched}
                     for s in flow_summaries],
                    f, indent=2, ensure_ascii=False,
                )
            if verbose:
                print(f"[stats] Business flows → {flows_path}")

        # Lineage chains
        if kg.lineage_chains:
            import json
            chains_path = str(out_dir / "lineage_chains.json")
            with open(chains_path, "w", encoding="utf-8") as f:
                json.dump(
                    [{"chain_id": c.chain_id, "chain_type": c.chain_type,
                      "depth": c.depth, "confidence": c.confidence,
                      "description": c.description,
                      "source": c.source_id, "sink": c.sink_id}
                     for c in kg.lineage_chains],
                    f, indent=2, ensure_ascii=False,
                )
            if verbose:
                print(f"[stats] Lineage chains → {chains_path}")

        # HLD summary
        hld = stats_gen.generate_hld_summary(kg)
        hld_path = str(out_dir / "hld_summary.md")
        Path(hld_path).write_text(hld, encoding="utf-8")
        if verbose:
            print(f"[stats] HLD summary → {hld_path}")

        # Index recommendations
        indexer = GraphIndexer(verbose=verbose)
        recs = indexer.recommend_indexes(kg)
        recs_path = str(out_dir / "index_recommendations.json")
        import json
        with open(recs_path, "w", encoding="utf-8") as f:
            json.dump(
                [{"name": r.name, "cypher": r.cypher, "reason": r.reason,
                  "priority": r.priority}
                 for r in recs],
                f, indent=2, ensure_ascii=False,
            )
        if verbose:
            print(f"[stats] Index recommendations → {recs_path}")
    else:
        if verbose:
            print("[6/6] Skipping stats (use --stats)\n")

    # ── Optional: Neo4j Live Push ────────────────────────────

    if args.neo4j:
        if verbose:
            print(f"\n[neo4j] Pushing to {args.neo4j}…")

        from knowledge_graph.neo4j_exporter import Neo4jExporter
        with Neo4jExporter(
            uri=args.neo4j,
            user=args.neo4j_user,
            password=args.neo4j_pass,
            database=args.neo4j_db,
            batch_size=args.batch_size,
            verbose=verbose,
        ) as exporter:
            result = exporter.push(kg)
            if result.success:
                verification = exporter.verify_graph(kg)
                if not verification.success:
                    print(f"\n  ⚠ Verification issues: {verification.issues}")

    # ── Summary ──────────────────────────────────────────────

    elapsed = time.time() - t_start

    if verbose:
        print(f"\n{'='*60}")
        print(f"  Component 4 Complete")
        print(f"  ─────────────────────")
        print(f"  Nodes:           {kg.node_count:,}")
        print(f"  Edges:           {kg.edge_count:,}")
        print(f"  Business Flows:  {len(kg.business_flows)}")
        print(f"  Service Clusters:{len(kg.service_clusters)}")
        print(f"  Lineage Chains:  {len(kg.lineage_chains)}")
        print(f"  Output:          {out_dir}/")
        print(f"  Time:            {elapsed:.2f}s")
        print(f"  Memory Estimate: heap={mem['recommended_heap']}, "
              f"pagecache={mem['recommended_pagecache']}")
        print(f"{'='*60}\n")

        # List generated files
        print("  Generated files:")
        for p in sorted(out_dir.rglob("*")):
            if p.is_file():
                kb = p.stat().st_size / 1024
                print(f"    {p.relative_to(out_dir)}  ({kb:.1f} KB)")
        print()


if __name__ == "__main__":
    main()
