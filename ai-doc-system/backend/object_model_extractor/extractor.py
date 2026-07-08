from typing import List, Dict, Optional, Tuple
from collections import defaultdict
from backend.semantic_ir.models import SemanticIR
from backend.knowledge_graph.models import KnowledgeGraph, KGNodeType, KGRelationType
from backend.object_model_extractor.models import (
    LLDModel,
    LLDClass,
    LLDInterface,
    LLDMethod,
    LLDDesignPattern,
    LLDAlgorithm,
    LLDDatabaseObject,
    LLDSequenceFlow,
    LLDErrorPath,
    LLDAPISpec,
    LLDModule,
    LLDComponent,
    LLDDependency,
    LLDExternalIntegration,
    LLDDeploymentUnit,
    LLDSecurityDesign,
    LLDConfigDesign,
    LLDDataType,
    LLDEnumType,
    LLDTypeAlias,
    LLDCircularDependency,
    LLDEntryPoint,
)

def _infer_fields_from_class(cls_name: str, comp) -> List[str]:
    """
    DISABLED: Fields must come from AST/KG evidence only.
    No heuristic field inference from class names.
    """
    return []

class ObjectModelExtractor:
    """
    Extracts an Object Model (LLD Model) from the Semantic IR and Knowledge Graph.
    Uses precise AST traversal on the KG for classes, methods, and relationships.
    """

    def extract(self, ir: SemanticIR, kg: Optional[KnowledgeGraph] = None) -> LLDModel:
        model = LLDModel(
            repository_type=ir.repository_type,
            architecture_pattern=ir.architecture_pattern,
            architecture_pattern_confidence=ir.architecture_pattern_confidence,
            architecture_pattern_evidence=ir.architecture_pattern_evidence,
            metadata=dict(ir.metadata)
        )

        model.classes, model.interfaces = self._extract_classes_and_interfaces(ir, kg)
        self._last_extracted_classes = model.classes  # save for data type fallback
        
        model.design_patterns = self._extract_design_patterns(ir, kg)
        model.algorithms = self._extract_algorithms(ir, kg)
        model.database_objects = self._extract_database_objects(ir, kg)
        model.data_type_tables = self._extract_data_type_tables(ir, kg)
        model.sequence_flows = self._extract_sequence_flows(ir, kg)
        model.error_paths = self._extract_error_paths(ir, kg)
        model.security = self._extract_security_design(ir, kg)
        model.configuration = self._extract_configuration_design(ir, kg)
        
        # NEW data types
        model.data_types, model.enum_types, model.type_aliases = self._extract_data_types(ir, kg)

        # NEW extractions
        model.api_specs = self._extract_api_specs(ir)
        model.components = self._extract_components(ir, kg)
        model.modules = self._extract_modules(ir, model.components)
        model.dependencies = self._extract_dependencies(ir, kg)
        model.circular_dependencies = self._extract_circular_dependencies(ir, kg, model.dependencies)
        model.entry_points = self._extract_entrypoints(ir, kg)
        model.external_integrations = self._extract_external_integrations(ir)
        model.deployment_units = self._extract_deployment_units(ir)
        model.system_overview = self._build_system_overview(ir, model)

        
        # --- RULE 4: Deduplication ---
        def dedup(items):
            seen = {}
            for item in items:
                key = item.name
                if key not in seen:
                    seen[key] = item
                else:
                    existing = seen[key]
                    if hasattr(item, 'methods') and len(item.methods) > len(existing.methods):
                        seen[key] = item
            return list(seen.values())
        
        model.classes = dedup(model.classes)
        model.interfaces = dedup(model.interfaces)
        model.database_objects = dedup(model.database_objects)
        
        sf_seen = {}
        for sf in model.sequence_flows:
            if sf.name not in sf_seen or len(sf.steps) > len(sf_seen[sf.name].steps):
                sf_seen[sf.name] = sf
        model.sequence_flows = list(sf_seen.values())

        return model

    def _extract_classes_and_interfaces(self, ir: SemanticIR, kg: Optional[KnowledgeGraph]) -> Tuple[List[LLDClass], List[LLDInterface]]:
        classes, interfaces = [], []
        
        parsed_files = getattr(ir, 'parsed_files', [])
        
        # Source 1: Semantic IR (stubbed entities)
        if java_scan := ir.metadata.get('java_scan'):
            for cls in java_scan.classes:
                methods = [LLDMethod(name=m.name, signature=f"{m.name}({', '.join(m.parameters)}) -> {m.return_type}", parameters=m.parameters, return_type=m.return_type) for m in cls.methods]
                fields = [f"{f.name}: {f.field_type}" for f in cls.fields]
                classes.append(LLDClass(name=cls.name, file_path=cls.file_path, fields=fields, methods=methods, dependencies=[], inherits_from=[cls.extends] if cls.extends else [], implements=cls.implements))
            for cls in java_scan.interfaces:
                methods = [LLDMethod(name=m.name, signature=f"{m.name}({', '.join(m.parameters)}) -> {m.return_type}", parameters=m.parameters, return_type=m.return_type) for m in cls.methods]
                interfaces.append(LLDInterface(name=cls.name, file_path=cls.file_path, methods=methods))

        if sql_procs := ir.metadata.get('sql_procedures'):
            for proc in sql_procs:
                methods = [LLDMethod(name="execute", signature=f"execute({proc['params']}) -> void", parameters=[proc['params']], return_type="void")]
                classes.append(LLDClass(name=proc['name'], file_path=proc['file'], fields=[], methods=methods, dependencies=[], inherits_from=[], implements=[]))

        if not kg:
            return classes, interfaces
        
        def infer_field_type(name):
            name = name.lower()
            if name in ('id', 'uuid'): return 'str'
            if any(k in name for k in ('count', 'total', 'size', 'num_', '_count', '_number')): return 'int'
            if any(name.startswith(k) for k in ('is_', 'has_')) or any(k in name for k in ('enabled', 'active', 'flag')): return 'bool'
            if any(k in name for k in ('_path', '_url', '_dir', '_file')): return 'str'
            if any(k in name for k in ('_list', 'items', 'nodes', 'edges')) or name.endswith('s'): return 'List'
            if any(k in name for k in ('_map', '_dict', '_index', '_cache')): return 'Dict'
            if any(k in name for k in ('_at', '_time', '_date')): return 'datetime'
            return 'untyped'
            
        def infer_method_desc(name):
            n = name.lower()
            if n.startswith(('get_', 'fetch_', 'load_')): return f"Returns {n.split('_', 1)[-1]}."
            if n.startswith(('set_', 'update_', 'save_')): return f"Updates {n.split('_', 1)[-1]}."
            if n.startswith(('create_', 'build_', 'generate_')): return f"Creates and returns {n.split('_', 1)[-1]}."
            if n.startswith(('extract_', 'parse_', 'analyze_')): return f"Extracts {n.split('_', 1)[-1]} from input."
            if n.startswith(('validate_', 'check_', 'verify_')): return f"Validates {n.split('_', 1)[-1]}, raises on failure."
            if n.startswith(('run_', 'execute_', 'process_')): return f"Executes the {n.split('_', 1)[-1]} operation."
            return f"Executes {name}."

        for cls_id, cls in kg.nodes.items():
            if cls.node_type not in (KGNodeType.CLASS, KGNodeType.INTERFACE): continue
            fields, methods = [], []
            dependencies, inherits_from, implements, composition, aggregation = [], [], [], [], []
            
            for edge in kg.outgoing_edges(cls.id):
                if edge.relation == KGRelationType.CONTAINS:
                    child = kg.nodes.get(edge.to_id)
                    if not child: continue
                    
                    if child.node_type in (KGNodeType.VARIABLE, KGNodeType.PROPERTY):
                        # FIX 2
                        f_type = getattr(child, 'return_type', None)
                        if not f_type:
                            for pf in parsed_files:
                                for node in getattr(pf, 'nodes', []):
                                    if getattr(node, 'category', '') == 'class' and getattr(node, 'name', '') == cls.name:
                                        for c in getattr(node, 'children', []):
                                            if getattr(c, 'category', '') == 'field' and getattr(c, 'name', '') == child.name:
                                                f_type = getattr(c, 'type_annotation', None)
                                                break
                        if not f_type: f_type = infer_field_type(child.name)
                        fields.append(f"{child.name}: {f_type}")
                        
                        # Extract composition from typed attributes
                        import re
                        type_matches = re.findall(r'[A-Z][a-zA-Z0-9_]+', f_type)
                        for t_match in type_matches:
                            if t_match not in ('List', 'Dict', 'Set', 'Tuple', 'Optional', 'Union', 'Any'):
                                if t_match not in composition: composition.append(t_match)
                                
                    elif child.node_type in (KGNodeType.METHOD, KGNodeType.FUNCTION, KGNodeType.CONSTRUCTOR):
                        # FIX 3
                        if child.name.startswith("_") and not child.name.startswith("__init"): continue
                        m_name = "constructor" if child.name.startswith("__init") else child.name
                        
                        m_params = getattr(child, 'params', [])
                        m_ret = getattr(child, 'return_type', None)
                        m_desc = child.docstring.split('.')[0] + '.' if child.docstring else ""
                        
                        if not m_params or not m_ret or not m_desc:
                            for pf in parsed_files:
                                for node in getattr(pf, 'nodes', []):
                                    if getattr(node, 'category', '') == 'class' and getattr(node, 'name', '') == cls.name:
                                        for c in getattr(node, 'children', []):
                                            if getattr(c, 'category', '') == 'function' and getattr(c, 'name', '') == child.name:
                                                m_params = m_params or getattr(c, 'parameters', getattr(c, 'params', []))
                                                m_ret = m_ret or getattr(c, 'return_type', None)
                                                m_desc = m_desc or (getattr(c, 'docstring', '') or "").split('.')[0]
                                                break
                        
                        m_ret = m_ret or "untyped"
                        m_desc = m_desc or infer_method_desc(child.name)
                        
                        params_clean = [p for p in m_params if not str(p).startswith("self") and not str(p).startswith("cls")]
                        if len(params_clean) == 0 and not child.docstring and m_name.startswith('get_'): continue
                        
                        methods.append(LLDMethod(name=m_name, signature=f"{m_name}({', '.join(params_clean)}) -> {m_ret}", description=m_desc, parameters=params_clean, return_type=m_ret))
                        
                        # Extract aggregation/composition from parameters
                        import re
                        for p in params_clean:
                            p_str = str(p)
                            if ":" in p_str:
                                p_type = p_str.split(":", 1)[1]
                                type_matches = re.findall(r'[A-Z][a-zA-Z0-9_]+', p_type)
                                for t_match in type_matches:
                                    if t_match not in ('List', 'Dict', 'Set', 'Tuple', 'Optional', 'Union', 'Any'):
                                        if m_name == "constructor":
                                            if t_match not in composition: composition.append(t_match)
                                        else:
                                            if t_match not in aggregation: aggregation.append(t_match)
                        
                elif edge.relation == KGRelationType.EXTENDS:
                    t = kg.nodes.get(edge.to_id)
                    if t: inherits_from.append(t.name)
                elif edge.relation == KGRelationType.IMPLEMENTS:
                    t = kg.nodes.get(edge.to_id)
                    if t: implements.append(t.name)
                elif edge.relation in (KGRelationType.DEPENDS_ON, KGRelationType.REFERENCES, KGRelationType.INSTANTIATES, KGRelationType.CALLS):
                    t = kg.nodes.get(edge.to_id)
                    if t and t.node_type in (KGNodeType.CLASS, KGNodeType.INTERFACE):
                        if t.name not in dependencies: dependencies.append(t.name)

            # FALLBACK: If KG missed CONTAINS edges, pull directly from kg nodes using parent_id
            if not fields and not methods and kg:
                import re
                for child in kg.nodes.values():
                    if getattr(child, 'parent_id', None) == cls.id:
                        node_type = getattr(child, 'node_type', '')
                        
                        # Collect dependencies from method/field outgoing edges
                        for edge in kg.outgoing_edges(child.id):
                            if edge.relation in (KGRelationType.DEPENDS_ON, KGRelationType.REFERENCES, KGRelationType.INSTANTIATES, KGRelationType.CALLS):
                                t = kg.nodes.get(edge.to_id)
                                if t and t.node_type in (KGNodeType.CLASS, KGNodeType.INTERFACE):
                                    if t.name not in dependencies and t.name != cls.name: 
                                        dependencies.append(t.name)
                                        
                        if node_type in (KGNodeType.VARIABLE, KGNodeType.PROPERTY, 'ASSIGNMENT', 'FIELD'):
                            fname = getattr(child, 'name', '')
                            ftype = getattr(child, 'return_type', None) or infer_field_type(fname)
                            fields.append(f"{fname}: {ftype}")
                            for tm in re.findall(r'[A-Z][a-zA-Z0-9_]+', ftype):
                                if tm not in ('List', 'Dict', 'Set', 'Tuple', 'Optional', 'Union', 'Any') and tm not in composition:
                                    composition.append(tm)
                        elif node_type in (KGNodeType.METHOD, KGNodeType.FUNCTION, KGNodeType.CONSTRUCTOR):
                            fname = getattr(child, 'name', '')
                            if fname.startswith("_") and not fname.startswith("__init"): continue
                            mname = "constructor" if fname.startswith("__init") else fname
                            mret = getattr(child, 'return_type', None) or "untyped"
                            mdesc = (getattr(child, 'docstring', '') or infer_method_desc(fname)).split('.')[0]
                            mparams = getattr(child, 'params', [])
                            p_clean = [p for p in mparams if not str(p).startswith("self") and not str(p).startswith("cls")]
                            
                            methods.append(LLDMethod(name=mname, signature=f"{mname}({', '.join(p_clean)}) -> {mret}", description=mdesc, parameters=p_clean, return_type=mret))
                            for p in p_clean:
                                p_str = str(p)
                                if ":" in p_str:
                                    ptype = p_str.split(":", 1)[1]
                                    for tm in re.findall(r'[A-Z][a-zA-Z0-9_]+', ptype):
                                        if tm not in ('List', 'Dict', 'Set', 'Tuple', 'Optional', 'Union', 'Any'):
                                            if mname == "constructor":
                                                if tm not in composition: composition.append(tm)
                                            else:
                                                if tm not in aggregation: aggregation.append(tm)

            if kg:
                # Synthesize class dependencies from file-level IMPORTS/CALLS
                file_node = None
                for node in kg.nodes.values():
                    if node.node_type == KGNodeType.FILE and node.file_path == cls.file_path:
                        file_node = node
                        break
                
                if file_node:
                    for edge in kg.outgoing_edges(file_node.id):
                        if edge.relation in (KGRelationType.IMPORTS, KGRelationType.CALLS):
                            target_file_node = kg.nodes.get(edge.to_id)
                            if target_file_node and target_file_node.node_type == KGNodeType.FILE:
                                for t_edge in kg.outgoing_edges(target_file_node.id):
                                    if t_edge.relation in (KGRelationType.CONTAINS, KGRelationType.DEFINES):
                                        t_cls = kg.nodes.get(t_edge.to_id)
                                        if t_cls and t_cls.node_type in (KGNodeType.CLASS, KGNodeType.INTERFACE):
                                            if t_cls.name not in dependencies and t_cls.name != cls.name:
                                                dependencies.append(t_cls.name)

            if cls.node_type == KGNodeType.CLASS:
                classes.append(LLDClass(name=cls.name, file_path=cls.file_path, fields=fields, methods=methods, dependencies=dependencies, inherits_from=inherits_from, implements=implements, composition=composition, aggregation=aggregation, business_domain=cls.business_domain))
            else:
                interfaces.append(LLDInterface(name=cls.name, file_path=cls.file_path, methods=methods, extends=inherits_from))
        return classes, interfaces

    def _extract_design_patterns(self, ir: SemanticIR, kg: Optional[KnowledgeGraph]) -> List[LLDDesignPattern]:
        patterns = []
        if kg:
            # Group classes by detected pattern
            repo_classes = []
            facade_classes = []
            singleton_classes = []
            observer_classes = []

            for cls in kg.nodes_by_type(KGNodeType.CLASS):
                # Repository Pattern
                has_db = any(e.relation in (KGRelationType.QUERIES_TABLE, KGRelationType.WRITES_TABLE) for e in kg.outgoing_edges(cls.id))
                if has_db:
                    repo_classes.append((cls.name, "High"))
                elif "Repository" in cls.name:
                    repo_classes.append((cls.name, "Low"))
                
                # Facade Pattern
                calls = {e.to_id for e in kg.outgoing_edges(cls.id) if e.relation in (KGRelationType.CALLS, "INVOKES")}
                if len(calls) > 3 and cls.in_degree > 1:
                    facade_classes.append((cls.name, "High"))
                elif "Facade" in cls.name:
                    facade_classes.append((cls.name, "Low"))
                
                # Observer/Pub-Sub
                pubsub_edges = any(e.relation in ("PUBLISHES_TO", "SUBSCRIBES_FROM") for e in kg.outgoing_edges(cls.id) + kg.incoming_edges(cls.id))
                if pubsub_edges:
                    observer_classes.append((cls.name, "High"))
                elif "Observer" in cls.name or "Listener" in cls.name:
                    observer_classes.append((cls.name, "Low"))

                # Singleton
                has_instance_prop = any(e.relation == KGRelationType.CONTAINS and kg.nodes.get(e.to_id) and kg.nodes.get(e.to_id).name == "instance" for e in kg.outgoing_edges(cls.id))
                if has_instance_prop:
                    singleton_classes.append((cls.name, "High"))
                elif "Singleton" in cls.name or "Manager" in cls.name or "Config" in cls.name:
                    singleton_classes.append((cls.name, "Low"))
            
            # Helper to aggregate
            def _add_pattern(name, desc, items):
                if items:
                    # Use highest confidence
                    conf = "High" if any(c == "High" for _, c in items) else "Low"
                    classes = [n for n, _ in items][:10]
                    patterns.append(LLDDesignPattern(name, classes, desc, confidence=conf))

            _add_pattern("Repository Pattern", "Abstracts data access logic", repo_classes)
            _add_pattern("Facade Pattern", "Provides simplified interface to complex subsystem", facade_classes)
            _add_pattern("Observer Pattern", "Event-driven state propagation", observer_classes)
            _add_pattern("Singleton Pattern", "Ensures single instance for shared state", singleton_classes)
                
            # ── Builder Pattern ────────────────────────────────────────
            # Classes with build() / create() method and chained setters
            builder_classes = []
            for cls in kg.nodes_by_type(KGNodeType.CLASS):
                method_names = []
                for edge in kg.outgoing_edges(cls.id):
                    if edge.relation == KGRelationType.CONTAINS:
                        child = kg.nodes.get(edge.to_id)
                        if child and child.node_type in (KGNodeType.METHOD, KGNodeType.FUNCTION):
                            method_names.append(child.name.lower())
                has_build = any(m in ("build", "create", "construct", "make") for m in method_names)
                has_setters = sum(1 for m in method_names if m.startswith("set_") or m.startswith("with_"))
                if has_build and has_setters >= 2:
                    builder_classes.append((cls.name, "High"))
                elif "Builder" in cls.name:
                    builder_classes.append((cls.name, "Medium"))

            if builder_classes:
                patterns.append(LLDDesignPattern(
                    pattern_name="Builder",
                    components_involved=[c for c, _ in builder_classes[:4]],
                    confidence=builder_classes[0][1],
                    description="Separates object construction from representation using chained builder methods.",
                ))

            # ── Factory Pattern ─────────────────────────────────────────
            factory_classes = []
            for cls in kg.nodes_by_type(KGNodeType.CLASS):
                method_names = []
                return_types = []
                for edge in kg.outgoing_edges(cls.id):
                    if edge.relation == KGRelationType.CONTAINS:
                        child = kg.nodes.get(edge.to_id)
                        if child and child.node_type in (KGNodeType.METHOD, KGNodeType.FUNCTION):
                            method_names.append(child.name.lower())
                            if child.return_type:
                                return_types.append(child.return_type)
                has_factory_method = any(m in ("create", "make", "build", "get_instance", "from_dict", "from_config") for m in method_names)
                varied_returns = len(set(return_types)) > 1
                if has_factory_method and varied_returns:
                    factory_classes.append((cls.name, "High"))
                elif "Factory" in cls.name or "Creator" in cls.name:
                    factory_classes.append((cls.name, "Medium"))

            if factory_classes:
                patterns.append(LLDDesignPattern(
                    pattern_name="Factory",
                    components_involved=[c for c, _ in factory_classes[:4]],
                    confidence=factory_classes[0][1],
                    description="Centralises object creation, decoupling callers from concrete implementations.",
                ))

            # ── Strategy Pattern ────────────────────────────────────────
            strategy_classes = []
            for cls in kg.nodes_by_type(KGNodeType.CLASS):
                # Strategy: implements an interface and has an execute/run/apply method
                iface_count = sum(1 for e in kg.outgoing_edges(cls.id) if e.relation == KGRelationType.IMPLEMENTS)
                method_names = []
                for edge in kg.outgoing_edges(cls.id):
                    if edge.relation == KGRelationType.CONTAINS:
                        child = kg.nodes.get(edge.to_id)
                        if child and child.node_type in (KGNodeType.METHOD, KGNodeType.FUNCTION):
                            method_names.append(child.name.lower())
                has_exec = any(m in ("execute", "run", "apply", "process", "handle", "perform") for m in method_names)
                if iface_count >= 1 and has_exec:
                    strategy_classes.append((cls.name, "High"))
                elif "Strategy" in cls.name or "Policy" in cls.name or "Handler" in cls.name:
                    strategy_classes.append((cls.name, "Low"))

            if len(strategy_classes) >= 2:
                patterns.append(LLDDesignPattern(
                    pattern_name="Strategy",
                    components_involved=[c for c, _ in strategy_classes[:5]],
                    confidence=strategy_classes[0][1],
                    description="Defines a family of interchangeable algorithms behind a common interface.",
                ))
            
        return patterns

    def _extract_algorithms(self, ir: SemanticIR, kg: Optional[KnowledgeGraph]) -> List[LLDAlgorithm]:
        algorithms = []
        for wf in ir.workflows:
            algorithms.append(LLDAlgorithm(
                name=f"{wf.name} Algorithm",
                location=wf.entry_point or "Unknown",
                description=wf.description or "Internal execution flow",
                steps=wf.steps
            ))
        return algorithms

    def _parse_create_table_columns(self, sql_file_path, table_name) -> list:
        import re
        try:
            content = open(sql_file_path).read()
            pattern = r"CREATE\s+TABLE\s+" + table_name + r"\s*\(([^)]+)\)"
            match = re.search(pattern, content, re.IGNORECASE | re.DOTALL)
            if match:
                col_block = match.group(1)
                lines = [l.strip() for l in col_block.split("\n") if l.strip()]
                cols = []
                for line in lines:
                    parts = line.split()
                    if parts and not parts[0].upper() in ("PRIMARY","FOREIGN","UNIQUE","INDEX","KEY","CONSTRAINT"):
                        cols.append(LLDTableColumn(name=parts[0], data_type=parts[1] if len(parts)>1 else "TEXT"))
                return cols
        except Exception:
            pass
        return []

    def _extract_database_objects(self, ir: SemanticIR, kg: Optional[KnowledgeGraph]) -> List[LLDDatabaseObject]:
        tables = []
        if not kg: return tables
        for cls_id, node in kg.nodes.items():
            if node.node_type == KGNodeType.SQL_TABLE:
                cols = getattr(node, 'properties', {}).get("columns") or getattr(node, 'properties', {}).get("schema") or []
                if not cols:
                    source = getattr(node, 'file_path', "")
                    if source and source.endswith(".sql"):
                        cols = self._parse_create_table_columns(source, node.name)
                
                col_strs = []
                for c in cols:
                    if isinstance(c, LLDTableColumn): col_strs.append(f"{c.name}: {c.data_type}")
                    elif isinstance(c, dict): col_strs.append(f"{c.get('name')}: {c.get('type')}")
                    else: col_strs.append(str(c))
                tables.append(LLDDatabaseObject(name=node.name, type="Table", fields=col_strs, relationships=[]))
        return tables

    def _extract_data_type_tables(
        self, ir: SemanticIR, kg: Optional[KnowledgeGraph]
    ) -> List["LLDDataTypeTable"]:
        """
        Extract typed data schemas from:
        1. KG SQL_TABLE / MONGO_COLLECTION nodes (highest fidelity)
        2. KG CLASS nodes that look like data models (ORM, Pydantic, dataclass)
        3. IR data_stores fallback
        """
        from backend.object_model_extractor.models import LLDDataTypeTable, LLDTableColumn
        tables: List[LLDDataTypeTable] = []
        seen_names: set = set()

        DATA_MODEL_SIGNALS = (
            "model", "schema", "entity", "record", "dto", "payload",
            "request", "response", "document", "table", "row", "base"
        )
        ORM_ANNOTATIONS = ("Column", "Field", "mapped_column", "attribute")

        # ── Source 1: KG SQL tables (highest precision) ──────────────
        if kg:
            for node in kg.nodes_by_type(KGNodeType.SQL_TABLE):
                if node.name in seen_names:
                    continue
                seen_names.add(node.name)
                cols: List[LLDTableColumn] = []
                rels: List[str] = []
                idxs: List[str] = []

                for edge in kg.outgoing_edges(node.id):
                    child = kg.nodes.get(edge.to_id)
                    if not child:
                        continue
                    if child.node_type in (KGNodeType.VARIABLE, KGNodeType.PROPERTY):
                        # Infer primary key from name convention
                        is_pk = child.name.lower() in ("id", f"{node.name.lower()}_id", "pk")
                        is_fk = any(k in child.name.lower() for k in ("_id", "_fk", "foreign"))
                        dtype = child.return_type or _infer_sql_type(child.name)
                        refs = None
                        if is_fk:
                            # Try to get FK target from edge evidence
                            refs = getattr(edge, "evidence", None) or f"{child.name.replace('_id', '')}s.id"
                        cols.append(LLDTableColumn(
                            name=child.name,
                            data_type=dtype,
                            is_primary_key=is_pk,
                            is_foreign_key=is_fk,
                            is_nullable=not is_pk,
                            references=refs,
                        ))
                    elif edge.relation == KGRelationType.REFERENCES:
                        target = kg.nodes.get(edge.to_id)
                        if target:
                            rels.append(f"{node.name}.{edge.from_id} → {target.name}")

                tables.append(LLDDataTypeTable(
                    name=node.name,
                    source_type="SQL Table",
                    file_path=node.file_path or "",
                    columns=cols,
                    relationships=rels[:5],
                    description=node.docstring or f"Database table storing {node.name} records",
                ))

            # ── Source 2: KG Mongo collections ──────────────────────
            for node in kg.nodes_by_type(KGNodeType.MONGO_COLLECTION):
                if node.name in seen_names:
                    continue
                seen_names.add(node.name)
                cols = []
                for edge in kg.outgoing_edges(node.id):
                    child = kg.nodes.get(edge.to_id)
                    if child and child.node_type in (KGNodeType.VARIABLE, KGNodeType.PROPERTY):
                        cols.append(LLDTableColumn(
                            name=child.name,
                            data_type=child.return_type or "Mixed",
                            is_nullable=True,
                        ))
                tables.append(LLDDataTypeTable(
                    name=node.name,
                    source_type="NoSQL Collection",
                    file_path=node.file_path or "",
                    columns=cols[:12],
                    description=node.docstring or f"MongoDB collection for {node.name}",
                ))

            # ── Source 3: KG CLASS nodes that are data models ────────
            for cls in kg.nodes_by_type(KGNodeType.CLASS):
                if cls.name in seen_names: continue

                name_lower = cls.name.lower()
                all_annots = " ".join(cls.annotations or [])
                is_orm = any(a in all_annots for a in ORM_ANNOTATIONS)
                
                has_tablename = False
                for edge in kg.outgoing_edges(cls.id):
                    if edge.relation == KGRelationType.CONTAINS:
                        child = kg.nodes.get(edge.to_id)
                        if child and child.name == "__tablename__":
                            has_tablename = True
                            break

                bases = [kg.nodes.get(e.to_id).name for e in kg.outgoing_edges(cls.id) 
                         if str(e.relation).endswith("EXTENDS") and kg.nodes.get(e.to_id)]
                has_model_base = any("Base" in b or "Model" in b for b in bases)

                is_model_by_name = any(sig in name_lower for sig in DATA_MODEL_SIGNALS)

                if not (is_orm or has_tablename or has_model_base or is_model_by_name):
                    continue

                seen_names.add(cls.name)
                cols = []
                for edge in kg.outgoing_edges(cls.id):
                    child = kg.nodes.get(edge.to_id)
                    if child and child.node_type in (KGNodeType.VARIABLE, KGNodeType.PROPERTY, KGNodeType.ASSIGNMENT):
                        is_pk = child.name.lower() in ("id", "pk", f"{name_lower}_id")
                        cols.append(LLDTableColumn(
                            name=child.name,
                            data_type=child.return_type or _infer_python_type(child.name),
                            is_primary_key=is_pk,
                            is_nullable=not is_pk,
                        ))

                if cols:
                    source = "Pydantic Model" if "BaseModel" in all_annots else \
                             "ORM Model" if is_orm else \
                             "Dataclass" if "dataclass" in all_annots else "Data Class"
                    tables.append(LLDDataTypeTable(
                        name=cls.name,
                        source_type=source,
                        file_path=cls.file_path or "",
                        columns=cols[:12],
                        description=cls.docstring or f"Data model for {cls.name}",
                    ))

        # ── Source 4: IR data_stores fallback ───────────────────────
        if not tables:
            for ds in ir.data_stores:
                if ds.name in seen_names:
                    continue
                seen_names.add(ds.name)
                tables.append(LLDDataTypeTable(
                    name=ds.name,
                    source_type="Data Store",
                    columns=[],
                    description=f"{ds.store_type} store accessed by: {', '.join(ds.accessed_by[:3])}",
                ))

        return tables[:20]

    def _extract_sequence_flows(self, ir, kg) -> List[LLDSequenceFlow]:
        BANNED_TRIGGERS = [".sql", ".csv", ".json", ".xml", ".txt"]
        def is_sql_stub(flow) -> bool:
            trigger = getattr(flow, "trigger", "") or ""
            steps = getattr(flow, "steps", []) or []
            if any(trigger.endswith(ext) for ext in BANNED_TRIGGERS):
                return True
            if len(steps) < 4:
                return True
            if all(s == s.upper() for s in steps if isinstance(s, str)):
                return True
            return False

        # Source 1: real IR flows — filter stubs
        ir_flows = [f for f in getattr(ir, 'request_flows', [])
                    if not is_sql_stub(LLDSequenceFlow(
                        name=f.name, trigger=f.entry_point,
                        steps=f.steps, description=f.description))]
        flows = [LLDSequenceFlow(name=f.name, trigger=f.entry_point,
                                  steps=f.steps, description=f.description)
                 for f in getattr(ir, 'request_flows', [])]
        flows = [f for f in flows if not is_sql_stub(f)]

        # Source 2: KG BFS (no stub filter)
        if not flows and kg:
            flows = self._kg_bfs_flows(ir, kg)

        if not flows and (java_scan := ir.metadata.get('java_scan')):
            for frm, to, rel in java_scan.dependency_chains:
                if rel == "CALLS":
                    flows.append(LLDSequenceFlow(
                        name=f"{frm} Flow",
                        trigger=f"Request to {frm}",
                        steps=[f"Client → {frm}", f"{frm} → {to}", f"{to} → Database", f"Database → {to}", f"{to} → {frm}", f"{frm} → Client"],
                        description=f"Execution flow through {frm} to {to}"
                    ))

        # Source 4: library method flows (no stub filter)
        if not flows:
            flows = self._library_method_flows(ir, kg)

        return flows[:6]



    def _kg_bfs_flows(self, ir, kg) -> List[LLDSequenceFlow]:
        """BFS from API/event/CLI entrypoints through KG call graph."""
        from backend.knowledge_graph.models import KGNodeType, KGRelationType
        flows = []
        STEP_RELATIONS = {
            "CALLS": "calls", "INVOKES": "invokes",
            "QUERIES_TABLE": "SELECT", "WRITES_TABLE": "INSERT/UPDATE",
            "PUBLISHES_TO": "publishes event", "READS_FROM": "read", "WRITES_TO": "write",
        }
        api_eps   = kg.nodes_by_type(KGNodeType.API_ENDPOINT)
        cli_mains = [n for n in kg.nodes_by_type(KGNodeType.FUNCTION)
                     if n.name in ("main", "cli", "run", "entry")]
        entrypoints = (
            [(ep, "API Request", ep.name) for ep in api_eps] +
            [(ep, "CLI",         f"command {ep.name}") for ep in cli_mains]
        )
        for ep, trigger_type, ep_label in entrypoints[:5]:
            steps = [f"Client → {ep.name}: {trigger_type}"]
            visited = {ep.id}
            queue   = [(ep.id, 0)]
            while queue and len(steps) < 12:
                curr_id, depth = queue.pop(0)
                if depth > 4: continue
                curr = kg.nodes.get(curr_id)
                if not curr: continue
                for edge in kg.outgoing_edges(curr_id):
                    rel = str(edge.relation).split(".")[-1]
                    if rel not in STEP_RELATIONS: continue
                    target = kg.nodes.get(edge.to_id)
                    if not target or target.id in visited: continue
                    visited.add(target.id)
                    queue.append((target.id, depth + 1))
                    steps.append(f"{curr.name} → {target.name}: {STEP_RELATIONS[rel]}")
                    is_db = target.node_type in (KGNodeType.SQL_TABLE, KGNodeType.MONGO_COLLECTION)
                    if is_db:
                        steps.append(f"{target.name} → {curr.name}: return rows")
            steps.append(f"{ep.name} → Client: return response")
            if len(steps) > 1:
                flows.append(LLDSequenceFlow(
                    name=f"{trigger_type}: {ep_label}",
                    trigger=trigger_type,
                    steps=steps,
                    description=f"Execution flow for {ep_label}",
                ))
        return flows



    def _library_method_flows(self, ir, kg) -> List[LLDSequenceFlow]:
        """For library repos with no HTTP endpoints — flows from public class methods."""
        from backend.knowledge_graph.models import KGNodeType, KGRelationType
        candidates = []
        if kg:
            for cls in kg.nodes_by_type(KGNodeType.CLASS):
                for edge in kg.outgoing_edges(cls.id):
                    if edge.relation == KGRelationType.CONTAINS:
                        m = kg.nodes.get(edge.to_id)
                        if m and m.node_type in (KGNodeType.METHOD, KGNodeType.FUNCTION) \
                                and not m.name.startswith("_"):
                            candidates.append((cls.name, m.name, m.docstring or "", m.id))
        if not candidates:
            for comp in ir.components:
                for fn in comp.key_functions:
                    if not fn.startswith("_"):
                        for cls in comp.key_classes:
                            candidates.append((cls, fn, "", None))

        INTERESTING = ("validate", "process", "execute", "build", "create",
                       "run", "parse", "check", "verify", "transform", "generate")
        scored = sorted(
            candidates,
            key=lambda c: sum(3 for k in INTERESTING if k in c[1].lower()) + 1,
            reverse=True,
        )[:4]

        exc_classes = [cn for comp in ir.components for cn in comp.key_classes
                       if any(x in cn.lower() for x in ("error", "exception"))]

        flows = []
        for cls_name, method_name, docstring, method_id in scored:
            steps = [f"Caller → {cls_name}: {method_name}(input)"]
            
            # Trace real execution calls if KG is available
            if method_id and kg:
                visited = set()
                queue = [(method_id, cls_name)]
                while queue and len(steps) < 6:
                    curr_id, curr_actor = queue.pop(0)
                    if curr_id in visited: continue
                    visited.add(curr_id)
                    
                    for edge in kg.outgoing_edges(curr_id):
                        if edge.relation in (KGRelationType.CALLS, KGRelationType.CALLS_API):
                            tgt = kg.nodes.get(edge.to_id)
                            if tgt:
                                tgt_actor = "System"
                                for inc_edge in kg.incoming_edges(tgt.id):
                                    if inc_edge.relation == KGRelationType.CONTAINS:
                                        parent = kg.nodes.get(inc_edge.from_id)
                                        if parent and parent.node_type == KGNodeType.CLASS:
                                            tgt_actor = parent.name
                                            break
                                steps.append(f"{curr_actor} → {tgt_actor}: {tgt.name}()")
                                steps.append(f"{tgt_actor} → {curr_actor}: return result")
                                queue.append((tgt.id, tgt_actor))

            # Fallback for empty traces removed as per instruction.
                
            if not any("→ Caller" in s for s in steps):
                steps.append(f"{cls_name} → Caller: return result")
            flows.append(LLDSequenceFlow(
                name=f"{cls_name}.{method_name}()",
                trigger="Direct method call",
                steps=steps,
                description=docstring[:80] if docstring else
                            f"Invocation flow for {cls_name}.{method_name}()",
            ))
        return flows

    def _extract_error_paths(self, ir, kg) -> List[LLDErrorPath]:
        paths = []
        seen  = set()

        # Source 1: IR error_paths (try/except traversal)
        for ep in getattr(ir, "error_paths", []):
            key = (ep.source_function, ep.error_type)
            if key not in seen:
                seen.add(key)
                impact = "System halted" if (ep.error_type and "Error" in ep.error_type) else "Process failed"
                severity = "High" if "Error" in (ep.error_type or "") else "Medium"
                paths.append(LLDErrorPath(
                    source=ep.source_function,
                    error_type=ep.error_type or "Exception",
                    handler=ep.error_handler or "caller",
                    recovery_strategy=ep.recovery_strategy,
                    trigger=f"{ep.source_function} invoked with invalid state",
                    affected_component=ep.source_function.split('.')[0] if '.' in ep.source_function else "Application",
                    impact=impact,
                    severity=severity
                ))

        # Source 2: KG RAISES/CATCHES edges
        if kg:
            for node in kg.nodes.values():
                for edge in kg.outgoing_edges(node.id):
                    rel = str(edge.relation).split(".")[-1]
                    if rel in ("RAISES", "THROWS"):
                        exc = kg.nodes.get(edge.to_id)
                        exc_type = exc.name if exc else "Exception"
                        key = (node.name, exc_type)
                        if key not in seen:
                            seen.add(key)
                            paths.append(LLDErrorPath(source=node.name, error_type=exc_type,
                                handler="caller", recovery_strategy="Propagated to caller",
                                trigger=f"Execution of {node.name}", affected_component=node.name,
                                impact="Caller operation fails", severity="Medium"))
                    elif rel in ("CATCHES", "HANDLES"):
                        exc = kg.nodes.get(edge.to_id)
                        exc_type = exc.name if exc else "Exception"
                        key = (node.name, f"catches:{exc_type}")
                        if key not in seen:
                            seen.add(key)
                            paths.append(LLDErrorPath(source=node.name, error_type=exc_type,
                                handler=node.name, recovery_strategy="Internal handler",
                                trigger=f"Exception {exc_type} caught", affected_component=node.name,
                                impact="Handled internally", severity="Low"))

            # Source 3: Operational Failures mapping
            operational_errors = {
                "Neo4jError": ("Database Connection", "Neo4j connection fails or query times out", "Data Persistence", "Graph updates fail", "Retry with exponential backoff", "High"),
                "OllamaError": ("LLM Service", "Ollama API unreachable or times out", "AI Engine", "Semantic inference fails", "Fallback to stub or retry", "High"),
                "XMLParseError": ("File Parser", "Malformed XML or encoding issue", "AST Builder", "Repository indexing halts", "Skip file and log warning", "Medium"),
                "RepositoryValidationError": ("Source Loader", "Invalid repository structure", "Project Loader", "Pipeline fails to start", "Abort and notify user", "Critical"),
                "FileAccessError": ("I/O System", "Permission denied or file missing", "File System", "Incomplete analysis", "Log error and continue", "Medium")
            }
            
            for cls in kg.nodes_by_type("CLASS"):
                if cls.name in operational_errors:
                    source, trigger, comp, impact, recovery, severity = operational_errors[cls.name]
                    key = (cls.name, "operational")
                    if key not in seen:
                        seen.add(key)
                        paths.append(LLDErrorPath(
                            source=source,
                            error_type=cls.name,
                            handler="Global Error Handler",
                            recovery_strategy=recovery,
                            trigger=trigger,
                            affected_component=comp,
                            impact=impact,
                            severity=severity
                        ))

            # Source 4: Validation function names
            VALIDATE_NAMES = ("validate", "check_", "verify_", "assert_", "ensure_")
            for fn in kg.nodes_by_type("FUNCTION"):
                if any(fn.name.lower().startswith(v) for v in VALIDATE_NAMES):
                    key = (fn.name, "ValidationError")
                    if key not in seen:
                        seen.add(key)
                        paths.append(LLDErrorPath(
                            source=fn.name, error_type="ValidationError",
                            handler=fn.name, recovery_strategy="Early return with error details",
                            trigger="Invalid input parameters",
                            affected_component=fn.name,
                            impact="Validation fails, operation aborted",
                            severity="Medium"
                        ))

        return paths[:20]

    def _extract_data_types(self, ir: SemanticIR, kg: Optional[KnowledgeGraph]) -> Tuple[List[LLDDataType], List[LLDEnumType], List[LLDTypeAlias]]:
        data_types = []
        enum_types = []
        type_aliases = []

        if not kg:
            return data_types, enum_types, type_aliases

        from backend.knowledge_graph.models import KGNodeType, KGRelationType
        
        # 1. Enums
        for node in kg.nodes_by_type(KGNodeType.ENUM):
            members = []
            for edge in kg.outgoing_edges(node.id):
                if edge.relation == KGRelationType.CONTAINS:
                    tgt = kg.nodes.get(edge.to_id)
                    if tgt and tgt.node_type == KGNodeType.VARIABLE:
                        val = str(edge.evidence) if edge.evidence else ""
                        members.append(f"{tgt.name} = {val}" if val else tgt.name)
            enum_types.append(LLDEnumType(
                name=node.name,
                members=members,
                description=node.docstring or "",
                file_path=node.file_path or ""
            ))

        # 2. Type Aliases
        for node in kg.nodes_by_type("TYPE_ALIAS"):
            target_type = "Unknown"
            for edge in kg.outgoing_edges(node.id):
                if edge.relation == "ALIASED_TO":
                    tgt = kg.nodes.get(edge.to_id)
                    if tgt:
                        target_type = tgt.name
                        break
            if target_type == "Unknown" and node.docstring:
                target_type = node.docstring  # Sometimes evidence is stored here
                
            type_aliases.append(LLDTypeAlias(
                name=node.name,
                alias_for=target_type,
                file_path=node.file_path or ""
            ))

        # 3. Data Types (Dataclasses, TypedDicts, Pydantic)
        for node in kg.nodes_by_type("DATA_STRUCTURE"):
            fields = []
            for edge in kg.outgoing_edges(node.id):
                if edge.relation == KGRelationType.CONTAINS:
                    tgt = kg.nodes.get(edge.to_id)
                    if tgt and tgt.node_type == KGNodeType.VARIABLE:
                        type_str = tgt.return_type or "untyped"
                        fields.append(LLDFieldDef(
                            name=tgt.name,
                            type_str=type_str,
                            is_optional="Optional" in type_str or "None" in type_str,
                            description=tgt.docstring or ""
                        ))
            
            kind = "dataclass"
            for base_edge in kg.outgoing_edges(node.id):
                if base_edge.relation == KGRelationType.EXTENDS:
                    base = kg.nodes.get(base_edge.to_id)
                    if base:
                        if "Model" in base.name or "BaseModel" in base.name:
                            kind = "Pydantic"
                        elif "TypedDict" in base.name:
                            kind = "TypedDict"
                        elif "NamedTuple" in base.name:
                            kind = "NamedTuple"

            data_types.append(LLDDataType(
                name=node.name,
                kind=kind,
                fields=fields,
                description=node.docstring or "",
                file_path=node.file_path or ""
            ))

        return data_types, enum_types, type_aliases

    # ══════════════════════════════════════════════════════════
    #  NEW EXTRACTION METHODS
    # ══════════════════════════════════════════════════════════

    def _extract_api_specs(self, ir: SemanticIR, kg: Optional[KnowledgeGraph] = None) -> List[LLDAPISpec]:
        """Build LLDAPISpec from ir.api_endpoints or graph evidence."""
        specs = []
        if ir.api_endpoints:
            for ep in ir.api_endpoints:
                auth = any(kw in (ep.path or "").lower() for kw in ["/auth", "/login", "/token", "/secure"])
                specs.append(LLDAPISpec(
                    path=ep.path or "/unknown",
                    method=ep.method or "GET",
                    service=ep.service or "Unknown",
                    description=getattr(ep, "description", "") or f"{ep.method} {ep.path}",
                    request_body=getattr(ep, "request_body", []) or [],
                    response_body=getattr(ep, "response_body", []) or [],
                    auth_required=auth,
                    error_codes=["400", "404", "500"],
                ))
        elif kg:
            for ep in kg.nodes_by_type(KGNodeType.API_ENDPOINT):
                auth = any(kw in ep.name.lower() for kw in ["/auth", "/login", "/token", "/secure"])
                specs.append(LLDAPISpec(
                    path=ep.name,
                    method="HTTP",
                    service=ep.file_path.split("/")[-1] if ep.file_path else "Unknown",
                    description=ep.docstring or f"Endpoint {ep.name}",
                    request_body=[],
                    response_body=[],
                    auth_required=auth,
                    error_codes=["400", "404", "500"],
                ))
        if not specs and (java_scan := ir.metadata.get('java_scan')):
            for cls in java_scan.classes:
                if cls.stereotype == "Controller":
                    for m in cls.methods:
                        if m.http_method:
                            path = (cls.base_path + m.http_path).replace('//', '/')
                            specs.append(LLDAPISpec(
                                path=path, method=m.http_method, service=cls.name,
                                description=f"Endpoint in {cls.name}", request_body=[], response_body=[], auth_required=False, error_codes=["400", "404", "500"]
                            ))
        return specs

    def _extract_components(self, ir: SemanticIR, kg: Optional[KnowledgeGraph] = None) -> List[LLDComponent]:
        """Map SemanticIR components to LLDComponent with layer classification."""
        LAYER_RULES = {
            "controller": "Presentation", "router": "Presentation", "view": "Presentation",
            "endpoint": "Presentation", "handler": "Presentation",
            "service": "Application",    "manager": "Application", "orchestrator": "Application",
            "repository": "Domain",      "model": "Domain",        "entity": "Domain",
            "schema": "Domain",          "domain": "Domain",
            "database": "Infrastructure","config": "Infrastructure","cache": "Infrastructure",
            "client": "Infrastructure",  "adapter": "Infrastructure",
        }
        TYPE_RULES = {
            "controller": "Controller",  "router": "Controller",
            "service": "Service",        "manager": "Service",
            "repository": "Repository",  "store": "Repository",
            "model": "Model",            "schema": "Model", "entity": "Model",
            "client": "Client",
        }

        components = []
        for comp in ir.components:
            name_lower = comp.name.lower()
            layer = "Application"
            comp_type = "Service"
            for kw, lyr in LAYER_RULES.items():
                if kw in name_lower:
                    layer = lyr
                    break
            for kw, typ in TYPE_RULES.items():
                if kw in name_lower:
                    comp_type = typ
                    break

            # Collect dependencies from relationships
            deps = [
                r.target for r in ir.relationships
                if r.source == comp.name
                and r.relationship_type in ("DEPENDS_ON", "CALLS", "IMPORTS", "INSTANTIATES")
            ]

            
            tech_evidence = []
            if kg:
                for node in kg.nodes.values():
                    if "test" in node.file_path.lower() or "mock" in node.file_path.lower(): continue
                    if name_lower in node.name.lower() or name_lower in node.file_path.lower():
                        for edge in kg.outgoing_edges(node.id):
                            if "IMPORT" in str(edge.relation):
                                target = kg.nodes.get(edge.to_id)
                                if target and any(k in target.name.lower() for k in ["kafka", "celery", "fastapi", "anthropic", "openai", "sqlalchemy", "neo4j", "pydantic", "jinja", "react"]):
                                    tech_evidence.append(f"{target.name} ({node.file_path})")
            tech_evidence = list(set(tech_evidence))
            tech_list = list(set(e.split(" ")[0] for e in tech_evidence))
            technology = ", ".join(tech_list) if tech_list else ""
            
            purpose = comp.description or ""
            consumes = [] if "repository" not in name_lower else ["Database queries"]
            produces = [] if "repository" not in name_lower else ["Data objects"]
            artifacts = []
            
            # Use IR to get real consumes/produces
            for cls in getattr(ir, 'classes', []):
                if name_lower in cls.name.lower():
                    if getattr(cls, 'receives', None): consumes = [cls.receives]
                    if getattr(cls, 'returns', None): produces = [cls.returns]
            
            components.append(LLDComponent(
                name=comp.name,
                component_type=comp_type,
                layer=layer,
                purpose=purpose,
                consumes=consumes,
                produces=produces,
                artifacts=artifacts,
                depends_on=list(set(deps))[:6],
                technology=technology,
                tech_evidence=tech_evidence,
                business_domain=comp.business_domain,
            ))
        return components

    def _extract_modules(self, ir: SemanticIR, components: List[LLDComponent]) -> List[LLDModule]:
        modules = []
        mod_dict = {}
        for c in components:
            pkg = c.name.lower().replace(" ", "_")
            primary_class = next((cls for cls in getattr(ir, 'classes', []) if cls.name.lower() in c.name.lower() or c.name.lower() in cls.name.lower()), None)
            if primary_class and getattr(primary_class, 'file_path', None):
                pkg = primary_class.file_path.split("/")[0]
            
            if pkg not in mod_dict: mod_dict[pkg] = []
            mod_dict[pkg].append(c.name)
            
        for pkg, classes in mod_dict.items():
            mod_name = pkg.replace("_", " ").title()
            
            tech_evidence = []
            for c in components:
                if c.name in classes and hasattr(c, 'tech_evidence'):
                    tech_evidence.extend(c.tech_evidence)
            tech_evidence = list(set(tech_evidence))
            modules.append(LLDModule(name=mod_name, package_path=pkg, responsibility=f"Handles operations for {mod_name}", classes_contained=classes, tech_evidence=tech_evidence))
        return modules

    def _extract_dependencies(self, ir: SemanticIR, kg: Optional[KnowledgeGraph]) -> List[LLDDependency]:
        """Extract directed dependency edges between components."""
        from collections import defaultdict
        
        # Group by (source, target)
        edge_groups = defaultdict(list)
        for rel in ir.relationships:
            if rel.source != rel.target:
                edge_groups[(rel.source, rel.target)].append(rel.relationship_type or "DEPENDS_ON")
                
        deps = []
        for (source, target), types in edge_groups.items():
            count = len(types)
            if count > 3:
                strength = "High"
            elif count > 1:
                strength = "Medium"
            else:
                strength = "Low"
                
            # Determine dependency type
            all_types = " ".join(types).upper()
            if "API" in all_types or "REST" in all_types:
                dep_type = "API Dependency"
                purpose = f"Consumes API from {target}"
            elif "DATA" in all_types or "DB" in all_types or "STORE" in target.upper() or "DATABASE" in target.upper():
                dep_type = "Data Dependency"
                purpose = f"Persists or retrieves data via {target}"
            elif "SERVICE" in target.upper() or "MANAGER" in target.upper() or "CALLS" in all_types:
                dep_type = "Service Dependency"
                purpose = f"Invokes domain logic in {target}"
            elif "INFRA" in target.upper() or "CLIENT" in target.upper():
                dep_type = "Infrastructure Dependency"
                purpose = f"Utilizes infrastructure via {target}"
            else:
                dep_type = "Runtime Dependency"
                purpose = f"Relies on {target} at runtime"
                
            deps.append(LLDDependency(
                source=source,
                target=target,
                dependency_type=dep_type,
                is_circular=False,
                strength=strength,
                purpose=purpose
            ))
            
        # Simple circular check: A→B and B→A
        edge_set = {(d.source, d.target) for d in deps}
        for dep in deps:
            if (dep.target, dep.source) in edge_set:
                dep.is_circular = True
                
        # Limit to top strongest dependencies per component
        # We'll just sort by strength (High > Medium > Low) and limit to top 4 per component
        strength_val = {"High": 3, "Medium": 2, "Low": 1}
        deps.sort(key=lambda d: strength_val.get(d.strength, 0), reverse=True)
        
        filtered_deps = []
        comp_counts = defaultdict(int)
        for d in deps:
            if comp_counts[d.source] < 4:
                comp_counts[d.source] += 1
                filtered_deps.append(d)
                
        return filtered_deps

    _EXTERNAL_PATTERNS = {
        "stripe":    ("Stripe Payment Gateway",   "REST API",      "Outbound", "API Key",   "JSON"),
        "paypal":    ("PayPal Gateway",           "REST API",      "Outbound", "OAuth2",    "JSON"),
        "twilio":    ("Twilio SMS/Voice",         "REST API",      "Outbound", "API Key",   "JSON"),
        "sendgrid":  ("SendGrid Email",           "REST API",      "Outbound", "API Key",   "JSON"),
        "redis":     ("Redis Cache",              "Database",      "Bidirectional","","Binary"),
        "celery":    ("Celery Task Queue",        "Message Queue", "Outbound", "",          ""),
        "kafka":     ("Apache Kafka",             "Message Queue", "Bidirectional","",      ""),
        "rabbitmq":  ("RabbitMQ",                "Message Queue", "Bidirectional","",      ""),
        "s3":        ("AWS S3 Object Storage",    "REST API",      "Bidirectional","API Key","Binary"),
        "elasticsearch":("Elasticsearch",         "REST API",      "Bidirectional","","JSON"),
        "neo4j":     ("Neo4j Graph Database",    "Database",      "Bidirectional","",""),
        "mongodb":   ("MongoDB",                 "Database",      "Bidirectional","","BSON"),
        "openai":    ("OpenAI API",              "REST API",      "Outbound",  "API Key",  "JSON"),
        "ollama":    ("Ollama LLM Runtime",      "REST API",      "Outbound",  "",         "JSON"),
    }

    def _extract_external_integrations(self, ir: SemanticIR) -> List[LLDExternalIntegration]:
        integrations = []
        all_signals = (
            " ".join(ir.frameworks).lower() + " "
            + " ".join(ir.databases).lower() + " "
            + " ".join(getattr(ir, "ai_ml_tools", []) or []).lower() + " "
            + " ".join(getattr(ir, "infrastructure", []) or []).lower()
        )
        for keyword, (name, itype, direction, auth, fmt) in self._EXTERNAL_PATTERNS.items():
            if keyword in all_signals:
                integrations.append(LLDExternalIntegration(
                    name=name,
                    integration_type=itype,
                    direction=direction,
                    endpoint_or_dsn=f"{keyword}://...",
                    used_by_components=[],
                    auth_mechanism=auth,
                    data_format=fmt,
                ))
        return integrations

    def _extract_deployment_units(self, ir: SemanticIR) -> List[LLDDeploymentUnit]:
        """
        Infer deployment units from framework signals and component structure.
        """
        units = []
        frameworks_lower = [f.lower() for f in ir.frameworks]

        # Web server unit
        web_frameworks = {"fastapi", "flask", "django", "express", "spring", "rails"}
        for fw in web_frameworks:
            if fw in frameworks_lower:
                units.append(LLDDeploymentUnit(
                    name=f"{fw.capitalize()} Application",
                    unit_type="Process",
                    entry_point="main.py" if fw in ("fastapi", "flask") else "manage.py",
                    hosts_components=[c.name for c in ir.components if c.component_type in ("service", "controller")][:5],
                    runtime=f"Python {ir.metadata.get('python_version', '3.11')}" if ir.languages and "python" in [l.lower() for l in ir.languages] else (ir.languages[0] if ir.languages else "Python"),
                    exposed_ports=[8000] if fw in ("fastapi", "uvicorn") else [5000] if fw == "flask" else [8080],
                    environment_variables=["DATABASE_URL", "SECRET_KEY", "LOG_LEVEL"],
                ))
                break

        # Database unit
        for db in ir.databases[:2]:
            units.append(LLDDeploymentUnit(
                name=f"{db} Database",
                unit_type="Process",
                entry_point="",
                hosts_components=[],
                runtime=db,
                exposed_ports=[5432] if "postgres" in db.lower() else [3306] if "mysql" in db.lower() else [27017] if "mongo" in db.lower() else [],
                environment_variables=["DATABASE_URL", "DB_PASSWORD"],
            ))

        if not units:
            # Fallback: generic process
            units.append(LLDDeploymentUnit(
                name="Application Process",
                unit_type="Process",
                entry_point="main.py",
                hosts_components=[c.name for c in ir.components[:4]],
                runtime=ir.languages[0] if ir.languages else "Python",
            ))
        return units


    def _extract_security_design(self, ir, kg) -> Optional[LLDSecurityDesign]:
        SECURITY_LIBRARIES = {"bcrypt", "passlib", "jwt", "oauth", "cryptography", "hashlib", "pyjwt", "authlib"}
        has_security_lib = False
        
        if kg:
            # Check for security library presence in imports or module names
            for node in kg.nodes.values():
                if any(sec_lib in node.name.lower() for sec_lib in SECURITY_LIBRARIES):
                    has_security_lib = True
                    break
        
        if not has_security_lib:
            return LLDSecurityDesign(
                mechanisms=[],
                description="No security mechanisms detected.",
                detected_evidence=[]
            )

        BUILTIN_EXCLUSIONS = {
            "__hash__", "__eq__", "__setattr__", "__getattr__", "__delattr__",
            "hashlib", "hash_table", "hashtable", "hash_map", "auth_tag",
        }
        mechanisms: Dict[str, List[str]] = {}
        if kg:
            for node in kg.nodes.values():
                name = node.name or ""
                name_lower = name.lower()
                if name in BUILTIN_EXCLUSIONS: continue
                if name.startswith("__") and name.endswith("__"): continue
                if "[" in name or "(" in name: continue
                if node.node_type not in (KGNodeType.CLASS, KGNodeType.FUNCTION,
                                           KGNodeType.METHOD, KGNodeType.VARIABLE): continue

                if "jwt" in name_lower and len(name) > 3:
                    mechanisms.setdefault("Token-based Authentication (JWT)", []).append(name)
                elif "oauth" in name_lower and len(name) > 5:
                    mechanisms.setdefault("OAuth2 Authorization", []).append(name)
                elif ("password" in name_lower and "hash" in name_lower) or \
                     any(x in name_lower for x in ("bcrypt", "argon2", "pbkdf2", "scrypt", "hmac")):
                    mechanisms.setdefault("Password Hashing", []).append(name)
                elif name_lower in ("authenticate", "authorize", "login_user", "logout_user",
                                    "check_permissions", "require_auth", "is_authenticated", "verify_token"):
                    mechanisms.setdefault("Authentication/Authorization Service", []).append(name)
                elif "encrypt" in name_lower and len(name) > 7 and "crypto" in name_lower:
                    mechanisms.setdefault("Encryption", []).append(name)
                elif any(x in name_lower for x in ("ssl_context", "tls_context", "x509")):
                    mechanisms.setdefault("TLS/SSL Transport Security", []).append(name)
                elif any(x in name_lower for x in ("rbac", "role_based", "access_control")):
                    mechanisms.setdefault("Role-based Access Control (RBAC)", []).append(name)
                elif any(x in name_lower for x in ("rate_limit", "throttle_request")):
                    mechanisms.setdefault("Rate Limiting / Throttling", []).append(name)

        if not mechanisms:
            return None

        evidence = [e for evs in mechanisms.values() for e in evs[:3]]
        return LLDSecurityDesign(
            mechanisms=list(mechanisms.keys()),
            description="Security mechanisms detected from structural code analysis.",
            detected_evidence=evidence[:10],
        )

    def _extract_configuration_design(self, ir: SemanticIR, kg: Optional[KnowledgeGraph]) -> Optional[LLDConfigDesign]:
        env_vars = set()
        if kg:
            for node in kg.nodes.values():
                if node.node_type == KGNodeType.VARIABLE or node.node_type == KGNodeType.ASSIGNMENT:
                    # Very simple heuristic: uppercase variables are often env vars
                    if node.name.isupper() and len(node.name) > 3:
                        env_vars.add(node.name)
                if node.node_type == "FUNCTION_CALL" and "getenv" in node.name.lower():
                    env_vars.add("os.getenv(...)")
                    
        if env_vars:
            return LLDConfigDesign(
                environment_variables=list(env_vars)[:15],
                config_files=[".env", "config.py", "settings.py"] if "settings" in " ".join(env_vars).lower() else [],
                description="Configuration mechanisms detected in codebase."
            )
        return None

    def _build_system_overview(self, ir: SemanticIR, model: LLDModel) -> str:
        lang_str = ", ".join(ir.languages[:3]) if ir.languages else "Python"
        fw_str = ", ".join(ir.frameworks[:3]) if ir.frameworks else "standard libraries"
        pattern = ir.architecture_pattern or "Layered"
        
        n_comp = len(ir.components)
        n_api = len(ir.api_endpoints)
        n_db = len(ir.databases)
        n_cli = len([c for c in ir.components if "CLI" in c.description or "main" in c.key_functions])

        repo_type = model.repository_type.lower()
        if "web" in repo_type or "api" in repo_type or n_api > 0:
            type_desc = f"a Web Service / API providing {n_api} endpoint(s)"
        elif "cli" in repo_type or n_cli > 0:
            type_desc = f"a Command-Line Tool / Script collection"
        elif "library" in repo_type or "package" in repo_type:
            type_desc = f"a Software Library / Package"
        else:
            type_desc = f"an Application System"

        return (
            f"This system is {type_desc} implemented in {lang_str} using {fw_str}. "
            f"It follows a {pattern} architectural pattern with {n_comp} core component(s) "
            f"and {n_db} data store(s). "
            f"The object model consists of {len(model.classes)} class(es) and "
            f"{len(model.interfaces)} interface(s) organized into {len(model.modules)} module(s). "
            f"External interactions are handled through "
            f"{len(model.external_integrations) or 'standard'} integration point(s)."
        )

    def _infer_method_from_kg(self, kg, ep_node) -> str:
        """Try to get HTTP method from KG node annotations."""
        for annot in (ep_node.annotations or []):
            for method in ("GET", "POST", "PUT", "DELETE", "PATCH"):
                if method in annot.upper():
                    return method
        return ep_node.name.split(" ")[0] if " " in ep_node.name else "HTTP"


    def _extract_circular_dependencies(self, ir, kg, deps):
        from collections import defaultdict
        adj = defaultdict(list)
        for dep in deps:
            adj[dep.source].append(dep.target)
            
        cycles = []
        visited = set()
        path = []
        
        def dfs(node):
            if node in path:
                idx = path.index(node)
                cycle = path[idx:] + [node]
                min_idx = cycle[:-1].index(min(cycle[:-1]))
                can_cycle = cycle[min_idx:-1] + cycle[:min_idx] + [cycle[min_idx]]
                if can_cycle not in cycles:
                    cycles.append(can_cycle)
                return
            if node in visited: return
            visited.add(node)
            path.append(node)
            for neighbor in adj[node]: dfs(neighbor)
            path.pop()
            
        for node in list(adj.keys()):
            dfs(node)
            
        circulars = []
        for cycle in cycles[:5]:
            root_cause = f"Direct architectural entanglement where {cycle[-2]} invokes logic belonging to {cycle[0]}."
            affected_files = []
            affected_classes = []
            if kg:
                for n_name in cycle:
                    for node in kg.nodes.values():
                        if n_name.lower() in node.name.lower():
                            affected_files.append(node.file_path)
                            if node.node_type == "CLASS": affected_classes.append(node.name)
            
            circulars.append(LLDCircularDependency(
                cycle_path=cycle,
                root_cause=root_cause,
                affected_files=list(set(affected_files)),
                affected_classes=list(set(affected_classes)),
                recommended_refactor=f"Extract the shared interface or data model into a common library, or inject {cycle[-2]}'s dependencies via an interface to decouple it from {cycle[0]}."
            ))
        return circulars

    def _extract_entrypoints(self, ir, kg):
        entry_points = []
        if kg:
            api_eps = kg.nodes_by_type("API_ENDPOINT")
            for ep in api_eps:
                entry_points.append(LLDEntryPoint(name=ep.name, evidence=[f"API Request to {ep.name} in {ep.file_path}"]))
            
            # Strict CLI detection: require actual __main__ conditions or explicit main entrypoints
            for cond in kg.nodes_by_type("CONDITION"):
                if cond.name and "__name__" in cond.name and "__main__" in cond.name:
                    entry_points.append(LLDEntryPoint(name="Python Main", evidence=[f"if __name__ == '__main__' in {cond.file_path}"]))
        return entry_points

def _infer_sql_type(field_name: str) -> str:
    """Guess SQL type from field name convention."""
    name = field_name.lower()
    if any(k in name for k in ("_id", "id")): return "INTEGER"
    if any(k in name for k in ("_at", "date", "time", "created", "updated", "deleted")): return "TIMESTAMP"
    if any(k in name for k in ("is_", "has_", "enabled", "active", "flag")): return "BOOLEAN"
    if any(k in name for k in ("price", "amount", "cost", "balance", "rate")): return "DECIMAL(10,2)"
    if any(k in name for k in ("count", "qty", "quantity", "num", "age", "score")): return "INTEGER"
    if any(k in name for k in ("email", "url", "path", "name", "title", "desc")): return "VARCHAR(255)"
    if any(k in name for k in ("body", "content", "text", "description", "notes")): return "TEXT"
    return "VARCHAR(255)"

def _infer_python_type(field_name: str) -> str:
    """Guess Python type from field name convention."""
    name = field_name.lower()
    if any(k in name for k in ("_id", "count", "num", "qty", "age")): return "int"
    if any(k in name for k in ("price", "rate", "amount", "score")): return "float"
    if any(k in name for k in ("is_", "has_", "enabled", "active")): return "bool"
    if any(k in name for k in ("_at", "date", "time", "created", "updated")): return "datetime"
    if any(k in name for k in ("items", "tags", "list", "roles")): return "List"
    return "str"


