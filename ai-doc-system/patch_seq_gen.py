with open("backend/diagram_generator/lld_sequence_generator.py", "r") as f:
    code = f.read()

old_func = """    def _generate_dependency_diagram(self, model: LLDModel) -> str:
        \"\"\"
        Generate a flowchart showing dependency edges between components.
        \"\"\"
        if not model.dependencies:
            return ""

        lines = ["flowchart LR", ""]

        # Styling
        lines.append("    classDef comp fill:#e3f2fd,stroke:#1976d2,stroke-width:2px,color:#0d47a1")
        lines.append("    classDef circular fill:#fce4ec,stroke:#e91e63,stroke-width:2px,color:#880e4f")
        lines.append("")

        # Collect all nodes and restrict to top 4 edges per component
        nodes = set()
        edges = []
        dep_counts = {}
        for dep in model.dependencies:
            if dep_counts.get(dep.source, 0) >= 4: continue
            dep_counts[dep.source] = dep_counts.get(dep.source, 0) + 1
            edges.append(dep)
            nodes.add(dep.source)
            nodes.add(dep.target)

        # Declare nodes
        for node in sorted(nodes):
            safe = self._safe_id(node)
            lbl = node.replace("_", " ").title()
            
            # Check if this node is in any circular dependency
            is_circ = False
            for circ in model.circular_dependencies:
                if node in circ.affected_classes or node in circ.cycle_path:
                    is_circ = True
                    break
                    
            cls = ":::circular" if is_circ else ":::comp"
            lines.append(f"    {safe}[\"{lbl}\"]{cls}")

        lines.append("")

        # Declare edges
        for dep in edges:
            src = self._safe_id(dep.source)
            tgt = self._safe_id(dep.target)
            
            rel = getattr(dep, 'dependency_type', 'uses').lower()
            if rel == "depends_on": rel = "uses"
            
            # Special styling for circular edges
            if getattr(dep, 'is_circular', False):
                lines.append(f"    {src} -- \"{rel} ⚠️\" --> {tgt}")
                lines.append(f"    linkStyle {len(lines)-2} stroke:#e91e63,stroke-width:2px,color:#e91e63;")
            else:
                lines.append(f"    {src} -- \"{rel}\" --> {tgt}")

        return "\n".join(lines)"""

new_func = """    def _generate_dependency_diagram(self, model: LLDModel) -> str:
        \"\"\"
        Generate a flowchart showing dependency edges between components.
        (Disabled in favor of Dependency Matrix)
        \"\"\"
        return \"\""""

code = code.replace(old_func, new_func)

with open("backend/diagram_generator/lld_sequence_generator.py", "w") as f:
    f.write(code)

print("Patched sequence generator.")
