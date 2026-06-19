"""
knowledge_graph/graph_schema.py
────────────────────────────────────────────────────────────────
Neo4j schema management — constraints, indexes, and label hierarchy.

Generates all DDL Cypher needed to set up a Neo4j database
for the knowledge graph before data loading.

Designed for Neo4j 5.x with APOC Core.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from .models import KGNodeType, KGRelationType


# ──────────────────────────────────────────────────────────────
#  SCHEMA DEFINITIONS
# ──────────────────────────────────────────────────────────────

class KGSchema:
    """
    Enterprise Neo4j schema definition for the knowledge graph.

    Generates:
      - Uniqueness constraints
      - Node property indexes
      - Composite indexes
      - Full-text indexes (for GraphRAG)
      - Relationship indexes
    """

    # All unique node labels that get a uniqueness constraint on `id`
    NODE_LABELS: List[str] = [
        "CodeEntity",
        "DataEntity",
        "BusinessEntity",
        "File",
        "Module",
        "Class",
        "Interface",
        "Enum",
        "Function",
        "AsyncFunction",
        "Method",
        "Constructor",
        "Variable",
        "Constant",
        "Property",
        "Decorator",
        "Lambda",
        "Import",
        "Package",
        "APIEndpoint",
        "APICall",
        "SQLTable",
        "SQLQuery",
        "DataFrame",
        "ReactComponent",
        "ReactHook",
        "SparkJob",
        "Service",
        "Repository",
        "Controller",
        "BusinessFlow",
        "ServiceCluster",
        "DataPipeline",
        "ModuleBoundary",
        "MongoCollection",
        "BsonSchema",
        "MongoQuery",
        "MongoPipeline",
        "DocumentModel",
        "BusinessCapability",
        "Domain",
        "Workflow",
        "BusinessEvent",
        "DomainService",
        "CapabilityGroup",
        "Microservice",
        "BoundedContext",
        "DomainLayer",
        "InfraComponent",
        "EventBus",
    ]

    # Relationship types
    RELATIONSHIP_TYPES: List[str] = KGRelationType.all_types()

    # ── Constraint generation ────────────────────────────────

    @classmethod
    def generate_constraints(cls) -> List[str]:
        """
        Generate uniqueness constraints for every node label.
        These ensure MERGE operations are idempotent.

        Returns Cypher statements ready for execution.
        """
        constraints: List[str] = []

        for label in cls.NODE_LABELS:
            safe_label = label.replace(" ", "_")
            constraint_name = f"uniq_{safe_label.lower()}_id"
            constraints.append(
                f"CREATE CONSTRAINT {constraint_name} IF NOT EXISTS "
                f"FOR (n:{safe_label}) REQUIRE n.id IS UNIQUE;"
            )

        return constraints

    # ── Index generation ─────────────────────────────────────

    @classmethod
    def generate_indexes(cls) -> List[str]:
        """
        Generate all indexes for query performance.

        Index categories:
          1. Lookup indexes (id, name, file_path)
          2. Composite indexes (node_type + file_path, language + node_type)
          3. Full-text indexes (name + docstring + body_preview) for GraphRAG
          4. Relationship property indexes (confidence, weight)
        """
        indexes: List[str] = []

        # ── 1. Single-property lookup indexes ────────────────
        lookup_configs = [
            ("CodeEntity", "name",      "idx_code_name"),
            ("CodeEntity", "file_path", "idx_code_filepath"),
            ("CodeEntity", "language",  "idx_code_language"),
            ("CodeEntity", "node_type", "idx_code_nodetype"),
            ("DataEntity", "name",      "idx_data_name"),
            ("BusinessEntity", "name",  "idx_business_name"),
        ]
        for label, prop, idx_name in lookup_configs:
            indexes.append(
                f"CREATE INDEX {idx_name} IF NOT EXISTS "
                f"FOR (n:{label}) ON (n.{prop});"
            )

        # ── 2. Composite indexes ─────────────────────────────
        composite_configs = [
            ("CodeEntity", ["node_type", "file_path"], "idx_code_type_file"),
            ("CodeEntity", ["language", "node_type"],  "idx_code_lang_type"),
            ("CodeEntity", ["node_type", "name"],      "idx_code_type_name"),
        ]
        for label, props, idx_name in composite_configs:
            prop_list = ", ".join(f"n.{p}" for p in props)
            indexes.append(
                f"CREATE INDEX {idx_name} IF NOT EXISTS "
                f"FOR (n:{label}) ON ({prop_list});"
            )

        # ── 3. Service boundary index ────────────────────────
        indexes.append(
            "CREATE INDEX idx_service_boundary IF NOT EXISTS "
            "FOR (n:CodeEntity) ON (n.service_boundary);"
        )

        # ── 4. Community ID index ────────────────────────────
        indexes.append(
            "CREATE INDEX idx_community IF NOT EXISTS "
            "FOR (n:CodeEntity) ON (n.community_id);"
        )

        return indexes

    @classmethod
    def generate_fulltext_indexes(cls) -> List[str]:
        """
        Generate full-text search indexes for GraphRAG retrieval.
        These enable natural language queries over the code graph.
        """
        return [
            # Full-text index across all code entities
            "CREATE FULLTEXT INDEX ft_code_search IF NOT EXISTS "
            "FOR (n:CodeEntity) ON EACH [n.name, n.docstring, n.body_preview];",

            # Full-text index for data entities
            "CREATE FULLTEXT INDEX ft_data_search IF NOT EXISTS "
            "FOR (n:DataEntity) ON EACH [n.name, n.docstring];",

            # Full-text index for business entities
            "CREATE FULLTEXT INDEX ft_business_search IF NOT EXISTS "
            "FOR (n:BusinessEntity) ON EACH [n.name, n.docstring];",
            
            # Full-text index for GraphRAG semantic chunk
            "CREATE FULLTEXT INDEX ft_semantic_chunk IF NOT EXISTS "
            "FOR (n:CodeEntity) ON EACH [n.semantic_chunk];",
        ]

    @classmethod
    def generate_vector_indexes(cls) -> List[str]:
        """
        Generate vector indexes for GraphRAG embedding search.
        (Requires Neo4j 5.x). Uses 1024 dims as placeholder for e5/bge-large.
        """
        return [
            "CREATE VECTOR INDEX vec_code_chunk IF NOT EXISTS "
            "FOR (n:CodeEntity) ON (n.embedding) "
            "OPTIONS {indexConfig: {`vector.dimensions`: 1024, `vector.similarity_function`: 'cosine'}};",
            
            "CREATE VECTOR INDEX vec_business_chunk IF NOT EXISTS "
            "FOR (n:BusinessEntity) ON (n.embedding) "
            "OPTIONS {indexConfig: {`vector.dimensions`: 1024, `vector.similarity_function`: 'cosine'}};"
        ]

    @classmethod
    def generate_relationship_indexes(cls) -> List[str]:
        """
        Generate relationship property indexes for filtered traversals.
        """
        return [
            # Confidence-based filtering
            "CREATE INDEX idx_rel_confidence IF NOT EXISTS "
            "FOR ()-[r:CALLS]-() ON (r.confidence);",

            "CREATE INDEX idx_rel_lineage IF NOT EXISTS "
            "FOR ()-[r:FEEDS_DATA_TO]-() ON (r.lineage_type);",
        ]

    # ── Full schema script ───────────────────────────────────

    @classmethod
    def generate_full_schema_script(cls) -> str:
        """
        Generate a complete Cypher schema setup script.
        This should be run BEFORE data loading.
        """
        lines: List[str] = [
            "// ============================================================",
            "// Neo4j Knowledge Graph Schema",
            "// Generated by: Enterprise AI Documentation System — Component 4",
            "// Run BEFORE data loading",
            "// ============================================================",
            "",
            "// ── Uniqueness Constraints ──────────────────────────────────",
        ]
        lines.extend(cls.generate_constraints())
        lines.append("")
        lines.append("// ── Property Indexes ─────────────────────────────────────")
        lines.extend(cls.generate_indexes())
        lines.append("")
        lines.append("// ── Full-Text Indexes (GraphRAG) ─────────────────────────")
        lines.extend(cls.generate_fulltext_indexes())
        lines.append("")
        lines.append("// ── Vector Indexes (GraphRAG Embeddings) ─────────────────")
        lines.extend(cls.generate_vector_indexes())
        lines.append("")
        lines.append("// ── Relationship Indexes ─────────────────────────────────")
        lines.extend(cls.generate_relationship_indexes())
        lines.append("")
        lines.append("// Schema setup complete.")

        return "\n".join(lines)

    # ── Validation ───────────────────────────────────────────

    @classmethod
    def validate_against_neo4j(
        cls,
        driver,
        database: str = "neo4j",
    ) -> List[Dict[str, str]]:
        """
        Validate that a live Neo4j instance matches expected schema.

        Args:
            driver: neo4j.GraphDatabase.driver instance
            database: target database name

        Returns:
            List of schema issues found (empty = all OK).
        """
        issues: List[Dict[str, str]] = []

        try:
            with driver.session(database=database) as session:
                # Check constraints
                result = session.run("SHOW CONSTRAINTS")
                existing_constraints = {
                    r["name"] for r in result
                }

                for constraint_cypher in cls.generate_constraints():
                    # Extract constraint name
                    parts = constraint_cypher.split()
                    if len(parts) >= 3:
                        name = parts[2]
                        if name not in existing_constraints:
                            issues.append({
                                "type": "missing_constraint",
                                "name": name,
                                "fix": constraint_cypher,
                            })

                # Check indexes
                result = session.run("SHOW INDEXES")
                existing_indexes = {
                    r["name"] for r in result
                }

                for index_cypher in cls.generate_indexes():
                    parts = index_cypher.split()
                    if len(parts) >= 3:
                        name = parts[2]
                        if name not in existing_indexes:
                            issues.append({
                                "type": "missing_index",
                                "name": name,
                                "fix": index_cypher,
                            })
        except Exception as e:
            issues.append({
                "type": "connection_error",
                "name": str(e),
                "fix": "Ensure Neo4j is running and accessible",
            })

        return issues

    # ── APOC schema helpers ──────────────────────────────────

    @classmethod
    def generate_apoc_schema(cls) -> str:
        """
        Generate APOC-compatible schema setup commands.
        Uses apoc.schema.assert for atomic schema management.
        """
        lines: List[str] = [
            "// APOC Schema Management",
            "// Requires: APOC Core plugin",
            "",
        ]

        # Use apoc.schema.assert for constraint management
        labels_json = ", ".join(
            f'"{label}": ["id"]'
            for label in cls.NODE_LABELS
        )
        lines.append(
            f"CALL apoc.schema.assert("
            f"{{{labels_json}}}, "
            f"{{{labels_json}}}, "
            f"true);"
        )

        return "\n".join(lines)

    # ── Cleanup ──────────────────────────────────────────────

    @classmethod
    def generate_cleanup_script(cls) -> str:
        """
        Generate a script to completely reset the graph database.
        WARNING: This deletes ALL data.
        """
        return "\n".join([
            "// ============================================================",
            "// WARNING: This will DELETE ALL DATA in the database",
            "// ============================================================",
            "",
            "// Delete all relationships first",
            "CALL apoc.periodic.iterate(",
            "  'MATCH ()-[r]->() RETURN r',",
            "  'DELETE r',",
            "  {batchSize: 10000, parallel: true}",
            ");",
            "",
            "// Delete all nodes",
            "CALL apoc.periodic.iterate(",
            "  'MATCH (n) RETURN n',",
            "  'DETACH DELETE n',",
            "  {batchSize: 10000, parallel: true}",
            ");",
            "",
            "// Drop all constraints",
            *[f"DROP CONSTRAINT {c.split()[2]} IF EXISTS;"
              for c in cls.generate_constraints()
              if len(c.split()) >= 3],
            "",
            "// Drop all indexes",
            *[f"DROP INDEX {i.split()[2]} IF EXISTS;"
              for i in cls.generate_indexes()
              if len(i.split()) >= 3],
            "",
            "// Cleanup complete.",
        ])
