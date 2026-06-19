from typing import List, Dict
import re
from backend.semantic_ir.models import SemanticIR
from backend.architecture_extractor.models import (
    ArchitectureBlueprint,
    ArchitectureCapability,
    ArchitectureService,
    ArchitectureComponent,
    ArchitectureWorkflow,
    ArchitectureDataFlow,
    ArchitectureAPI,
    ArchitectureDatabase,
    ArchitectureIntegration,
    ArchitectureDeploymentNode,
    SecurityBoundary,
    ArchitectureArtifact
)

class ArchitectureExtractor:
    """
    Extracts an Architecture Blueprint from the Semantic IR.
    Transforms low-level implementation details into enterprise architectural abstractions.
    """

    def extract(self, ir: SemanticIR) -> ArchitectureBlueprint:
        metadata = dict(ir.metadata)
        metadata["languages"] = ir.languages
        metadata["frameworks"] = ir.frameworks
        metadata["databases"] = ir.databases
        metadata["messaging_systems"] = ir.messaging_systems
        metadata["infrastructure"] = ir.infrastructure
        metadata["ai_ml_tools"] = ir.ai_ml_tools
        metadata["code_analysis_tools"] = ir.code_analysis_tools
        
        arch_pattern = ir.architecture_pattern
        arch_conf = getattr(ir, 'architecture_pattern_confidence', 'Unknown')
        arch_ev = getattr(ir, 'architecture_pattern_evidence', 'None')

        if not arch_ev or arch_ev.lower() in ('none', 'unknown', ''):
            arch_pattern = "Unknown"
            arch_conf = "Unknown"
            arch_ev = "Insufficient structural evidence to confidently determine architecture pattern."

        blueprint = ArchitectureBlueprint(
            repository_type=ir.repository_type,
            architecture_pattern=arch_pattern,
            architecture_pattern_confidence=arch_conf,
            architecture_pattern_evidence=arch_ev,
            metadata=metadata
        )

        # 1. Infer Capabilities
        blueprint.capabilities = self._extract_capabilities(ir)
        
        # 2. Extract Artifacts (Independent Asset Discovery)
        blueprint.artifacts = self._extract_artifacts(ir)
        
        # 3. Generate Architectural Services
        blueprint.services = self._extract_services(ir, blueprint.capabilities, blueprint.artifacts)
        
        # Keep raw components for reference
        blueprint.components = self._extract_components(ir)
        
        # 4. Generate Workflows (Capabilities)
        blueprint.workflows = self._extract_workflows(ir, blueprint.capabilities)
        
        # 5. Generate Data Flows (Artifacts)
        blueprint.data_flows = self._extract_data_flows(ir, blueprint.artifacts, blueprint.capabilities)
        
        # Keep APIs and Databases
        blueprint.apis = self._extract_apis(ir)
        blueprint.databases = self._extract_databases(ir)
        
        # 6. Generate Integrations (Architectural Services)
        blueprint.integrations = self._extract_integrations(ir, blueprint.capabilities)
        
        blueprint.deployment_nodes = self._extract_deployment_nodes(ir)
        blueprint.security_boundaries = self._extract_security_boundaries(ir)

        return blueprint

    # ══════════════════════════════════════════════════════════════
    #  SEMANTIC INFERENCE
    # ══════════════════════════════════════════════════════════════

    def _infer_capability(self, name: str, description: str):
        name_lower = name.lower().replace("_", " ")
        desc_lower = (description or "").lower()
        
        domain_words = []
        
        if description:
            desc_tokens = re.findall(r"[a-zA-Z]+", description)
            verbs = {
                "process", "processes", "processing", "execute", "executes", 
                "analyze", "analyzes", "analyzing", "scan", "scans", "extract", "extracts", 
                "generate", "generates", "create", "creates", "build", "builds", "construct", "constructs", 
                "detect", "detects", "monitor", "monitors", "model", "models", 
                "export", "exports", "publish", "publishes", "manage", "manages", 
                "control", "controls", "handle", "handles", "parse", "parses",
                "orchestrate", "orchestrates", "combine", "combines", "evaluate", "evaluates"
            }
            stopwords = {"for", "the", "a", "an", "into", "from", "of", "to", "and", "in", "with", "all", "any", "this", "that"}
            
            for i, token in enumerate(desc_tokens):
                if token.lower() in verbs:
                    for next_token in desc_tokens[i+1:i+4]:
                        if next_token.lower() not in stopwords:
                            domain_words.append(next_token)
                        else:
                            if domain_words: break
                    if domain_words:
                        break

        if not domain_words:
            tech_words = {
                "service", "controller", "manager", "gateway", "api", "handler", 
                "engine", "processor", "builder", "generator", "extractor", 
                "model", "orchestrator", "combiner", "parser", "component",
                "system", "module", "worker", "job", "task", "agent"
            }
            words = re.findall(r'[A-Z]?[a-z]+|[A-Z]+(?=[A-Z][a-z]|\b)', name)
            for w in words:
                if w.lower() not in tech_words:
                    domain_words.append(w)
                    
        if not domain_words:
            domain_words = ["Core"]
            
        domain = " ".join(domain_words).title()
        
        action = None
        if any(x in name_lower or x in desc_lower for x in ["process", "execute", "run"]):
            action = "Processing"
        elif any(x in name_lower or x in desc_lower for x in ["analyz", "scan", "extract", "parse", "evaluat"]):
            action = "Analysis"
        elif any(x in name_lower or x in desc_lower for x in ["generat", "creat", "build", "construct", "produc"]):
            action = "Generation"
        elif any(x in name_lower or x in desc_lower for x in ["detect", "monitor", "watch"]):
            action = "Detection"
        elif any(x in name_lower or x in desc_lower for x in ["model", "graph", "relation"]):
            action = "Modeling"
        elif any(x in name_lower or x in desc_lower for x in ["export", "deliver", "publish"]):
            action = "Export"
        elif any(x in name_lower or x in desc_lower for x in ["manage", "control", "handle", "orchestrat"]):
            action = "Management"
            
        if action:
            cap_name = f"{domain} {action}"
        else:
            cap_name = domain
            if len(domain_words) == 1 and domain_words[0].lower() in {"data", "core", "system"}:
                action = "Processing"
                cap_name = f"{domain} Processing"
            
        if action is None:
            action = "Processing"
            
        if cap_name.endswith(" Processing Processing"): cap_name = cap_name.replace(" Processing Processing", " Processing")
        if cap_name.endswith(" Management Management"): cap_name = cap_name.replace(" Management Management", " Management")
        if cap_name.endswith(" Detector Detection"): cap_name = cap_name.replace(" Detector Detection", " Detection")
        if cap_name.endswith(" Transformer"): cap_name = cap_name.replace(" Transformer", " Transformation")
            
        return domain, action, cap_name

    def _classify_layer(self, name: str) -> str:
        n = name.lower()
        if any(k in n for k in ("controller","router","view","endpoint","handler","frontend","ui")):
            return "Presentation"
        if any(k in n for k in ("service","manager","orchestrator","use case","application")):
            return "Application"
        if any(k in n for k in ("model","entity","schema","repository","domain","rule","aggregate")):
            return "Domain"
        if any(k in n for k in ("database","cache","queue","config","infra","store","persistence","adapter")):
            return "Infrastructure"
        return "Application"

    def _get_capability_for_component(self, comp_name: str, capabilities: List[ArchitectureCapability]) -> str:
        for cap in capabilities:
            if comp_name in cap.supporting_components:
                return cap.name
        return None

    # ══════════════════════════════════════════════════════════════
    #  STEP 2: CAPABILITIES
    # ══════════════════════════════════════════════════════════════

    def _extract_capabilities(self, ir: SemanticIR) -> List[ArchitectureCapability]:
        capabilities_dict = {}

        for comp in ir.components:
            domain, action, cap_name = self._infer_capability(comp.name, comp.description)
            
            if cap_name not in capabilities_dict:
                capabilities_dict[cap_name] = ArchitectureCapability(
                    name=cap_name,
                    description=f"Provides {cap_name} capabilities to the platform.",
                    confidence="high"
                )
            capabilities_dict[cap_name].supporting_components.append(comp.name)
            
        caps = list(capabilities_dict.values())
        caps.sort(key=lambda x: len(x.supporting_components), reverse=True)
        return caps[:7]

    # ══════════════════════════════════════════════════════════════
    #  STEP 3: SERVICES
    # ══════════════════════════════════════════════════════════════

    def _extract_services(self, ir: SemanticIR, capabilities: List[ArchitectureCapability], artifacts: List[ArchitectureArtifact]) -> List[ArchitectureService]:
        services = []
        for cap in capabilities:
            service_name = f"{cap.name} Service" if "Service" not in cap.name else cap.name
                
            dependencies = set()
            consumers = set()
            inputs = set()
            outputs = set()
            
            # Identify inter-service boundaries from relationships
            for rel in ir.relationships:
                src_cap = self._get_capability_for_component(rel.source, capabilities)
                tgt_cap = self._get_capability_for_component(rel.target, capabilities)
                
                if src_cap and tgt_cap and src_cap != tgt_cap:
                    if src_cap == cap.name:
                        tgt_service = f"{tgt_cap} Service" if "Service" not in tgt_cap else tgt_cap
                        dependencies.add(tgt_service)
                    if tgt_cap == cap.name:
                        src_service = f"{src_cap} Service" if "Service" not in src_cap else src_cap
                        consumers.add(src_service)

            # Map inputs and outputs to discovered information assets (Artifacts)
            for art in artifacts:
                # If the service's underlying components produced the artifact
                if art.producer in cap.supporting_components:
                    outputs.add(art.name)
                # If the service consumes the artifact
                if any(c in cap.supporting_components for c in art.consumers):
                    inputs.add(art.name)

                # Incorporate data store artifacts if accessed by this capability
                for ds in ir.data_stores:
                    if ds.name == art.name:
                        for accessor in ds.accessed_by:
                            if self._get_capability_for_component(accessor, capabilities) == cap.name:
                                if "write" in str(ds.operations).lower() or "insert" in str(ds.operations).lower() or "update" in str(ds.operations).lower():
                                    outputs.add(art.name)
                                else:
                                    inputs.add(art.name)

            # If no strict mapping exists, use a generic fallback that DOES NOT use capability terms
            if not inputs:
                inputs.add("External Request")
            if not outputs:
                outputs.add("System Response")

            total_rels = len(dependencies) + len(consumers)
            if total_rels <= 3:
                complexity_score = "Low"
            elif total_rels <= 10:
                complexity_score = "Medium"
            else:
                complexity_score = "High"

            confidence_factors = 0
            if cap.description and len(cap.description) > 10:
                confidence_factors += 1
            if total_rels > 0:
                confidence_factors += 1
            if len(cap.supporting_components) > 1:
                confidence_factors += 1
                
            if confidence_factors >= 2:
                confidence_score = "High"
            elif confidence_factors == 1:
                confidence_score = "Medium"
            else:
                confidence_score = "Low"

            # Derive purpose from artifacts instead of class/function names to prevent hallucinations
            in_arts = [a for a in inputs if a != "External Request"]
            out_arts = [a for a in outputs if a != "System Response"]
            
            if in_arts and out_arts:
                purpose = f"Consumes {', '.join(in_arts[:2])} to produce {', '.join(out_arts[:2])}."
            elif out_arts:
                purpose = f"Produces {', '.join(out_arts[:3])} artifacts."
            elif in_arts:
                purpose = f"Processes {', '.join(in_arts[:3])} artifacts."
            elif dependencies:
                purpose = f"Coordinates {', '.join(list(dependencies)[:2])} execution."
            else:
                purpose = "Orchestrates component execution and data flow."

            services.append(ArchitectureService(
                name=service_name,
                purpose=purpose,
                responsibilities=[f"Process {a}" for a in in_arts] + [f"Produce {a}" for a in out_arts],
                inputs=sorted(list(inputs)),
                outputs=list(outputs),
                layer=self._classify_layer(cap.name),
                complexity_score=complexity_score,
                confidence_score=confidence_score
            ))

        services.sort(key=lambda x: len(x.responsibilities) + len(x.inputs) + len(x.outputs), reverse=True)
        return services[:5]

    # ══════════════════════════════════════════════════════════════
    #  STEP 4: ARTIFACTS
    # ══════════════════════════════════════════════════════════════

    def _extract_artifacts(self, ir: SemanticIR) -> List[ArchitectureArtifact]:
        INVALID_ARTIFACT_TERMS = {
            "Analysis", "Detection", "Processing", "Generation", "Modeling", "Management",
            "Frameworks Detection", "Architecture Analysis", "Extractor", "Builder", "Generator",
            "Service", "Controller", "Router", "Manager", "Orchestrator",
            "Blueprint", "Data", "Store", "Payload", "Request", "Response", "Object", "Entity", "Context"
        }

        def clean_name(name: str) -> str:
            cleaned = name.replace("_", " ").title()
            for term in INVALID_ARTIFACT_TERMS:
                cleaned = cleaned.replace(term, "").strip()
            return " ".join(cleaned.split())

        artifacts_dict = {}

        # 1. Database Schemas / Data Stores
        for ds in ir.data_stores:
            art_name = ds.name
            artifacts_dict[art_name] = ArchitectureArtifact(
                name=art_name,
                description=f"Persistent data entity for {ds.name}",
                producer="System Data Store",
                consumers=ds.accessed_by,
                artifact_type="Data Store"
            )

        # 2. API Contracts
        for api in ir.api_endpoints:
            parts = [p for p in api.path.split("/") if p and not p.startswith("{")]
            if parts:
                domain = clean_name(parts[-1])
                if not domain: continue
                req_name = f"{domain} Request"
                res_name = f"{domain} Response"
                if req_name not in artifacts_dict:
                    artifacts_dict[req_name] = ArchitectureArtifact(
                        name=req_name,
                        description=f"API Request payload for {api.path}",
                        producer="External",
                        consumers=[api.service or "API Gateway"],
                        artifact_type="Request Payload"
                    )
                if res_name not in artifacts_dict:
                    artifacts_dict[res_name] = ArchitectureArtifact(
                        name=res_name,
                        description=f"API Response payload for {api.path}",
                        producer=api.service or "API Gateway",
                        consumers=["External"],
                        artifact_type="Response Payload"
                    )

        # 3. Data Models from key classes
        for comp in ir.components:
            for cls_name in getattr(comp, "key_classes", []):
                if any(x in cls_name for x in ["Service", "Controller", "Manager", "Handler", "Generator"]):
                    continue
                art_name = clean_name(cls_name)
                if art_name and len(art_name) > 2 and art_name not in artifacts_dict:
                    artifacts_dict[art_name] = ArchitectureArtifact(
                        name=art_name,
                        description=f"Domain model representing {art_name}",
                        producer=comp.name,
                        consumers=[],
                        artifact_type="Domain Entity"
                    )

        # 4. Processing Outputs (Information Inference from Components)
        for comp in ir.components:
            art_name = clean_name(comp.name)
            if not art_name or len(art_name) < 3:
                continue
                
            # Architectural heuristics for AI Documentation System
            if "Ast" in art_name: art_name = "AST Model"
            elif "Graph" in art_name: art_name = "Knowledge Graph"
            elif "Doc" in art_name: art_name = "Generated Documentation"
            elif "Context" in art_name: art_name = "Documentation Context"
            elif "Dependency" in art_name: art_name = "Dependency Graph"
            elif "Semantic" in art_name or "Model" in art_name: art_name = "Semantic Model"
            elif "Source" in art_name or "Code" in art_name: art_name = "Source Code"
            elif "Architecture" in art_name: art_name = "Architecture Documents"
            
            if art_name not in artifacts_dict:
                artifacts_dict[art_name] = ArchitectureArtifact(
                    name=art_name,
                    description=f"Information asset: {art_name}",
                    producer=comp.name,
                    consumers=[],
                    artifact_type="Information Asset"
                )

        INVALID_ARTIFACT_TERMS = {
            "Analysis", "Detection", "Processing", "Generation", "Modeling", "Management",
            "Service", "Controller", "Router", "Manager", "Orchestrator",
            "Builder", "Registry", "Node", "Category", "Result", 
            "Runner", "Partitioner", "Status", "Model", "Workflow",
            "Blueprint", "Extractor", "Service", "Controller", 
            "Manager", "Orchestrator", "API", "Integration", "DeploymentNode", "DTO", "Entity", "Context",
            "Walker", "Loader", "Linker", "Engine", "Orchestrator", "Pattern", "Path", "Score", "Flow"
        }
        
        ALLOWED_EXACT = {"astmodel", "architecturecontext", "knowledgegraph", "dependencygraph", "sourcecode", "generateddocumentation"}

        final_artifacts = []
        for art in artifacts_dict.values():
            if art.name.lower().replace(" ", "") in ALLOWED_EXACT:
                final_artifacts.append(art)
                continue
            is_valid = True
            for term in INVALID_ARTIFACT_TERMS:
                if term.lower() in art.name.lower():
                    is_valid = False
                    break
            if is_valid:
                final_artifacts.append(art)

        # If fallback is entirely empty, seed a generic business entity
        if not final_artifacts:
            final_artifacts.append(ArchitectureArtifact(
                name="Domain Entity",
                description="Core domain entity for the system",
                producer="System",
                consumers=[],
                artifact_type="Domain Object"
            ))

        final_artifacts.sort(key=lambda x: len(x.consumers), reverse=True)
        return final_artifacts[:8]

    # ══════════════════════════════════════════════════════════════
    #  COMPONENTS
    # ══════════════════════════════════════════════════════════════

    def _extract_components(self, ir: SemanticIR) -> List[ArchitectureComponent]:
        comps = []
        for c in ir.components:
            comps.append(ArchitectureComponent(
                name=c.name,
                parent_service=None,
                description=c.description or f"Implementation module {c.name}",
                technologies=c.languages,
                responsibilities=[],
                interfaces=[]
            ))
        return comps

    # ══════════════════════════════════════════════════════════════
    #  STEP 5: WORKFLOWS
    # ══════════════════════════════════════════════════════════════

    def _extract_workflows(self, ir: SemanticIR, capabilities: List[ArchitectureCapability]) -> List[ArchitectureWorkflow]:
        if not capabilities:
            return []

        # 1. Build Capability DAG from relationships
        adj = {}
        for cap in capabilities:
            adj[cap.name] = set()

        for rel in ir.relationships:
            src_cap = self._get_capability_for_component(rel.source, capabilities)
            tgt_cap = self._get_capability_for_component(rel.target, capabilities)
            if src_cap and tgt_cap and src_cap != tgt_cap:
                adj[src_cap].add(tgt_cap)

        # 2. Find longest path in the DAG (ignoring cycles by simple visited tracking)
        longest_path = []
        
        def dfs(node, current_path):
            nonlocal longest_path
            if len(current_path) > len(longest_path):
                longest_path = list(current_path)
            
            for neighbor in adj.get(node, []):
                if neighbor not in current_path:
                    current_path.append(neighbor)
                    dfs(neighbor, current_path)
                    current_path.pop()
                    
        for start_node in adj.keys():
            dfs(start_node, [start_node])
            
        # 3. Fallback if no relationships
        if len(longest_path) < 2:
            if len(capabilities) > 1:
                longest_path = [capabilities[0].name, capabilities[-1].name]
            else:
                longest_path = [capabilities[0].name]
                
        # 4. Format into ArchitectureWorkflow
        steps_formatted = [f"{longest_path[j]} → {longest_path[j+1]}" for j in range(len(longest_path)-1)]
        if not steps_formatted:
            steps_formatted = [longest_path[0]]
            
        workflow = ArchitectureWorkflow(
            name="Primary Processing Pipeline",
            description=f"End-to-end architectural workflow driving {longest_path[-1]}.",
            workflow_type="Business Process",
            trigger=longest_path[0],
            business_goal=f"Execute {longest_path[-1]}",
            steps=steps_formatted,
            inputs=["Business Request"],
            outputs=["Business Result"],
            participants=longest_path
        )
        
        return [workflow]

    # ══════════════════════════════════════════════════════════════
    #  STEP 6: DATA FLOWS
    # ══════════════════════════════════════════════════════════════

    def _extract_data_flows(self, ir: SemanticIR, artifacts: List[ArchitectureArtifact], capabilities: List[ArchitectureCapability]) -> List[ArchitectureDataFlow]:
        import os
        import re
        data_flows = []
        
        repo_root = "/Users/sarabafna/ai-doc-system/backend"
        if not os.path.exists(repo_root):
            repo_root = os.getcwd()

        # 1. Discover Producer and Consumer Evidence for each artifact
        artifact_lineage = {}
        
        for art in artifacts:
            target_class_name = art.name.replace(" ", "")
            prod_comp = None
            prod_ev = None
            consumers = {}
            
            for comp in ir.components:
                is_prod = False
                is_cons = False
                ev_str_prod = None
                ev_str_cons = None
                
                for fpath in comp.files:
                    full_path = os.path.join(repo_root, fpath)
                    if not os.path.exists(full_path): continue
                    with open(full_path, 'r', encoding='utf-8') as f:
                        for line in f:
                            if is_prod and is_cons: break
                            
                            # Fast string check before regex
                            if target_class_name.lower() not in line.lower():
                                continue
                            
                            # Producer evidence
                            if not is_prod:
                                if re.search(r'class\s+' + re.escape(target_class_name) + r'\b', line, re.IGNORECASE):
                                    is_prod = True
                                    ev_str_prod = f"Class {target_class_name} defined in {fpath}"
                                elif re.search(r'->\s*.*?' + re.escape(target_class_name) + r'\b', line, re.IGNORECASE):
                                    is_prod = True
                                    ev_str_prod = f"Return type {target_class_name} found in {fpath}"
                                    
                            # Consumer evidence
                            if not is_cons:
                                if re.search(r'\b\w+\s*:\s*.*?' + re.escape(target_class_name) + r'\b', line, re.IGNORECASE):
                                    is_cons = True
                                    ev_str_cons = f"Parameter typed as {target_class_name} in {fpath}"
                                elif re.search(r'import\s+.*?' + re.escape(target_class_name) + r'\b', line, re.IGNORECASE):
                                    is_cons = True
                                    ev_str_cons = f"Imported {target_class_name} in {fpath}"
                                    
                if is_prod and not prod_comp:
                    prod_comp = comp.name
                    prod_ev = ev_str_prod
                if is_cons:
                    consumers[comp.name] = ev_str_cons
                    
            artifact_lineage[art.name] = {
                "producer": prod_comp,
                "producer_evidence": prod_ev,
                "consumers": consumers
            }

        # Add Data Store lineage
        for ds in ir.data_stores:
            if ds.name in artifact_lineage:
                artifact_lineage[ds.name]["producer"] = "System"
                artifact_lineage[ds.name]["producer_evidence"] = f"Detected database operations"
                for acc in ds.accessed_by:
                    artifact_lineage[ds.name]["consumers"][acc] = f"Executes queries on {ds.name}"

        # 2. Build Valid Edges
        # Artifact A -> Artifact B if Producer of B consumes A
        for art_A in artifacts:
            lineage_A = artifact_lineage.get(art_A.name)
            if not lineage_A or not lineage_A["producer"]: continue
            prod_A = lineage_A["producer"]
            
            for cons_comp, cons_ev in lineage_A["consumers"].items():
                for art_B in artifacts:
                    if art_B.name == art_A.name: continue
                    lineage_B = artifact_lineage.get(art_B.name)
                    if not lineage_B or not lineage_B["producer"]: continue
                    
                    if lineage_B["producer"] == cons_comp:
                        # VALID EDGE!
                        edge_evidence = (
                            f"{prod_A} produces {art_A.name} ({lineage_A['producer_evidence']}). "
                            f"{cons_comp} consumes {art_A.name} ({cons_ev}) "
                            f"and produces {art_B.name} ({lineage_B['producer_evidence']})."
                        )
                        
                        # Get matching capability services
                        src_service = f"{prod_A} Service"
                        tgt_service = f"{cons_comp} Service"
                        for cap in capabilities:
                            if prod_A in cap.supporting_components: src_service = cap.name
                            if cons_comp in cap.supporting_components: tgt_service = cap.name
                        
                        data_flows.append(ArchitectureDataFlow(
                            source=art_A.name,
                            sink=art_B.name,
                            producer_service=src_service,
                            consumer_service=tgt_service,
                            evidence=edge_evidence,
                            name=f"{art_A.name} Transformation"
                        ))
                        
        return data_flows

    # ══════════════════════════════════════════════════════════════
    #  APIs & DATABASES
    # ══════════════════════════════════════════════════════════════

    def _extract_apis(self, ir: SemanticIR) -> List[ArchitectureAPI]:
        apis = []
        for ep in ir.api_endpoints:
            apis.append(ArchitectureAPI(
                method=ep.method,
                path=ep.path,
                handler=ep.handler_function or "Unknown Handler",
                service=ep.service,
                description=ep.description
            ))
        return apis

    def _extract_databases(self, ir: SemanticIR) -> List[ArchitectureDatabase]:
        dbs = []
        for ds in ir.data_stores:
            dbs.append(ArchitectureDatabase(
                name=ds.name,
                type=ds.store_type,
                operations=ds.operations,
                accessed_by=ds.accessed_by
            ))
        return dbs

    # ══════════════════════════════════════════════════════════════
    #  STEP 7: INTEGRATIONS (ARCHITECTURAL SERVICES)
    # ══════════════════════════════════════════════════════════════

    def _extract_integrations(self, ir: SemanticIR, capabilities: List[ArchitectureCapability]) -> List[ArchitectureIntegration]:
        integrations_dict = {}

        RELATIONSHIP_MAP = {
            "CALLS": "Function Call",
            "CALLS_API": "API Call",
            "DEPENDS_ON": "Dependency",
            "IMPORTS": "Module Import",
            "INVOKES_SERVICE": "Service Invocation",
            "FEEDS_DATA_TO": "Data Feed",
            "PUBLISHES_TO": "Event Publish",
            "SUBSCRIBES_FROM": "Event Subscribe",
            "READS_FROM": "Data Read",
            "WRITES_TO": "Data Write",
            "QUERIES_TABLE": "DB Query",
            "WRITES_TABLE": "DB Write"
        }

        def add_integration(source: str, target: str, int_type: str, **kwargs):
            if not source or not target or source == target:
                return
            key = (source, target, int_type)
            if key not in integrations_dict:
                integrations_dict[key] = ArchitectureIntegration(
                    source=source,
                    target=target,
                    integration_type=int_type,
                    **kwargs
                )

        for rel in ir.relationships:
            if rel.source and rel.target and rel.source != rel.target:
                # Map raw components to Architectural Services
                src_cap = self._get_capability_for_component(rel.source, capabilities)
                tgt_cap = self._get_capability_for_component(rel.target, capabilities)
                
                if src_cap and tgt_cap and src_cap != tgt_cap:
                    src_service = f"{src_cap} Service" if "Service" not in src_cap else src_cap
                    tgt_service = f"{tgt_cap} Service" if "Service" not in tgt_cap else tgt_cap
                    
                    rel_type = rel.relationship_type.upper()
                    int_type = RELATIONSHIP_MAP.get(rel_type, rel.relationship_type.replace("_", " ").title())
                    
                    add_integration(
                        source=src_service,
                        target=tgt_service,
                        int_type=int_type,
                        description=getattr(rel, "evidence", None),
                        confidence=getattr(rel, "confidence", "medium")
                    )

        for ds in ir.data_stores:
            for accessor in ds.accessed_by:
                src_cap = self._get_capability_for_component(accessor, capabilities)
                if src_cap:
                    src_service = f"{src_cap} Service" if "Service" not in src_cap else src_cap
                    ops = ds.operations if ds.operations else ["Data Access"]
                    purpose = f"Performs {', '.join(ops)} on {ds.name}"
                    int_type = "Database Access" if "sql" in ds.store_type.lower() or "db" in ds.store_type.lower() else "Data Store Access"
                    add_integration(
                        source=src_service,
                        target=ds.name,
                        int_type=int_type,
                        description=f"Data store access for {ds.name}",
                        purpose=purpose
                    )

        for ep in ir.api_endpoints:
            if ep.service:
                tgt_cap = self._get_capability_for_component(ep.service, capabilities)
                if tgt_cap:
                    tgt_service = f"{tgt_cap} Service" if "Service" not in tgt_cap else tgt_cap
                    add_integration(
                        source="External Client",
                        target=tgt_service,
                        int_type="REST API",
                        description=f"External access via {ep.method} {ep.path}",
                        purpose="External API access"
                    )

        results = list(integrations_dict.values())
        results.sort(key=lambda x: (x.source, x.target, x.integration_type))
        return results[:10]

    # ══════════════════════════════════════════════════════════════
    #  INFRASTRUCTURE
    # ══════════════════════════════════════════════════════════════

    def _extract_deployment_nodes(self, ir: SemanticIR) -> List[ArchitectureDeploymentNode]:
        nodes = []
        if "container_orchestration" in ir.metadata:
            nodes.append(ArchitectureDeploymentNode(
                node_type="Container Orchestration",
                name=ir.metadata["container_orchestration"],
                services_hosted=ir.metadata.get("docker_services", "").split(", ")
            ))
        return nodes

    def _extract_security_boundaries(self, ir: SemanticIR) -> List[SecurityBoundary]:
        boundaries = []
        return boundaries
