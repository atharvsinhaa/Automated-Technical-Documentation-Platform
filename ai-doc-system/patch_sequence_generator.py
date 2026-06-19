with open("backend/diagram_generator/lld_sequence_generator.py", "r") as f:
    code = f.read()

old_dep = """        # Collect all nodes
        nodes = set()
        for dep in model.dependencies[:15]:
            nodes.add(dep.source)
            nodes.add(dep.target)"""

new_dep = """        # Collect all nodes and restrict to top 4 edges per component
        nodes = set()
        edges = []
        dep_counts = {}
        for dep in model.dependencies:
            if dep_counts.get(dep.source, 0) >= 4: continue
            dep_counts[dep.source] = dep_counts.get(dep.source, 0) + 1
            edges.append(dep)
            nodes.add(dep.source)
            nodes.add(dep.target)
"""

code = code.replace(old_dep, new_dep)

old_dep2 = """        # Declare edges
        for dep in model.dependencies[:15]:
            src = self._safe_id(dep.source)
            tgt = self._safe_id(dep.target)"""

new_dep2 = """        # Declare edges
        for dep in edges:
            src = self._safe_id(dep.source)
            tgt = self._safe_id(dep.target)"""

code = code.replace(old_dep2, new_dep2)

with open("backend/diagram_generator/lld_sequence_generator.py", "w") as f:
    f.write(code)

print("Patched sequence generator deps")
