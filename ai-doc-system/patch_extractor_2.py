import re

with open('backend/object_model_extractor/extractor.py', 'r') as f:
    code = f.read()

# -------------------------------------------------------------------
# RULE 2 & 3: Types and Method Signatures
# -------------------------------------------------------------------
def rewrite_extract_classes():
    global code
    # We will replace the inner body of class node processing
    # It's safer to just replace the whole _extract_classes_and_interfaces
    # I'll use regex to replace it
    pass

# Wait, regex replacement of 180 lines is risky. Let's write the whole method.
extract_classes_method = """    def _extract_classes_and_interfaces(self, ir: SemanticIR, kg: Optional[KnowledgeGraph]) -> Tuple[List[LLDClass], List[LLDInterface]]:
        classes = []
        interfaces = []
        if not kg:
            return classes, interfaces
            
        for cls_id, cls in kg.nodes.items():
            if cls.node_type in (KGNodeType.CLASS, KGNodeType.INTERFACE):
                fields = []
                methods = []
                dependencies = []
                inherits_from = []
                implements = []
                composition = []
                aggregation = []
                
                for edge in kg.outgoing_edges(cls.id):
                    if edge.relation == KGRelationType.CONTAINS:
                        child = kg.nodes.get(edge.to_id)
                        if child:
                            if child.node_type in (KGNodeType.METHOD, KGNodeType.FUNCTION, KGNodeType.CONSTRUCTOR):
                                # Rule 3: method signature, params, docstring
                                params_clean = [p for p in child.params if not p.startswith("self") and not p.startswith("cls")]
                                
                                # Rule 2: method return type
                                ret_type = child.return_type
                                if not ret_type or ret_type == "Any":
                                    ret_type = "untyped"
                                ret_type = ret_type.split(".")[-1] # strip module prefix
                                
                                desc = child.docstring or ""
                                if not desc:
                                    name_clean = child.name.replace("_", " ").title()
                                    desc = f"{name_clean}s and returns the processed data."
                                desc = " ".join(desc.split()[:15]) # max 15 words
                                
                                methods.append(LLDMethod(
                                    name=child.name,
                                    signature=f"{child.name}({', '.join(params_clean)}) -> {ret_type}",
                                    description=desc,
                                    parameters=params_clean,
                                    return_type=ret_type
                                ))
                            elif child.node_type in (KGNodeType.VARIABLE, KGNodeType.PROPERTY, KGNodeType.ASSIGNMENT):
                                # Rule 2: field type
                                f_type = child.return_type
                                if not f_type or f_type == "Any":
                                    f_type = "untyped"
                                f_type = f_type.split(".")[-1]
                                fields.append(f"{child.name}: {f_type}")
                                
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

code = re.sub(r'    def _extract_classes_and_interfaces\(self, ir: SemanticIR, kg: Optional\[KnowledgeGraph\]\) -> Tuple\[List\[LLDClass\], List\[LLDInterface\]\]:.*?return classes, interfaces', extract_classes_method, code, flags=re.DOTALL)


# -------------------------------------------------------------------
# RULE 5: Sequence Flows
# -------------------------------------------------------------------
sf_method = """    def _extract_sequence_flows(self, ir: SemanticIR, kg: Optional[KnowledgeGraph] = None) -> List[LLDSequenceFlow]:
        flows = []
        if not kg: return flows
        for flow_id, steps in ir.request_flows.items():
            if len(steps) < 4: continue # Rule 5: drop stubs < 4
            
            flow_steps = []
            for s in steps:
                flow_steps.append(f"{s.get('source', 'Unknown')} → {s.get('target', 'Unknown')}: {s.get('operation', 'call')}() → untyped")
                
            flows.append(LLDSequenceFlow(
                name=f"Flow {flow_id}",
                trigger="External Request",
                steps=flow_steps,
                description="Triggers " + flow_steps[0]
            ))
        return flows"""

code = re.sub(r'    def _extract_sequence_flows\(\s*self, ir: SemanticIR, kg: Optional\[KnowledgeGraph\] = None\s*\) -> List\[LLDSequenceFlow\]:.*?return flows', sf_method, code, flags=re.DOTALL)


# -------------------------------------------------------------------
# RULE 6: Data Model Relationships
# -------------------------------------------------------------------
dt_method = """    def _extract_data_type_tables(self, ir: SemanticIR, kg: Optional[KnowledgeGraph]) -> List[LLDDataTypeTable]:
        tables = []
        for cls in ir.classes:
            is_model = any(k in cls.name.lower() for k in ["model", "schema", "entity"]) or "dataclass" in getattr(cls, 'decorators', [])
            if not is_model: continue
            
            cols = []
            rels = []
            for var in cls.variables:
                v_type = var.type_str or "untyped"
                # Rule 6 logic
                is_pk = var.name in ["id", "name"]
                is_fk = var.name.endswith("_id") or var.name.endswith("_ref")
                is_null = "Optional" in v_type
                
                if is_fk: rels.append(f"foreign-key → {var.name.split('_')[0]}")
                elif "List[" in v_type: rels.append(f"one-to-many → {v_type}")
                elif v_type not in ["str", "int", "bool", "float", "untyped"]: rels.append(f"has-one {v_type}")
                
                cols.append(LLDTableColumn(name=var.name, data_type=v_type, is_primary_key=is_pk, is_foreign_key=is_fk, is_nullable=is_null))
                
            tables.append(LLDDataTypeTable(name=cls.name, source_type="ORM Model", file_path=cls.file_path, columns=cols, relationships=rels))
        return tables"""

code = re.sub(r'    def _extract_data_type_tables\(\s*self, ir: SemanticIR, kg: Optional\[KnowledgeGraph\]\s*\) -> List\[LLDDataTypeTable\]:.*?return tables', dt_method, code, flags=re.DOTALL)


with open('backend/object_model_extractor/extractor.py', 'w') as f:
    f.write(code)

print("Applied classes, sequence flows, and data tables patches.")
