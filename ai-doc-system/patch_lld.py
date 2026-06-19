import re
import os

with open('backend/document_generator/lld_generator.py', 'r') as f:
    code = f.read()

# 1. Update Component Architecture
comp_arch_new = """    def _get_sub_modules(self, comp_name: str, model) -> str:
        import os
        # Find folder matching component name
        folder_name = comp_name.replace(" ", "_").lower()
        
        # Try to find base path from classes
        base_dir = None
        for cls in model.classes:
            if cls.file_path and folder_name in cls.file_path:
                parts = cls.file_path.split("/")
                for i, p in enumerate(parts):
                    if p == folder_name:
                        base_dir = "/".join(parts[:i+1])
                        break
                if base_dir: break
                
        if base_dir and os.path.exists(base_dir):
            py_files = [f[:-3].replace("_", " ").title() for f in os.listdir(base_dir) if f.endswith(".py") and not f.startswith("__")]
            if py_files:
                return ", ".join(py_files)
        return "Single-file module"

    def _get_component_classes(self, comp_name: str, model) -> str:
        folder_name = comp_name.replace(" ", "_").lower()
        comp_classes = [c.name for c in model.classes if c.file_path and folder_name in c.file_path]
        if not comp_classes:
            return "None detected"
        if len(comp_classes) > 6:
            return ", ".join(comp_classes[:6]) + f" (+ {len(comp_classes)-6} more)"
        return ", ".join(comp_classes)

    def _get_receives_returns(self, comp_name: str, model):
        folder_name = comp_name.replace(" ", "_").lower()
        primary_cls = None
        for cls in model.classes:
            if cls.file_path and folder_name in cls.file_path and (folder_name in cls.name.lower() or "extractor" in cls.name.lower() or "generator" in cls.name.lower() or "builder" in cls.name.lower()):
                primary_cls = cls
                break
        if not primary_cls:
            for cls in model.classes:
                if cls.file_path and folder_name in cls.file_path:
                    primary_cls = cls
                    break
        
        receives = "Configuration only"
        returns = "None"
        
        if primary_cls:
            # Receives
            custom_inputs = []
            methods_to_check = [m for m in primary_cls.methods if m.name == "constructor" or not m.name.startswith("_")]
            for m in methods_to_check:
                for p in m.parameters:
                    if ":" in p:
                        pname, ptype = p.split(":", 1)
                        ptype = ptype.strip()
                        if ptype not in ("str", "int", "bool", "float", "Path", "Any", "Dict", "List"):
                            custom_inputs.append(f"{ptype} from upstream")
                        elif "path" in pname.lower() or "file" in pname.lower():
                            custom_inputs.append("File path (str) from user / API")
            if custom_inputs:
                receives = ", ".join(set(custom_inputs))
                
            # Returns
            pub_methods = [m for m in primary_cls.methods if m.name != "constructor" and not m.name.startswith("_")]
            if pub_methods:
                ret_type = pub_methods[0].return_type or "untyped"
                # Infer consumer
                consumers = []
                for d in getattr(model, 'dependencies', []):
                    if d.target.lower() == comp_name.lower():
                        consumers.append(d.source)
                consumer_str = consumers[0] if consumers else "downstream"
                returns = f"{ret_type} → consumed by {consumer_str}"
                
        return receives, returns

    def _get_storage_tech(self, comp_name: str, model):
        folder_name = comp_name.replace(" ", "_").lower()
        storage = "In-memory only"
        techs = []
        
        has_neo4j = False
        has_file = False
        has_ast = False
        has_llm = False
        has_rules = False
        
        for cls in model.classes:
            if cls.file_path and folder_name in cls.file_path:
                # check imports/content via naive word match if possible, or just fields
                all_text = " ".join([m.name for m in cls.methods]) + " " + " ".join(cls.fields) + " " + (cls.docstring or "")
                if "neo4j" in all_text.lower() or "graph" in all_text.lower(): has_neo4j = True
                if "file" in all_text.lower() or "write" in all_text.lower() or "open" in all_text.lower(): has_file = True
                if "ast" in all_text.lower() or "tree_sitter" in all_text.lower() or "parser" in all_text.lower(): has_ast = True
                if "llm" in all_text.lower() or "prompt" in all_text.lower() or "ollama" in all_text.lower(): has_llm = True
                if "rule" in all_text.lower() or "validator" in all_text.lower(): has_rules = True
                
        # Also try reading actual files if accessible
        try:
            import os
            base_dir = None
            for cls in model.classes:
                if cls.file_path and folder_name in cls.file_path:
                    parts = cls.file_path.split("/")
                    for i, p in enumerate(parts):
                        if p == folder_name:
                            base_dir = "/".join(parts[:i+1])
                            break
                    if base_dir: break
            if base_dir and os.path.exists(base_dir):
                for f in os.listdir(base_dir):
                    if f.endswith(".py"):
                        content = open(os.path.join(base_dir, f)).read().lower()
                        if "neo4j" in content or "cypher" in content: has_neo4j = True
                        if "open(" in content or ".write(" in content: has_file = True
                        if "tree_sitter" in content: techs.append("Tree-sitter parser")
                        if "import ast" in content or "from ast" in content: techs.append("Python AST")
                        if "javalang" in content: techs.append("Java parser")
                        if "ollama" in content or "openai" in content or "anthropic" in content: has_llm = True
                        if "template" in content or "jinja" in content: techs.append("Template engine")
                        if "prompt" in content: techs.append("Prompt chain")
                        if "rule" in content or "validator" in content: has_rules = True
        except Exception:
            pass
            
        if has_neo4j: storage = "Reads/Writes nodes to Neo4j"
        elif has_file: storage = "Writes files to disk"
        
        if has_llm: techs.append("LLM")
        if has_rules: techs.append("Rule-based engine")
        
        tech_str = ", ".join(set(techs)) if techs else "Standard Python"
        return storage, tech_str

    def _section_component_architecture(self, lines: List[str], model: LLDModel, mmd_code=None):
        if not model.components: return
        lines.append("## Component Architecture")
        lines.append("")
        if mmd_code:
            lines.append("```mermaid")
            lines.append(mmd_code)
            lines.append("```")
            lines.append("Figure 1: Component Architecture Diagram — Displays system boundaries, internal components, and core data flow paths.")
            lines.append("")
            
        for c in model.components:
            lines.append(f"### {c.name}")
            lines.append("| Property | Value |")
            lines.append("|----------|-------|")
            lines.append(f"| Layer | {c.layer} |")
            lines.append(f"| Sub-modules | {self._get_sub_modules(c.name, model)} |")
            lines.append(f"| Classes | {self._get_component_classes(c.name, model)} |")
            
            receives, returns = self._get_receives_returns(c.name, model)
            lines.append(f"| Receives | {receives} |")
            lines.append(f"| Returns | {returns} |")
            
            storage, tech = self._get_storage_tech(c.name, model)
            lines.append(f"| Storage | {storage} |")
            lines.append(f"| Internal tech | {tech} |")
            lines.append("")
            
    def _section_storage_layer(self, lines: List[str], model: LLDModel):
        lines.append("## Storage Layer")
        lines.append("")
        lines.append("| Store | Type | Contains | Access Pattern |")
        lines.append("|-------|------|----------|----------------|")
        
        # Determine neo4j contents
        neo4j_nodes = []
        try:
            import os, re
            # scan codebase for KGNodeType
            for root, _, files in os.walk("backend"):
                for f in files:
                    if f.endswith(".py"):
                        content = open(os.path.join(root, f)).read()
                        matches = re.findall(r'KGNodeType\.([A-Z_]+)', content)
                        neo4j_nodes.extend(matches)
        except:
            pass
        
        if neo4j_nodes:
            unique_nodes = list(set([n.title().replace("_", " ") + " Nodes" for n in neo4j_nodes]))
            contains_str = ", ".join(unique_nodes[:10])
            if len(unique_nodes) > 10: contains_str += "..."
            lines.append(f"| Neo4j | Graph DB | {contains_str} | Read/Write via Cypher |")
            
        # SQL / ORM
        sql_tables = [t.name for t in getattr(model, 'database_objects', []) if getattr(t, 'type', 'Table') == 'Table']
        if sql_tables:
            lines.append(f"| Relational DB | Relational | {', '.join(sql_tables)} | Read/Write via ORM |")
            
        lines.append("| File System | Files | .docx, .md, .svg, .mmd | Write-only |")
        lines.append("| In-Memory | Objects | SemanticIR, ArchitectureBlueprint, LLDModel | Pipeline lifetime |")
        lines.append("")"""

code = re.sub(r'    def _section_component_architecture\(self, lines: List\[str\], model: LLDModel, mmd_code=None\):.*?lines\.append\(""\)', comp_arch_new, code, flags=re.DOTALL)

# Inject storage layer into generate()
code = code.replace('self._section_component_architecture(body_lines, model, dp.get("component_architecture_diagram") or dp.get("lld_component_architecture_diagram"))',
                    'self._section_component_architecture(body_lines, model, dp.get("component_architecture_diagram") or dp.get("lld_component_architecture_diagram"))\n        self._section_storage_layer(body_lines, model)')

# 2. Update Component Dependencies with Data Format
dep_arch_new = """    def _section_dependency_architecture(self, lines: List[str], model: LLDModel, mmd_code=None):
        if not getattr(model, 'dependencies', []): return
        lines.append("## Dependency Architecture")
        lines.append("")
        if mmd_code:
            lines.append("```mermaid")
            lines.append(mmd_code)
            lines.append("```")
            lines.append("Figure 4: Dependency Architecture Diagram — Maps internal service and class dependencies, highlighting tight coupling.")
            lines.append("")
            
        all_pairs = {(d.source, d.target) for d in model.dependencies}
        circular = set()
        
        lines.append("### Component Dependencies")
        lines.append("| Source Component | Target Component | Relation Type | Data Format |")
        lines.append("|------------------|------------------|---------------|-------------|")
        
        def get_data_format(src, tgt):
            src_l, tgt_l = src.lower(), tgt.lower()
            if "ast" in src_l and "combiner" in tgt_l: return "ParsedProject (AST XML)"
            if "knowledge" in tgt_l or "kg" in tgt_l: return "KnowledgeGraph (JSON)"
            if "ir" in tgt_l or "semantic" in tgt_l: return "SemanticIR (object)"
            if "extractor" in tgt_l: return "SemanticIR (object)"
            if "extractor" in src_l: return "ArchitectureBlueprint (object)"
            if "aim" in src_l: return "AIM (JSON)"
            if "diagram" in tgt_l: return "AIM + Blueprint (object)"
            if "diagram" in src_l: return "Mermaid string / SVG"
            if "document" in tgt_l or "docx" in tgt_l: return "Markdown / DOCX"
            if "llm" in tgt_l or "orchestrator" in tgt_l: return "PromptPayload (JSON)"
            if "llm" in src_l or "orchestrator" in src_l: return "LLM response (str)"
            
            # fallback: find primary method return of source
            for cls in model.classes:
                if cls.file_path and src_l.replace(" ", "_") in cls.file_path:
                    pub_methods = [m for m in cls.methods if m.name != "constructor" and not m.name.startswith("_")]
                    if pub_methods and pub_methods[0].return_type:
                        return pub_methods[0].return_type
            return "Object reference"
            
        for d in model.dependencies:
            if (d.target, d.source) in all_pairs:
                if (d.target, d.source) not in circular: circular.add((d.source, d.target))
                continue
            fmt = get_data_format(d.source, d.target)
            lines.append(f"| `{d.source}` | `{d.target}` | IMPORTS | {fmt} |")
        lines.append("")
        
        if circular:
            lines.append("### Circular Dependencies")
            lines.append("| Source | Target | Reason |")
            lines.append("|--------|--------|--------|")
            for src, tgt in circular:
                lines.append(f"| `{src}` | `{tgt}` | Bidirectional Import |")
            lines.append("")"""
code = re.sub(r'    def _section_dependency_architecture\(self, lines: List\[str\], model: LLDModel, mmd_code=None\):.*?def _section_external_integrations', dep_arch_new + "\n\n    def _section_external_integrations", code, flags=re.DOTALL)

# 3. Class Design Single Table
class_design_new = """    def _is_worth_documenting(self, cls) -> bool:
        name = cls.name
        active_keywords = ("Builder", "Engine", "Extractor", "Mapper", "Recognizer", "Runner", "Orchestrator", "Service", "Generator", "Analyzer", "Client", "Loader")
        if any(name.endswith(k) for k in active_keywords):
            return True
        has_content = bool(cls.fields or cls.methods)
        not_empty_shell = not (len(cls.fields) == 0 and len(cls.methods) == 0)
        return has_content and not_empty_shell

    def _section_class_design(self, lines: List[str], model: LLDModel):
        if not model.classes: return
        lines.append("## Class Design")
        lines.append("")
        
        valid_classes = [c for c in model.classes if self._is_worth_documenting(c)]
        
        active_keywords = ("Builder", "Engine", "Extractor", "Mapper", "Recognizer", "Runner", "Orchestrator", "Service", "Generator", "Analyzer", "Client", "Loader")
        
        def calc_score(cls):
            score = (len(cls.methods) * 3) + (len(cls.fields) * 1)
            if any(cls.name.endswith(k) for k in active_keywords):
                score += 10
            return score
            
        sorted_cls = sorted(valid_classes, key=calc_score, reverse=True)
        
        omitted = 0
        if len(sorted_cls) > 25:
            kept = []
            for c in sorted_cls:
                is_active = any(c.name.endswith(k) for k in active_keywords)
                if calc_score(c) > 5 or is_active:
                    kept.append(c)
                else:
                    omitted += 1
            sorted_cls = kept
            
        lines.append("| Class | Path | Fields (name: type) | Key Methods (signature → return) | Purpose |")
        lines.append("|-------|------|---------------------|----------------------------------|---------|")
        
        for cls in sorted_cls:
            # Path
            path = cls.file_path or ""
            if path.startswith("backend/"): path = path[8:]
            
            # Fields
            fields_list = []
            for f in cls.fields:
                parts = f.split(":", 1)
                if len(parts) == 2:
                    fields_list.append(f"{parts[0].strip()}: {parts[1].strip()}")
                else:
                    fields_list.append(f"{f}: untyped")
            
            fields_str = " · ".join(fields_list[:5])
            if len(fields_list) > 5: fields_str += f" …+{len(fields_list)-5}"
            if not fields_str: fields_str = "—"
            
            # Methods
            methods_list = []
            pub_methods = [m for m in cls.methods if not m.name.startswith("_") or m.name == "constructor"]
            # sort by longest body? we don't have body length, so just take first 3
            for m in pub_methods[:3]:
                methods_list.append(f"{m.name}({', '.join(m.parameters)}) → {m.return_type or 'untyped'}")
            
            methods_str = " \\| ".join(methods_list)
            if len(pub_methods) > 3: methods_str += f" …+{len(pub_methods)-3}"
            if not methods_str: 
                is_active = any(cls.name.endswith(k) for k in active_keywords)
                if is_active:
                    methods_str = "Methods not extracted — add docstrings"
                else:
                    methods_str = "—"
            
            # Purpose
            purpose = "—"
            if getattr(cls, 'description', None) and len(cls.description) > 5:
                purpose = cls.description.split(".")[0].strip() + "."
            elif getattr(cls, 'docstring', None) and len(cls.docstring) > 5:
                purpose = cls.docstring.split(".")[0].strip() + "."
            else:
                # infer from name
                import re
                words = re.findall('[A-Z][^A-Z]*', cls.name)
                purpose = " ".join(words) + " implementation."
            
            # truncate purpose to 12 words max
            purpose_words = purpose.split()
            if len(purpose_words) > 12:
                purpose = " ".join(purpose_words[:12]) + "..."
                
            lines.append(f"| `{cls.name}` | `{path}` | {fields_str} | {methods_str} | {purpose} |")
            
        lines.append("")
        if omitted > 0:
            lines.append(f"*{omitted} data-model classes omitted (fields only, no logic).*")
            lines.append("")"""
code = re.sub(r'    def _is_worth_documenting\(self, cls\).*?def _render_class_full\(self, lines: List\[str\], cls\):.*?(?=    # ══════════════════════════════════════════════════════════\n    #  SECTION 6)', class_design_new + "\n\n", code, flags=re.DOTALL)

# 4. Module Design (C1)
mod_design_new = """    def _section_module_design(self, lines: List[str], model: LLDModel):
        if not model.classes: return
        lines.append("## Module Design")
        lines.append("")
        lines.append("| Module Package | Primary Responsibility | Contained Classes |")
        lines.append("|----------------|------------------------|-------------------|")
        
        mod_map = {}
        for cls in model.classes:
            if cls.file_path:
                pkg = cls.file_path.split("/")[0]
                if pkg not in mod_map: mod_map[pkg] = []
                mod_map[pkg].append(cls)
                
        for pkg, cls_list in mod_map.items():
            mod_name = pkg.replace("_", " ").title()
            cls_names = [c.name for c in cls_list]
            classes_str = "<br>".join([f"`{c}`" for c in cls_names[:5]])
            if len(cls_names) > 5: classes_str += f"<br>... (+{len(cls_names)-5} more)"
            
            # infer responsibility
            primary_cls = None
            for c in cls_list:
                if any(k in c.name for k in ("Builder", "Engine", "Extractor", "Service", "Generator", "Orchestrator")):
                    primary_cls = c
                    break
            if not primary_cls and cls_list: primary_cls = cls_list[0]
            
            verb = "Manages"
            if primary_cls:
                import re
                words = re.findall('[A-Z][^A-Z]*', primary_cls.name)
                if words:
                    v = words[-1].lower()
                    if v == "builder": verb = "Builds"
                    elif v == "extractor": verb = "Extracts"
                    elif v == "generator": verb = "Generates"
                    elif v == "orchestrator": verb = "Orchestrates"
                    elif v == "engine": verb = "Processes"
                    else: verb = words[0] + "s"
            
            sub_resp = ", ".join([c.name for c in cls_list[:3]])
            resp = f"{verb} the {mod_name} from input — {sub_resp}."
            lines.append(f"| `{pkg}` | {resp} | {classes_str} |")
        lines.append("")"""
code = re.sub(r'    def _section_module_design\(self, lines: List\[str\], model: LLDModel\):.*?def _section_class_design', mod_design_new + "\n\n    def _section_class_design", code, flags=re.DOTALL)

# 5. Deployment Units (C3)
dep_unit_new = """    def _section_deployment_units(self, lines: List[str], model: LLDModel, mmd_code=None):
        lines.append("## Deployment Units")
        lines.append("")
        
        # Inject missing units
        existing_names = [u.name.lower() for u in getattr(model, 'deployment_units', [])]
        added = []
        deps_str = " ".join([d.target.lower() for d in getattr(model, 'dependencies', [])])
        import os
        codebase_str = ""
        try:
            for root, _, files in os.walk("backend"):
                for f in files:
                    if f.endswith(".py"):
                        codebase_str += open(os.path.join(root, f)).read().lower()[:1000]
        except:
            pass
            
        from backend.object_model_extractor.models import LLDDeploymentUnit
        if "neo4j" in deps_str or "neo4j" in codebase_str:
            if not any("neo4j" in n for n in existing_names):
                added.append(LLDDeploymentUnit(name="Neo4j Database", unit_type="Database", runtime="Docker", dependencies=["Volume Mounts"]))
        if "ollama" in deps_str or "ollama" in codebase_str:
            if not any("ollama" in n for n in existing_names):
                added.append(LLDDeploymentUnit(name="Ollama LLM Runtime", unit_type="AI Service", runtime="Docker/Local", dependencies=["Models"]))
        if "fastapi" in codebase_str or "uvicorn" in codebase_str:
            if not any("fastapi" in n for n in existing_names):
                added.append(LLDDeploymentUnit(name="FastAPI Application Server", unit_type="Web Server", runtime="Python ASGI", dependencies=["Python"]))
                
        if not any("python application" in n for n in existing_names):
            added.append(LLDDeploymentUnit(name="Python Application", unit_type="Application", runtime="Python 3.x", dependencies=["Pip Packages"]))
            
        all_units = getattr(model, 'deployment_units', []) + added
        
        lines.append("| Unit | Type | Runtime | Env Variables | Depends On |")
        lines.append("|------|------|---------|---------------|------------|")
        for unit in all_units:
            env = ", ".join(unit.environment_variables) if getattr(unit, "environment_variables", None) else "—"
            deps = ", ".join(unit.dependencies) if getattr(unit, "dependencies", None) else "—"
            lines.append(f"| `{unit.name}` | {unit.unit_type} | {unit.runtime} | {env} | {deps} |")
        lines.append("")
        
        if mmd_code and "Empty[" not in mmd_code and "No Deployment" not in mmd_code:
            lines.append("```mermaid")
            lines.append(mmd_code.strip())
            lines.append("```")
            lines.append("")"""
code = re.sub(r'    def _section_deployment_units\(self, lines: List\[str\], model: LLDModel, mmd_code=None\):.*?def _section_security_design', dep_unit_new + "\n\n    # ══════════════════════════════════════════════════════════\n    #  SECTION 15: Security Design", code, flags=re.DOTALL)

with open('backend/document_generator/lld_generator.py', 'w') as f:
    f.write(code)
print("Updated lld_generator.py successfully.")
