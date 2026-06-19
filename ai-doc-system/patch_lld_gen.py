import re

with open("backend/document_generator/lld_generator.py", "r") as f:
    code = f.read()

# Replace _section_circular_dependencies
old_circ = """    def _section_circular_dependencies(self, lines, model):
        circs = getattr(model, 'circular_dependencies', [])
        if not circs: return
        
        lines.append("## Circular Dependency Analysis")
        lines.append("")
        for circ in circs[:5]:
            cycle_str = " → ".join(circ.cycle_path)
            lines.append(f"**Cycle:** `{cycle_str}`")
            lines.append("")
            lines.append(f"**Root Cause:** {circ.root_cause}")
            lines.append(f"**Affected Files:** {', '.join(circ.affected_files) if circ.affected_files else 'None'}")
            lines.append(f"**Affected Classes:** {', '.join(circ.affected_classes) if circ.affected_classes else 'None'}")
            lines.append("")
            lines.append(f"**Recommendation:** {circ.recommended_refactor}")
            lines.append("")"""

new_circ = """    def _section_circular_dependencies(self, lines, model):
        circs = getattr(model, 'circular_dependencies', [])
        if not circs: return
        
        lines.append("## Architecture Health")
        lines.append("")
        lines.append("| Cycle Path | Root Cause | Recommended Fix |")
        lines.append("|---|---|---|")
        for circ in circs[:5]:
            cycle_str = " → ".join(circ.cycle_path)
            cause = circ.root_cause.replace("\n", " ")
            fix = circ.recommended_refactor.replace("\n", " ")
            lines.append(f"| `{cycle_str}` | {cause} | {fix} |")
        lines.append("")"""

code = code.replace(old_circ, new_circ)

# Define new _section_dependency_matrix
dep_matrix_code = """
    def _section_dependency_matrix(self, lines, model):
        deps = getattr(model, 'dependencies', [])
        if not deps: return
        
        lines.append("## Component Dependency Matrix")
        lines.append("")
        lines.append("| Component | Depends On | Dependency Type | Strength | Purpose |")
        lines.append("|---|---|---|---|---|")
        
        # Deduplicate exactly to avoid repeating identical rows
        seen = set()
        for d in deps:
            key = (d.source, d.target, getattr(d, 'dependency_type', ''), getattr(d, 'strength', ''), getattr(d, 'purpose', ''))
            if key in seen: continue
            seen.add(key)
            
            src = d.source.replace("_", " ").title()
            tgt = d.target.replace("_", " ").title()
            dep_type = getattr(d, 'dependency_type', 'Service Dependency')
            strength = getattr(d, 'strength', 'Medium')
            purpose = getattr(d, 'purpose', '')
            
            lines.append(f"| {src} | {tgt} | {dep_type} | {strength} | {purpose} |")
        lines.append("")
"""

# Insert _section_dependency_matrix before _section_module_map
if "def _section_dependency_matrix" not in code:
    code = code.replace("    def _section_module_map(self, lines, model, dp):", dep_matrix_code + "\n    def _section_module_map(self, lines, model, dp):")

# Remove dependency_diagram insertion from _section_module_map
old_mod_map = """        if dp and dp.get("dependency_diagram"):
            lines.append("### Component Dependencies")
            lines.append("")
            lines.append("```mermaid")
            lines.append(dp["dependency_diagram"])
            lines.append("```")
            lines.append("")"""
code = code.replace(old_mod_map, "")

with open("backend/document_generator/lld_generator.py", "w") as f:
    f.write(code)

print("Patched lld generator.")
