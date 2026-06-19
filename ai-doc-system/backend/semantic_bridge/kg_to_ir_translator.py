"""
semantic_bridge/kg_to_ir_translator.py
────────────────────────────────────────────────────────────────
The critical bridge between Knowledge Graph and Semantic IR.

Translates KG's graph-shaped entities into the linear SemanticIR
structure consumed by document generators, diagram generators,
and the comment engine.

This is the single highest-ROI component in the pipeline.
Without it, all downstream generators produce self-referencing
or hardcoded output.

Translation Pipeline:
  1. Service clusters → IR Components
  2. KG edges (inter-service) → IR Relationships
  3. Business flows + lineage chains → IR Workflows
  4. API_ENDPOINT nodes → IR API Endpoints
  5. SQL_TABLE / MONGO_COLLECTION nodes → IR Data Stores
  6. Lineage chains → IR Request Flows
  7. Exception edges → IR Error Paths
  8. Architecture metadata → IR metadata
"""

from __future__ import annotations

import os
import re
import collections
from typing import Dict, List, Optional, Set, Tuple

from backend.knowledge_graph.models import (
    KnowledgeGraph,
    KGNode,
    KGEdge,
    KGNodeType,
    KGRelationType,
    ServiceCluster,
    BusinessFlow,
    LineageChain,
)

from backend.semantic_ir.models import (
    SemanticIR,
    IRComponent,
    IRRelationship,
    IRWorkflow,
    IRApiEndpoint,
    IRDataStore,
    IRRequestFlow,
    IRErrorPath,
)


class KGToIRTranslator:
    """
    Translates a KnowledgeGraph into a SemanticIR.

    This replaces the old directory-scan approach with a graph-grounded
    translation that extracts actual architecture from the KG.

    Usage:
        from backend.knowledge_graph.models import KnowledgeGraph
        from backend.semantic_bridge.kg_to_ir_translator import KGToIRTranslator

        translator = KGToIRTranslator()
        semantic_ir = translator.translate(kg)
    """

    def __init__(self, verbose: bool = True):
        self.verbose = verbose

    def translate(self, kg: KnowledgeGraph) -> SemanticIR:
        """
        Translate a KnowledgeGraph into a SemanticIR.

        Returns a fully populated SemanticIR with components,
        relationships, workflows, API endpoints, data stores,
        request flows, and error paths — all extracted from the KG.
        """
        self._log(f"\n{'='*60}")
        self._log(f"  KG → IR Translator")
        self._log(f"  Input: {kg.node_count} nodes, {kg.edge_count} edges")
        self._log(f"{'='*60}\n")

        ir = SemanticIR(
            repository_type=self._detect_repo_type(kg),
        )

        # 1. Components from service clusters + architecture nodes
        self._log("[1/8] Extracting components…")
        ir.components = self._extract_components(kg)
        self._log(f"  → {len(ir.components)} components")

        # 2. Relationships from inter-component edges
        self._log("[2/8] Extracting relationships…")
        ir.relationships = self._extract_relationships(kg, ir.components)
        self._log(f"  → {len(ir.relationships)} relationships")

        # 3. Workflows from business flows + lineage chains
        self._log("[3/8] Extracting workflows…")
        ir.workflows = self._extract_workflows(kg)
        self._log(f"  → {len(ir.workflows)} workflows")

        # 4. API endpoints
        self._log("[4/8] Extracting API endpoints…")
        ir.api_endpoints = self._extract_api_endpoints(kg)
        self._log(f"  → {len(ir.api_endpoints)} API endpoints")

        # 5. Data stores
        self._log("[5/8] Extracting data stores…")
        ir.data_stores = self._extract_data_stores(kg)
        self._log(f"  → {len(ir.data_stores)} data stores")

        # 6. Request flows from lineage chains
        self._log("[6/8] Extracting request flows…")
        ir.request_flows = self._extract_request_flows(kg)
        self._log(f"  → {len(ir.request_flows)} request flows")

        # 7. Error paths
        self._log("[7/8] Extracting error paths…")
        ir.error_paths = self._extract_error_paths(kg)
        self._log(f"  → {len(ir.error_paths)} error paths")

        # 8. Metadata
        self._log("[8/8] Building metadata…")
        ir.languages = self._extract_languages(kg)
        ir.frameworks = self._extract_frameworks(kg)
        ir.databases = self._extract_databases(kg)
        ir.messaging_systems = self._extract_messaging_systems(kg)
        ir.infrastructure = self._extract_infrastructure(kg)
        ir.ai_ml_tools = self._extract_ai_ml_tools(kg)
        ir.code_analysis_tools = self._extract_code_analysis_tools(kg)
        ir.architecture_pattern, ir.architecture_pattern_confidence, ir.architecture_pattern_evidence = self._detect_architecture_pattern(kg)
        ir.service_count = len(kg.service_clusters)
        self._log(f"  → Languages: {ir.languages}")
        self._log(f"  → Architecture: {ir.architecture_pattern}")

        self._log(f"\n{'='*60}")
        self._log(f"  Translation Complete")
        self._log(f"  Components: {len(ir.components)}")
        self._log(f"  Relationships: {len(ir.relationships)}")
        self._log(f"  Workflows: {len(ir.workflows)}")
        self._log(f"  API Endpoints: {len(ir.api_endpoints)}")
        self._log(f"  Data Stores: {len(ir.data_stores)}")
        self._log(f"  Request Flows: {len(ir.request_flows)}")
        self._log(f"  Error Paths: {len(ir.error_paths)}")
        self._log(f"{'='*60}\n")

        return ir

    # ══════════════════════════════════════════════════════════════
    #  1. COMPONENT EXTRACTION
    # ══════════════════════════════════════════════════════════════

    @staticmethod
    def _infer_layer(component_name: str, component_type: str) -> str:
        """
        Infer enterprise architecture layer from component name,
        type, responsibilities, and purpose.
        """
        name = (component_name or "").lower()
        ctype = (component_type or "").lower()

        # Presentation Layer
        if any(k in name for k in (
            "api", "endpoint", "controller", "router", "view", "handler", "gateway"
        )):
            return "Presentation"

        # Domain Layer
        if any(k in name for k in (
            "domain", "entity", "model", "schema", "semantic", "knowledge"
        )):
            return "Domain"

        # Infrastructure Layer
        if any(k in name for k in (
            "database", "db", "cache", "storage", "queue", "export", "neo4j", "docx", "dependency_extractor"
        )):
            return "Infrastructure"

        # Application Layer (Catch-all for services, pipelines, orchestrators)
        if any(k in name for k in (
            "service", "workflow", "pipeline", "orchestrator", "use_case", 
            "processor", "intelligence", "ast", "context", "combiner", 
            "generator", "analysis"
        )):
            return "Application"

        # Type-based fallback
        if "api" in ctype:
            return "Presentation"
        if "database" in ctype:
            return "Infrastructure"

        return "Application"

    def _extract_components(self, kg: KnowledgeGraph) -> List[IRComponent]:
        """
        Extract components following strict priority rules for file grouping:
        1. Package/module boundaries (directories)
        2. Dependency clusters (SERVICE_CLUSTER nodes)
        3. Call graph communities (from label propagation)
        4. File basenames (last fallback)
        """
        components: List[IRComponent] = []
        seen_names: Set[str] = set()

        # Strategy 1: Explicit MICROSERVICE nodes (keep these as they are high-level architecture)
        for node in kg.nodes_by_type(KGNodeType.MICROSERVICE):
            name = node.name
            if name in seen_names:
                continue
            seen_names.add(name)

            file_paths = self._files_linked_to(kg, node.id)
            components.append(IRComponent(
                name=name,
                component_type="Microservice",
                description=node.docstring or f"Microservice: {name}",
                files=file_paths,
                key_classes=self._key_entities_in(kg, node.id, KGNodeType.CLASS),
                key_functions=self._key_entities_in(kg, node.id, KGNodeType.FUNCTION),
                api_endpoints=self._api_endpoints_for(kg, node.id),
                data_stores=self._data_stores_for(kg, node.id),
                languages=self._languages_for(kg, file_paths),
                service_boundary=name,
                layer=self._infer_layer(name, "Microservice"),
                complexity_score=node.complexity_score,
                confidence=self._cluster_confidence(kg, node.id),
            ))

        # Now we process all files not yet assigned to a microservice
        assigned_files = set()
        for c in components:
            assigned_files.update(c.files)

        groups = collections.defaultdict(list)
        cluster_by_name = {c.cluster_name: c for c in kg.service_clusters}

        for node in kg.nodes_by_type(KGNodeType.FILE):
            path = node.file_path or node.name
            if path in assigned_files:
                continue

            parts = path.replace("\\", "/").split("/")
            
            # Rule 1: Package/module boundaries (Directories)
            if len(parts) >= 2 and parts[0] != ".":
                group_name = parts[0].replace("_", " ").title()
                groups[group_name].append(path)
                continue
            if len(parts) >= 3 and parts[0] == ".":
                group_name = parts[1].replace("_", " ").title()
                groups[group_name].append(path)
                continue

            # Rule 2: Dependency clusters
            cluster_name = None
            for c_name, cluster in cluster_by_name.items():
                if path in cluster.file_paths:
                    cluster_name = c_name
                    break
            if cluster_name:
                groups[cluster_name].append(path)
                continue

            # Rule 3: Call graph communities
            if getattr(node, "community_id", None) is not None:
                group_name = f"Community {node.community_id}"
                groups[group_name].append(path)
                continue

            # Rule 4: File basenames
            basename = parts[-1].split(".")[0]
            if basename.lower() == "root":
                basename = "Core"
            groups[basename.title()].append(path)

        # Rename Community groups to something meaningful based on their files
        final_groups = collections.defaultdict(list)
        for group_name, files in groups.items():
            if group_name.startswith("Community "):
                basenames = [f.split("/")[-1].split(".")[0] for f in files if f]
                if basenames:
                    best_name = sorted(basenames, key=len, reverse=True)[0]
                    final_groups[best_name.title()].extend(files)
                else:
                    final_groups[group_name].extend(files)
            else:
                final_groups[group_name].extend(files)

        for group_name, files in sorted(final_groups.items()):
            if group_name.startswith(".") or group_name.lower() in ("__pycache__", "node_modules", "venv"):
                continue
            if group_name in seen_names:
                continue
            seen_names.add(group_name)

            key_classes = self._classes_in_files(kg, files)
            key_functions = self._functions_in_files(kg, files)
            languages = self._languages_for(kg, files)

            # Re-attach cluster metadata if this group is a dependency cluster
            api_eps = []
            data_stores_list = []
            confidence = "low"
            if group_name in cluster_by_name:
                cluster = cluster_by_name[group_name]
                api_eps = cluster.api_endpoints
                data_stores_list = cluster.tables_accessed
                confidence = cluster.confidence

            description = self._generate_component_description(
                group_name, key_classes, api_eps,
                file_paths=files,
                functions=key_functions,
            )

            components.append(IRComponent(
                name=group_name,
                component_type="Module",
                description=description,
                files=files,
                key_classes=key_classes,
                key_functions=key_functions,
                api_endpoints=api_eps,
                data_stores=data_stores_list,
                languages=languages,
                layer=self._infer_layer(group_name, "Module"),
                confidence=confidence,
            ))

        return components

    # ══════════════════════════════════════════════════════════════
    #  2. RELATIONSHIP EXTRACTION
    # ══════════════════════════════════════════════════════════════

    def _extract_relationships(
        self, kg: KnowledgeGraph, components: List[IRComponent]
    ) -> List[IRRelationship]:
        """
        Extract inter-component relationships from KG edges.

        For each edge in the KG, determine which components the
        source and target nodes belong to. If they belong to
        different components, create an IR relationship.
        """
        # Build node → component mapping
        node_to_component: Dict[str, str] = {}
        for comp in components:
            for f in comp.files:
                # Map files to components
                for node in kg.nodes.values():
                    if node.file_path and (
                        node.file_path == f
                        or node.file_path.endswith(f)
                        or f.endswith(node.file_path)
                    ):
                        node_to_component[node.id] = comp.name

            # Also map by service boundary
            if comp.service_boundary:
                for node in kg.nodes.values():
                    if node.service_boundary == comp.service_boundary:
                        node_to_component[node.id] = comp.name

        # Find inter-component edges
        rel_pairs: Dict[Tuple[str, str, str], int] = {}
        rel_evidence: Dict[Tuple[str, str, str], str] = {}

        # Interesting relationship types for HLD/LLD
        interesting_relations = {
            KGRelationType.CALLS,
            KGRelationType.CALLS_API,
            KGRelationType.IMPORTS,
            KGRelationType.DEPENDS_ON,
            KGRelationType.QUERIES_TABLE,
            KGRelationType.WRITES_TABLE,
            KGRelationType.READS_FROM,
            KGRelationType.WRITES_TO,
            KGRelationType.EXTENDS,
            KGRelationType.IMPLEMENTS,
            KGRelationType.PUBLISHES_TO,
            KGRelationType.SUBSCRIBES_FROM,
            KGRelationType.INVOKES_SERVICE,
        }

        for edge in kg.edges:
            if edge.relation not in interesting_relations:
                continue

            src_comp = node_to_component.get(edge.from_id)
            tgt_comp = node_to_component.get(edge.to_id)

            if src_comp and tgt_comp and src_comp != tgt_comp:
                key = (src_comp, tgt_comp, edge.relation)
                rel_pairs[key] = rel_pairs.get(key, 0) + 1
                if edge.evidence:
                    rel_evidence[key] = edge.evidence

        # Convert to IR relationships (deduped, with count as weight)
        relationships = []
        for (src, tgt, rel_type), count in sorted(
            rel_pairs.items(), key=lambda x: -x[1]
        ):
            relationships.append(IRRelationship(
                source=src,
                target=tgt,
                relationship_type=rel_type,
                evidence=rel_evidence.get((src, tgt, rel_type), ""),
                confidence="high" if count >= 3 else "medium" if count >= 1 else "low",
            ))

        return relationships

    # ══════════════════════════════════════════════════════════════
    #  3. WORKFLOW EXTRACTION
    # ══════════════════════════════════════════════════════════════

    def _extract_workflows(self, kg: KnowledgeGraph) -> List[IRWorkflow]:
        """
        Extract workflows from KG business flows and lineage chains.
        """
        workflows: List[IRWorkflow] = []

        # From business flows
        for flow in kg.business_flows:
            step_names = self._resolve_node_names(kg, flow.node_ids)
            step_names = self._clean_workflow_steps(step_names)
            if not step_names:
                continue

            workflows.append(IRWorkflow(
                name=flow.flow_name,
                steps=step_names,
                workflow_type=flow.flow_type,
                entry_point=self._resolve_node_name(kg, flow.entry_node_id),
                description=flow.description,
                confidence=flow.confidence,
            ))

        # From lineage chains (top-level chains only)
        for chain in kg.lineage_chains:
            if chain.depth < 3:
                continue  # Skip trivial chains

            step_names = self._resolve_node_names(kg, chain.ordered_node_ids)
            step_names = self._clean_workflow_steps(step_names)
            if not step_names:
                continue

            name = chain.description or f"{chain.chain_type.title()} Flow"

            # Deduplicate step names while preserving order
            seen = set()
            deduped_steps = []
            for s in step_names:
                if s not in seen:
                    seen.add(s)
                    deduped_steps.append(s)

            workflows.append(IRWorkflow(
                name=name,
                steps=deduped_steps,
                workflow_type=chain.chain_type,
                entry_point=deduped_steps[0] if deduped_steps else None,
                exit_points=[deduped_steps[-1]] if deduped_steps else [],
                confidence=chain.confidence,
            ))

        # If no workflows were found, synthesize from the call graph
        if not workflows:
            workflows = self._synthesize_workflows_from_call_graph(kg)

        return workflows[:20]  # Cap at 20 workflows

    def _synthesize_workflows_from_call_graph(
        self, kg: KnowledgeGraph
    ) -> List[IRWorkflow]:
        """
        When no business flows or lineage chains exist, synthesize
        basic workflows from the call graph by tracing from API
        endpoints or high-in-degree functions.
        """
        workflows = []

        # Find API endpoint handlers
        for node in kg.nodes_by_type(KGNodeType.API_ENDPOINT):
            # Trace the call chain from this endpoint
            chain = self._trace_call_chain(kg, node.id, max_depth=6)
            if len(chain) >= 2:
                step_names = self._resolve_node_names(kg, chain)
                step_names = self._clean_workflow_steps(step_names)
                if len(step_names) >= 2:
                    workflows.append(IRWorkflow(
                        name=f"API: {node.name}",
                        steps=step_names,
                        workflow_type="api_flow",
                        entry_point=node.name,
                        confidence="medium",
                    ))

        # Find entry-point functions (high in-degree, no callers)
        if not workflows:
            for node in kg.nodes.values():
                if node.node_type in (
                    KGNodeType.FUNCTION, KGNodeType.ASYNC_FUNCTION
                ) and node.in_degree == 0 and node.out_degree >= 2:
                    chain = self._trace_call_chain(kg, node.id, max_depth=5)
                    if len(chain) >= 2:
                        step_names = self._resolve_node_names(kg, chain)
                        step_names = self._clean_workflow_steps(step_names)
                        if len(step_names) >= 2:
                            workflows.append(IRWorkflow(
                                name=f"Flow: {node.name}",
                                steps=step_names,
                                workflow_type="generic",
                                entry_point=node.name,
                                confidence="low",
                            ))

        return workflows[:10]

    def _trace_call_chain(
        self, kg: KnowledgeGraph, start_id: str, max_depth: int = 6
    ) -> List[str]:
        """BFS trace from a start node following CALLS/CALLS_API edges."""
        visited: List[str] = []
        queue = [start_id]
        seen: Set[str] = set()

        while queue and len(visited) < max_depth:
            current = queue.pop(0)
            if current in seen:
                continue
            seen.add(current)
            visited.append(current)

            for edge in kg.outgoing_edges(current):
                if edge.relation in (
                    KGRelationType.CALLS,
                    KGRelationType.CALLS_API,
                    KGRelationType.INVOKES,
                    KGRelationType.EXECUTES_AFTER,
                ):
                    if edge.to_id not in seen:
                        queue.append(edge.to_id)

        return visited

    # ══════════════════════════════════════════════════════════════
    #  4. API ENDPOINT EXTRACTION
    # ══════════════════════════════════════════════════════════════

    def _extract_api_endpoints(self, kg: KnowledgeGraph) -> List[IRApiEndpoint]:
        """Extract API endpoints from KG API_ENDPOINT nodes."""
        endpoints = []

        for node in kg.nodes_by_type(KGNodeType.API_ENDPOINT):
            if self._is_mock_or_test_node(node, kg):
                continue

            # Reject invalid placeholders
            invalid_paths = ["/path", "/test", "/example", "/placeholder", "/foo", "/bar", "/mock", "/sample"]
            if any(inv in node.name.lower() for inv in invalid_paths) or len(node.name) <= 1:
                continue

            # Find the handler function
            handler_fn = None
            handler_file = None
            service = None

            for edge in kg.incoming_edges(node.id):
                src = kg.nodes.get(edge.from_id)
                if not src:
                    continue
                if edge.relation == KGRelationType.DEFINES:
                    if src.node_type == KGNodeType.FILE:
                        handler_file = src.file_path or src.name
                    elif src.node_type in (
                        KGNodeType.FUNCTION, KGNodeType.ASYNC_FUNCTION,
                        KGNodeType.METHOD
                    ):
                        handler_fn = src.name
                        handler_file = src.file_path

                if src.service_boundary:
                    service = src.service_boundary

            # Determine HTTP method from the endpoint name
            method = self._infer_http_method(node.name)

            endpoints.append(IRApiEndpoint(
                path=node.name,
                method=method,
                handler_function=handler_fn,
                handler_file=handler_file,
                service=service,
                description=node.docstring,
            ))

        return endpoints

    # ══════════════════════════════════════════════════════════════
    #  5. DATA STORE EXTRACTION
    # ══════════════════════════════════════════════════════════════

    def _extract_data_stores(self, kg: KnowledgeGraph) -> List[IRDataStore]:
        """Extract data stores from SQL_TABLE, MONGO_COLLECTION, DATAFRAME nodes."""
        stores = []

        type_map = {
            KGNodeType.SQL_TABLE: "sql_table",
            KGNodeType.MONGO_COLLECTION: "mongo_collection",
            KGNodeType.DATAFRAME: "dataframe",
        }

        for node_type, store_type in type_map.items():
            for node in kg.nodes_by_type(node_type):
                if self._is_mock_or_test_node(node, kg):
                    continue
                # Find which functions access this store
                accessed_by = []
                operations = set()

                for edge in kg.incoming_edges(node.id):
                    src = kg.nodes.get(edge.from_id)
                    if src:
                        name = src.service_boundary or src.name
                        if not any(ext in name.lower() for ext in (".sql", ".py", ".ts", ".js", ".java", ".json", ".xml", ".csv", ".yml", ".yaml")):
                            if name not in accessed_by:
                                accessed_by.append(name)
                                
                        if edge.relation == KGRelationType.QUERIES_TABLE:
                            operations.add("SELECT")
                        elif edge.relation == KGRelationType.WRITES_TABLE:
                            operations.add("INSERT/UPDATE")
                        elif edge.relation == KGRelationType.CREATES_TABLE:
                            operations.add("CREATE")
                        elif edge.relation == KGRelationType.READS_FROM:
                            operations.add("READ")
                        elif edge.relation == KGRelationType.WRITES_TO:
                            operations.add("WRITE")

                stores.append(IRDataStore(
                    name=node.name,
                    store_type=store_type,
                    accessed_by=accessed_by[:10],
                    operations=sorted(operations),
                ))

        return stores

    # ══════════════════════════════════════════════════════════════
    #  6. REQUEST FLOW EXTRACTION
    # ══════════════════════════════════════════════════════════════

    def _extract_request_flows(self, kg: KnowledgeGraph) -> List[IRRequestFlow]:
        """
        Extract request lifecycle flows from lineage chains.
        A request flow traces: API Endpoint → Handler → Service → Repository → DB
        """
        flows = []

        for chain in kg.lineage_chains:
            if chain.chain_type == "api" and chain.depth >= 2:
                step_names = self._resolve_node_names(kg, chain.ordered_node_ids)
                if not step_names:
                    continue

                # Determine exit point
                exit_node_id = chain.ordered_node_ids[-1] if chain.ordered_node_ids else None
                exit_node = kg.nodes.get(exit_node_id) if exit_node_id else None
                exit_name = exit_node.name if exit_node else None

                flows.append(IRRequestFlow(
                    name=chain.description or f"API Chain ({chain.chain_id})",
                    entry_point=step_names[0],
                    steps=step_names,
                    exit_point=exit_name,
                    flow_type="api_flow",
                    description=chain.description,
                ))

            elif chain.chain_type == "sql" and chain.depth >= 2:
                step_names = self._resolve_node_names(kg, chain.ordered_node_ids)
                if step_names:
                    flows.append(IRRequestFlow(
                        name=chain.description or f"Data Flow ({chain.chain_id})",
                        entry_point=step_names[0],
                        steps=step_names,
                        exit_point=step_names[-1] if step_names else None,
                        flow_type="data_flow",
                        description=chain.description,
                    ))

        return flows[:20]

    # ══════════════════════════════════════════════════════════════
    #  7. ERROR PATH EXTRACTION
    # ══════════════════════════════════════════════════════════════

    def _extract_error_paths(self, kg: KnowledgeGraph) -> List[IRErrorPath]:
        """Extract error/exception paths from RETURNS_TO edges."""
        error_paths = []

        for edge in kg.edges:
            if edge.relation == KGRelationType.RETURNS_TO:
                src = kg.nodes.get(edge.from_id)
                tgt = kg.nodes.get(edge.to_id)
                if src and tgt:
                    error_paths.append(IRErrorPath(
                        source_function=src.name,
                        error_handler=tgt.name,
                        error_type="exception",
                        recovery_strategy=edge.evidence,
                    ))

        return error_paths

    # ══════════════════════════════════════════════════════════════
    #  8. METADATA EXTRACTION
    # ══════════════════════════════════════════════════════════════

    def _detect_repo_type(self, kg: KnowledgeGraph) -> str:
        """Detect repository type from KG structure."""
        has_api = len(kg.nodes_by_type(KGNodeType.API_ENDPOINT)) > 0
        has_react = len(kg.nodes_by_type(KGNodeType.REACT_COMPONENT)) > 0
        has_sql = len(kg.nodes_by_type(KGNodeType.SQL_TABLE)) > 0
        has_spark = len(kg.nodes_by_type(KGNodeType.SPARK_JOB)) > 0
        has_services = len(kg.service_clusters) > 2

        if has_services and has_api:
            return "Microservices Platform"
        if has_api and has_sql:
            return "Backend API Platform"
        if has_react and has_api:
            return "Full-Stack Application"
        if has_react:
            return "Frontend Application"
        if has_spark:
            return "Data Processing Platform"
        if has_api:
            return "API Service"
        if has_sql:
            return "Data-Driven Application"
        return "Software Platform"

    def _detect_architecture_pattern(self, kg: KnowledgeGraph) -> Tuple[str, str, str]:
        """
        Detect architecture pattern using structural evidence, NOT service count.
        Uses coupling, deployment topology, and runtime patterns.
        Returns: (pattern, confidence, evidence)
        """
        evidence_log = []
        # Evidence counters
        signals = {
            "microservices": 0,
            "event_driven":  0,
            "layered":       0,
            "modular":       0,
        }

        # Signal 1: Separate databases per cluster (strong microservice evidence)
        cluster_dbs: dict = {}
        for node in kg.nodes_by_type(KGNodeType.SQL_TABLE):
            for edge in kg.incoming_edges(node.id):
                src = kg.nodes.get(edge.from_id)
                if src and src.service_boundary:
                    cluster_dbs.setdefault(src.service_boundary, set()).add(node.name)
        if len(cluster_dbs) > 2:
            signals["microservices"] += 3  # different clusters, different tables
            evidence_log.append(f"Found {len(cluster_dbs)} distinct service clusters with dedicated database isolation.")

        # Signal 2: Event bus nodes (event-driven pattern)
        event_bus_count = len(kg.nodes_by_type(KGNodeType.EVENT_BUS))
        pub_sub_edges = sum(
            1 for n in kg.nodes.values()
            for e in kg.outgoing_edges(n.id)
            if e.relation in ("PUBLISHES_TO", "SUBSCRIBES_FROM")
        )
        if event_bus_count > 0:
            signals["event_driven"] += 4
            evidence_log.append(f"Detected {event_bus_count} dedicated event bus nodes.")
        elif pub_sub_edges > 3:
            signals["event_driven"] += 2
            evidence_log.append(f"Detected {pub_sub_edges} publish/subscribe relationships.")

        # Signal 3: Layer nodes (controllers/repos/services in clear separation)
        has_controllers = len(kg.nodes_by_type(KGNodeType.CONTROLLER)) > 0
        has_repos = len(kg.nodes_by_type(KGNodeType.REPOSITORY)) > 0
        has_services = any(
            "service" in n.name.lower()
            for n in kg.nodes.values()
            if n.node_type == KGNodeType.CLASS
        )
        if has_controllers and has_repos and has_services:
            signals["layered"] += 4
            evidence_log.append("Detected clear Controller → Service → Repository structural layers.")
        elif has_controllers or has_repos:
            signals["layered"] += 2
            evidence_log.append("Detected partial layered patterns (Controllers/Repositories).")

        # Signal 4: Cross-service coupling
        cross_cluster_calls = sum(
            1 for n in kg.nodes.values()
            for e in kg.outgoing_edges(n.id)
            if e.relation == KGRelationType.CALLS
            and n.service_boundary
            and kg.nodes.get(e.to_id)
            and kg.nodes.get(e.to_id).service_boundary != n.service_boundary
        )
        total_calls = sum(
            1 for n in kg.nodes.values()
            for e in kg.outgoing_edges(n.id)
            if e.relation == KGRelationType.CALLS
        )
        coupling_ratio = cross_cluster_calls / max(total_calls, 1)
        if coupling_ratio < 0.15 and len(kg.service_clusters) > 2:
            signals["microservices"] += 2  # low coupling + multiple services = microservices
            evidence_log.append(f"Low cross-service coupling ({coupling_ratio:.2f}) across {len(kg.service_clusters)} clusters strongly indicates Microservices.")
        elif coupling_ratio < 0.30 and len(kg.service_clusters) > 1:
            signals["modular"] += 2
            evidence_log.append(f"Moderate coupling ({coupling_ratio:.2f}) across {len(kg.service_clusters)} clusters indicates Modular Monolith.")

        # Signal 5: Deployment containers
        container_count = len(kg.nodes_by_type(KGNodeType.DOCKER_CONTAINER)) if hasattr(KGNodeType, "DOCKER_CONTAINER") else 0
        if container_count > 2:
            signals["microservices"] += 2
            evidence_log.append(f"Multiple ({container_count}) Docker containers suggest independent deployments.")
        elif container_count == 1:
            signals["modular"] += 1
            evidence_log.append("Single container deployment suggests a Monolithic or Modular Monolith topology.")

        # Pick winner
        winner = max(signals, key=signals.get)
        max_score = signals[winner]

        if max_score == 0:
            return ("Unknown", "Low", "Insufficient structural signals to determine architecture pattern.")

        confidence = "High" if max_score >= 6 else "Medium"
        evidence_str = " ".join(evidence_log)

        if winner == "microservices":
            pattern = "Event-Driven Microservices" if signals.get("event_driven", 0) >= 2 else "Microservices"
        elif winner == "event_driven":
            pattern = "Event-Driven Architecture"
        elif winner == "layered":
            pattern = "Layered Architecture"
        else:
            pattern = "Modular Monolith"

        return (pattern, confidence, evidence_str)

    def _is_mock_or_test_node(self, node, kg=None) -> bool:
        """Return True if node belongs to test data, mock repos, or fixtures."""
        def is_mock_path(path_str):
            if not path_str:
                return False
            p = path_str.replace("\\", "/").lower()
            return any(x in p for x in [
                "/mock_repos/", "mock_repos/",
                "/test_repo/", "test_repo/",
                "/tests/", "tests/",
                "/test/", "test/",
                "/fixtures/", "fixtures/",
                "/test_data/", "test_data/",
                "/samples/", "samples/"
            ])

        path = getattr(node, 'file_path', None)
        if is_mock_path(path):
            return True
        if not path and is_mock_path(node.name):
            return True

        if kg and node.node_type in (KGNodeType.SQL_TABLE, KGNodeType.MONGO_COLLECTION, KGNodeType.API_ENDPOINT):
            incoming = kg.incoming_edges(node.id)
            if incoming:
                all_mock = True
                for edge in incoming:
                    src = kg.nodes.get(edge.from_id)
                    if src and not self._is_mock_or_test_node(src, kg):
                        all_mock = False
                        break
                if all_mock:
                    return True
                    
        return False

    def _extract_languages(self, kg: KnowledgeGraph) -> List[str]:
        """Extract all languages from KG file nodes."""
        languages: Set[str] = set()
        for node in kg.nodes_by_type(KGNodeType.FILE):
            if self._is_mock_or_test_node(node, kg):
                continue
            if node.language and node.language not in ("", "unknown"):
                languages.add(node.language)
        return sorted(languages)

    def _extract_frameworks(self, kg: KnowledgeGraph) -> List[str]:
        """Extract detected frameworks from KG annotations and service patterns."""
        frameworks: Set[str] = set()

        # From service/controller/repository annotations
        for node in kg.nodes.values():
            if self._is_mock_or_test_node(node, kg):
                continue
            for annot in node.annotations:
                if "Spring" in annot or "@Service" in annot:
                    frameworks.add("Spring")
                if "FastAPI" in annot or "fastapi" in annot:
                    frameworks.add("FastAPI")
                if "Flask" in annot or "flask" in annot:
                    frameworks.add("Flask")
                if "Express" in annot or "express" in annot:
                    frameworks.add("Express")

        # From React components - validate they are real components by checking for JS/TS
        if kg.nodes_by_type(KGNodeType.REACT_COMPONENT):
            has_js = any(lang in ("javascript", "typescript", "jsx", "tsx") for lang in self._extract_languages(kg))
            if has_js:
                frameworks.add("React")

        # From Spark jobs
        if kg.nodes_by_type(KGNodeType.SPARK_JOB):
            frameworks.add("Apache Spark")

        return sorted(frameworks)

    def _extract_databases(self, kg: KnowledgeGraph) -> List[str]:
        databases: Set[str] = set()
        for node in kg.nodes.values():
            if self._is_mock_or_test_node(node, kg):
                continue
            # Based on node types
            if node.node_type == KGNodeType.SQL_TABLE:
                databases.add("SQL Database") # Fallback, maybe postgres
            if node.node_type == KGNodeType.MONGO_COLLECTION:
                databases.add("MongoDB")
            
            # Based on annotations or names
            name_lower = node.name.lower() if node.name else ""
            if "neo4j" in name_lower or "cypher" in name_lower:
                databases.add("Neo4j")
            if "postgres" in name_lower:
                databases.add("PostgreSQL")
            if "redis" in name_lower:
                databases.add("Redis")
        
        return sorted(databases)

    def _extract_messaging_systems(self, kg: KnowledgeGraph) -> List[str]:
        systems: Set[str] = set()
        for node in kg.nodes.values():
            if self._is_mock_or_test_node(node, kg):
                continue
            name_lower = node.name.lower() if node.name else ""
            if "kafka" in name_lower:
                systems.add("Kafka")
            if "rabbitmq" in name_lower or "rabbit" in name_lower:
                systems.add("RabbitMQ")
        return sorted(systems)

    def _extract_infrastructure(self, kg: KnowledgeGraph) -> List[str]:
        infra: Set[str] = set()
        for node in kg.nodes.values():
            if self._is_mock_or_test_node(node, kg):
                continue
            
            # Only infer infrastructure from configuration files or specific deployment nodes
            if node.node_type == KGNodeType.FILE:
                name_lower = node.name.lower() if node.name else ""
                if "dockerfile" in name_lower or "docker-compose" in name_lower:
                    infra.add("Docker")
                if "kubernetes" in name_lower or "k8s" in name_lower or "helm" in name_lower:
                    infra.add("Kubernetes")
        return sorted(infra)

    def _extract_ai_ml_tools(self, kg: KnowledgeGraph) -> List[str]:
        tools: Set[str] = set()
        for node in kg.nodes.values():
            if self._is_mock_or_test_node(node, kg):
                continue
            name_lower = node.name.lower() if node.name else ""
            if "ollama" in name_lower:
                tools.add("Ollama")
            if "langchain" in name_lower:
                tools.add("LangChain")
            if "llamaindex" in name_lower or "llama_index" in name_lower:
                tools.add("LlamaIndex")
            if "deepseek" in name_lower:
                tools.add("DeepSeek")
        return sorted(tools)

    def _extract_code_analysis_tools(self, kg: KnowledgeGraph) -> List[str]:
        tools: Set[str] = set()
        for node in kg.nodes.values():
            if self._is_mock_or_test_node(node, kg):
                continue
            name_lower = node.name.lower() if node.name else ""
            if "tree-sitter" in name_lower or "tree_sitter" in name_lower:
                tools.add("Tree-sitter")
            if "ast" in name_lower and node.node_type == KGNodeType.PACKAGE:
                tools.add("AST Tools")
        return sorted(tools)

    # ══════════════════════════════════════════════════════════════
    #  HELPER METHODS
    # ══════════════════════════════════════════════════════════════

    def _files_linked_to(self, kg: KnowledgeGraph, node_id: str) -> List[str]:
        """Find file paths linked to a given node via edges."""
        files = set()
        for edge in kg.incoming_edges(node_id):
            src = kg.nodes.get(edge.from_id)
            if src and src.node_type == KGNodeType.FILE:
                files.add(src.file_path or src.name)
        for edge in kg.outgoing_edges(node_id):
            tgt = kg.nodes.get(edge.to_id)
            if tgt and tgt.node_type == KGNodeType.FILE:
                files.add(tgt.file_path or tgt.name)
        return sorted(files)

    def _key_entities_in(
        self, kg: KnowledgeGraph, parent_id: str, entity_type: str
    ) -> List[str]:
        """Find key entities (classes/functions) linked to a parent node."""
        entities = []
        for edge in kg.incoming_edges(parent_id):
            src = kg.nodes.get(edge.from_id)
            if src and src.node_type == entity_type:
                entities.append(src.name)
        return entities[:15]

    def _classes_in_files(
        self, kg: KnowledgeGraph, file_paths: List[str]
    ) -> List[str]:
        """Find class names defined in the given files."""
        classes = []
        file_set = set(file_paths)
        for node in kg.nodes.values():
            if (
                node.node_type in (KGNodeType.CLASS, KGNodeType.SERVICE, KGNodeType.CONTROLLER)
                and node.file_path in file_set
            ):
                classes.append(node.name)
        return classes[:15]

    def _functions_in_files(
        self, kg: KnowledgeGraph, file_paths: List[str]
    ) -> List[str]:
        """Find function names defined in the given files."""
        funcs = []
        file_set = set(file_paths)
        for node in kg.nodes.values():
            if (
                node.node_type in (KGNodeType.FUNCTION, KGNodeType.ASYNC_FUNCTION)
                and node.file_path in file_set
            ):
                funcs.append(node.name)
        return funcs[:15]

    def _api_endpoints_for(self, kg: KnowledgeGraph, service_id: str) -> List[str]:
        """Find API endpoint paths linked to a service."""
        endpoints = []
        for edge in kg.outgoing_edges(service_id):
            tgt = kg.nodes.get(edge.to_id)
            if tgt and tgt.node_type == KGNodeType.API_ENDPOINT:
                endpoints.append(tgt.name)
        # Also check nodes linked via EXPOSES_API
        for edge in kg.edges:
            if edge.relation == KGRelationType.EXPOSES_API:
                src = kg.nodes.get(edge.from_id)
                tgt = kg.nodes.get(edge.to_id)
                if src and tgt and src.id == service_id:
                    endpoints.append(tgt.name)
        return list(set(endpoints))

    def _data_stores_for(self, kg: KnowledgeGraph, service_id: str) -> List[str]:
        """Find data stores accessed by a service's nodes."""
        stores = set()
        related_nodes = set()

        # Find all nodes belonging to this service
        for edge in kg.incoming_edges(service_id):
            related_nodes.add(edge.from_id)

        # Find what data stores those nodes access
        for node_id in related_nodes:
            for edge in kg.outgoing_edges(node_id):
                if edge.relation in (
                    KGRelationType.QUERIES_TABLE,
                    KGRelationType.WRITES_TABLE,
                    KGRelationType.READS_FROM,
                    KGRelationType.WRITES_TO,
                ):
                    tgt = kg.nodes.get(edge.to_id)
                    if tgt:
                        stores.add(tgt.name)

        return sorted(stores)

    def _languages_for(self, kg: KnowledgeGraph, file_paths: List[str]) -> List[str]:
        """Determine languages for a set of file paths."""
        langs = set()
        file_set = set(file_paths)
        for node in kg.nodes.values():
            if (
                node.node_type == KGNodeType.FILE
                and (node.file_path in file_set or node.name in file_set)
                and node.language
            ):
                langs.add(node.language)
        return sorted(langs)

    def _cluster_confidence(self, kg: KnowledgeGraph, node_id: str) -> str:
        """Determine confidence level for a service cluster."""
        edge_count = len(kg.incoming_edges(node_id)) + len(kg.outgoing_edges(node_id))
        if edge_count >= 10:
            return "high"
        if edge_count >= 3:
            return "medium"
        return "low"

    def _resolve_node_names(self, kg: KnowledgeGraph, node_ids: List[str]) -> List[str]:
        """Convert node IDs to human-readable names."""
        names = []
        for nid in node_ids:
            name = self._resolve_node_name(kg, nid)
            if name:
                names.append(name)
        return names

    def _resolve_node_name(self, kg: KnowledgeGraph, node_id: str) -> Optional[str]:
        """Convert a single node ID to a human-readable name."""
        node = kg.nodes.get(node_id)
        if not node:
            return None
        return node.name

    # ══════════════════════════════════════════════════════════════
    #  WORKFLOW STEP VALIDATION & HUMANIZATION
    # ══════════════════════════════════════════════════════════════

    @staticmethod
    def _is_valid_workflow_step(step: str) -> bool:
        """
        Reject implementation details and allow only
        architecture-level workflow steps.
        """
        if not step:
            return False

        step = str(step).strip()

        # Reject dunder and private methods
        if step.startswith("__"):
            return False
        if step.startswith("_"):
            return False

        # Reject file paths and source file references
        if ".py" in step:
            return False
        if ".js" in step:
            return False
        if ".ts" in step:
            return False
        if ".java" in step:
            return False
        if "/" in step:
            return False
        if os.sep in step:
            return False

        # Reject very short tokens (likely variables or noise)
        if len(step) < 3:
            return False

        return True

    @staticmethod
    def _humanise_workflow_step(step: str) -> str:
        """
        Convert a raw KG node name into a readable workflow step.
        e.g. 'build_graph' → 'Build Graph'
        """
        clean = step.strip().lstrip("_")
        if not clean:
            return step
        return clean.replace("_", " ").title()

    def _clean_workflow_steps(self, steps: List[str]) -> List[str]:
        """
        Filter out invalid steps and humanise the remainder.
        Preserves order and deduplicates.
        """
        result = []
        seen: Set[str] = set()
        for step in steps:
            if not self._is_valid_workflow_step(step):
                continue
            humanised = self._humanise_workflow_step(step)
            if humanised not in seen:
                seen.add(humanised)
                result.append(humanised)
        return result

    def _generate_component_description(
        self,
        name: str,
        classes: List[str],
        api_endpoints: List[str],
        docstring: Optional[str] = None,
        file_paths: Optional[List[str]] = None,
        functions: Optional[List[str]] = None,
        dependencies: Optional[List[str]] = None,
    ) -> str:
        """
        Generate an architectural purpose statement for a component.

        Priority:
          1. Package-level __init__.py docstring (from disk).
          2. Provided docstring (if genuinely authored).
          3. Semantic inference from class/function names.
          4. Dependency-based inference.

        Never mentions file counts, class counts, or function counts.
        """
        # ── Strategy 1: Package __init__.py docstring ─────────
        pkg_docstring = self._read_package_docstring(name, file_paths)
        if pkg_docstring:
            return pkg_docstring

        # ── Strategy 2: Provided docstring (skip auto-generated) ──
        if docstring and docstring.strip():
            stripped = docstring.strip()
            is_autogenerated = (
                stripped.startswith("Service:")
                or stripped.startswith("Microservice:")
                or stripped.startswith("Module:")
                or "file(s)" in stripped
                or "files)" in stripped
                or "class(es)" in stripped
            )
            if not is_autogenerated:
                first_sentence = stripped.split(".")[0].strip()
                if first_sentence and len(first_sentence) > 10:
                    return first_sentence + "."

        # ── Strategy 3: Semantic inference from names ─────────
        all_symbols = (classes or []) + (functions or [])
        inferred = self._infer_purpose_from_symbols(name, all_symbols, api_endpoints)
        if inferred:
            return inferred

        # ── Strategy 4: Dependency-based inference ────────────
        if dependencies:
            dep_names = ", ".join(
                d.replace("_", " ").title() for d in dependencies[:3]
            )
            name_human = name.replace("_", " ").title()
            return (
                f"Coordinates {name_human} functionality, integrating "
                f"with {dep_names}."
            )

        # ── Final fallback (should rarely trigger) ────────────
        return ""

    def _read_package_docstring(
        self,
        component_name: str,
        file_paths: Optional[List[str]] = None,
    ) -> Optional[str]:
        """
        Attempt to read the first meaningful sentence from the
        component's __init__.py file.
        """
        import os

        candidates = []

        # Try to find __init__.py from file_paths
        if file_paths:
            for fp in file_paths:
                if fp.endswith("__init__.py"):
                    candidates.append(fp)

        # Try common paths
        for prefix in ("backend/", ""):
            candidates.append(
                os.path.join(prefix, component_name, "__init__.py")
            )
            candidates.append(
                os.path.join("backend", component_name, "__init__.py")
            )

        for path in candidates:
            if not os.path.isfile(path):
                continue
            try:
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read(2000)  # First 2KB is plenty

                # Extract module docstring (triple-quoted at top)
                for quote in ('"""', "'''"):
                    if quote in content:
                        start = content.index(quote) + 3
                        end = content.index(quote, start)
                        raw_docstring = content[start:end].strip()
                        if raw_docstring:
                            return self._extract_purpose_sentence(raw_docstring)
            except (OSError, ValueError):
                continue

        return None

    def _extract_purpose_sentence(self, raw_docstring: str) -> Optional[str]:
        """
        Extract the first purpose-describing sentence from a raw
        docstring, skipping header lines (module names, dividers).
        """
        lines = raw_docstring.strip().splitlines()
        purpose_lines = []

        for line in lines:
            stripped = line.strip()

            # Skip header lines: module names, dividers, blanks
            if not stripped:
                if purpose_lines:
                    break  # Stop at first blank after content
                continue
            if stripped.startswith("─") or stripped.startswith("="):
                continue
            if stripped.endswith("—") and len(stripped.split()) <= 6:
                continue
            # Skip lines that are just module identifiers
            if stripped.endswith("/") or stripped.endswith("__init__.py"):
                continue
            # Skip component name headers like "context_builder — Component 5:"
            if "Component" in stripped and "—" in stripped:
                continue
            # Skip system identification lines
            if "Enterprise" in stripped and "System" in stripped:
                continue
            # Skip lines about offline/cloud
            if stripped.startswith("Fully offline"):
                continue
            if stripped.startswith("Supports:"):
                continue

            purpose_lines.append(stripped)

        if not purpose_lines:
            return None

        # Join and take the first sentence.
        # Use regex to split on sentence boundaries (". " or ".\n")
        # This avoids breaking on filenames like "graph_dependencies.xml"
        import re
        full_text = " ".join(purpose_lines)
        # Split on period followed by whitespace and an uppercase letter,
        # or period followed by end-of-string — but NOT period inside
        # a filename (period followed by lowercase extension).
        sentences = re.split(r'\.(?:\s+(?=[A-Z])|\s*$)', full_text, maxsplit=1)
        first_sentence = sentences[0].strip() if sentences else full_text.strip()
        if first_sentence and len(first_sentence) > 15:
            # Cap at a reasonable length for a single purpose statement
            if len(first_sentence) > 200:
                # Trim to the last comma or conjunction before 200 chars
                truncated = first_sentence[:200]
                last_comma = truncated.rfind(",")
                if last_comma > 100:
                    first_sentence = truncated[:last_comma]
            return first_sentence + "."
        return None

    def _infer_purpose_from_symbols(
        self,
        component_name: str,
        symbols: List[str],
        api_endpoints: List[str],
    ) -> Optional[str]:
        """
        Infer the architectural purpose of a component from its
        class names, function names, and API endpoints.

        Uses keyword→purpose-fragment mapping to construct a
        natural-language sentence.
        """
        name_lower = component_name.lower()
        symbol_text = " ".join(s.lower() for s in symbols)
        combined = f"{name_lower} {symbol_text}"

        purpose_signals = [
            (["extract", "parser", "reader", "load"], "Handles data extraction and parsing from raw inputs"),
            (["engine", "processor", "compute"], "Core processing engine for business logic execution"),
            (["model", "entity", "schema", "dto"], "Defines domain models and data structures"),
            (["repo", "database", "store", "cache"], "Manages data persistence and retrieval"),
            (["api", "controller", "router", "handler"], "Provides public API endpoints and request routing"),
            (["auth", "security", "token", "login"], "Manages authentication and security controls"),
            (["config", "settings", "env"], "Handles application configuration and environment settings"),
            (["util", "helper", "common"], "Provides shared utilities and helper functions"),
            (["ui", "view", "render", "template"], "Manages presentation and user interface rendering"),
            (["diagram", "mermaid", "visual"], "Generates visual diagrams and architectural representations"),
            (["document", "docx", "pdf", "export"], "Handles document generation and export"),
            (["comment", "docstring", "annotate"], "Manages code documentation and semantic comments"),
            (["semantic", "ir", "knowledge", "graph", "translator"], "Manages knowledge graph translation and semantic IR building"),
        ]

        for keywords, purpose in purpose_signals:
            if any(kw in combined for kw in keywords):
                return purpose + "."

        # ── API-driven inference ──────────────────────────────
        if api_endpoints:
            name_human = component_name.replace("_", " ").title()
            return (
                f"Exposes REST API endpoints for {name_human} "
                f"operations and external integration."
            )

        name_human = component_name.replace("_", " ").title()
        return f"Manages {name_human} operations and logic within the domain."

    def _infer_http_method(self, endpoint_name: str) -> str:
        """Infer HTTP method from endpoint path naming conventions."""
        name_lower = endpoint_name.lower()
        if any(kw in name_lower for kw in ("create", "register", "add", "post")):
            return "POST"
        if any(kw in name_lower for kw in ("update", "edit", "put", "modify")):
            return "PUT"
        if any(kw in name_lower for kw in ("delete", "remove")):
            return "DELETE"
        if any(kw in name_lower for kw in ("patch",)):
            return "PATCH"
        return "GET"

    def _log(self, msg: str):
        if self.verbose:
            print(msg, flush=True)
