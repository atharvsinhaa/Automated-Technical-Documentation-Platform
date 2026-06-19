import re

with open("backend/document_generator/lld_generator.py", "r") as f:
    code = f.read()

# Replace _section_dependency_matrix
old_dep_matrix = """    def _section_dependency_matrix(self, lines, model):
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
        lines.append(\"\"\")"""

new_dep_matrix = """    def _section_dependency_matrix(self, lines, model):
        deps = getattr(model, 'dependencies', [])
        if not deps: return
        
        lines.append("## Component Dependency Matrix")
        lines.append("")
        lines.append("| Component | Key Dependencies |")
        lines.append("|---|---|")
        
        from collections import defaultdict
        grouped = defaultdict(list)
        for d in deps:
            src = d.source.replace("_", " ").title()
            tgt = d.target.replace("_", " ").title()
            if tgt not in grouped[src]:
                grouped[src].append(tgt)
                
        for src, targets in grouped.items():
            # limit to top 2-3 targets (grouped is already sorted by strength from extractor)
            top_targets = targets[:3]
            targets_str = ", ".join(top_targets)
            lines.append(f"| {src} | {targets_str} |")
        lines.append("")"""

code = code.replace(old_dep_matrix, new_dep_matrix)

# Replace _section_module_map
old_module_map = """    def _section_module_map(self, lines, model, dp):
        lines.append("## Module & Component Map")
        lines.append("")
        if dp and dp.get("component_architecture_diagram"):
            lines.append("### Component Architecture (Layered View)")
            lines.append("")
            lines.append("```mermaid")
            lines.append(dp["component_architecture_diagram"])
            lines.append("```")
            lines.append("")


        rows = 0
        for comp in model.components:
            if rows >= 20: break
            name = comp.name.lower().replace("_", "_")
            if name == "__init__" or name.startswith("test_"): continue
            
            mod_title = comp.name.replace("_", " ").title()
            
            # Skip if purpose is missing or generic and we have no real evidence
            purpose = getattr(comp, 'purpose', '').strip()
            
            lines.append(f"### {mod_title}")
            lines.append("")
            
            if purpose:
                lines.append("**Purpose:**")
                lines.append(purpose)
                lines.append("")
            
            consumes = getattr(comp, 'consumes', [])
            if consumes:
                lines.append("**Consumes:**")
                for c in consumes: lines.append(f"- {c}")
                lines.append("")
                
            produces = getattr(comp, 'produces', [])
            if produces:
                lines.append("**Produces:**")
                for p in produces: lines.append(f"- {p}")
                lines.append("")
                
            deps = getattr(comp, 'depends_on', [])
            if deps:
                lines.append("**Dependencies:**")
                for d in deps: lines.append(f"- {d}")
                lines.append("")
                
            artifacts = getattr(comp, 'artifacts', [])
            if artifacts:
                lines.append("**Artifacts:**")
                for a in artifacts: lines.append(f"- {a}")
                lines.append("")
                
            lines.append("---")
            lines.append("")
            rows += 1"""

new_module_map = """    def _section_module_map(self, lines, model, dp):
        lines.append("## Module & Component Map")
        lines.append("")
        if dp and dp.get("component_architecture_diagram"):
            lines.append("### Component Architecture (Layered View)")
            lines.append("")
            lines.append("```mermaid")
            lines.append(dp["component_architecture_diagram"])
            lines.append("```")
            lines.append("")

        lines.append("| Component | Purpose |")
        lines.append("|---|---|")
        
        rows = 0
        for comp in model.components:
            if rows >= 20: break
            name = comp.name.lower()
            if name == "__init__" or name.startswith("test_"): continue
            
            mod_title = comp.name.replace("_", " ").title()
            purpose = getattr(comp, 'purpose', '').strip().replace("\\n", " ")
            if not purpose:
                purpose = "Internal component."
                
            # If the purpose is too long, we extract a concise sentence.
            sentences = [s.strip() for s in purpose.split(".") if s.strip()]
            concise_purpose = sentences[0] + "." if sentences else purpose
            
            lines.append(f"| {mod_title} | {concise_purpose} |")
            rows += 1
            
        lines.append("")"""

# Let's check if the replace will fail due to exact matching issues by doing a regex or substring search
import sys
if old_dep_matrix in code:
    print("Found exact dep matrix.")
else:
    print("WARNING: Exact match failed for dep matrix")
    
if "def _section_module_map(self, lines, model, dp):" in code:
    # Need to substring match
    start = code.find("def _section_module_map(self, lines, model, dp):")
    end = code.find("def _section_enterprise_diagrams(self, lines, model, dp):")
    if start != -1 and end != -1:
        code = code[:start] + new_module_map + "\n\n    " + code[end:]
        print("Replaced section_module_map")

with open("backend/document_generator/lld_generator.py", "w") as f:
    f.write(code)

print("Conciseness patch applied.")
