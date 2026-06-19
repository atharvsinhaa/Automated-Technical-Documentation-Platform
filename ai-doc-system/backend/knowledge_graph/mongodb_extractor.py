"""
knowledge_graph/mongodb_extractor.py
────────────────────────────────────────────────────────────────
Enterprise Semantic Extractor for MongoDB and NoSQL patterns.

Infers collections, queries, schemas, aggregation pipelines,
and cross-collection lookups from AST patterns. Supports both
Python (PyMongo/Motor) and JavaScript (Mongoose) semantics.

Does not require runtime data — all inference is from static
code analysis.
"""

from __future__ import annotations

import re
from typing import Dict, List, Set, Tuple

from .models import (
    KnowledgeGraph, KGNode, KGEdge,
    KGNodeType, KGRelationType, make_kg_node_id
)


class MongoDBExtractor:
    """Extracts MongoDB semantic nodes from the raw code graph."""

    def __init__(self, verbose: bool = True):
        self.verbose = verbose
        # Import indicators
        self.mongo_indicators = {
            "pymongo", "mongoose", "motor", "spring-data-mongodb",
            "mongodb", "mongoclient", "mongoengine",
        }
        # Collection name patterns
        self.collection_patterns = [
            re.compile(r"db\.([a-zA-Z0-9_]+)"),                   # db.users.find()
            re.compile(r"collection\(['\"]([^'\"]+)['\"]\)"),      # .collection('users')
            re.compile(r"([a-zA-Z0-9_]+)_collection", re.I),       # users_collection
            re.compile(r"model\(['\"]([^'\"]+)['\"]\s*,", re.I),    # mongoose.model('User', ...)
            re.compile(r"Schema\(\{", re.I),                        # Mongoose schema
        ]
        # Aggregation pipeline stages
        self.pipeline_stages = [
            "$match", "$group", "$sort", "$project", "$unwind",
            "$lookup", "$addFields", "$replaceRoot", "$merge",
            "$out", "$facet", "$bucket", "$graphLookup",
        ]
        # Write operation indicators
        self.write_ops = {
            "insert", "insertone", "insertmany", "update", "updateone",
            "updatemany", "delete", "deleteone", "deletemany", "save",
            "create", "findoneandupdate", "findoneandreplace",
            "bulkwrite", "replaceone",
        }
        # Read operation indicators
        self.read_ops = {
            "find", "findone", "findbyid", "aggregate", "distinct",
            "count", "countdocuments", "estimateddocumentcount",
        }

    def extract(self, kg: KnowledgeGraph) -> int:
        """
        Run the extraction phase on the knowledge graph.
        Returns the number of new semantic nodes/edges created.
        """
        added_nodes = 0
        added_edges = 0

        # Step 1: Identify files/modules that use MongoDB
        mongo_files: Set[str] = set()
        for node in kg.nodes.values():
            if node.node_type == KGNodeType.IMPORT:
                if any(ind in node.name.lower() for ind in self.mongo_indicators):
                    if node.parent_id:
                        mongo_files.add(node.parent_id)
            elif node.node_type == KGNodeType.FILE:
                text = f"{node.name} {node.docstring or ''} {node.body_preview or ''}".lower()
                if any(ind in text for ind in self.mongo_indicators):
                    mongo_files.add(node.id)

        # Step 2: Scan for collections and operations
        collections_found: Dict[str, KGNode] = {}

        for node in list(kg.nodes.values()):
            # Check if node is in a mongo context
            is_mongo_context = self._is_in_mongo_context(node, kg, mongo_files)
            if not is_mongo_context:
                continue

            text = f"{node.name} {node.body_preview or ''}"

            # Extract collection names
            col_names = self._extract_collection_names(text)

            for col_name in col_names:
                col_id = make_kg_node_id(KGNodeType.MONGO_COLLECTION, col_name)

                if col_id not in collections_found:
                    col_node = KGNode(
                        id=col_id,
                        node_type=KGNodeType.MONGO_COLLECTION,
                        name=col_name,
                        language="multi",
                        docstring=f"MongoDB Collection: {col_name}",
                        semantic_tags=["nosql", "mongodb"],
                    )
                    kg.add_node(col_node)
                    collections_found[col_id] = col_node
                    added_nodes += 1

                # Determine read/write relationship
                rel = self._classify_operation(text)
                if kg.safe_add_edge(node.id, col_id, rel,
                                     confidence="medium",
                                     evidence="Inferred from MongoDB AST patterns"):
                    added_edges += 1

                # Link parent function too
                if node.parent_id and node.node_type in (KGNodeType.VARIABLE, KGNodeType.PROPERTY):
                    if kg.safe_add_edge(node.parent_id, col_id, rel,
                                         confidence="low",
                                         evidence="Parent function uses collection variable"):
                        added_edges += 1

            # Step 3: Detect aggregation pipelines
            pipeline_node, p_edges = self._detect_pipeline(node, kg, collections_found)
            if pipeline_node:
                added_nodes += 1
                added_edges += p_edges

            # Step 4: Detect $lookup (cross-collection joins)
            lookup_edges = self._detect_lookups(node, text, kg, collections_found)
            added_edges += lookup_edges

            # Step 5: Detect Mongoose schemas → BSON_SCHEMA nodes
            schema_node = self._detect_mongoose_schema(node, kg)
            if schema_node:
                added_nodes += 1

        if self.verbose:
            print(
                f"[mongodb] Extracted {added_nodes} nodes "
                f"({len(collections_found)} collections) and {added_edges} access edges."
            )

        return added_nodes + added_edges

    def _is_in_mongo_context(
        self, node: KGNode, kg: KnowledgeGraph, mongo_files: Set[str]
    ) -> bool:
        """Check if a node is within a file that imports mongo."""
        if any(ind in node.name.lower() for ind in self.mongo_indicators):
            return True
        curr = node
        depth = 0
        while curr and depth < 5:
            if curr.id in mongo_files:
                return True
            curr = kg.nodes.get(curr.parent_id) if curr.parent_id else None
            depth += 1
        return False

    def _extract_collection_names(self, text: str) -> List[str]:
        """Extract MongoDB collection names from text."""
        names = []
        for pat in self.collection_patterns:
            for m in pat.finditer(text):
                if m.groups():
                    name = m.group(1).lower()
                    # Filter out likely false positives
                    if name not in ("__", "prototype", "constructor", "test") and len(name) > 1:
                        names.append(name)
        return list(set(names))

    def _classify_operation(self, text: str) -> str:
        """Determine if the operation is read, write, or aggregate."""
        text_lower = text.lower()
        if "aggregate" in text_lower or any(s in text_lower for s in self.pipeline_stages):
            return KGRelationType.AGGREGATES_COLLECTION
        if any(op in text_lower for op in self.write_ops):
            return KGRelationType.WRITES_COLLECTION
        return KGRelationType.READS_COLLECTION

    def _detect_pipeline(
        self, node: KGNode, kg: KnowledgeGraph,
        collections: Dict[str, KGNode],
    ) -> Tuple[KGNode | None, int]:
        """Detect aggregation pipeline patterns."""
        text = f"{node.name} {node.body_preview or ''}"
        stages_found = [s for s in self.pipeline_stages if s in text.lower()]

        if len(stages_found) < 2:
            return None, 0

        pipe_id = make_kg_node_id(KGNodeType.MONGO_PIPELINE, f"{node.name}_pipeline")
        pipe_node = KGNode(
            id=pipe_id,
            node_type=KGNodeType.MONGO_PIPELINE,
            name=f"{node.name} Pipeline",
            language=node.language,
            file_path=node.file_path,
            docstring=f"Aggregation pipeline with stages: {', '.join(stages_found)}",
            semantic_tags=["nosql", "pipeline", "aggregation"],
        )
        kg.add_node(pipe_node)

        edges = 0
        if kg.safe_add_edge(node.id, pipe_id, KGRelationType.CALLS,
                             confidence="medium", evidence="Aggregation pipeline"):
            edges += 1

        return pipe_node, edges

    def _detect_lookups(
        self, node: KGNode, text: str,
        kg: KnowledgeGraph, collections: Dict[str, KGNode],
    ) -> int:
        """Detect $lookup patterns and create LOOKUP_COLLECTION edges."""
        edges = 0
        if "$lookup" not in text.lower():
            return 0

        # Try to find the 'from' collection in the lookup
        lookup_from = re.findall(r"from['\"\s:]+([a-zA-Z0-9_]+)", text, re.I)
        for col_name in lookup_from:
            col_name = col_name.lower()
            col_id = make_kg_node_id(KGNodeType.MONGO_COLLECTION, col_name)
            if col_id not in kg.nodes:
                col_node = KGNode(
                    id=col_id,
                    node_type=KGNodeType.MONGO_COLLECTION,
                    name=col_name,
                    language="multi",
                    docstring=f"MongoDB Collection: {col_name} (via $lookup)",
                    semantic_tags=["nosql", "mongodb"],
                )
                kg.add_node(col_node)
            if kg.safe_add_edge(node.id, col_id, KGRelationType.LOOKUP_COLLECTION,
                                 confidence="medium",
                                 evidence="$lookup aggregation stage"):
                edges += 1
        return edges

    def _detect_mongoose_schema(self, node: KGNode, kg: KnowledgeGraph) -> KGNode | None:
        """Detect Mongoose Schema definitions."""
        text = f"{node.name} {node.body_preview or ''}"
        if "schema(" not in text.lower() or node.language not in ("javascript", "typescript", ""):
            return None

        schema_id = make_kg_node_id(KGNodeType.BSON_SCHEMA, f"{node.name}_schema")
        schema_node = KGNode(
            id=schema_id,
            node_type=KGNodeType.BSON_SCHEMA,
            name=f"{node.name} Schema",
            language=node.language,
            file_path=node.file_path,
            docstring=f"Mongoose Schema: {node.name}",
            semantic_tags=["nosql", "schema", "mongoose"],
        )
        kg.add_node(schema_node)
        kg.safe_add_edge(node.id, schema_id, KGRelationType.DEFINES,
                          confidence="medium", evidence="Mongoose Schema definition")
        return schema_node
