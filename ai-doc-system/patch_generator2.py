import re

with open("backend/document_generator/lld_generator.py", "r") as f:
    code = f.read()

# 1. Validation Logic Update
old_val = """        # Architecture evidence
        arch_ev = getattr(model, 'architecture_pattern_evidence', None)
        if not arch_ev or "No structural evidence" in arch_ev:
            warnings.append("Validation Failed: Architecture unsupported by evidence. Suppressing Arch details.")
            flags["suppress_arch"] = True
            
        # Mock/Test contamination in tech stack
        for comp in getattr(model, 'components', []):
            tech = getattr(comp, 'internal_tech', "")
            if "test" in tech.lower() or "mock" in tech.lower():
                warnings.append(f"Validation Failed: Test contamination detected in {comp.name} tech stack.")"""

new_val = """        # Architecture evidence
        arch_ev = getattr(model, 'architecture_pattern_evidence', None)
        if not arch_ev or "No structural evidence" in arch_ev:
            warnings.append("Validation Failed: Architecture unsupported by evidence. Suppressing Arch details.")
            flags["suppress_arch"] = True
            
        # Mock/Test contamination in tech stack
        for comp in getattr(model, 'components', []):
            tech_evidence = getattr(comp, 'tech_evidence', [])
            for e in tech_evidence:
                if "test" in e.lower() or "mock" in e.lower():
                    warnings.append(f"Validation Failed: Test contamination detected in {comp.name} tech evidence.")
                    
            if "Transforms" in getattr(comp, 'purpose', ""):
                warnings.append(f"Validation Failed: Generic signature-based heuristics detected in {comp.name}.")"""

code = code.replace(old_val, new_val)

# 2. Snapshot (Architecture) Update
old_snap = """        arch = model.architecture_pattern or "N/A"
        arch_conf = getattr(model, 'architecture_pattern_confidence', "Medium")
        
        # Format the values exactly as expected by tests
        if arch_conf:
            arch = f"{arch} ({arch_conf} Confidence)"
            
        if flags.get("suppress_arch"):
            arch = "Unknown (Insufficient structural evidence)"
            
        entry = ", ".join(model.entrypoints[:3]) if getattr(model, 'entrypoints', None) else "N/A"
        ext_str = ", ".join([e.name for e in model.external_integrations]) if getattr(model, 'external_integrations', None) else "None detected"
        circular = len([d for d in getattr(model, 'dependencies', []) if d.is_circular])"""

new_snap = """        arch = model.architecture_pattern or "N/A"
        arch_conf = getattr(model, 'architecture_pattern_confidence', "N/A")
        arch_ev = getattr(model, 'architecture_pattern_evidence', "")
        
        if flags.get("suppress_arch"):
            arch = "Unknown"
            arch_conf = "None"
            arch_ev = "Not enough evidence detected."
            
        entry = ", ".join([e.name for e in getattr(model, 'entry_points', [])]) if getattr(model, 'entry_points', None) else "N/A"
        ext_str = ", ".join([e.name for e in model.external_integrations]) if getattr(model, 'external_integrations', None) else "None detected"
        circular = len(getattr(model, 'circular_dependencies', []))"""
code = code.replace(old_snap, new_snap)

# 3. Module Map Update
old_mod = """        lines.append("| Module | Responsibility | Files | Receives | Returns | Tech Stack |")
        lines.append("|---|---|---|---|---|---|")
        
        rows = 0
        for comp in model.components:
            if rows >= 20: break
            name = comp.name.lower().replace(" ", "_")
            if name == "__init__" or name.startswith("test_"): continue
            
            sub = getattr(comp, 'sub_modules', "—")
            if sub == "Single-file module": sub = "—"
            
            rec = getattr(comp, 'receives', "—")
            ret = getattr(comp, 'returns', "—")
            
            tech = getattr(comp, 'internal_tech', "—")
            if tech == "Standard Python": tech = "—"
            
            desc = getattr(comp, 'description', "")
            if not desc:
                if rec != "—" and ret != "—":
                    desc = f"Transforms {rec} into {ret}."
                else:
                    desc = "Core processing module."
            
            if sub == "—" and rec == "—" and ret == "—" and tech == "—":
                continue
                
            mod_title = comp.name.replace("_", " ").title()
            
            if sub and sub != "—":
                files = [x.strip() for x in sub.split(",")]
                if len(files) > 5:
                    sub = ", ".join(files[:5]) + f" +{len(files)-5} more"
            
            lines.append(f"| {mod_title} | {desc} | {sub} | {rec} | {ret} | {tech} |")
            rows += 1
            
        lines.append("")"""

new_mod = """        rows = 0
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
code = code.replace(old_mod, new_mod)

with open("backend/document_generator/lld_generator.py", "w") as f:
    f.write(code)

print("Patch applied to generator2")
