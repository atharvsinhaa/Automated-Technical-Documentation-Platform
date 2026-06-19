"""
context_builder/lineage_context.py
────────────────────────────────────────────────────────────────
Extracts data lineage context: SQL, MongoDB, API, event, import chains.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from .models import LineageContext
from .neo4j_client import Neo4jClient
from .graph_traverser import GraphTraverser


class LineageExtractor:
    """Extracts lineage context for a target node."""

    # Relation types by lineage category
    SQL_RELS = ["QUERIES_TABLE", "WRITES_TABLE", "CREATES_TABLE", "READS_FROM", "WRITES_TO"]
    MONGO_RELS = ["READS_COLLECTION", "WRITES_COLLECTION", "AGGREGATES_COLLECTION", "LOOKUP_COLLECTION"]
    API_RELS = ["CALLS_API", "RETURNS_RESPONSE", "USES_API", "EXPOSES_API"]
    EVENT_RELS = ["PUBLISHES_TO", "SUBSCRIBES_FROM", "PRODUCES_EVENT", "CONSUMES_EVENT",
                  "PUBLISHES_TO_TOPIC", "SUBSCRIBES_TO_TOPIC"]
    IMPORT_RELS = ["IMPORTS"]

    def __init__(self, client: Neo4jClient, traverser: GraphTraverser, verbose: bool = True):
        self.client = client
        self.traverser = traverser
        self.verbose = verbose

    def extract(self, target: Dict, target_id: str) -> LineageContext:
        """Extract all lineage dimensions for a target."""
        ctx = LineageContext()

        # SQL lineage
        for rel in self.SQL_RELS:
            edges = self.client.get_edges_from(target_id, [rel])
            for e in edges:
                ctx.sql_tables.append({
                    "table": e.get("to_name", ""),
                    "operation": rel.lower(),
                    "file": e.get("to_file_path", ""),
                })

        # Also check downstream for SQL tables
        downstream = self.client.get_downstream(target_id, depth=2, limit=30)
        for d in downstream:
            if d.get("node_type") in ("SQL_TABLE", "SQL_QUERY"):
                if not any(t["table"] == d.get("name") for t in ctx.sql_tables):
                    ctx.sql_tables.append({
                        "table": d.get("name", ""),
                        "operation": "referenced",
                        "file": d.get("file_path", ""),
                    })

        # MongoDB lineage
        for rel in self.MONGO_RELS:
            edges = self.client.get_edges_from(target_id, [rel])
            for e in edges:
                ctx.mongo_collections.append({
                    "collection": e.get("to_name", ""),
                    "operation": rel.lower(),
                })

        # Also check downstream for Mongo collections
        for d in downstream:
            if d.get("node_type") in ("MONGO_COLLECTION", "MONGO_PIPELINE"):
                if not any(c["collection"] == d.get("name") for c in ctx.mongo_collections):
                    ctx.mongo_collections.append({
                        "collection": d.get("name", ""),
                        "operation": "referenced",
                    })

        # API lineage
        for rel in self.API_RELS:
            edges_out = self.client.get_edges_from(target_id, [rel])
            for e in edges_out:
                ctx.api_lineage.append({
                    "api": e.get("to_name", ""),
                    "direction": "outbound",
                    "relation": rel,
                })

            edges_in = self.client.get_edges_to(target_id, [rel])
            for e in edges_in:
                ctx.api_lineage.append({
                    "api": e.get("from_name", ""),
                    "direction": "inbound",
                    "relation": rel,
                })

        # Event / Kafka lineage
        for rel in self.EVENT_RELS:
            edges_out = self.client.get_edges_from(target_id, [rel])
            for e in edges_out:
                ctx.event_lineage.append({
                    "target": e.get("to_name", ""),
                    "direction": "publishes",
                    "relation": rel,
                })
            edges_in = self.client.get_edges_to(target_id, [rel])
            for e in edges_in:
                ctx.event_lineage.append({
                    "source": e.get("from_name", ""),
                    "direction": "subscribes",
                    "relation": rel,
                })

        # Import chain (first 2 levels)
        import_edges = self.client.get_edges_from(target_id, self.IMPORT_RELS)
        for e in import_edges:
            ctx.import_chain.append(e.get("to_name", ""))

        if self.verbose:
            parts = []
            if ctx.sql_tables: parts.append(f"sql={len(ctx.sql_tables)}")
            if ctx.mongo_collections: parts.append(f"mongo={len(ctx.mongo_collections)}")
            if ctx.api_lineage: parts.append(f"api={len(ctx.api_lineage)}")
            if ctx.event_lineage: parts.append(f"events={len(ctx.event_lineage)}")
            if ctx.import_chain: parts.append(f"imports={len(ctx.import_chain)}")
            if parts:
                print(f"[lineage-ctx] {', '.join(parts)}")

        return ctx
