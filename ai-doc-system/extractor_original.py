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
)

def _infer_fields_from_class(cls_name: str, comp) -> List[str]:
    """Infer likely fields from class name patterns when KG unavailable."""
    name_lower = cls_name.lower()

    if any(x in name_lower for x in ("error", "exception", "warning")):
        return ["message: str", "errors: List[str]", "key: Optional[str]"]
    elif any(x in name_lower for x in ("model", "schema", "entity", "record", "dto")):
        return ["id: int", "created_at: datetime", "updated_at: Optional[datetime]"]
    elif any(x in name_lower for x in ("service", "manager", "handler", "processor")):
        return ["_logger: Logger", "_config: dict"]
    elif any(x in name_lower for x in ("repository", "store", "repo", "dao")):
        return ["_session: Session", "_model: Type"]
    elif any(x in name_lower for x in ("validator", "rule", "schema", "optional", "literal", "const")):
        return ["_schema: Any", "_error: Optional[str]"]
    elif any(x in name_lower for x in ("config", "setting", "option")):
        return ["_values: dict"]
    return []

class ObjectModelExtractor:
    """
    Extracts an Object Model (LLD Model) from the Semantic IR and Knowledge Graph.
    Uses precise AST traversal on the KG for classes, methods, and relationships.
    """

    def extract(self, ir: SemanticIR, kg: Optional[KnowledgeGraph] = None) -> LLDModel:
        model = LLDModel(
            repository_type=ir.repository_type,
            metadata=ir.metadata
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
        model.components = self._extract_components(ir)
        model.modules = self._extract_modules(ir, model.components)
        model.dependencies = self._extract_dependencies(ir, kg)
        model.external_integrations = self._extract_external_integrations(ir)
        model.deployment_units = self._extract_deployment_units(ir)
        model.system_overview = self._build_system_overview(ir, model)

        return model

    def _extract_classes_and_interfaces(self, ir: SemanticIR, kg: Optional[KnowledgeGraph]) -> Tuple[List[LLDClass], List[LLDInterface]]:
        classes = []
        interfaces = []
        
        if kg:
            # Traversal using KnowledgeGraph for precise AST relationships
            kg_interfaces = kg.nodes_by_type(KGNodeType.INTERFACE)
            for iface in kg_interfaces:
                methods = []
                for edge in kg.outgoing_edges(iface.id):
                    if edge.relation == KGRelationType.CONTAINS:
                        method_node = kg.nodes.get(edge.to_id)
                        if method_node and method_node.node_type in (KGNodeType.METHOD, KGNodeType.FUNCTION):
                            methods.append(LLDMethod(
                                name=method_node.name,
                                signature=f"{method_node.name}({', '.join(method_node.params)}) -> {method_node.return_type or 'Any'}",
                                description=method_node.docstring,
                                parameters=method_node.params,
                                return_type=method_node.return_type
                            ))
                interfaces.append(LLDInterface(
                    name=iface.name,
                    file_path=iface.file_path,
                    description=iface.docstring,
                    methods=methods
                ))

            kg_classes = kg.nodes_by_type(KGNodeType.CLASS)
            for cls in kg_classes:
                methods = []
                constructors = []
                inherits_from = []
                implements = []
                dependencies = []
                fields = []
                composition = []
                aggregation = []
                
                # Analyze edges connected to this class
                for edge in kg.outgoing_edges(cls.id):
                    if edge.relation == KGRelationType.CONTAINS:
                        child = kg.nodes.get(edge.to_id)
                        if child:
                            if child.node_type == KGNodeType.CONSTRUCTOR:
                                constructors.append(LLDMethod(
                                    name=child.name,
                                    signature=f"{child.name}({', '.join(child.params)})",
                                    description=child.docstring,
                                    parameters=child.params
                                ))
                                for p in child.params:
                                    if ":" in p:
                                        p_type = p.split(":", 1)[1].strip().replace("Optional[", "").replace("List[", "").replace("]", "")
                                        if p_type and p_type not in ("str", "int", "float", "bool", "dict", "list", "set", "Any", "None") and p_type != cls.name:
                                            if p_type not in dependencies: dependencies.append(p_type)
                                            if p_type not in aggregation: aggregation.append(p_type)
                            elif child.node_type in (KGNodeType.METHOD, KGNodeType.FUNCTION):
                                methods.append(LLDMethod(
                                    name=child.name,
                                    signature=f"{child.name}({', '.join(child.params)}) -> {child.return_type or 'Any'}",
                                    description=child.docstring,
                                    parameters=child.params,
                                    return_type=child.return_type
                                ))
                                for p in child.params:
                                    if ":" in p:
                                        p_type = p.split(":", 1)[1].strip().replace("Optional[", "").replace("List[", "").replace("]", "")
                                        if p_type and p_type not in ("str", "int", "float", "bool", "dict", "list", "set", "Any", "None") and p_type != cls.name:
                                            if p_type not in dependencies: dependencies.append(p_type)
                                # Check for dependencies inside methods
                                for child_edge in kg.outgoing_edges(child.id):
                                    if child_edge.relation in (KGRelationType.CALLS, KGRelationType.INSTANTIATES, KGRelationType.REFERENCES):
                                        tgt = kg.nodes.get(child_edge.to_id)
                                        if tgt:
                                            if tgt.node_type == KGNodeType.CLASS:
                                                if tgt.name not in dependencies: dependencies.append(tgt.name)
                                            else:
                                                for inc in kg.incoming_edges(tgt.id):
                                                    if inc.relation == KGRelationType.CONTAINS:
                                                        ptgt = kg.nodes.get(inc.from_id)
                                                        if ptgt and ptgt.node_type == KGNodeType.CLASS and ptgt.name != cls.name:
                                                            if ptgt.name not in dependencies: dependencies.append(ptgt.name)
                                                            
                            elif child.node_type in (KGNodeType.VARIABLE, KGNodeType.PROPERTY, KGNodeType.ASSIGNMENT):
                                fields.append(f"{child.name}: {child.return_type or 'Any'}")
                                if child.return_type and child.return_type not in ("str", "int", "float", "bool", "dict", "list", "set", "Any", "None"):
                                    c_type = child.return_type.replace("Optional[", "").replace("List[", "").replace("]", "").strip()
                                    if c_type and c_type != cls.name and c_type not in composition:
                                        composition.append(c_type)
                    
                    elif edge.relation == KGRelationType.EXTENDS:
                        target = kg.nodes.get(edge.to_id)
                        if target:
                            inherits_from.append(target.name)
                            
                    elif edge.relation == KGRelationType.IMPLEMENTS:
                        target = kg.nodes.get(edge.to_id)
                        if target:
                            implements.append(target.name)
                            
                    elif edge.relation in (KGRelationType.DEPENDS_ON, KGRelationType.REFERENCES, KGRelationType.INSTANTIATES):
                        target = kg.nodes.get(edge.to_id)
                        if target and target.node_type in (KGNodeType.CLASS, KGNodeType.INTERFACE):
                            dep_name = target.name
                            if dep_name not in dependencies:
                                dependencies.append(dep_name)
                                # Simple heuristic for comp/agg: if it instantiates, likely composition
                                if edge.relation == KGRelationType.INSTANTIATES:
                                    if dep_name not in composition:
                                        composition.append(dep_name)
                                else:
                                    if dep_name not in aggregation:
                                        aggregation.append(dep_name)

                classes.append(LLDClass(
                    name=cls.name,
                    file_path=cls.file_path,
                    description=cls.docstring,
                    inherits_from=inherits_from,
                    implements=implements,
                    constructors=constructors,
                    methods=methods,
                    fields=fields,
                    composition=composition,
                    aggregation=aggregation,
                    dependencies=dependencies
                ))
                
        else:
            # ── Fallback: extract full class detail from SemanticIR ────────────
            for comp in ir.components:
                for cls_name in comp.key_classes:
                    is_interface = (
                        "Interface" in cls_name
                        or (cls_name.startswith("I") and len(cls_name) > 1 and cls_name[1].isupper())
                        or cls_name.startswith("Abstract")
                        or cls_name.startswith("Base")
                    )

                    # Build rich methods from key_functions — not just 2 stubs
                    methods = []
                    for fn_name in comp.key_functions:
                        if fn_name.startswith("__") and fn_name != "__init__":
                            continue
                        display_name = "constructor" if fn_name == "__init__" else fn_name
                        methods.append(LLDMethod(
                            name=display_name,
                            signature=f"{display_name}(...)",
                            description=None,
                            parameters=[],
                            return_type=None,
                        ))

                    fields = _infer_fields_from_class(cls_name, comp)

                    inherits_from = []
                    if any(x in cls_name for x in ("Error", "Exception", "Warning")):
                        inherits_from = ["Exception"]
                    elif cls_name.startswith("Abstract") or cls_name.startswith("Base"):
                        inherits_from = ["ABC"]

                    if is_interface:
                        interfaces.append(LLDInterface(
                            name=cls_name,
                            file_path=comp.file_path or f"src/{comp.name.replace('.', '/')}.py",
                            description=comp.description or f"Interface defined in {comp.name}",
                            methods=methods,
                        ))
                    else:
                        classes.append(LLDClass(
                            name=cls_name,
                            file_path=comp.file_path or f"src/{comp.name.replace('.', '/')}.py",
                            description=comp.description,
                            inherits_from=inherits_from,
                            methods=methods,
                            fields=fields,
                            dependencies=comp.dependencies[:6],
                        ))
                        
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

    def _extract_database_objects(self, ir: SemanticIR, kg: Optional[KnowledgeGraph]) -> List[LLDDatabaseObject]:
        objects = []
        # First check KG for ORM classes (which are SQL_TABLE or CLASS with __tablename__)
        if kg:
            for cls in kg.nodes_by_type(KGNodeType.CLASS):
                is_orm = False
                fields = []
                for edge in kg.outgoing_edges(cls.id):
                    if edge.relation == KGRelationType.CONTAINS:
                        child = kg.nodes.get(edge.to_id)
                        if child and child.node_type in (KGNodeType.ASSIGNMENT, KGNodeType.VARIABLE, KGNodeType.PROPERTY):
                            if child.name == "__tablename__":
                                is_orm = True
                            elif child.name != "id":
                                fields.append(child.name)
                
                if is_orm or "Model" in cls.name or "Entity" in cls.name:
                    objects.append(LLDDatabaseObject(
                        name=cls.name,
                        type="Relational Table" if is_orm else "Document / Entity",
                        fields=fields[:10],
                        relationships=[]
                    ))
        if not objects:
            for ds in ir.data_stores:
                objects.append(LLDDatabaseObject(
                    name=ds.name,
                    type=ds.store_type,
                    fields=ds.operations,
                    relationships=[]
                ))
        return objects

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

    def _extract_sequence_flows(
        self, ir: SemanticIR, kg: Optional[KnowledgeGraph]
    ) -> List[LLDSequenceFlow]:
        """
        Generate execution sequence flows for ANY repo type:
        web API, library, CLI, data pipeline, utility package.
        """
        flows = []

        # Source 1: Real request flows from IR
        for rf in getattr(ir, 'request_flows', []):
            flows.append(LLDSequenceFlow(
                name=rf.name,
                trigger=rf.entry_point,
                steps=rf.steps,
                description=rf.description,
            ))

        # Source 2: KG graph traversal (BFS from entrypoints)
        if not flows and kg:
            flows = self._kg_bfs_flows(ir, kg)

        # Source 3: Web API endpoint flows
        if not flows and ir.api_endpoints:
            flows = self._api_endpoint_flows(ir)

        # Source 4: Library / utility flows (public class methods)
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

    def _api_endpoint_flows(self, ir) -> List[LLDSequenceFlow]:
        """One sequence flow per API endpoint."""
        HTTP_STEPS = {
            "POST":   ["Validate request body", "Apply business rules",
                       "Persist to database", "Return 201 Created"],
            "GET":    ["Parse query parameters", "Query database",
                       "Serialize response", "Return 200 OK"],
            "PUT":    ["Validate request body", "Find existing record",
                       "Update record", "Return 200 OK"],
            "DELETE": ["Verify authorization", "Delete record", "Return 204 No Content"],
            "PATCH":  ["Validate partial body", "Apply partial update", "Return 200 OK"],
        }
        flows = []
        for ep in ir.api_endpoints[:5]:
            service     = getattr(ep, "service", "Service") or "Service"
            path_parts  = [p for p in (ep.path or "").split("/") if p and not p.startswith("{")]
            steps       = [f"Client → {service}: {ep.method} {ep.path}"]
            steps      += [f"{service}: {s}" for s in HTTP_STEPS.get(ep.method, ["Process request"])]
            steps.append(f"{service} → Client: response")
            flows.append(LLDSequenceFlow(
                name=f"{ep.method} {ep.path}",
                trigger=f"HTTP {ep.method} to {ep.path}",
                steps=steps,
                description=f"{ep.method} endpoint via {service}",
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
                                queue.append((tgt.id, tgt_actor))

            # Fallback for empty traces removed as per instruction.
                
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
                paths.append(LLDErrorPath(
                    source=ep.source_function,
                    error_type=ep.error_type or "Exception",
                    handler=ep.error_handler or "caller",
                    recovery_strategy=ep.recovery_strategy,
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
                                handler="caller", recovery_strategy="Propagated to caller"))
                    elif rel in ("CATCHES", "HANDLES"):
                        exc = kg.nodes.get(edge.to_id)
                        exc_type = exc.name if exc else "Exception"
                        key = (node.name, f"catches:{exc_type}")
                        if key not in seen:
                            seen.add(key)
                            paths.append(LLDErrorPath(source=node.name, error_type=exc_type,
                                handler=node.name, recovery_strategy="Internal handler"))

            # Source 3: Exception CLASS definitions
            for cls in kg.nodes_by_type("CLASS"):
                if any(x in cls.name for x in ("Error", "Exception", "Warning", "Fault")):
                    parent_name = "Exception"
                    for edge in kg.outgoing_edges(cls.id):
                        if str(edge.relation).endswith("EXTENDS"):
                            parent = kg.nodes.get(edge.to_id)
                            if parent:
                                parent_name = parent.name
                            break
                    key = (cls.name, "definition")
                    if key not in seen:
                        seen.add(key)
                        paths.append(LLDErrorPath(
                            source="(raised by system)",
                            error_type=cls.name,
                            handler="catch block",
                            recovery_strategy=cls.docstring[:80] if cls.docstring
                                              else f"Custom exception extending {parent_name}",
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
                        type_str = tgt.return_type or "Any"
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
        return specs

    def _extract_components(self, ir: SemanticIR) -> List[LLDComponent]:
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

            components.append(LLDComponent(
                name=comp.name,
                component_type=comp_type,
                layer=layer,
                responsibility=comp.description or f"{comp_type} component",
                depends_on=list(set(deps))[:6],
                technology=", ".join(ir.frameworks[:2]) if ir.frameworks else "",
            ))
        return components

    def _extract_modules(self, ir: SemanticIR, components: List[LLDComponent]) -> List[LLDModule]:
        """
        Group components into modules by service or directory.
        Each module = one architectural service or package.
        """
        groups: dict = defaultdict(list)

        for comp in ir.components:
            # Try to derive module from component description or name
            svc = getattr(comp, "service_boundary", None) or comp.name.split("Service")[0].strip()
            if not svc:
                svc = "Core"
            groups[svc].append(comp)

        modules = []
        for service_name, comps in groups.items():
            comp_names = [c.name for c in comps]
            # Find common package path
            import os as _os
            comp = comps[0] if comps else None
            if comp:
                real_path = getattr(comp, 'file_path', '') or ''
                if real_path and 'component://' not in real_path:
                    package_path = _os.path.dirname(real_path) + '/' if real_path else ''
                else:
                    # Derive from component name
                    package_path = comp.name.replace('.', '/') + '/'
                    for ir_comp in ir.components:
                        fp = getattr(ir_comp, 'file_path', '')
                        if ir_comp.name == comp.name and fp and 'component://' not in fp:
                            package_path = _os.path.dirname(fp) + '/'
                            break
            else:
                package_path = ""
            
            # Find best description
            descriptions = [c.description for c in comps if c.description]
            responsibility = descriptions[0] if descriptions else f"Manages {service_name} operations and business logic."

            # Find APIs belonging to this module
            apis = [
                ep.path for ep in ir.api_endpoints
                if (ep.service or "").lower() in service_name.lower()
                   or service_name.lower() in (ep.service or "").lower()
            ]

            modules.append(LLDModule(
                name=service_name,
                package_path=package_path or f"{service_name.lower().replace(' ', '_')}/",
                responsibility=responsibility,
                classes_contained=comp_names,
                interfaces_contained=[],
                depends_on_modules=[],
                exposed_apis=apis[:5],
            ))
        return modules

    def _extract_dependencies(self, ir: SemanticIR, kg: Optional[KnowledgeGraph]) -> List[LLDDependency]:
        """Extract directed dependency edges between components."""
        seen = set()
        deps = []
        for rel in ir.relationships:
            key = (rel.source, rel.target, rel.relationship_type)
            if key in seen:
                continue
            seen.add(key)
            deps.append(LLDDependency(
                source=rel.source,
                target=rel.target,
                dependency_type=rel.relationship_type or "DEPENDS_ON",
                is_circular=False,
            ))
        # Simple circular check: A→B and B→A
        edge_set = {(d.source, d.target) for d in deps}
        for dep in deps:
            if (dep.target, dep.source) in edge_set:
                dep.is_circular = True
        return deps[:30]  # cap at 30

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
