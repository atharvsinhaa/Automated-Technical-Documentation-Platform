with open("backend/document_generator/lld_generator.py", "r") as f:
    code = f.read()

old_block = """        if dp and dp.get("transformation_flow_diagram"):
            lines.append("## Data Lineage (KG → IR → AIM)")
            lines.append("")
            lines.append("```mermaid")
            lines.append(dp["transformation_flow_diagram"])
            lines.append("```")
            lines.append("")"""

new_block = """        if dp and dp.get("transformation_flow_diagram"):
            lines.append("## Data Lineage Transformation")
            lines.append("")
            
            diag = dp["transformation_flow_diagram"]
            if diag.startswith("flowchart"):
                lines.append("```mermaid")
                lines.append("%%{init: {'themeVariables': {'fontSize': '12px', 'fontFamily': 'arial'}}}%%")
                lines.append(diag)
                lines.append("```")
            else:
                lines.append(diag)
            lines.append("")"""

code = code.replace(old_block, new_block)

with open("backend/document_generator/lld_generator.py", "w") as f:
    f.write(code)

print("Patched lld_generator for data lineage fallback.")
