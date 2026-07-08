"""
semantic_ir/ir_builder.py
────────────────────────────────────────────────────────────────
Full-Pipeline IR Builder.

This is the PRODUCTION entry point for building SemanticIR.
It runs the complete pipeline:

  1. Repository Intelligence (profiling, HTTP endpoints, DB schemas,
     architecture patterns)
  2. AST Engine → XML
  3. Dependency Extraction → graph_dependencies.xml
  4. Knowledge Graph → KnowledgeGraph
  5. KGToIRTranslator → SemanticIR (KG-grounded)
  6. Enrichment: merge extractor results into SemanticIR

If the KG pipeline fails (missing tree-sitter, missing XML, etc.),
it falls back to directory-based IR + extractor enrichment.

Backward compatible:
    build(repo_path)            → full pipeline
    build(repo_path, kg=kg)     → KG-grounded (skip steps 2-4)
    build_from_kg(kg)           → direct KG translation
"""

from __future__ import annotations

import os
import glob
from typing import List, Optional

from backend.semantic_ir.models import (
    SemanticIR,
    IRComponent,
    IRApiEndpoint,
    IRDataStore,
    IRRequestFlow,
)
from backend.semantic_ir.component_builder import ComponentBuilder
from backend.semantic_ir.relationship_builder import RelationshipBuilder
from backend.semantic_ir.workflow_builder import WorkflowBuilder
from backend.repository_intelligence.repository_profiler import RepositoryProfiler


class IRBuilder:

    def __init__(self, verbose: bool = True):
        self.verbose = verbose
        self.profiler = RepositoryProfiler()
        self.component_builder = ComponentBuilder()
        self.relationship_builder = RelationshipBuilder()
        self.workflow_builder = WorkflowBuilder()

    def build(self, repo_path: str, kg=None) -> SemanticIR:
        """
        Build a SemanticIR from a repository.

        This method runs the FULL pipeline:
        1. If a KG is provided, use it directly.
        2. Otherwise, try to load an existing KG JSON.
        3. If no KG is available, try to build one from the AST pipeline.
        4. If all else fails, fall back to directory-based IR.

        In ALL cases, the result is enriched with repository-intelligence
        extractors (HTTP endpoints, DB schemas, architecture patterns).
        """
        self._log(f"\n{'='*60}")
        self._log(f"  IR Builder — Full Pipeline")
        self._log(f"  Repository: {repo_path}")
        self._log(f"{'='*60}\n")

        # ── Strategy 1: KG provided directly ─────────────────
        if kg is not None:
            self._log("[strategy] Using provided KnowledgeGraph")
            self.kg = kg
            ir = self.build_from_kg(kg)
            return self._enrich_with_extractors(ir, repo_path)

        # ── Strategy 2: Load existing KG JSON ────────────────
        kg = self._try_load_kg_json(repo_path)
        if kg is not None:
            self._log("[strategy] Using loaded KnowledgeGraph from JSON")
            self.kg = kg
            ir = self.build_from_kg(kg)
            return self._enrich_with_extractors(ir, repo_path)

        # ── Strategy 3: Build KG from AST pipeline ───────────
        kg = self._try_build_kg_from_ast(repo_path)
        if kg is not None:
            self._log("[strategy] Using KG built from AST pipeline")
            self.kg = kg
            ir = self.build_from_kg(kg)
            return self._enrich_with_extractors(ir, repo_path)

        # ── Strategy 4: Fallback to static extraction ────────
        self._log("[strategy] KG extraction failed. Attempting static extraction fallback.")
        from backend.semantic_ir.models import SemanticIR
        empty_ir = SemanticIR(repository_type="unknown")
        enriched_ir = self._enrich_with_extractors(empty_ir, repo_path)
        
        # Removed RuntimeError to support frontend and generic repositories
            
        self._log("[strategy] Recovered using static extraction evidence.")
        return enriched_ir

    def build_from_kg(self, kg) -> SemanticIR:
        """
        Build SemanticIR directly from a KnowledgeGraph.

        This is the preferred code path. The KGToIRTranslator
        extracts real architecture from the graph.
        """
        from backend.semantic_bridge.kg_to_ir_translator import (
            KGToIRTranslator,
        )

        translator = KGToIRTranslator(verbose=self.verbose)
        return translator.translate(kg)

    # ══════════════════════════════════════════════════════════
    #  KG LOADING STRATEGIES
    # ══════════════════════════════════════════════════════════

    def _try_load_kg_json(self, repo_path: str):
        """
        Try to load a pre-built KnowledgeGraph from JSON files
        in the standard output locations.
        """
        search_paths = [
            os.path.join(repo_path, "outputs", "knowledge_graph_streaming", "knowledge_graph.json"),
            os.path.join(repo_path, "outputs", "knowledge_graph", "knowledge_graph.json"),
            os.path.join(repo_path, "backend", "outputs", "knowledge_graph_streaming", "knowledge_graph.json"),
            os.path.join(repo_path, "backend", "outputs", "knowledge_graph", "knowledge_graph.json"),
        ]

        # Also search for any knowledge_graph.json
        for pattern in glob.glob(
            os.path.join(repo_path, "**", "knowledge_graph.json"),
            recursive=True,
        ):
            if pattern not in search_paths:
                search_paths.append(pattern)

        for json_path in search_paths:
            if os.path.isfile(json_path):
                try:
                    self._log(f"[kg-load] Found KG JSON: {json_path}")
                    from backend.knowledge_graph.models import KnowledgeGraph
                    import json

                    with open(json_path, "r", encoding="utf-8") as f:
                        data = json.load(f)

                    kg = KnowledgeGraph.from_dict(data)
                    self._log(
                        f"[kg-load] Loaded: {kg.node_count} nodes, "
                        f"{kg.edge_count} edges"
                    )
                    return kg

                except Exception as e:
                    self._log(f"[kg-load] Failed to load {json_path}: {e}")

        self._log("[kg-load] No KG JSON found")
        return None

    def _try_build_kg_from_ast(self, repo_path: str):
        """
        Try to build a KG by running the AST → Dependency → KG pipeline.

        This requires tree-sitter and the full AST engine to be available.
        """
        try:
            # Step 1: Check for existing graph_dependencies.xml
            xml_paths = [
                os.path.join(repo_path, "outputs", "graph_dependencies.xml"),
                os.path.join(repo_path, "backend", "outputs", "graph_dependencies.xml"),
            ]

            xml_path = None
            for p in xml_paths:
                if os.path.isfile(p):
                    xml_path = p
                    break

            if not xml_path:
                self._log("[kg-build] No existing XML found. Running AST pipeline...")
                
                # Normalize output dir for exclusion
                self._output_exclusion = getattr(self, '_output_exclusion', set())
                
                # 1. Run AST Engine
                from backend.ast_engine.core.engine import ASTEngine
                from backend.ast_engine.output.xml_generator import generate_xml
                
                ast_engine = ASTEngine(verbose=self.verbose)
                project = ast_engine.parse_directory(repo_path)
                
                ast_xml_path = os.path.join(repo_path, "outputs", "ast.xml")
                os.makedirs(os.path.dirname(ast_xml_path), exist_ok=True)
                generate_xml(project, ast_xml_path)
                
                # 2. Run Combiner
                from backend.combiner.combiner import SimpleCodeCombiner
                from backend.combiner.exporter import export_xml as export_combined_xml
                
                combined_xml_path = os.path.join(repo_path, "outputs", "combined.xml")
                combiner = SimpleCodeCombiner(project_name=os.path.basename(repo_path), verbose=self.verbose)
                combined_project = combiner.combine([ast_xml_path])
                export_combined_xml(combined_project, combined_xml_path)
                
                # 3. Run Dependency Extractor
                from backend.dependency_extractor.extractor import DependencyExtractor
                
                xml_path = os.path.join(repo_path, "outputs", "graph_dependencies.xml")
                dep_engine = DependencyExtractor(project_name=os.path.basename(repo_path), verbose=self.verbose)
                dep_engine.extract(combined_xml_path, output_xml=xml_path)

            if xml_path and os.path.isfile(xml_path):
                self._log(f"[kg-build] Found dependency XML: {xml_path}")
                from backend.knowledge_graph.graph_loader import GraphXMLLoader
                from backend.knowledge_graph.graph_builder import KnowledgeGraphBuilder

                loader = GraphXMLLoader(verbose=self.verbose)
                kg = loader.load(xml_path)

                builder = KnowledgeGraphBuilder(verbose=self.verbose)
                kg = builder.build(kg)

                self._log(
                    f"[kg-build] Built KG: {kg.node_count} nodes, "
                    f"{kg.edge_count} edges"
                )
                return kg

        except Exception as e:
            self._log(f"[kg-build] AST pipeline failed: {e}")

        return None

    # ══════════════════════════════════════════════════════════
    #  DIRECTORY-BASED FALLBACK
    # ══════════════════════════════════════════════════════════

    def _build_from_directory(self, repo_path: str) -> SemanticIR:
        """
        Fallback: build IR from directory structure.

        This is the legacy code path. Components are discovered
        by scanning directories, and relationships/workflows
        are synthesized from dependency lists.
        """
        profile = self.profiler.profile(repo_path)

        semantic_ir = SemanticIR(
            repository_type=profile.repository_type,
        )

        # Components from directory scan
        semantic_ir.components = (
            self.component_builder.build(repo_path)
        )

        # Relationships from component dependencies
        semantic_ir.relationships = (
            self.relationship_builder.build(
                components=semantic_ir.components,
            )
        )

        # Workflows from component ordering
        semantic_ir.workflows = (
            self.workflow_builder.build(
                components=semantic_ir.components,
            )
        )

        return semantic_ir

    # ══════════════════════════════════════════════════════════
    #  EXTRACTOR ENRICHMENT
    # ══════════════════════════════════════════════════════════

    def _enrich_with_extractors(
        self, ir: SemanticIR, repo_path: str,
    ) -> SemanticIR:
        """
        Enrich the KG-derived SemanticIR with evidence from static-analysis
        extractors (HTTP endpoints, database schemas, connection strings).

        This fills the gaps the KG cannot cover: framework-specific decorators,
        ORM column definitions, and database connection strings.

        Deduplication: results are merged only if no matching entity already
        exists in the IR from the KG translation pass.
        """
        # ── 0. Java/Spring Source Extraction ─────────────────
        try:
            from backend.repository_intelligence.java_source_scanner import JavaSourceScanner
            java_scanner = JavaSourceScanner(verbose=self.verbose)
            java_result = java_scanner.scan(repo_path)
            
            if java_result.classes or java_result.interfaces:
                ir.metadata['java_scan'] = java_result
                if java_result.architecture_pattern != "Unknown":
                    ir.architecture_pattern = java_result.architecture_pattern
                    ir.architecture_pattern_confidence = java_result.architecture_confidence
                    ir.architecture_pattern_evidence = java_result.architecture_evidence
                    
                for fw in java_result.frameworks:
                    if fw not in ir.frameworks:
                        ir.frameworks.append(fw)
                
                if not ir.components:
                    from backend.semantic_ir.models import IRComponent, IRRelationship
                    for mod in java_result.modules:
                        ir.components.append(IRComponent(
                            name=mod.name,
                            component_type="Module",
                            description=f"Java Module: {mod.name}",
                            files=[],
                            key_classes=mod.classes,
                            layer="Application",
                            confidence="high"
                        ))
                    for frm, to, rel in java_result.dependency_chains:
                        ir.relationships.append(IRRelationship(source=frm, target=to, relationship_type=rel, confidence="high"))
        except Exception as e:
            self._log(f"[enrich] Java source extraction failed: {e}")

        # ── 0.5. SQL Source Extraction ─────────────────
        try:
            from backend.repository_intelligence.sql_extractor import SQLExtractor
            sql_extractor = SQLExtractor(verbose=self.verbose)
            sql_extractor.extract_from_directory(repo_path, ir)
        except Exception as e:
            self._log(f"[enrich] SQL source extraction failed: {e}")

        # ── 1. HTTP Endpoint Extraction ──────────────────────
        try:
            from backend.repository_intelligence.http_endpoint_extractor import (
                HTTPEndpointExtractor,
            )
            ep_extractor = HTTPEndpointExtractor(verbose=self.verbose)
            endpoints = ep_extractor.extract_from_directory(repo_path)

            existing_endpoints = {(ep.method, ep.path) for ep in ir.api_endpoints}
            added = 0
            for ep in endpoints:
                if (ep.method, ep.path) not in existing_endpoints:
                    ir.api_endpoints.append(IRApiEndpoint(
                        path=ep.path,
                        method=ep.method,
                        handler_function=ep.handler,
                        handler_file=ep.handler_file,
                        request_model=ep.request_model,
                        response_model=ep.response_model,
                        description=f"{ep.method} {ep.path}",
                    ))
                    existing_endpoints.add((ep.method, ep.path))
                    added += 1

                # Merge framework into IR
                if ep.framework and ep.framework not in [f.lower() for f in ir.frameworks]:
                    framework_name = {
                        "fastapi": "FastAPI",
                        "flask": "Flask",
                        "django": "Django",
                        "express": "Express",
                        "nestjs": "NestJS",
                        "spring": "Spring Boot",
                    }.get(ep.framework, ep.framework.title())
                    if framework_name not in ir.frameworks:
                        ir.frameworks.append(framework_name)

            if added:
                self._log(f"[enrich] Added {added} API endpoints from static analysis")

        except Exception as e:
            self._log(f"[enrich] HTTP endpoint extraction failed: {e}")

        # ── 2. Database Schema Extraction ────────────────────
        try:
            from backend.repository_intelligence.database_schema_extractor import (
                DatabaseSchemaExtractor,
            )
            db_extractor = DatabaseSchemaExtractor(verbose=self.verbose)
            tables, models = db_extractor.extract_from_directory(repo_path)

            existing_stores = {ds.name for ds in ir.data_stores}
            added = 0
            for table in tables:
                if table.name not in existing_stores:
                    ir.data_stores.append(IRDataStore(
                        name=table.name,
                        store_type=table.store_type,
                        accessed_by=[],
                        operations=[],
                    ))
                    existing_stores.add(table.name)
                    added += 1

                # Merge framework into IR
                if table.framework:
                    framework_name = {
                        "sqlalchemy": "SQLAlchemy",
                        "django": "Django ORM",
                        "typeorm": "TypeORM",
                        "mongoose": "Mongoose",
                    }.get(table.framework, table.framework.title())
                    if framework_name not in ir.frameworks:
                        ir.frameworks.append(framework_name)

            if added:
                self._log(f"[enrich] Added {added} data stores from static analysis")

        except Exception as e:
            self._log(f"[enrich] Database schema extraction failed: {e}")

        # ── 3. Connection String → Database Technology ───────
        try:
            db_tech = self._detect_database_from_source(repo_path)
            for tech in db_tech:
                if tech not in ir.databases:
                    ir.databases.append(tech)
                    self._log(f"[enrich] Detected database: {tech}")
        except Exception as e:
            self._log(f"[enrich] Database detection failed: {e}")

        # ── 4. Build Request Flows from API + KG ─────────────
        try:
            kg = getattr(self, "kg", None)
            if kg and ir.api_endpoints:
                flows = self._build_request_flows_from_apis(ir, kg)
                if flows:
                    existing_flow_names = {f.name for f in ir.request_flows}
                    for flow in flows:
                        if flow.name not in existing_flow_names:
                            ir.request_flows.append(flow)
                            existing_flow_names.add(flow.name)
                    self._log(f"[enrich] Built {len(flows)} request flows from API endpoints")
        except Exception as e:
            self._log(f"[enrich] Request flow building failed: {e}")

        # ── Step 5: Static Error Path Extraction ─────────────────
        if not ir.error_paths:
            import re
            raise_pattern = re.compile(r'(?:raise|throw new)\s+([A-Za-z0-9_]+Error|[A-Za-z0-9_]+Exception|Exception|Error)\b')
            for ep in ir.api_endpoints:
                if ep.handler_file and os.path.isfile(os.path.join(repo_path, ep.handler_file)):
                    try:
                        with open(os.path.join(repo_path, ep.handler_file), "r", encoding="utf-8") as f:
                            content = f.read()
                        
                        # Find all exceptions raised in the file (approximation for the endpoint)
                        for match in raise_pattern.finditer(content):
                            exc_type = match.group(1)
                            from backend.semantic_ir.models import IRErrorPath
                            ir.error_paths.append(IRErrorPath(
                                source_function=ep.handler_function or ep.path,
                                error_handler="Client/Caller",
                                error_type=exc_type,
                                recovery_strategy="Propagate to caller"
                            ))
                    except Exception:
                        pass
            
            # Deduplicate
            seen_errs = set()
            unique_errs = []
            for ep in ir.error_paths:
                key = (ep.source_function, ep.error_type)
                if key not in seen_errs:
                    seen_errs.add(key)
                    unique_errs.append(ep)
            ir.error_paths = unique_errs

        # ── Finish Enrichment ──────────────────────────────────
        self._log(f"\n[IR Builder] Final IR:")
        self._log(f"  Components:    {len(ir.components)}")
        self._log(f"  Relationships: {len(ir.relationships)}")
        self._log(f"  Workflows:     {len(ir.workflows)}")
        self._log(f"  API Endpoints: {len(ir.api_endpoints)}")
        self._log(f"  Data Stores:   {len(ir.data_stores)}")
        self._log(f"  Request Flows: {len(ir.request_flows)}")
        self._log(f"  Error Paths:   {len(ir.error_paths)}")
        self._log(f"  Architecture:  {ir.architecture_pattern}")
        self._log(f"  Languages:     {ir.languages}")
        self._log(f"  Frameworks:    {ir.frameworks}")
        self._log(f"  Databases:     {ir.databases}")

        return ir

    def _detect_database_from_source(self, repo_path: str) -> List[str]:
        """
        Detect database technologies from connection strings and imports.
        Evidence-based only: no name-matching heuristics.
        """
        import re as _re

        databases = set()
        patterns = {
            r'sqlite:///': "SQLite",
            r'postgresql://': "PostgreSQL",
            r'postgres://': "PostgreSQL",
            r'mysql://': "MySQL",
            r'mysql\+pymysql://': "MySQL",
            r'mongodb://': "MongoDB",
            r'mongodb\+srv://': "MongoDB",
            r'redis://': "Redis",
        }
        import_patterns = {
            r'import\s+sqlite3': "SQLite",
            r'from\s+sqlite3': "SQLite",
            r'import\s+psycopg2': "PostgreSQL",
            r'from\s+psycopg2': "PostgreSQL",
            r'import\s+pymongo': "MongoDB",
            r'from\s+pymongo': "MongoDB",
            r'import\s+redis': "Redis",
            r'from\s+redis': "Redis",
            r'import\s+pymysql': "MySQL",
            r'from\s+pymysql': "MySQL",
        }

        source_exts = {".py", ".js", ".ts", ".java", ".go", ".rb", ".env", ".cfg", ".ini", ".toml", ".yaml", ".yml"}
        skip_dirs = {"__pycache__", ".git", "venv", ".venv", "node_modules", "dist", "build", "outputs"}

        for root, dirs, files in os.walk(repo_path):
            dirs[:] = [d for d in dirs if d not in skip_dirs and not d.startswith(".")]
            for fname in files:
                if os.path.splitext(fname)[1] not in source_exts:
                    continue
                try:
                    fpath = os.path.join(root, fname)
                    with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read(8192)  # first 8KB is enough for imports/config
                    for pattern, db_name in patterns.items():
                        if _re.search(pattern, content):
                            databases.add(db_name)
                    for pattern, db_name in import_patterns.items():
                        if _re.search(pattern, content):
                            databases.add(db_name)
                except Exception:
                    pass

        return sorted(databases)

    def _build_request_flows_from_apis(
        self, ir: SemanticIR, kg,
    ) -> List[IRRequestFlow]:
        """
        Build request flows by tracing API handler → KG call chain → data store.
        Only produces flows with ≥2 hops backed by KG evidence.
        """
        from backend.knowledge_graph.models import KGNodeType, KGRelationType

        flows = []

        for endpoint in ir.api_endpoints:
            handler = endpoint.handler_function
            if not handler:
                continue

            # Find handler node in KG
            handler_node = None
            for node in kg.nodes.values():
                if node.name == handler and node.node_type in (
                    KGNodeType.FUNCTION, KGNodeType.ASYNC_FUNCTION, KGNodeType.METHOD,
                ):
                    handler_node = node
                    break

            if not handler_node:
                continue

            # BFS trace from handler
            chain = [f"{endpoint.method} {endpoint.path}"]
            visited = set()
            queue = [handler_node.id]

            while queue and len(chain) < 8:
                current_id = queue.pop(0)
                if current_id in visited:
                    continue
                visited.add(current_id)

                current_node = kg.nodes.get(current_id)
                if current_node and current_node.name != handler:
                    chain.append(current_node.name)

                for edge in kg.outgoing_edges(current_id):
                    if edge.relation in (
                        KGRelationType.CALLS,
                        KGRelationType.INVOKES,
                    ):
                        if edge.to_id not in visited:
                            queue.append(edge.to_id)

            if len(chain) >= 2:
                flows.append(IRRequestFlow(
                    name=f"{endpoint.method} {endpoint.path}",
                    entry_point=f"{endpoint.method} {endpoint.path}",
                    steps=chain,
                    exit_point=chain[-1],
                    flow_type="api_flow",
                    description=f"Request flow for {endpoint.method} {endpoint.path}",
                ))

        return flows

    # ══════════════════════════════════════════════════════════
    #  CONFIGURATION EXTRACTION
    # ══════════════════════════════════════════════════════════

    def _extract_config_metadata(self, repo_path: str) -> dict:
        """
        Extract configuration metadata from deployment/config files.

        Supports:
        - docker-compose.yml
        - Dockerfile
        - Kubernetes YAML
        - .env
        - GitHub Actions
        """
        meta = {}

        # Docker
        docker_compose = os.path.join(repo_path, "docker-compose.yml")
        if not os.path.isfile(docker_compose):
            docker_compose = os.path.join(repo_path, "docker-compose.yaml")

        if os.path.isfile(docker_compose):
            meta["container_orchestration"] = "Docker Compose"
            try:
                with open(docker_compose, "r") as f:
                    content = f.read()
                import re
                services = re.findall(r'^\s{2}(\w[\w-]*):', content, re.MULTILINE)
                if services:
                    meta["docker_services"] = ", ".join(services[:10])
            except Exception:
                pass

        dockerfile = os.path.join(repo_path, "Dockerfile")
        if os.path.isfile(dockerfile):
            meta["containerized"] = "Yes (Dockerfile)"

        # Kubernetes
        k8s_files = glob.glob(
            os.path.join(repo_path, "**", "deployment.yaml"),
            recursive=True,
        ) + glob.glob(
            os.path.join(repo_path, "**", "deployment.yml"),
            recursive=True,
        )
        if k8s_files:
            meta["kubernetes"] = f"{len(k8s_files)} deployment(s)"

        # .env
        env_file = os.path.join(repo_path, ".env")
        if os.path.isfile(env_file):
            try:
                with open(env_file, "r") as f:
                    lines = [
                        l.strip() for l in f
                        if l.strip() and not l.startswith("#")
                    ]
                meta["env_variables"] = f"{len(lines)} variable(s)"
            except Exception:
                pass

        env_example = os.path.join(repo_path, ".env.example")
        if os.path.isfile(env_example):
            meta["env_example"] = "Present"

        # GitHub Actions
        gh_actions = glob.glob(
            os.path.join(repo_path, ".github", "workflows", "*.yml"),
        ) + glob.glob(
            os.path.join(repo_path, ".github", "workflows", "*.yaml"),
        )
        if gh_actions:
            names = [os.path.basename(f) for f in gh_actions]
            meta["ci_cd"] = f"GitHub Actions ({', '.join(names)})"

        # requirements.txt / pyproject.toml / package.json
        if os.path.isfile(os.path.join(repo_path, "requirements.txt")):
            meta["python_deps"] = "requirements.txt"
        if os.path.isfile(os.path.join(repo_path, "pyproject.toml")):
            meta["python_deps"] = "pyproject.toml"
        if os.path.isfile(os.path.join(repo_path, "package.json")):
            meta["node_deps"] = "package.json"

        return meta

    # ══════════════════════════════════════════════════════════
    #  LOGGING
    # ══════════════════════════════════════════════════════════

    def _log(self, msg: str):
        if self.verbose:
            print(msg, flush=True)