with open("backend/diagram_generator/lld_sequence_generator.py", "r") as f:
    code = f.read()

code = code.replace(
    'existing_comp_names = [c.name.lower() for c in getattr(model, \'components\', [])]',
    'existing_comp_names = [c.name.lower().replace("_", " ") for c in getattr(model, \'components\', [])]'
)

old_stages = """        pipeline_stages = [
            ("ast_engine", "AST", "Universal AST", "Repository Source Code", "AST Nodes"),
            ("dependency_extractor", "DEP", "Dependency Graph", "AST Nodes", "Raw Dependencies"),
            ("knowledge_graph", "KG", "Knowledge Graph", "Raw Dependencies", "Graph Model"),
            ("semantic_ir", "IR", "Semantic IR", "Graph Model", "Normalized Semantic Model"),
            ("architecture_intelligence", "AIM", "Architecture Intelligence", "Semantic Model", "Architecture Intelligence Model"),
            ("document_generator", "HLD", "HLD / LLD Models", "Architecture Intelligence Model", "Markdown Documents"),
            ("docx_service", "DOCX", "DOCX Output", "Markdown Documents", "DOCX Artifacts")
        ]"""

new_stages = """        pipeline_stages = [
            ("ast engine", "AST", "Universal AST", "Repository Source Code", "AST Nodes"),
            ("universal ast", "AST", "Universal AST", "Repository Source Code", "AST Nodes"),
            ("dependency extractor", "DEP", "Dependency Graph", "AST Nodes", "Raw Dependencies"),
            ("knowledge graph", "KG", "Knowledge Graph", "Raw Dependencies", "Graph Model"),
            ("semantic ir", "IR", "Semantic IR", "Graph Model", "Normalized Semantic Model"),
            ("architecture intelligence", "AIM", "Architecture Intelligence", "Semantic Model", "Architecture Intelligence Model"),
            ("document generator", "HLD", "HLD / LLD Models", "Architecture Intelligence Model", "Markdown Documents"),
            ("docx service", "DOCX", "DOCX Output", "Markdown Documents", "DOCX Artifacts")
        ]"""

code = code.replace(old_stages, new_stages)

with open("backend/diagram_generator/lld_sequence_generator.py", "w") as f:
    f.write(code)

print("Fixed component names.")
