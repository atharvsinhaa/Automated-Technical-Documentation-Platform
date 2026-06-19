import re

with open("backend/object_model_extractor/extractor.py", "r") as f:
    code = f.read()

# 1. Update extract method
old_deps = "model.dependencies = self._extract_dependencies(ir, kg)"
new_deps = """model.dependencies = self._extract_dependencies(ir, kg)
        model.circular_dependencies = self._extract_circular_dependencies(ir, kg, model.dependencies)
        model.entry_points = self._extract_entrypoints(ir, kg)"""
code = code.replace(old_deps, new_deps)

# 2. Add methods at the end of the class
# Find the end of the class. A good anchor is the end of _build_system_overview or we can just append if we find the last method.
# Let's insert them before `def _build_system_overview`

old_overview = "def _build_system_overview(self, ir: SemanticIR, model: LLDModel) -> Optional[str]:"
new_methods = """def _extract_circular_dependencies(self, ir: SemanticIR, kg: Optional[KnowledgeGraph], deps: List[LLDDependency]) -> List[LLDCircularDependency]:
        from collections import defaultdict
        adj = defaultdict(list)
        for dep in deps:
            adj[dep.source].append(dep.target)
            
        cycles = []
        visited = set()
        path = []
        
        def dfs(node):
            if node in path:
                idx = path.index(node)
                cycle = path[idx:] + [node]
                min_idx = cycle[:-1].index(min(cycle[:-1]))
                can_cycle = cycle[min_idx:-1] + cycle[:min_idx] + [cycle[min_idx]]
                if can_cycle not in cycles:
                    cycles.append(can_cycle)
                return
            if node in visited: return
            visited.add(node)
            path.append(node)
            for neighbor in adj[node]: dfs(neighbor)
            path.pop()
            
        for node in list(adj.keys()):
            dfs(node)
            
        circulars = []
        for cycle in cycles[:5]:
            root_cause = f"Direct architectural entanglement where {cycle[-2]} invokes logic belonging to {cycle[0]}."
            affected_files = []
            affected_classes = []
            if kg:
                for n_name in cycle:
                    for node in kg.nodes.values():
                        if n_name.lower() in node.name.lower():
                            affected_files.append(node.file_path)
                            if node.node_type == "CLASS": affected_classes.append(node.name)
            
            circulars.append(LLDCircularDependency(
                cycle_path=cycle,
                root_cause=root_cause,
                affected_files=list(set(affected_files)),
                affected_classes=list(set(affected_classes)),
                recommended_refactor=f"Extract the shared interface or data model into a common library, or inject {cycle[-2]}'s dependencies via an interface to decouple it from {cycle[0]}."
            ))
        return circulars

    def _extract_entrypoints(self, ir: SemanticIR, kg: Optional[KnowledgeGraph]) -> List[LLDEntryPoint]:
        entry_points = []
        if kg:
            api_eps = kg.nodes_by_type("API_ENDPOINT")
            cli_mains = [n for n in kg.nodes_by_type("FUNCTION") if n.name in ("main", "cli", "run", "entry")]
            for ep in api_eps:
                entry_points.append(LLDEntryPoint(name=ep.name, evidence=[f"API Request to {ep.name} in {ep.file_path}"]))
            for cli in cli_mains:
                entry_points.append(LLDEntryPoint(name=cli.name, evidence=[f"CLI command {cli.name} in {cli.file_path}"]))
        return entry_points

    def _build_system_overview(self, ir: SemanticIR, model: LLDModel) -> Optional[str]:"""

code = code.replace(old_overview, new_methods)

# Fix LLDComponent invocation to include kg
old_comp_call = "model.components = self._extract_components(ir)"
new_comp_call = "model.components = self._extract_components(ir, kg)"
code = code.replace(old_comp_call, new_comp_call)

old_comp_def = "def _extract_components(self, ir: SemanticIR) -> List[LLDComponent]:"
new_comp_def = "def _extract_components(self, ir: SemanticIR, kg: Optional[KnowledgeGraph] = None) -> List[LLDComponent]:"
code = code.replace(old_comp_def, new_comp_def)

# Add imports for LLDCircularDependency, LLDEntryPoint
old_imports = "LLDTypeAlias,"
new_imports = "LLDTypeAlias,\n    LLDCircularDependency,\n    LLDEntryPoint,"
code = code.replace(old_imports, new_imports)

with open("backend/object_model_extractor/extractor.py", "w") as f:
    f.write(code)

print("Patch applied to extractor.py")
