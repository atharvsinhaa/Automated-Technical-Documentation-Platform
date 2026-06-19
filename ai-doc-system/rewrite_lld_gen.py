import re

with open('backend/document_generator/lld_generator.py', 'r') as f:
    code = f.read()

# Remove Executive Summary and Revision History
code = re.sub(r'# 1\. Executive Summary.*?# 2\. Component Architecture', r'# 2. Component Architecture', code, flags=re.DOTALL)

# Let's just create a completely new generate() method string, it's safer.
new_generate = """    def generate(
        self,
        model_data: Dict[str, Any],
        diagram_paths: Optional[Dict[str, str]] = None,
        repository_name: str = "Unknown"
    ) -> str:
        diagram_paths = diagram_paths or {}
        
        lines = []
        lines.append(f"# Low-Level Design (LLD) - {repository_name}")
        lines.append("")
        
        # --- Component Architecture ---
        lines.append("## 1. Component Architecture")
        lines.append("")
        if "full_system_diagram" in diagram_paths:
            lines.append(f"![Component Architecture]({diagram_paths['full_system_diagram']})")
            lines.append("*Figure 1: Full System Architecture*")
            lines.append("")
            
        components = model_data.get("components", [])
        if components:
            lines.append("| Component | Type | Layer | Responsibility |")
            lines.append("|---|---|---|---|")
            for c in components:
                lines.append(f"| **{c['name']}** | {c.get('component_type', 'Service')} | {c.get('layer', 'Application')} | {c.get('responsibility', '')} |")
        else:
            lines.append("[EXTRACTION INCOMPLETE — add docstrings to source code]")
        lines.append("")

        # --- Inter-Module Dependency Map (NEW) ---
        lines.append("## 2. Inter-Module Dependency Map")
        lines.append("")
        deps = model_data.get("dependencies", [])
        if deps:
            lines.append("| Module | Imports From | Import Type |")
            lines.append("|---|---|---|")
            for d in deps:
                lines.append(f"| {d['source']} | {d['target']} | {d.get('dependency_type', 'direct')} |")
        else:
            lines.append("[EXTRACTION INCOMPLETE — add docstrings to source code]")
        lines.append("")

        # --- Public API Surface (NEW) ---
        lines.append("## 3. Public API Surface")
        lines.append("")
        classes = model_data.get("classes", [])
        if classes:
            lines.append("| Class | Method | Signature | Purpose |")
            lines.append("|---|---|---|---|")
            for cls in classes:
                for m in cls.get("methods", []):
                    lines.append(f"| {cls['name']} | {m['name']} | `{m.get('signature', '')}` | {m.get('description', '')} |")
        else:
            lines.append("[EXTRACTION INCOMPLETE — add docstrings to source code]")
        lines.append("")

        # --- Configuration & Environment (NEW) ---
        lines.append("## 4. Configuration & Environment")
        lines.append("")
        lines.append("| Key | Default | Used In | Purpose |")
        lines.append("|---|---|---|---|")
        lines.append("| DATABASE_URL | None | DBClient | Connection string |")
        lines.append("")

        # --- Class Design ---
        lines.append("## 5. Class Design")
        lines.append("")
        if "class_diagram" in diagram_paths:
            lines.append(f"![Class Diagram]({diagram_paths['class_diagram']})")
            lines.append("*Figure 2: Core Class Relationships*")
            lines.append("")
            
        # Top 15 ranking
        top_classes = sorted(classes, key=lambda x: (len(x.get('methods', [])) * 2) + len(x.get('dependencies', [])), reverse=True)[:15]
        
        for cls in top_classes:
            lines.append(f"### {cls['name']}")
            lines.append(f"**Path**: `{cls.get('file_path', '')}`")
            lines.append("")
            if cls.get("fields"):
                lines.append("#### Fields")
                for f in cls["fields"]: lines.append(f"- `{f}`")
                lines.append("")
            
            methods = [m for m in cls.get("methods", []) if m['name'] != "__init__"]
            if methods:
                lines.append("#### Methods")
                lines.append("| Method | Parameters | Returns | Description |")
                lines.append("|--------|-----------|---------|-------------|")
                for m in methods:
                    params = ", ".join(m.get("parameters", []))
                    lines.append(f"| `{m['name']}` | `{params}` | `{m.get('return_type', 'untyped')}` | {m.get('description', '')} |")
                lines.append("")

        # --- Data Model ---
        lines.append("## 6. Data Model & Database")
        lines.append("")
        if "erd_diagram" in diagram_paths:
            lines.append(f"![ERD]({diagram_paths['erd_diagram']})")
            lines.append("*Figure 3: Entity Relationship Diagram*")
            lines.append("")
            
        tables = model_data.get("data_type_tables", [])
        if tables:
            for t in tables:
                lines.append(f"### Table: {t['name']}")
                lines.append("| Column | Type | PK/FK | Nullable | References |")
                lines.append("|---|---|---|---|---|")
                for col in t.get("columns", []):
                    pk_fk = []
                    if col.get("is_primary_key"): pk_fk.append("PK")
                    if col.get("is_foreign_key"): pk_fk.append("FK")
                    pk_str = "/".join(pk_fk) if pk_fk else "-"
                    null_str = "YES" if col.get("is_nullable") else "NO"
                    ref_str = col.get("references") or "-"
                    lines.append(f"| `{col['name']}` | {col.get('data_type', 'untyped')} | {pk_str} | {null_str} | {ref_str} |")
                lines.append("")
                
                rels = t.get("relationships", [])
                if rels:
                    lines.append("**Relationships:**")
                    for r in rels: lines.append(f"- {r}")
                lines.append("")

        # --- Sequence Flows ---
        lines.append("## 7. Sequence Flows")
        lines.append("")
        for sf in model_data.get("sequence_flows", []):
            lines.append(f"### {sf['name']}")
            lines.append("| Step | Caller | Action | Data Passed | Expected Output |")
            lines.append("|---|---|---|---|---|")
            for i, step in enumerate(sf.get("steps", [])):
                lines.append(f"| {i+1} | Extractor | `{step}` | Payload | Success |")
            lines.append("")
            
        # --- Key Algorithms & Processing Logic ---
        lines.append("## 8. Key Algorithms & Processing Logic")
        lines.append("")
        algos = model_data.get("algorithms", [])
        if algos:
            for a in algos:
                lines.append(f"### {a['name']}")
                lines.append(f"**Complexity:** {a.get('complexity', 'O(?)')}")
                lines.append(f"**Description:** {a.get('description', '')}")
                lines.append("**Steps:**")
                for i, s in enumerate(a.get("steps", [])): lines.append(f"{i+1}. {s}")
                lines.append("")
                
        # --- Error Handling & Exception Map ---
        lines.append("## 9. Error Handling & Exception Map")
        lines.append("")
        errs = model_data.get("error_paths", [])
        if errs:
            lines.append("| Class | Method | Exception Type | Condition | Handling |")
            lines.append("|-------|--------|---------------|-----------|----------|")
            for e in errs:
                c_name, m_name = e.get("source", ".").split(".", 1) if "." in e.get("source", "") else (e.get("source"), "unknown")
                lines.append(f"| {c_name} | {m_name} | {e.get('error_type')} | unknown | {e.get('handler')} |")
            lines.append("")
        else:
            lines.append("⚠ No exception handling detected — consider adding guards for empty input and filesystem errors.")
            lines.append("")

        return "\\n".join(lines)
"""

code = re.sub(r'    def generate\(.*?return "\\n"\.join\(lines\)', new_generate, code, flags=re.DOTALL)

with open('backend/document_generator/lld_generator.py', 'w') as f:
    f.write(code)

print("Applied LLD generator changes.")
