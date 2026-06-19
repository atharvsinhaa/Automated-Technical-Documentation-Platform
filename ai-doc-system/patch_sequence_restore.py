import re

with open("backend/diagram_generator/lld_sequence_generator.py", "r") as f:
    code = f.read()

# 1. Pipeline diagram
old_pipe = """    def _generate_pipeline_diagram(self, model: LLDModel) -> str:
        if not model.sequence_flows: return ""
        lines = [
            "%%{init: {'themeVariables': {'fontSize': '12px', 'fontFamily': 'arial'}}}%%",
            "flowchart LR",
            "    classDef proc fill:#e8f5e9,stroke:#388e3c,stroke-width:2px,color:#1b5e20",
            ""
        ]
        
        flow = model.sequence_flows[0]
        nodes = set()
        edges = []
        for step in flow.steps:
            for sep in ("-->>", "->>", "→"):
                if sep in step:
                    parts = step.split(sep, 1)
                    src = self._safe_id(parts[0].strip())
                    rest = parts[1].strip()
                    if ":" in rest:
                        tgt = self._safe_id(rest.split(":", 1)[0].strip())
                        action = rest.split(":", 1)[1].strip()
                    else:
                        tgt = self._safe_id(rest)
                        action = "calls"
                    nodes.add(src)
                    nodes.add(tgt)
                    edges.append(f"    {src} -->|{action}| {tgt}")
                    break
                    
        for n in nodes:
            lines.append(f"    {n}[{n.replace('_', ' ')}]:::proc")
        lines.append("")
        lines.extend(edges)
        
        return "\\n".join(lines)"""

new_pipe = """    def _generate_pipeline_diagram(self, model: LLDModel) -> str:
        \"\"\"
        Pipeline Flow Diagram
        Repository -> AST -> Dependency Extractor -> Knowledge Graph -> Semantic IR -> AIM -> HLD/LLD
        \"\"\"
        lines = [
            "%%{init: {'themeVariables': {'fontSize': '12px', 'fontFamily': 'arial'}}}%%",
            "flowchart LR",
            "    classDef item fill:#f3e5f5,stroke:#ab47bc,stroke-width:2px,color:#4a148c",
            "    classDef proc fill:#e8f5e9,stroke:#388e3c,stroke-width:2px,color:#1b5e20",
            "    classDef doc fill:#fff3e0,stroke:#f57c00,stroke-width:2px,color:#e65100",
            "",
            "    R[Repository]:::item",
            "    A[AST Generation]:::proc",
            "    D[Dependency Extractor]:::proc",
            "    K[Knowledge Graph]:::item",
            "    S[Semantic IR]:::item",
            "    M[Architecture Intelligence Model]:::item",
            "    H[HLD / LLD Documents]:::doc",
            "",
            "    R -->|Source Code| A",
            "    A -->|Universal AST| D",
            "    D -->|Nodes & Edges| K",
            "    K -->|Graph Context| S",
            "    S -->|Semantic Context| M",
            "    M -->|Enterprise View| H"
        ]
        return "\\n".join(lines)"""
code = code.replace(old_pipe, new_pipe)

with open("backend/diagram_generator/lld_sequence_generator.py", "w") as f:
    f.write(code)

print("Restored original pipeline diagram")
