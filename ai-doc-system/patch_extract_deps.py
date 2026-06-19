with open("backend/object_model_extractor/extractor.py", "r") as f:
    code = f.read()

old_ext = """    def _extract_dependencies(self, ir: SemanticIR, kg: Optional[KnowledgeGraph]) -> List[LLDDependency]:
        \"\"\"Extract directed dependency edges between components.\"\"\"
        seen = set()
        deps = []
        for rel in ir.relationships:
            key = (rel.source, rel.target, rel.relationship_type)
            if key in seen:
                continue
            seen.add(key)
            deps.append(LLDDependency(
                source=rel.source,
                target=rel.target,
                dependency_type=rel.relationship_type or "DEPENDS_ON",
                is_circular=False,
            ))
        # Simple circular check: A→B and B→A
        edge_set = {(d.source, d.target) for d in deps}
        for dep in deps:
            if (dep.target, dep.source) in edge_set:
                dep.is_circular = True
        return deps[:30]  # cap at 30"""

new_ext = """    def _extract_dependencies(self, ir: SemanticIR, kg: Optional[KnowledgeGraph]) -> List[LLDDependency]:
        \"\"\"Extract directed dependency edges between components.\"\"\"
        from collections import defaultdict
        
        # Group by (source, target)
        edge_groups = defaultdict(list)
        for rel in ir.relationships:
            if rel.source != rel.target:
                edge_groups[(rel.source, rel.target)].append(rel.relationship_type or "DEPENDS_ON")
                
        deps = []
        for (source, target), types in edge_groups.items():
            count = len(types)
            if count > 3:
                strength = "High"
            elif count > 1:
                strength = "Medium"
            else:
                strength = "Low"
                
            # Determine dependency type
            all_types = " ".join(types).upper()
            if "API" in all_types or "REST" in all_types:
                dep_type = "API Dependency"
                purpose = f"Consumes API from {target}"
            elif "DATA" in all_types or "DB" in all_types or "STORE" in target.upper() or "DATABASE" in target.upper():
                dep_type = "Data Dependency"
                purpose = f"Persists or retrieves data via {target}"
            elif "SERVICE" in target.upper() or "MANAGER" in target.upper() or "CALLS" in all_types:
                dep_type = "Service Dependency"
                purpose = f"Invokes domain logic in {target}"
            elif "INFRA" in target.upper() or "CLIENT" in target.upper():
                dep_type = "Infrastructure Dependency"
                purpose = f"Utilizes infrastructure via {target}"
            else:
                dep_type = "Runtime Dependency"
                purpose = f"Relies on {target} at runtime"
                
            deps.append(LLDDependency(
                source=source,
                target=target,
                dependency_type=dep_type,
                is_circular=False,
                strength=strength,
                purpose=purpose
            ))
            
        # Simple circular check: A→B and B→A
        edge_set = {(d.source, d.target) for d in deps}
        for dep in deps:
            if (dep.target, dep.source) in edge_set:
                dep.is_circular = True
                
        # Limit to top strongest dependencies per component
        # We'll just sort by strength (High > Medium > Low) and limit to top 4 per component
        strength_val = {"High": 3, "Medium": 2, "Low": 1}
        deps.sort(key=lambda d: strength_val.get(d.strength, 0), reverse=True)
        
        filtered_deps = []
        comp_counts = defaultdict(int)
        for d in deps:
            if comp_counts[d.source] < 4:
                comp_counts[d.source] += 1
                filtered_deps.append(d)
                
        return filtered_deps"""

code = code.replace(old_ext, new_ext)

with open("backend/object_model_extractor/extractor.py", "w") as f:
    f.write(code)

print("Patched extractor dependencies.")
