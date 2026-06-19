import re

with open("backend/diagram_generator/lld_sequence_generator.py", "r") as f:
    code = f.read()

old_func = """    def _generate_transformation_flow(self, model: LLDModel) -> str:
        if not model.dependencies: return ""
        lines = [
            "%%{init: {'themeVariables': {'fontSize': '12px', 'fontFamily': 'arial'}}}%%",
            "flowchart LR",
            "    classDef comp fill:#e3f2fd,stroke:#1976d2,stroke-width:2px,color:#0d47a1"
        ]
        nodes = set()
        edges = []
        for dep in model.dependencies[:15]:
            src = self._safe_id(dep.source)
            tgt = self._safe_id(dep.target)
            nodes.add(src)
            nodes.add(tgt)
            edges.append(f"    {src} -->|{dep.dependency_type}| {tgt}")
            
        for n in nodes:
            lines.append(f"    {n}[{n.replace('_', ' ')}]:::comp")
            
        lines.append("")
        lines.extend(edges)
        return "\\n".join(lines)"""

new_func = """    def _generate_transformation_flow(self, model: LLDModel) -> str:
        # Define the strict linear pipeline stages for ai-doc-system lineage
        # Tuple: (Component substring to detect, Node ID, Node Label, Input Artifact, Output Artifact)
        pipeline_stages = [
            ("ast_engine", "AST", "Universal AST", "Repository Source Code", "AST Nodes"),
            ("dependency_extractor", "DEP", "Dependency Graph", "AST Nodes", "Raw Dependencies"),
            ("knowledge_graph", "KG", "Knowledge Graph", "Raw Dependencies", "Graph Model"),
            ("semantic_ir", "IR", "Semantic IR", "Graph Model", "Normalized Semantic Model"),
            ("architecture_intelligence", "AIM", "Architecture Intelligence", "Semantic Model", "Architecture Intelligence Model"),
            ("document_generator", "HLD", "HLD / LLD Models", "Architecture Intelligence Model", "Markdown Documents"),
            ("docx_service", "DOCX", "DOCX Output", "Markdown Documents", "DOCX Artifacts")
        ]
        
        # Check which stages exist
        existing_comp_names = [c.name.lower() for c in getattr(model, 'components', [])]
        
        proven_stages = []
        for stage in pipeline_stages:
            comp_sub, n_id, label, in_art, out_art = stage
            # if we find any component matching the substring
            if any(comp_sub in c for c in existing_comp_names):
                proven_stages.append(stage)
                
        # If we can't prove enough of the lineage (e.g. not ai-doc-system or heavily modified)
        if len(proven_stages) < 2:
            return "> **Note:** Data lineage could not be confidently determined."
            
        lines = [
            "flowchart TD",
            "    classDef dataNode fill:#f3e5f5,stroke:#8e24aa,stroke-width:2px,color:#4a148c"
        ]
        
        # Add the initial repository node since it's the root input
        lines.append('    repo["<b>Repository Source Code</b>"]:::dataNode')
        
        # Render the nodes
        prev_id = "repo"
        for i, stage in enumerate(proven_stages):
            comp_sub, n_id, label, in_art, out_art = stage
            lines.append(f'    {n_id}["<b>{label}</b><br/><i>Input: {in_art}</i><br/><i>Output: {out_art}</i>"]:::dataNode')
            lines.append(f"    {prev_id} --> {n_id}")
            prev_id = n_id
            
        return "\\n".join(lines)"""

code = code.replace(old_func, new_func)

with open("backend/diagram_generator/lld_sequence_generator.py", "w") as f:
    f.write(code)

print("Patched lld_sequence_generator data lineage.")
