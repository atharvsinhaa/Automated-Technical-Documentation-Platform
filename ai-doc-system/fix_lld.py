import re

with open('backend/document_generator/lld_generator.py', 'r') as f:
    code = f.read()

# NEW generate method
generate_method = """    def generate(self, model: LLDModel, diagrams: Dict[str, str], repository_name: str = "Unknown") -> str:
        lines = []
        lines.append(f"# Low-Level Design (LLD): {repository_name}")
        lines.append("")
        
        # Determine actual module count for sync
        modules_count = len(set(cls.file_path.split("/")[0] for cls in model.classes if cls.file_path)) if model.classes else 0
        setattr(model, 'modules_count', modules_count)

        self._section_executive_summary(lines, model, repository_name)
        self._section_module_design(lines, model)
        self._section_component_architecture(lines, model, diagrams.get("lld_component_architecture_diagram"))
        self._section_class_design(lines, model)
        self._section_sequence_diagrams(lines, model, diagrams.get("lld_sequence_diagram"))
        self._section_api_specifications(lines, model)
        self._section_data_model(lines, model)
        self._section_database_design(lines, model, diagrams.get("lld_erd_diagram"))
        self._section_dependency_architecture(lines, model, diagrams.get("lld_dependency_diagram"))
        self._section_external_integrations(lines, model)
        self._section_design_patterns(lines, model)
        self._section_error_handling_strategy(lines, model)
        self._section_deployment_units(lines, model, diagrams.get("lld_deployment_unit_diagram"))
        
        return "\\n".join(lines)"""
code = re.sub(r'    def generate\(.*?-> str:.*?return "\\n"\.join\(lines\)', lambda _: generate_method, code, flags=re.DOTALL)

# NEW component responsibility (Fix 1)
comp_method = """    def _get_component_responsibility(self, component, lld_model) -> str:
        name_clean = component.name.replace(" ", "").lower()
        for cls in lld_model.classes:
            if cls.name.replace(" ", "").lower() in name_clean or name_clean in cls.name.replace(" ", "").lower():
                if cls.description and len(cls.description.split()) > 10:
                    return cls.description.split(".")[0].strip() + "."
                if getattr(cls, 'docstring', None) and len(cls.docstring.split()) > 10:
                    return cls.docstring.split(".")[0].strip() + "."
                if cls.methods:
                    verbs = [m.name.replace("_", " ") for m in cls.methods[:4] if not m.name.startswith("_")]
                    if verbs:
                        return f"Handles: {', '.join(verbs)}."
        return f"[NO DOCSTRING — add docstring to {component.name} primary class]"

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
            
        lines.append("| Component | Layer | Responsibility |")
        lines.append("|-----------|-------|----------------|")
        for c in model.components:
            resp = self._get_component_responsibility(c, model)
            lines.append(f"| `{c.name}` | {c.layer} | {resp} |")
        lines.append("")"""
code = re.sub(r'    def _section_component_architecture\(self, lines: List\[str\], model: LLDModel, mmd_code=None\):.*?lines\.append\(""\)', lambda _: comp_method, code, flags=re.DOTALL)

# Module Design (Fix 6)
mod_method = """    def _section_module_design(self, lines: List[str], model: LLDModel):
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
                mod_map[pkg].append(cls.name)
                
        for pkg, cls_list in mod_map.items():
            mod_name = pkg.replace("_", " ").title()
            classes_str = "<br>".join([f"`{c}`" for c in cls_list[:5]])
            if len(cls_list) > 5: classes_str += f"<br>... (+{len(cls_list)-5} more)"
            lines.append(f"| `{pkg}` | Sub-system handling {mod_name} operations. | {classes_str} |")
        lines.append("")"""
code = re.sub(r'    def _section_module_design\(self, lines: List\[str\], model: LLDModel\):.*?lines\.append\(""\)', lambda _: mod_method, code, flags=re.DOTALL)

# Executive Summary (Fix 7)
exec_summary = """    def _section_executive_summary(self, lines: List[str], model: LLDModel, repo_name: str):
        lines.append("## Executive Summary")
        lines.append("")
        
        mod_count = getattr(model, 'modules_count', 0)
        c_count = len(model.components)
        cls_count = len(model.classes)
        t_count = len(model.database_objects)
        
        lines.append("| Metric | Count |")
        lines.append("|--------|-------|")
        lines.append(f"| **Modules** | {mod_count} |")
        lines.append(f"| **Components** | {c_count} |")
        lines.append(f"| **Classes** | {cls_count} |")
        lines.append(f"| **Database Tables** | {t_count} |")
        lines.append("")"""
code = re.sub(r'    def _section_executive_summary\(self, lines: List\[str\], model: LLDModel, repo_name: str\):.*?lines\.append\(""\)', lambda _: exec_summary, code, flags=re.DOTALL)

# System overview removal
sys_overview = """    def _section_system_overview(self, lines: List[str], model: LLDModel):
        pass"""
code = re.sub(r'    def _section_system_overview\(self, lines: List\[str\], model: LLDModel\):.*?lines\.append\(""\)', lambda _: sys_overview, code, flags=re.DOTALL)

# Class Design (Fix 9 & Fix 10)
cls_design = """    def _is_worth_documenting(self, cls) -> bool:
        has_content = bool(cls.fields or cls.methods)
        not_empty_shell = not (len(cls.fields) == 0 and len(cls.methods) == 0)
        not_pure_enum = not (getattr(cls, 'docstring', None) is None and len(cls.methods) == 0 and all("=" in f for f in cls.fields))
        return has_content and not_empty_shell

    def _section_class_design(self, lines: List[str], model: LLDModel):
        if not model.classes: return
        lines.append("## Class Design")
        lines.append("")
        
        valid_classes = [c for c in model.classes if self._is_worth_documenting(c)]
        skipped = [c for c in model.classes if not self._is_worth_documenting(c)]
        
        sorted_cls = sorted(valid_classes, key=lambda c: (len(c.methods)*2) + len(c.dependencies), reverse=True)
        top_15 = sorted_cls[:15]
        
        for cls in top_15:
            lines.append(f"### Class: `{cls.name}`")
            if cls.file_path: lines.append(f"**Path**: `{cls.file_path}`")
            if getattr(cls, 'description', getattr(cls, 'docstring', None)): lines.append(f"**Responsibility**: {getattr(cls, 'description', getattr(cls, 'docstring', ''))}")
            lines.append("")
            
            if cls.fields:
                lines.append("**Fields:**")
                lines.append("| Field | Type |")
                lines.append("|-------|------|")
                for f in cls.fields:
                    parts = f.split(":", 1)
                    if len(parts) == 2:
                        lines.append(f"| `{parts[0].strip()}` | `{parts[1].strip()}` |")
                    else:
                        lines.append(f"| `{f}` | `untyped` |")
                lines.append("")
                
            if cls.methods:
                lines.append("**Methods:**")
                lines.append("| Method | Parameters | Return Type | Description |")
                lines.append("|--------|------------|-------------|-------------|")
                for m in cls.methods:
                    params = "<br>".join([f"`{p}`" for p in m.parameters]) if m.parameters else "None"
                    lines.append(f"| `{m.name}` | {params} | `{m.return_type or 'untyped'}` | {m.description or '—'} |")
                lines.append("")
                
        if skipped:
            lines.append(f"*(Note: {len(skipped)} empty or data-only classes were omitted: {', '.join([c.name for c in skipped[:10]])}...)*")
            lines.append("")"""
code = re.sub(r'    def _section_class_design\(self, lines: List\[str\], model: LLDModel\):.*?lines\.append\(""\)', lambda _: cls_design, code, flags=re.DOTALL)

# Sequence Flows (Fix 4c & 10)
seq_method = """    def _section_sequence_diagrams(self, lines: List[str], model: LLDModel, mmd_code=None):
        if not getattr(model, 'sequence_flows', []): return
        lines.append("## Sequence Flows")
        lines.append("")
        if mmd_code:
            lines.append("```mermaid")
            lines.append(mmd_code)
            lines.append("```")
            lines.append("Figure 2: Sequence Flows Diagram — Illustrates the critical path step-by-step execution flows through the system.")
            lines.append("")
            
        for sf in model.sequence_flows:
            lines.append(f"### Flow: {sf.name}")
            lines.append(f"**Trigger**: {sf.trigger}")
            lines.append("")
            lines.append("| Step | From | To | Action | Data |")
            lines.append("|------|------|----|--------|------|")
            for i, step in enumerate(sf.steps):
                parts = step.split(":", 1)
                action = parts[1].strip() if len(parts) > 1 else step
                actors = parts[0].split("→") if len(parts) > 1 else ["System", "System"]
                frm = actors[0].strip() if len(actors) > 0 else "System"
                to = actors[1].strip() if len(actors) > 1 else "System"
                lines.append(f"| {i+1} | `{frm}` | `{to}` | {action} | — |")
            lines.append("")"""
code = re.sub(r'    def _section_sequence_diagrams\(self, lines: List\[str\], model: LLDModel, mmd_code=None\):.*?lines\.append\(""\)', lambda _: seq_method, code, flags=re.DOTALL)

# Database / Schema (Fix 5, 10 & 11)
db_method = """    def _section_database_design(self, lines: List[str], model: LLDModel, mmd_code):
        if not model.database_objects: return
        lines.append("## Database Schema")
        lines.append("")
        if mmd_code:
            lines.append("```mermaid")
            lines.append(mmd_code)
            lines.append("```")
            lines.append("Figure 3: Database Entity-Relationship Diagram — Shows the structure and foreign key relationships between persistent data tables.")
            lines.append("")
            
        for db in model.database_objects:
            lines.append(f"### Table: `{db.name}`")
            lines.append("")
            lines.append("| Column | Type | Nullable | Description |")
            lines.append("|--------|------|----------|-------------|")
            
            seen_columns = set()
            deduped_fields = []
            for f in db.fields:
                parts = f.split(":", 1)
                col_name = parts[0].strip()
                if col_name.lower() not in seen_columns:
                    seen_columns.add(col_name.lower())
                    deduped_fields.append(f)
                    
            for i, f in enumerate(deduped_fields):
                parts = f.split(":", 1)
                col = parts[0].strip()
                dtype = parts[1].strip() if len(parts) > 1 else "TEXT"
                
                # Nullable logic
                nullable = "YES" if "Optional" in dtype or "None" in dtype else "NO"
                if i == 0 and nullable == "NO": nullable = "NO (PK)" # Primary id identifier
                lines.append(f"| `{col}` | `{dtype}` | {nullable} | — |")
            lines.append("")"""
code = re.sub(r'    def _section_database_design\(self, lines: List\[str\], model: LLDModel, mmd_code\):.*?lines\.append\(""\)', lambda _: db_method, code, flags=re.DOTALL)

# Dependency Architecture (Fix 8 & 10)
dep_method = """    def _section_dependency_architecture(self, lines: List[str], model: LLDModel, mmd_code):
        if not model.dependencies: return
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
        lines.append("| Source Component | Target Component | Relation Type |")
        lines.append("|------------------|------------------|---------------|")
        for d in model.dependencies:
            if (d.target, d.source) in all_pairs:
                if (d.target, d.source) not in circular: circular.add((d.source, d.target))
                continue
            lines.append(f"| `{d.source}` | `{d.target}` | IMPORTS |")
        lines.append("")
        
        if circular:
            lines.append("### Circular Dependencies")
            lines.append("| Source | Target | Reason |")
            lines.append("|--------|--------|--------|")
            for src, tgt in circular:
                lines.append(f"| `{src}` | `{tgt}` | Bidirectional Import |")
            lines.append("")"""
code = re.sub(r'    def _section_dependency_architecture\(self, lines: List\[str\], model: LLDModel, mmd_code\):.*?lines\.append\(""\)', lambda _: dep_method, code, flags=re.DOTALL)

# Disable duplicate Data types section
data_method = """    def _section_data_types_and_tables(self, lines: List[str], model: LLDModel):
        pass"""
code = re.sub(r'    def _section_data_types_and_tables\(self, lines: List\[str\], model: LLDModel\):.*?lines\.append\(""\)', lambda _: data_method, code, flags=re.DOTALL)

# Finalize and write
with open('backend/document_generator/lld_generator.py', 'w') as f:
    f.write(code)

print("LLD Generator patched safely.")
