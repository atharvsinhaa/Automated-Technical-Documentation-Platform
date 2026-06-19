with open("backend/document_generator/lld_generator.py", "r") as f:
    code = f.read()

old_mod = """        rows = 0
        for comp in model.components:
            if rows >= 20: break
            name = comp.name.lower().replace(" ", "_")
            if name == "__init__" or name.startswith("test_"): continue
            
            mod_title = comp.name.replace("_", " ").title()
            
            lines.append(f"### {mod_title}")
            lines.append(f"**Purpose:** {getattr(comp, 'purpose', 'Core processing module')}")
            
            consumes = getattr(comp, 'consumes', [])
            produces = getattr(comp, 'produces', [])
            deps = getattr(comp, 'depends_on', [])
            artifacts = getattr(comp, 'artifacts', [])
            
            lines.append(f"**Consumes:** {', '.join(consumes) if consumes else 'None'}")
            lines.append(f"**Produces:** {', '.join(produces) if produces else 'None'}")
            lines.append(f"**Dependencies:** {', '.join(deps) if deps else 'None'}")
            lines.append(f"**Artifacts:** {', '.join(artifacts) if artifacts else 'None'}")
            
            tech_ev = getattr(comp, 'tech_evidence', [])
            if tech_ev:
                lines.append(f"**Technology:** {getattr(comp, 'technology', 'None')}")
                lines.append("**Evidence:**")
                for e in tech_ev:
                    lines.append(f"- {e}")
            else:
                lines.append("**Technology:** None")
                
            lines.append("")
            rows += 1"""

new_mod = """        rows = 0
        for comp in model.components:
            if rows >= 20: break
            name = comp.name.lower().replace(" ", "_")
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
                lines.append("**Artifacts Generated:**")
                for a in artifacts: lines.append(f"- {a}")
                lines.append("")
            
            tech_ev = getattr(comp, 'tech_evidence', [])
            if tech_ev:
                tech = getattr(comp, 'technology', 'None')
                if tech != "None":
                    lines.append(f"**Technology:** {tech}")
                    lines.append("**Evidence:**")
                    for e in tech_ev:
                        lines.append(f"- {e}")
                    lines.append("")
                
            rows += 1"""

code = code.replace(old_mod, new_mod)

with open("backend/document_generator/lld_generator.py", "w") as f:
    f.write(code)

print("Patched module map.")
