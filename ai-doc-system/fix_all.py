import re

# PATCH EXTRACTOR
with open('backend/object_model_extractor/extractor.py', 'r') as f:
    code = f.read()

code = code.replace("'Any'", "'untyped'")
code = code.replace('"Any"', '"untyped"')

classes_method = """    def _extract_classes_and_interfaces(self, ir: SemanticIR, kg: Optional[KnowledgeGraph]) -> Tuple[List[LLDClass], List[LLDInterface]]:
        classes, interfaces = [], []
        if not kg: return classes, interfaces
        
        parsed_files = getattr(ir, 'parsed_files', [])
        
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
                        f_type = child.properties.get("type_annotation") or child.properties.get("field_type")
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
                        
                    elif child.node_type in (KGNodeType.METHOD, KGNodeType.FUNCTION, KGNodeType.CONSTRUCTOR):
                        # FIX 3
                        if child.name.startswith("_") and not child.name.startswith("__init"): continue
                        m_name = "constructor" if child.name.startswith("__init") else child.name
                        
                        m_params = child.properties.get("parameters", child.params)
                        m_ret = child.properties.get("return_type", child.return_type)
                        m_desc = child.docstring.split('.')[0] + '.' if child.docstring else ""
                        
                        if not m_params or not m_ret or not m_desc:
                            for pf in parsed_files:
                                for node in getattr(pf, 'nodes', []):
                                    if getattr(node, 'category', '') == 'class' and getattr(node, 'name', '') == cls.name:
                                        for c in getattr(node, 'children', []):
                                            if getattr(c, 'category', '') == 'function' and getattr(c, 'name', '') == child.name:
                                                m_params = m_params or getattr(c, 'parameters', [])
                                                m_ret = m_ret or getattr(c, 'return_type', None)
                                                m_desc = m_desc or (getattr(c, 'docstring', '') or "").split('.')[0]
                                                break
                        
                        m_ret = m_ret or "untyped"
                        m_desc = m_desc or infer_method_desc(child.name)
                        
                        params_clean = [p for p in m_params if not str(p).startswith("self") and not str(p).startswith("cls")]
                        if len(params_clean) == 0 and not child.docstring and m_name.startswith('get_'): continue
                        
                        methods.append(LLDMethod(name=m_name, signature=f"{m_name}({', '.join(params_clean)}) -> {m_ret}", description=m_desc, parameters=params_clean, return_type=m_ret))
                        
                elif edge.relation == KGRelationType.EXTENDS:
                    t = kg.nodes.get(edge.to_id)
                    if t: inherits_from.append(t.name)
                elif edge.relation == KGRelationType.IMPLEMENTS:
                    t = kg.nodes.get(edge.to_id)
                    if t: implements.append(t.name)
                elif edge.relation in (KGRelationType.DEPENDS_ON, KGRelationType.REFERENCES, KGRelationType.INSTANTIATES):
                    t = kg.nodes.get(edge.to_id)
                    if t and t.node_type in (KGNodeType.CLASS, KGNodeType.INTERFACE):
                        if t.name not in dependencies: dependencies.append(t.name)

            if cls.node_type == KGNodeType.CLASS:
                classes.append(LLDClass(name=cls.name, file_path=cls.file_path, fields=fields, methods=methods, dependencies=dependencies, inherits_from=inherits_from, implements=implements, composition=composition, aggregation=aggregation))
            else:
                interfaces.append(LLDInterface(name=cls.name, file_path=cls.file_path, methods=methods, extends=inherits_from))
        return classes, interfaces"""
code = re.sub(r'    def _extract_classes_and_interfaces\(self, ir: SemanticIR, kg: Optional\[KnowledgeGraph\]\) -> Tuple\[List\[LLDClass\], List\[LLDInterface\]\]:.*?return classes, interfaces', lambda _: classes_method, code, flags=re.DOTALL)

sf_method = """    def _extract_sequence_flows(self, ir: SemanticIR, kg: Optional[KnowledgeGraph] = None) -> List[LLDSequenceFlow]:
        flows = []
        if getattr(ir, 'request_flows', None):
            for i, flow in enumerate(ir.request_flows):
                if flow.entry_point and '.sql' in flow.entry_point: continue
                if len(flow.steps) < 4: continue
                
                if all(not '(' in s.get('target', '') and s.get('target', '').isupper() for s in flow.steps): continue
                
                f_steps = []
                for s in flow.steps:
                    f_steps.append(f"{s.get('source', 'Unknown')} → {s.get('target', 'Unknown')}: {s.get('operation', 'call')}()")
                flows.append(LLDSequenceFlow(name=f"Flow {i+1}", trigger=flow.entry_point or "External", steps=f_steps, description=f"Executes {flow.entry_point}"))
        else:
            if kg and getattr(ir, 'classes', None):
                top_class = max(ir.classes, key=lambda c: len(c.dependencies) if hasattr(c, 'dependencies') else 0, default=None)
                if top_class and hasattr(top_class, 'methods') and top_class.methods:
                    method = top_class.methods[0]
                    flows.append(LLDSequenceFlow(name="Primary Processing Pipeline", trigger="Application Start", steps=[
                        f"Entry → {top_class.name}: initialize()",
                        f"{top_class.name} → {top_class.name}: {method.name}()",
                        f"{top_class.name} → DataStore: save()",
                        f"DataStore → Exit: return"
                    ], description="Synthetic execution flow"))
        return flows"""
code = re.sub(r'    def _extract_sequence_flows\(\s*self, ir: SemanticIR, kg: Optional\[KnowledgeGraph\] = None\s*\) -> List\[LLDSequenceFlow\]:.*?return flows', lambda _: sf_method, code, flags=re.DOTALL)

mod_method = """    def _extract_modules(self, ir: SemanticIR, components: List[LLDComponent]) -> List[LLDModule]:
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
            modules.append(LLDModule(name=mod_name, package_path=pkg, responsibility=f"Handles operations for {mod_name}", classes_contained=classes))
        return modules"""
code = re.sub(r'    def _extract_modules\(self, ir: SemanticIR, components: List\[LLDComponent\]\) -> List\[LLDModule\]:.*?return modules', lambda _: mod_method, code, flags=re.DOTALL)

db_method = r"""    def _parse_create_table_columns(self, sql_file_path, table_name) -> list:
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
                cols = node.properties.get("columns") or node.properties.get("schema") or node.properties.get("fields") or []
                if not cols:
                    source = node.properties.get("source_file", "")
                    if source and source.endswith(".sql"):
                        cols = self._parse_create_table_columns(source, node.name)
                
                col_strs = []
                for c in cols:
                    if isinstance(c, LLDTableColumn): col_strs.append(f"{c.name}: {c.data_type}")
                    elif isinstance(c, dict): col_strs.append(f"{c.get('name')}: {c.get('type')}")
                    else: col_strs.append(str(c))
                tables.append(LLDDatabaseObject(name=node.name, type="Table", fields=col_strs, relationships=[]))
        return tables"""
code = re.sub(r'    def _extract_database_objects\(\s*self, ir: SemanticIR, kg: Optional\[KnowledgeGraph\]\s*\) -> List\[LLDDatabaseObject\]:.*?return \w+', lambda _: db_method, code, flags=re.DOTALL)

dedup_logic = """
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

        return model"""
code = code.replace("return model", dedup_logic)

with open('backend/object_model_extractor/extractor.py', 'w') as f:
    f.write(code)

print("Extractor patched safely.")
