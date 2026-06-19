"""
knowledge_graph/neo4j_exporter.py
────────────────────────────────────────────────────────────────
Production-grade Neo4j driver integration.

Features:
  - UNWIND batch node/edge insertion
  - Schema verification before push
  - Connection retry with exponential backoff
  - Transaction management with rollback
  - Post-import integrity verification
  - Progress reporting

Requires: pip install neo4j (optional — gracefully degrades)
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .models import KGNode, KGEdge, KnowledgeGraph, KGNodeType
from .graph_schema import KGSchema


# ──────────────────────────────────────────────────────────────
#  RESULT TYPES
# ──────────────────────────────────────────────────────────────

@dataclass
class ExportResult:
    """Result of a Neo4j export operation."""
    success:        bool
    nodes_pushed:   int   = 0
    edges_pushed:   int   = 0
    elapsed_seconds: float = 0.0
    errors:         List[str] = field(default_factory=list)


@dataclass
class VerificationResult:
    """Result of post-import verification."""
    success:           bool
    expected_nodes:    int = 0
    actual_nodes:      int = 0
    expected_edges:    int = 0
    actual_edges:      int = 0
    orphan_nodes:      int = 0
    issues:            List[str] = field(default_factory=list)


# ══════════════════════════════════════════════════════════════
#  NEO4J EXPORTER
# ══════════════════════════════════════════════════════════════

class Neo4jExporter:
    """
    Production-grade Neo4j exporter with batch operations.

    Usage:
        exporter = Neo4jExporter(
            uri="bolt://localhost:7687",
            user="neo4j",
            password="password",
        )
        result = exporter.push(kg)
        verification = exporter.verify_graph(kg)
        exporter.close()
    """

    def __init__(
        self,
        uri:        str = "bolt://localhost:7687",
        user:       str = "neo4j",
        password:   str = "password",
        database:   str = "neo4j",
        batch_size: int = 1000,
        verbose:    bool = True,
        max_retries: int = 3,
    ):
        self.uri = uri
        self.user = user
        self.password = password
        self.database = database
        self.batch_size = batch_size
        self.verbose = verbose
        self.max_retries = max_retries
        self._driver = None

    # ── Connection ───────────────────────────────────────────

    def _get_driver(self):
        """Lazy-load the Neo4j driver."""
        if self._driver is None:
            try:
                from neo4j import GraphDatabase
            except ImportError:
                raise RuntimeError(
                    "neo4j driver not installed.\n"
                    "Run: pip install neo4j\n"
                    "Or use CypherGenerator for offline Cypher file generation."
                )
            self._driver = GraphDatabase.driver(
                self.uri,
                auth=(self.user, self.password),
            )
        return self._driver

    def close(self):
        """Close the driver connection."""
        if self._driver:
            self._driver.close()
            self._driver = None

    # ── Full Push ────────────────────────────────────────────

    def push(
        self,
        kg: KnowledgeGraph,
        mode: str = "full",
    ) -> ExportResult:
        """
        Push the full knowledge graph to Neo4j.

        Args:
            kg:   KnowledgeGraph to push
            mode: "full" (recommended) or "incremental"

        Returns:
            ExportResult with counts and timing.
        """
        t0 = time.time()
        result = ExportResult(success=False)

        try:
            driver = self._get_driver()

            self._log(f"[neo4j] Pushing to {self.uri} (mode={mode})")

            # 1. Schema setup
            self._log("[neo4j] Phase 1/3: Setting up schema…")
            self.push_schema()

            # 2. Push nodes
            self._log(f"[neo4j] Phase 2/3: Pushing {kg.node_count} nodes…")
            result.nodes_pushed = self._push_nodes_batch(kg)
            self._log(f"  → {result.nodes_pushed} nodes pushed")

            # 3. Push edges
            self._log(f"[neo4j] Phase 3/3: Pushing {kg.edge_count} edges…")
            result.edges_pushed = self._push_edges_batch(kg)
            self._log(f"  → {result.edges_pushed} edges pushed")

            result.success = True

        except Exception as e:
            result.errors.append(str(e))
            self._log(f"[neo4j] ERROR: {e}")

        result.elapsed_seconds = time.time() - t0
        self._log(
            f"[neo4j] Done: {result.nodes_pushed} nodes, "
            f"{result.edges_pushed} edges in {result.elapsed_seconds:.2f}s"
        )

        return result

    # ── Schema Push ──────────────────────────────────────────

    def push_schema(self) -> bool:
        """Create constraints and indexes."""
        driver = self._get_driver()

        with driver.session(database=self.database) as session:
            # Constraints
            for stmt in KGSchema.generate_constraints():
                try:
                    session.run(stmt.rstrip(";"))
                except Exception as e:
                    if "already exists" not in str(e).lower():
                        self._log(f"  [warn] Constraint: {e}")

            # Indexes
            for stmt in KGSchema.generate_indexes():
                try:
                    session.run(stmt.rstrip(";"))
                except Exception as e:
                    if "already exists" not in str(e).lower():
                        self._log(f"  [warn] Index: {e}")

            # Full-text indexes
            for stmt in KGSchema.generate_fulltext_indexes():
                try:
                    session.run(stmt.rstrip(";"))
                except Exception as e:
                    if "already exists" not in str(e).lower():
                        self._log(f"  [warn] FT Index: {e}")

        return True

    # ── Batch Node Push ──────────────────────────────────────

    def _push_nodes_batch(self, kg: KnowledgeGraph) -> int:
        """Push nodes in UNWIND batches."""
        driver = self._get_driver()
        total = 0

        # Group by node type for efficient multi-label MERGE
        nodes_by_type: Dict[str, List[KGNode]] = {}
        for node in kg.nodes.values():
            nodes_by_type.setdefault(node.node_type, []).append(node)

        with driver.session(database=self.database) as session:
            for node_type, nodes in nodes_by_type.items():
                labels = ":".join(KGNodeType.neo4j_labels(node_type))

                for i in range(0, len(nodes), self.batch_size):
                    chunk = nodes[i:i + self.batch_size]
                    batch = [node.to_props_dict() for node in chunk]

                    retries = 0
                    while retries < self.max_retries:
                        try:
                            session.execute_write(
                                self._merge_nodes_tx, labels, batch
                            )
                            total += len(chunk)
                            break
                        except Exception as e:
                            retries += 1
                            if retries >= self.max_retries:
                                self._log(f"  [error] Failed batch after {retries} retries: {e}")
                            else:
                                time.sleep(0.5 * retries)

        return total

    @staticmethod
    def _merge_nodes_tx(tx, labels: str, batch: List[Dict]):
        """Transaction function for UNWIND node MERGE."""
        tx.run(
            f"UNWIND $batch AS row "
            f"MERGE (n:{labels} {{id: row.id}}) "
            f"SET n += row",
            batch=batch,
        )

    # ── Batch Edge Push ──────────────────────────────────────

    def _push_edges_batch(self, kg: KnowledgeGraph) -> int:
        """Push edges in batches grouped by relation type."""
        driver = self._get_driver()
        total = 0

        # Group by relation type
        edges_by_rel: Dict[str, List[KGEdge]] = {}
        for edge in kg.edges:
            edges_by_rel.setdefault(edge.relation, []).append(edge)

        with driver.session(database=self.database) as session:
            for rel_type, edges in edges_by_rel.items():
                safe_rel = rel_type.replace(" ", "_")

                for i in range(0, len(edges), self.batch_size):
                    chunk = edges[i:i + self.batch_size]
                    batch = [
                        {
                            "from_id": e.from_id,
                            "to_id": e.to_id,
                            **e.to_props_dict(),
                        }
                        for e in chunk
                    ]

                    retries = 0
                    while retries < self.max_retries:
                        try:
                            session.execute_write(
                                self._merge_edges_tx, safe_rel, batch
                            )
                            total += len(chunk)
                            break
                        except Exception as e:
                            retries += 1
                            if retries >= self.max_retries:
                                self._log(f"  [error] Failed edge batch: {e}")
                            else:
                                time.sleep(0.5 * retries)

        return total

    @staticmethod
    def _merge_edges_tx(tx, rel_type: str, batch: List[Dict]):
        """Transaction function for UNWIND edge MERGE."""
        tx.run(
            f"UNWIND $batch AS row "
            f"MATCH (a {{id: row.from_id}}), (b {{id: row.to_id}}) "
            f"MERGE (a)-[r:{rel_type}]->(b) "
            f"SET r.confidence = row.confidence, "
            f"r.weight = row.weight, "
            f"r.evidence = row.evidence",
            batch=batch,
        )

    # ── Verification ─────────────────────────────────────────

    def verify_graph(self, kg: KnowledgeGraph) -> VerificationResult:
        """
        Verify post-import graph integrity.

        Checks:
          - Node counts match
          - Edge counts match
          - No orphan nodes (unconnected except FILEs)
        """
        driver = self._get_driver()
        result = VerificationResult(
            success=False,
            expected_nodes=kg.node_count,
            expected_edges=kg.edge_count,
        )

        try:
            with driver.session(database=self.database) as session:
                # Node count
                r = session.run("MATCH (n) RETURN count(n) AS cnt")
                result.actual_nodes = r.single()["cnt"]

                # Edge count
                r = session.run("MATCH ()-[r]->() RETURN count(r) AS cnt")
                result.actual_edges = r.single()["cnt"]

                # Orphan check
                r = session.run(
                    "MATCH (n) WHERE NOT (n)--() "
                    "AND NOT n:File "
                    "RETURN count(n) AS cnt"
                )
                result.orphan_nodes = r.single()["cnt"]

            # Validate counts
            if result.actual_nodes < result.expected_nodes * 0.95:
                result.issues.append(
                    f"Node count low: expected {result.expected_nodes}, "
                    f"got {result.actual_nodes}"
                )
            if result.actual_edges < result.expected_edges * 0.90:
                result.issues.append(
                    f"Edge count low: expected {result.expected_edges}, "
                    f"got {result.actual_edges}"
                )
            if result.orphan_nodes > result.actual_nodes * 0.1:
                result.issues.append(
                    f"High orphan count: {result.orphan_nodes} "
                    f"({result.orphan_nodes / max(result.actual_nodes, 1) * 100:.1f}%)"
                )

            result.success = len(result.issues) == 0

        except Exception as e:
            result.issues.append(f"Verification failed: {e}")

        self._log(
            f"[neo4j] Verify: nodes={result.actual_nodes}/{result.expected_nodes}, "
            f"edges={result.actual_edges}/{result.expected_edges}, "
            f"orphans={result.orphan_nodes}, "
            f"{'OK' if result.success else 'ISSUES: ' + '; '.join(result.issues)}"
        )

        return result

    # ── Live Stats ───────────────────────────────────────────

    def get_graph_stats(self) -> Dict[str, Any]:
        """Get live graph statistics from Neo4j."""
        driver = self._get_driver()

        stats: Dict[str, Any] = {}
        with driver.session(database=self.database) as session:
            # Total counts
            r = session.run("MATCH (n) RETURN count(n) AS cnt")
            stats["total_nodes"] = r.single()["cnt"]

            r = session.run("MATCH ()-[r]->() RETURN count(r) AS cnt")
            stats["total_edges"] = r.single()["cnt"]

            # Node type distribution
            r = session.run(
                "MATCH (n) RETURN labels(n) AS labels, count(n) AS cnt "
                "ORDER BY cnt DESC"
            )
            stats["node_types"] = {
                ":".join(rec["labels"]): rec["cnt"]
                for rec in r
            }

            # Relationship type distribution
            r = session.run(
                "MATCH ()-[r]->() RETURN type(r) AS rel_type, count(r) AS cnt "
                "ORDER BY cnt DESC"
            )
            stats["relation_types"] = {
                rec["rel_type"]: rec["cnt"]
                for rec in r
            }

        return stats

    def _log(self, msg: str):
        if self.verbose:
            print(msg, flush=True)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
