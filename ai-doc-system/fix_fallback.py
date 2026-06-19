with open("backend/diagram_generator/lld_sequence_generator.py", "r") as f:
    code = f.read()

code = code.replace(
    'return "> **Note:** Data lineage could not be confidently determined."',
    'return ""'
)

with open("backend/diagram_generator/lld_sequence_generator.py", "w") as f:
    f.write(code)

with open("backend/document_generator/lld_generator.py", "r") as f:
    code2 = f.read()

old_block = """        if dp and dp.get("transformation_flow_diagram"):
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

new_block = """        lines.append("## Data Lineage Transformation")
        lines.append("")
        diag = dp.get("transformation_flow_diagram", "") if dp else ""
        if diag:
            lines.append("```mermaid")
            lines.append("%%{init: {'themeVariables': {'fontSize': '12px', 'fontFamily': 'arial'}}}%%")
            lines.append(diag)
            lines.append("```")
        else:
            lines.append("> **Note:** Data lineage could not be confidently determined.")
        lines.append("")"""

code2 = code2.replace(old_block, new_block)

with open("backend/document_generator/lld_generator.py", "w") as f:
    f.write(code2)

print("Fixed fallback.")
