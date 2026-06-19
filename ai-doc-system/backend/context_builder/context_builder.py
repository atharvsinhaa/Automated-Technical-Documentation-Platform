"""
context_builder/context_builder.py
────────────────────────────────────────────────────────────────
Main orchestrator for the Enterprise Context Builder (Component 5).

Single entry point that coordinates all extractors, traversers,
rankers, and compressors to produce a compact, LLM-ready context.
"""

from __future__ import annotations

import time
from typing import Dict, List, Optional

from .models import (
    ContextQuery, ContextResult, ContextNode, PromptPayload,
)
from .neo4j_client import Neo4jClient
from .graph_traverser import GraphTraverser, _dict_to_context_node
from .architecture_context import ArchitectureExtractor
from .business_context import BusinessExtractor
from .telecom_context import TelecomExtractor
from .lineage_context import LineageExtractor
from .workflow_context import WorkflowExtractor
from .source_loader import SourceLoader
from .semantic_ranker import SemanticRanker
from .context_compressor import ContextCompressor
from .prompt_builder import PromptBuilder


class ContextBuilder:
    """
    Enterprise Context Builder — the bridge between Knowledge Graph and LLM.

    Usage:
        builder = ContextBuilder(kg_json_path="knowledge_graph.json")
        result = builder.build_context(ContextQuery(target_file="app.py"))
        prompt = builder.build_prompt(result, prompt_type="documentation")
    """

    def __init__(
        self,
        neo4j_uri:      str = "bolt://localhost:7687",
        neo4j_user:     str = "neo4j",
        neo4j_pass:     str = "password",
        neo4j_db:       str = "neo4j",
        kg_json_path:   Optional[str] = None,
        source_root:    str = ".",
        verbose:        bool = True,
    ):
        self.verbose = verbose
        self.source_root = source_root

        # Initialize Neo4j client
        self.client = Neo4jClient(
            uri=neo4j_uri,
            user=neo4j_user,
            password=neo4j_pass,
            database=neo4j_db,
            kg_json_path=kg_json_path,
            verbose=verbose,
        )

        # Initialize components
        self.traverser = GraphTraverser(self.client, verbose=verbose)
        self.arch_extractor = ArchitectureExtractor(self.client, self.traverser, verbose=verbose)
        self.biz_extractor = BusinessExtractor(self.client, self.traverser, verbose=verbose)
        self._telecom_extractor = None
        self.lineage_extractor = LineageExtractor(self.client, self.traverser, verbose=verbose)
        self.workflow_extractor = WorkflowExtractor(self.client, self.traverser, verbose=verbose)
        self.source_loader = SourceLoader(source_root=source_root, verbose=verbose)
        self.ranker = SemanticRanker()
        self.compressor = ContextCompressor(verbose=verbose)
        self.prompt_builder = PromptBuilder(verbose=verbose)

    def _get_telecom_extractor(self):
        if self._telecom_extractor is None:
            from .telecom_context import TelecomExtractor
            self._telecom_extractor = TelecomExtractor(self.client, self.traverser, verbose=self.verbose)
        return self._telecom_extractor

    def build_context(self, query: ContextQuery) -> ContextResult:
        """
        Build a complete, compressed context for the given query.

        Orchestration:
        1. Resolve target node
        2. Graph traversal (neighborhood + upstream + downstream)
        3. Extract semantic sections (arch, biz, telecom, lineage, workflow)
        4. Load source code
        5. Rank and compress
        """
        t0 = time.time()

        if self.verbose:
            print(f"\n{'='*60}")
            print(f"  Context Builder: {query.target_description}")
            print(f"{'='*60}\n")

        # 1. Resolve target node
        self._log("[1/7] Resolving target node…")
        target_dict = self._resolve_target(query)
        if not target_dict:
            self._log("  ⚠ Target node not found. Building partial context.")
            return ContextResult(query=query, estimated_tokens=0)

        target_id = target_dict.get("id", "")
        target_node = _dict_to_context_node(target_dict, hop=0)
        self._log(f"  → {target_node.name} ({target_node.node_type}) [{target_id}]")

        # 2. Graph traversal
        self._log(f"[2/7] Graph traversal (depth={query.depth})…")
        neighbors, edges = self.traverser.expand_neighborhood(
            target_id, depth=query.depth, limit=80,
        )
        upstream = self.traverser.trace_upstream(target_id, max_depth=query.depth)
        downstream = self.traverser.trace_downstream(target_id, max_depth=query.depth)

        # Merge all neighbors
        all_neighbors = neighbors + upstream + downstream
        all_neighbors = self.ranker.deduplicate(all_neighbors)
        # Remove the target itself from neighbors
        all_neighbors = [n for n in all_neighbors if n.id != target_id]

        self._log(
            f"  → {len(all_neighbors)} neighbors, {len(edges)} edges "
            f"({len(upstream)} upstream, {len(downstream)} downstream)"
        )

        # 3. Extract semantic sections
        self._log("[3/7] Extracting architecture context…")
        arch_ctx = self.arch_extractor.extract(target_dict, target_id)

        self._log("[4/7] Extracting business context…")
        biz_ctx = self.biz_extractor.extract(target_dict, target_id)

        # Telecom context is gated — only extract if the target
        # has telecom-related signals (semantic_tags, business_domain)
        from .models import TelecomContext
        telecom_ctx = TelecomContext()

        telecom_signals = set()
        tags = target_dict.get("semantic_tags", [])
        if isinstance(tags, str):
            tags = [tags]
        telecom_keywords = {
            "telecom", "billing", "charging", "cdr", "provisioning",
            "subscriber", "roaming", "oss", "bss", "5g", "mediation",
        }
        telecom_signals = {t for t in tags if t in telecom_keywords}

        biz_domain = target_dict.get("business_domain", "")
        if biz_domain and any(
            kw in biz_domain.lower()
            for kw in telecom_keywords
        ):
            telecom_signals.add(biz_domain)

        if telecom_signals:
            self._log(f"[4b/7] Telecom signals detected: {telecom_signals}")
            telecom_ctx = self._get_telecom_extractor().extract(target_dict, target_id)
        else:
            self._log("[4b/7] Skipping telecom context (no telecom signals)")

        self._log("[5/7] Extracting lineage + workflow context…")
        lineage_ctx = self.lineage_extractor.extract(target_dict, target_id)
        workflow_ctx = self.workflow_extractor.extract(target_dict, target_id)

        # 6. Load source code
        self._log("[6/7] Loading source code…")
        source_code = None
        related_functions: List[Dict] = []

        if query.include_source and target_node.file_path:
            source_code = self.source_loader.load_file(target_node.file_path)
            related_functions = self.source_loader.load_related_functions(
                all_neighbors, max_functions=8,
            )

        # 7. Compress and assemble
        self._log("[7/7] Compressing context…")
        result = self.compressor.compress(
            query=query,
            target_node=target_node,
            architecture=arch_ctx,
            business=biz_ctx,
            telecom=telecom_ctx,
            lineage=lineage_ctx,
            workflow=workflow_ctx,
            neighbors=all_neighbors,
            edges=edges,
            source_code=source_code,
            related_functions=related_functions,
        )

        elapsed = time.time() - t0
        if self.verbose:
            print(f"\n{'='*60}")
            print(f"  Context Built in {elapsed:.2f}s")
            print(f"  {'─'*40}")
            print(f"  Target:         {target_node.name}")
            print(f"  Nodes:          {result.node_count}")
            print(f"  Edges:          {result.edge_count}")
            print(f"  Est. Tokens:    ~{result.estimated_tokens}")
            print(f"  Token Budget:   {query.token_budget}")
            print(f"{'='*60}\n")

        return result

    def build_prompt(
        self,
        context: ContextResult,
        prompt_type: str = "documentation",
    ) -> PromptPayload:
        """Generate an LLM-ready prompt from the context."""
        return self.prompt_builder.build_prompt(context, prompt_type)

    def _resolve_target(self, query: ContextQuery) -> Optional[Dict]:
        """Resolve the target node from the query."""
        # Try by node ID first
        if query.node_id:
            return self.client.find_node(node_id=query.node_id)

        # Try by file path
        if query.target_file:
            node = self.client.find_node(file_path=query.target_file)
            if node:
                return node
            # Try just the filename
            node = self.client.find_node(name=query.target_file)
            if node:
                return node

        # Try by API
        if query.api:
            node = self.client.find_node(name=query.api, node_type="API_ENDPOINT")
            if node:
                return node

        # Try by service
        if query.service:
            node = self.client.find_node(name=query.service, node_type="SERVICE")
            if not node:
                node = self.client.find_node(name=query.service, node_type="SERVICE_CLUSTER")
            if not node:
                node = self.client.find_node(name=query.service)
            if node:
                return node

        # Try by workflow
        if query.workflow:
            node = self.client.find_node(name=query.workflow, node_type="BUSINESS_FLOW")
            if not node:
                node = self.client.find_node(name=query.workflow)
            if node:
                return node

        # Try by domain
        if query.domain:
            node = self.client.find_node(name=query.domain, node_type="DOMAIN")
            if node:
                return node

        # Try by module
        if query.module:
            node = self.client.find_node(name=query.module)
            if node:
                return node

        return None

    def close(self):
        """Close the Neo4j client."""
        self.client.close()

    def _log(self, msg: str):
        if self.verbose:
            print(msg, flush=True)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
