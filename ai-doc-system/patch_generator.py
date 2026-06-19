import re

with open("backend/document_generator/lld_generator.py", "r") as f:
    code = f.read()

# 1. Circular dependencies
old_circ = """    def _section_circular_dependencies(self, lines, model):
        # Build adjacency list
        from collections import defaultdict
        adj = defaultdict(list)
        for dep in getattr(model, 'dependencies', []):
            adj[dep.source].append(dep.target)
            
        def find_cycles():
            cycles = []
            visited = set()
            path = []
            
            def dfs(node):
                if node in path:
                    idx = path.index(node)
                    cycle = path[idx:] + [node]
                    # Canonicalize cycle to avoid duplicates
                    min_idx = cycle[:-1].index(min(cycle[:-1]))
                    can_cycle = cycle[min_idx:-1] + cycle[:min_idx] + [cycle[min_idx]]
                    if can_cycle not in cycles:
                        cycles.append(can_cycle)
                    return
                if node in visited:
                    return
                    
                visited.add(node)
                path.append(node)
                for neighbor in adj[node]:
                    dfs(neighbor)
                path.pop()
                
            for node in list(adj.keys()):
                dfs(node)
            return cycles
            
        cycles = find_cycles()
        if not cycles:
            return
            
        lines.append("## Circular Dependency Analysis")
        lines.append("")
        for cycle in cycles[:5]:
            cycle_str = " → ".join(cycle)
            lines.append(f"**Cycle:** `{cycle_str}`")
            lines.append("")
            lines.append(f"**Cause:** Direct architectural entanglement where {cycle[-2]} invokes logic belonging to {cycle[0]}.")
            lines.append("")
            lines.append(f"**Recommendation:** Extract the shared interface or data model into a common library, or inject {cycle[-2]}'s dependencies via an interface to decouple it from {cycle[0]}.")
            lines.append("")"""

new_circ = """    def _section_circular_dependencies(self, lines, model):
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
code = code.replace(old_circ, new_circ)

# 2. Error Analysis
old_err = """    def _section_error_analysis(self, lines, model):
        error_paths = getattr(model, 'error_paths', [])
        if not error_paths:
            return
            
        lines.append("## Critical Error Paths")
        lines.append("")
        lines.append("| Exception | Trigger (Source) | Impact / Recovery |")
        lines.append("|---|---|---|")
        
        # Sort and deduplicate
        seen = set()
        for ep in error_paths:
            key = (ep.error_type, ep.source)
            if key in seen: continue
            seen.add(key)
            if len(seen) > 10: break
            
            trigger = ep.source.replace("_", " ").title()
            recovery = ep.recovery_strategy or ep.handler or "Propagated to caller"
            lines.append(f"| `{ep.error_type}` | {trigger} | {recovery} |")
            
        lines.append("")"""

new_err = """    def _section_error_analysis(self, lines, model):
        error_paths = getattr(model, 'error_paths', [])
        if not error_paths:
            return
            
        lines.append("## Critical Error Paths")
        lines.append("")
        lines.append("| Exception | Trigger | Affected Component | Impact | Recovery | Severity |")
        lines.append("|---|---|---|---|---|---|")
        
        seen = set()
        for ep in error_paths:
            key = (ep.error_type, ep.source)
            if key in seen: continue
            seen.add(key)
            if len(seen) > 10: break
            
            trigger = getattr(ep, 'trigger', ep.source)
            component = getattr(ep, 'affected_component', ep.source)
            impact = getattr(ep, 'impact', 'Unknown')
            severity = getattr(ep, 'severity', 'Unknown')
            recovery = ep.recovery_strategy or ep.handler or "Propagated to caller"
            lines.append(f"| `{ep.error_type}` | {trigger} | {component} | {impact} | {recovery} | {severity} |")
            
        lines.append("")"""
code = code.replace(old_err, new_err)

with open("backend/document_generator/lld_generator.py", "w") as f:
    f.write(code)

print("Patch applied")
