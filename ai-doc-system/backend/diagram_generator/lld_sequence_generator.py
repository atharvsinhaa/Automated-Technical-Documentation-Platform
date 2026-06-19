"""
diagram_generator/lld_sequence_generator.py
────────────────────────────────────────────────────────────────
Enterprise LLD Diagram Generator — 6 Diagram Types.

Generates professional Class, Sequence, ERD, Dependency,
Component Architecture, and Deployment Unit diagrams from
the LLDModel.
"""

from __future__ import annotations

import re
from typing import Dict, List

from backend.object_model_extractor.models import LLDModel, LLDComponent

MERMAID_INIT = (
    '%%{init: {"theme": "base", "themeVariables": {'
    '"fontSize": "12px", "fontFamily": "Arial, sans-serif",'
    '"primaryColor": "#E3F2FD", "lineColor": "#555555",'
    '"edgeLabelBackground": "#ffffff"}}}%%\n'
)


class LLDSequenceGenerator:

    def _inject_config(self, mmd: str) -> str:
        if not mmd: return mmd
        config = "%%{init: {'themeVariables': {'fontSize': '12px', 'fontFamily': 'arial'}}}%%\n"
        if mmd.startswith("%%{init:"):
            # Don't inject if it already has one, or replace font size
            return mmd.replace("'fontSize': '14px'", "'fontSize': '12px'").replace("'fontSize': '24px'", "'fontSize': '12px'")
        return config + mmd

    def generate(self, model: LLDModel) -> Dict[str, str]:
        """
        Generate all 6 LLD diagram types from LLDModel.
        Returns a dictionary mapping diagram type to Mermaid code.
        """
        diagrams = {
            "object_interaction_diagram":      self._generate_object_interaction_diagram(model),
            "erd_diagram":                    self._generate_erd_diagram(model),
            "dependency_diagram":             self._generate_dependency_diagram(model),
            "component_architecture_diagram": self._generate_component_architecture_diagram(model),
            "full_system_diagram":            self._generate_full_system_diagram(model),
            "deployment_unit_diagram":        self._generate_deployment_unit_diagram(model),
            "layered_architecture_diagram":   self._generate_layered_architecture(model),
            "pipeline_flow_diagram":          self._generate_pipeline_diagram(model),
            "transformation_flow_diagram":    self._generate_transformation_flow(model),
        }
        
        # New multi-diagram sequence generation
        seq_diagrams = self._generate_sequence_diagrams(model)
        diagrams["sequence_diagram"] = seq_diagrams[0] if seq_diagrams else ""
        diagrams["sequence_diagram_2"] = seq_diagrams[1] if len(seq_diagrams) > 1 else ""
        diagrams["sequence_diagram_3"] = seq_diagrams[2] if len(seq_diagrams) > 2 else ""
        diagrams["sequence_diagram_4"] = seq_diagrams[3] if len(seq_diagrams) > 3 else ""

        result = {k: self._inject_config(v) for k, v in diagrams.items() if v}

        for key in result:
            if result[key] and not result[key].startswith("%%{init"):
                result[key] = MERMAID_INIT + result[key]
        return result

    def _safe_id(self, text: str) -> str:
        if not text:
            return "unknown"
        safe = re.sub(r"[^a-zA-Z0-9_]", "_", text)
        if safe.lower() in ("actor", "participant", "loop", "alt", "opt", "end", "activate", "deactivate"):
            safe = safe + "_Node"
        return safe

    # ══════════════════════════════════════════════════════════
    #  Class Diagram — FIXED broken signature rendering
    # ══════════════════════════════════════════════════════════

    def _clean_method_sig(self, raw_sig: str, name: str, params: List[str], return_type: str) -> str:
        """
        Produce a clean Mermaid class method signature.
        Output: methodName(param1, param2) ReturnType
        """
        # Filter params — drop 'self', 'cls', empty strings
        clean_params = [p for p in (params or []) if p and p not in ("self", "cls")]
        param_str = ", ".join(clean_params[:4])
        ret = return_type or "Any"
        clean_name = name or raw_sig.split("(")[0].strip() if raw_sig else "unknown"
        if not clean_name:
            return ""
        # Skip dunder methods except __init__
        if clean_name.startswith("__") and clean_name != "__init__":
            return ""
        if clean_name == "__init__":
            clean_name = "constructor"
            
        ret = ret.replace("[", "~").replace("]", "~")
        param_str = param_str.replace("[", "~").replace("]", "~")
        return f"{clean_name}({param_str}) {ret}"

    def _generate_layered_architecture(self, model: LLDModel) -> str:
        """
        Layered Architecture Diagram replacing the Class Diagram.
        AST Layer -> Knowledge Graph Layer -> Semantic IR Layer -> Architecture Intelligence Layer -> Document Generation Layer.
        """
        lines = [
            "%%{init: {'themeVariables': {'fontSize': '12px', 'fontFamily': 'arial'}}}%%",
            "flowchart LR",
            "    classDef layer fill:#e3f2fd,stroke:#1976d2,stroke-width:2px,color:#0d47a1",
            "    classDef node fill:#fff,stroke:#64b5f6,stroke-width:1px,color:#1565c0",
            "",
            "    subgraph L1 [AST Layer]",
            "        direction TB",
            "        UniversalAst[Universal AST Node]:::node",
            "        PythonAst[Python Normalizer]:::node",
            "        JsAst[JS/TS Normalizer]:::node",
            "    end",
            "    class L1 layer",
            "",
            "    subgraph L2 [Knowledge Graph Layer]",
            "        direction TB",
            "        GraphBuilder[Graph Builder]:::node",
            "        DependencyExtractor[Dependency Extractor]:::node",
            "        CrossLanguageLinker[Cross Language Linker]:::node",
            "    end",
            "    class L2 layer",
            "",
            "    subgraph L3 [Semantic IR Layer]",
            "        direction TB",
            "        IrBuilder[IR Builder]:::node",
            "        SemanticBridge[Semantic Bridge]:::node",
            "    end",
            "    class L3 layer",
            "",
            "    subgraph L4 [Architecture Intelligence Layer]",
            "        direction TB",
            "        AimBuilder[AIM Builder]:::node",
            "        ServiceArchitect[Service Architect]:::node",
            "        CapabilityModeler[Capability Modeler]:::node",
            "    end",
            "    class L4 layer",
            "",
            "    subgraph L5 [Document Generation Layer]",
            "        direction TB",
            "        HldGenerator[HLD Generator]:::node",
            "        LldGenerator[LLD Generator]:::node",
            "        NarrativeEngine[Narrative Engine]:::node",
            "    end",
            "    class L5 layer",
            "",
            "    L1 --> L2",
            "    L2 --> L3",
            "    L3 --> L4",
            "    L4 --> L5"
        ]
        return "\n".join(lines)

    def _generate_pipeline_diagram(self, model: LLDModel) -> str:
        """
        Pipeline Flow Diagram
        Repository -> AST -> Dependency Extractor -> Knowledge Graph -> Semantic IR -> AIM -> HLD/LLD
        """
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
        return "\n".join(lines)

    def _generate_transformation_flow(self, model: LLDModel) -> str:
        # Define the strict linear pipeline stages for ai-doc-system lineage
        # Tuple: (Component substring to detect, Node ID, Node Label, Input Artifact, Output Artifact)
        components = getattr(model, 'components', [])
        if not components:
            return ""

        lines = [
            "flowchart LR",
            "    classDef dataNode fill:#f3e5f5,stroke:#8e24aa,stroke-width:2px,color:#4a148c",
            "    classDef compNode fill:#e3f2fd,stroke:#1565c0,stroke-width:2px,color:#0d47a1"
        ]

        edges = set()
        nodes_added = set()

        import re
        for comp in components:
            comp_id = "comp_" + re.sub(r'[^A-Za-z0-9]', '_', comp.name)
            
            # Only include components that actually participate in data flow
            if comp.consumes or comp.produces:
                if comp_id not in nodes_added:
                    lines.append(f'    {comp_id}["<b>{comp.name}</b>"]:::compNode')
                    nodes_added.add(comp_id)

            for art in comp.consumes:
                if art in ("External Request", "System Response"): continue
                art_id = "art_" + re.sub(r'[^A-Za-z0-9]', '_', art)
                if art_id not in nodes_added:
                    lines.append(f'    {art_id}["<i>{art}</i>"]:::dataNode')
                    nodes_added.add(art_id)
                edges.add(f"    {art_id} -->|consumes| {comp_id}")

            for art in comp.produces:
                if art in ("External Request", "System Response"): continue
                art_id = "art_" + re.sub(r'[^A-Za-z0-9]', '_', art)
                if art_id not in nodes_added:
                    lines.append(f'    {art_id}["<i>{art}</i>"]:::dataNode')
                    nodes_added.add(art_id)
                edges.add(f"    {comp_id} -->|produces| {art_id}")

        if not edges:
            return ""

        lines.extend(sorted(list(edges)))
        return "\n".join(lines)

    # ══════════════════════════════════════════════════════════
    #  Sequence Diagram — FIXED multi-participant rendering
    # ══════════════════════════════════════════════════════════

    def _generate_sequence_diagrams(self, model: LLDModel) -> List[str]:
        """
        Generate multiple individual sequence diagrams (up to 4).
        """
        if not model.sequence_flows:
            return []

        diagrams = []
        # Sort by steps length so most detailed flows get diagrams
        flows = sorted(model.sequence_flows, key=lambda f: len(f.steps), reverse=True)[:4]

        for flow in flows:
            diagrams.append(self._build_one_sequence_diagram(flow))

        return diagrams

    def _build_one_sequence_diagram(self, flow) -> str:
        """Builds a single Mermaid sequence diagram for one flow."""
        lines = ["sequenceDiagram", "    autonumber"]

        # Collect unique participants for this specific flow
        participants = []
        for step in flow.steps:
            for sep in ("-->>", "->>", "→"):
                if sep in step:
                    parts = step.split(sep, 1)
                    src = self._safe_id(parts[0].strip())
                    rest = parts[1].strip()
                    if ":" in rest:
                        tgt = self._safe_id(rest.split(":", 1)[0].strip())
                    else:
                        tgt = self._safe_id(rest)
                    for p in (src, tgt):
                        if p and p not in participants:
                            participants.append(p)
                    break

        if not participants:
            participants = ["Client", "System"]

        # Define participants with smart styling
        for p in participants:
            p_clean = p.replace("_", " ")
            if any(db in p.lower() for db in ("db", "database", "table", "collection", "redis", "store")):
                lines.append(f'    participant {p} as 🗄 {p_clean}')
            elif p.lower() in ("client", "user", "browser", "frontend"):
                lines.append(f'    actor {p} as 👤 {p_clean}')
            else:
                lines.append(f'    participant {p} as ⚙️ {p_clean}')

        lines.append("")

        for step in flow.steps:
            # Handle return steps explicitly generated by extraction
            if "-->>" in step or "return" in step.lower():
                sep = "-->>" if "-->>" in step else ("→" if "→" in step else "->")
                if sep in step:
                    parts = step.split(sep, 1)
                    src = self._safe_id(parts[0].strip())
                    rest = parts[1].strip()
                    if ":" in rest:
                        tgt, action = rest.split(":", 1)
                    else:
                        tgt, action = rest, "return"
                    tgt = self._safe_id(tgt.strip())
                    action_clean = action.strip()[:60]
                    
                    lines.append(f"    {src}-->>{tgt}: {action_clean}")
            # Handle standard forward calls
            elif "→" in step or "->" in step:
                sep = "→" if "→" in step else "->"
                parts = step.split(sep, 1)
                src = self._safe_id(parts[0].strip())
                rest = parts[1].strip()
                if ":" in rest:
                    tgt, action = rest.split(":", 1)
                else:
                    tgt, action = rest, "invoke"
                tgt = self._safe_id(tgt.strip())
                action_clean = action.strip()[:60]

                lines.append(f"    {src}->>{tgt}: {action_clean}")
            else:
                continue

        return "\n".join(lines)

    # ══════════════════════════════════════════════════════════
    #  Object Interaction Diagram — kept for backward compat
    # ══════════════════════════════════════════════════════════

    def _generate_object_interaction_diagram(self, model: LLDModel) -> str:
        # The user requested this low-value diagram to be completely removed.
        return None
        
        # We derive runtime interactions from composition, aggregation, and methods.
        for cls in model.classes:
            cid = self._safe_id(cls.name)
            
            has_relations = bool(cls.composition or cls.aggregation or cls.dependencies)
            if has_relations and cid not in drawn:
                lines.append(f'    {cid}["{cls.name} Instance"]:::obj')
                drawn.add(cid)
                
            for comp in cls.composition:
                comp_id = self._safe_id(comp)
                if comp_id not in drawn:
                    lines.append(f'    {comp_id}["{comp} Instance"]:::obj')
                    drawn.add(comp_id)
                lines.append(f'    {cid} -->|owns| {comp_id}')
                
            for agg in cls.aggregation:
                agg_id = self._safe_id(agg)
                if agg_id not in drawn:
                    lines.append(f'    {agg_id}["{agg} Instance"]:::obj')
                    drawn.add(agg_id)
                lines.append(f'    {cid} -.->|references| {agg_id}')
                
        if not drawn:
            return None
                
        return "\n".join(lines)

    # ══════════════════════════════════════════════════════════
    #  ERD Diagram — NEW
    # ══════════════════════════════════════════════════════════

    def _clean_erd_type(self, python_type: str) -> str:
        """Convert Python type annotations to Mermaid erDiagram types."""
        t = python_type.strip()
        # Strip wrappers
        for wrapper in ("Optional[", "List[", "Set[", "Dict[", "Tuple["):
            if t.startswith(wrapper):
                t = t[len(wrapper):].rstrip("]")
        # Map Python → SQL-compatible
        TYPE_MAP = {
            "str": "string", "int": "int", "float": "float",
            "bool": "boolean", "datetime": "datetime", "date": "date",
            "bytes": "binary", "Any": "string", "None": "string",
        }
        return TYPE_MAP.get(t, "string")

    def _generate_erd_diagram(self, model: LLDModel) -> str:
        """
        Generate a Mermaid erDiagram from LLDDatabaseObject entries.
        Falls back to class-based ERD when no DB objects are present.
        """
        db_objects = model.database_objects

        # Fallback: use classes as entities when no DB objects exist
        if not db_objects:
            if not model.classes:
                return ""
            # Convert classes to pseudo-DB entities
            lines = ["erDiagram", ""]
            for cls in model.classes[:6]:
                ename = self._safe_id(cls.name)
                lines.append(f"    {ename} {{")
                for fld in cls.fields[:6]:
                    fname = fld.split(":")[0].strip()
                    ftype = fld.split(":")[-1].strip() if ":" in fld else "string"
                    # Clean type for ER notation
                    fname_clean = self._safe_id(fname)
                    lines.append(f"        {self._clean_erd_type(ftype)} {fname_clean}")
                lines.append("    }")
                lines.append("")
            # Relationships from composition/aggregation
            known_names = {self._safe_id(c.name) for c in model.classes[:6]}
            for cls in model.classes[:6]:
                cname = self._safe_id(cls.name)
                for dep in cls.dependencies[:2]:
                    dname = self._safe_id(dep)
                    if dname in known_names and dname != cname:
                        lines.append(f'    {cname} ||--o{{ {dname} : "has"')
            return "\n".join(lines)

        # Real DB objects
        lines = ["erDiagram", ""]
        for dbo in db_objects[:8]:
            ename = self._safe_id(dbo.name)
            lines.append(f"    {ename} {{")
            for fld in dbo.fields[:8]:
                parts = fld.split()
                fname = self._safe_id(parts[0]) if parts else "field"
                ftype = parts[1] if len(parts) > 1 else "string"
                lines.append(f"        {self._clean_erd_type(ftype)} {fname}")
            lines.append("    }")
            lines.append("")
        # Relationships from DB relationships
        known_db = {self._safe_id(d.name) for d in db_objects[:8]}
        for dbo in db_objects[:8]:
            ename = self._safe_id(dbo.name)
            for rel in dbo.relationships[:3]:
                rname = self._safe_id(rel)
                if rname in known_db and rname != ename:
                    lines.append(f'    {ename} ||--o{{ {rname} : "references"')
        return "\n".join(lines)

    # ══════════════════════════════════════════════════════════
    #  Dependency Diagram — NEW
    # ══════════════════════════════════════════════════════════

    def _generate_dependency_diagram(self, model: LLDModel) -> str:
        """
        Generate a flowchart showing dependency edges between components.
        """
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
            nid = self._safe_id(node)
            is_circ = any(d.is_circular and (d.source == node or d.target == node) for d in model.dependencies)
            style = "circular" if is_circ else "comp"
            lines.append(f'    {nid}["{node}"]:::{style}')

        lines.append("")

        # Draw edges
        for dep in model.dependencies[:15]:
            src = self._safe_id(dep.source)
            tgt = self._safe_id(dep.target)
            label = dep.dependency_type.replace("_", " ").title()
            if dep.is_circular:
                lines.append(f'    {src} <-.->|{label}| {tgt}')
            else:
                lines.append(f'    {src} -->|{label}| {tgt}')

        return "\n".join(lines)

    # ══════════════════════════════════════════════════════════
    #  Component Architecture Diagram — NEW
    # ══════════════════════════════════════════════════════════

    def _generate_component_architecture_diagram(self, model: LLDModel) -> str:
        """
        Generate a Layer-Based Architecture view of the components.
        """
        if not model.components:
            return self._generate_full_system_diagram(model)

        lines = ["flowchart LR", ""]

        lines.append("    classDef layer fill:none,stroke:#455a64,stroke-width:2px,stroke-dasharray: 5 5")
        lines.append("    classDef comp fill:#e3f2fd,stroke:#1976d2,stroke-width:2px,color:#0d47a1")
        lines.append("")

        from collections import defaultdict
        layers = defaultdict(list)
        for comp in model.components:
            l = getattr(comp, 'layer', 'Application') or 'Application'
            layers[l].append(comp)

        # Standard layer order
        layer_order = ["Presentation", "Application", "Domain", "Infrastructure", "Platform"]
        sorted_layers = sorted(layers.keys(), key=lambda k: layer_order.index(k) if k in layer_order else 99)

        drawn_comps = set()
        for idx, layer_name in enumerate(sorted_layers):
            lines.append(f'    subgraph L{idx} ["{layer_name} Layer"]')
            lines.append('        direction TB')
            for comp in layers[layer_name][:8]:  # limit to 8 components per layer
                cid = self._safe_id(comp.name)
                lines.append(f'        {cid}["{comp.name}"]:::comp')
                drawn_comps.add(comp.name)
            lines.append('    end')
            lines.append(f'    class L{idx} layer')
            lines.append("")

        # Add relationships between layers instead of individual components to avoid spaghetti
        for idx in range(len(sorted_layers) - 1):
            lines.append(f'    L{idx} --> L{idx+1}')

        return "\n".join(lines)

    def _extract_service_responsibilities(self, cls_name: str, model: LLDModel) -> str:
        target_cls = next((c for c in model.classes if c.name == cls_name), None)
        if not target_cls or not target_cls.methods:
            return ""
        
        phrases = []
        for m in target_cls.methods[:3]:
            name = m.name.replace("_", " ").title()
            if name.startswith("Create "): name = name.replace("Create ", "") + " Creation"
            elif name.startswith("Process "): name = name.replace("Process ", "") + " Processing"
            elif name.startswith("Get ") or name.startswith("Fetch "): name = name.replace("Get ", "").replace("Fetch ", "") + " Retrieval"
            elif name.startswith("Update "): name = name.replace("Update ", "") + " Updates"
            phrases.append(name)
            
        return " · ".join(phrases)

    def _detect_brokers(self, model: LLDModel) -> list[str]:
        brokers = set()
        keywords = ["kafka", "rabbitmq", "celery", "queue", "event", "pub", "sub", "stream"]
        
        for cls in model.classes:
            if any(k in cls.name.lower() for k in keywords):
                brokers.add(cls.name)
        for comp in model.components:
            if any(k in comp.name.lower() for k in keywords):
                brokers.add(comp.name)
        for dep in model.dependencies:
            if any(k in dep.target.lower() for k in keywords):
                brokers.add(dep.target)
        
        return list(brokers)[:2]

    def _detect_external_integrations(self, model: LLDModel) -> list[str]:
        externals = set()
        keywords = ["stripe", "twilio", "blockchain", "circle", "polygon", "aws", "gcp", "azure", "sendgrid", "mailgun"]
        
        for dep in model.dependencies:
            if any(k in dep.target.lower() for k in keywords):
                externals.add(dep.target)
        for ext in model.external_integrations:
            externals.add(ext.name)
            
        return list(externals)[:3]

    def _detect_outputs(self, model: LLDModel) -> list[str]:
        outputs = set()
        # 1. API Specs
        for api in model.api_specs:
            if api.response_body:
                outputs.add("API JSON Responses")
                break
                
        # 2. File/Data outputs from classes
        keywords = ["export", "generate", "report", "download", "render"]
        for cls in model.classes:
            for m in cls.methods:
                if any(k in m.name.lower() for k in keywords):
                    name = m.name.replace("_", " ").title()
                    if name.startswith("Export "): name = name.replace("Export ", "") + " Exports"
                    elif name.startswith("Generate "): name = name.replace("Generate ", "") + " Generation"
                    elif name.startswith("Render "): name = name.replace("Render ", "") + " Views"
                    outputs.add(name)
                    
        res = list(outputs)[:3]
        if not res:
            res = ["System Responses & Results"]
        return res

    def _build_legend(self) -> str:
        lines = []
        lines.append('    subgraph Legend ["Legend"]')
        lines.append('        direction TB')
        lines.append('        L1["🔴 Non-DMZ — External-facing"]:::note')
        lines.append('        L2["🔵 DMZ — Trusted internal"]:::note')
        lines.append('        L3["🟠 External Systems"]:::note')
        lines.append('        L4["⚫ Observability"]:::note')
        lines.append('        L5["🟢 Outputs & Responses"]:::note')
        lines.append('    end')
        lines.append('    L1 -.-> L2')
        lines.append('    L2 -.-> L3')
        lines.append('    L3 -.-> L4')
        lines.append('    L4 -.-> L5')
        return "\n".join(lines)

    def _generate_full_system_diagram(self, model: LLDModel) -> str:
        """
        A rich, horizontal 7-band system component diagram mapping the entire architectural surface.
        """
        lines = ["flowchart LR", ""]
        
        # Styles
        lines.append("    classDef actor     fill:#f3e5f5,stroke:#ab47bc,stroke-width:2px,color:#4a148c")
        lines.append("    classDef lb        fill:#eceff1,stroke:#607d8b,stroke-width:1px,color:#263238,stroke-dasharray:4 4")
        lines.append("    classDef auth      fill:#fce4ec,stroke:#e57373,stroke-width:2px,color:#880e4f")
        lines.append("    classDef service   fill:#e3f2fd,stroke:#1976d2,stroke-width:2px,color:#0d47a1")
        lines.append("    classDef broker    fill:#e8eaf6,stroke:#3949ab,stroke-width:2px,color:#1a237e")
        lines.append("    classDef external  fill:#fff3e0,stroke:#f57c00,stroke-width:2px,color:#e65100")
        lines.append("    classDef store     fill:#e8f5e9,stroke:#388e3c,stroke-width:2px,color:#1b5e20")
        lines.append("    classDef security  fill:#ffebee,stroke:#c62828,stroke-width:2px,color:#b71c1c")
        lines.append("    classDef monitor   fill:#f3f3f3,stroke:#757575,stroke-width:1px,color:#424242")
        lines.append("    classDef note      fill:#fafafa,stroke:#bdbdbd,stroke-width:1px,color:#424242")
        lines.append("    classDef output    fill:#e0f2f1,stroke:#00695c,stroke-width:2px,color:#004d40")
        lines.append("")
        # Add classDefs for subgraphs to avoid empty nodes
        lines.append("    classDef sgb_client fill:none,stroke:#ab47bc,stroke-width:2px,stroke-dasharray: 5 5")
        lines.append("    classDef sgb_lb fill:none,stroke:#607d8b,stroke-width:2px,stroke-dasharray: 5 5")
        lines.append("    classDef sgb_dmz fill:#fce4ec,stroke:#e57373,stroke-width:2px,stroke-dasharray: 5 5")
        lines.append("    classDef sgb_core fill:none,stroke:#1976d2,stroke-width:2px")
        lines.append("    classDef sgb_data fill:none,stroke:#388e3c,stroke-width:2px")
        lines.append("    classDef sgb_sec fill:none,stroke:#c62828,stroke-width:2px")
        lines.append("    classDef sgb_obs fill:#f3f3f3,stroke:#757575,stroke-width:2px")
        lines.append("    classDef sgb_out fill:#e0f2f1,stroke:#00695c,stroke-width:2px,stroke-dasharray: 5 5")
        lines.append("")

        total_nodes = 0
        MAX_NODES = 30
        
        # Band 1
        client_types = set()
        for comp in model.components:
            if comp.layer == "Presentation":
                client_types.add(comp.name.replace("Controller", "").replace("Handler", "").strip())
        
        if not client_types:
            client_types.add("End Users")
            
        actor_ids = []
        lines.append('    subgraph Band1 ["Client Tier"]')
        lines.append('        direction TB')
        for i, ct in enumerate(list(client_types)[:3]):
            aid = f"Actor_{i}"
            lines.append(f'        {aid}["{ct}"]:::actor')
            actor_ids.append(aid)
            total_nodes += 1
            
        auth_classes = [c for c in model.classes if any(k in c.name.lower() for k in ["jwt", "session", "auth", "token"])]
        if auth_classes and total_nodes < MAX_NODES:
            lines.append(f'        Auth_Token["Login → JWT issued here"]:::note')
            lines.append(f'        Auth_Token -.-> {actor_ids[0]}')
            total_nodes += 1
            
        lines.append('    end')
        lines.append('    class Band1 sgb_client')
        lines.append("")
        
        # Band 2
        lb_ids = []
        lines.append('    subgraph Band2 ["Load Balancers & API Gateway"]')
        lines.append('        direction TB')
        for i, aid in enumerate(actor_ids):
            if total_nodes >= MAX_NODES: break
            lbid = f"LB_{i}"
            lines.append(f'        {lbid}["Load Balancer"]:::lb')
            lb_ids.append(lbid)
            total_nodes += 1
            
        gw_id = "API_Gateway"
        lines.append(f'        {gw_id}["API Gateway"]:::lb')
        total_nodes += 1
        lines.append('    end')
        lines.append('    class Band2 sgb_lb')
        lines.append("")
        
        # Band 3
        lines.append('    subgraph Band3 ["DMZ / Identity"]')
        lines.append('        direction TB')
        idam_id = "IDAM"
        lines.append(f'        {idam_id}["Identity & Access Management (IDAM)"]:::auth')
        total_nodes += 1
        lines.append('    end')
        lines.append('    class Band3 sgb_dmz')
        lines.append("")
        
        # Band 4
        lines.append('    subgraph Band4 ["Core Application Services"]')
        # Stack Top-to-Bottom to fix aspect ratio
        lines.append('        direction TB')
        lines.append('        subgraph Band4A ["Application Services"]')
        # Stack Top-to-Bottom
        lines.append('            direction TB')
        app_svcs = [c for c in model.components if c.layer in ["Application", "Domain"]]
        if not app_svcs:
            for c in model.classes[:4]:
                if not any(k in c.name.lower() for k in ["auth", "jwt", "model", "repo"]):
                    app_svcs.append(LLDComponent(name=c.name, component_type="Service", layer="Application", purpose=""))
                    
        svc_ids = []
        for svc in app_svcs[:5]:
            if total_nodes >= MAX_NODES: break
            sid = self._safe_id(svc.name)
            short_name = svc.name.replace("Service", "").replace("Controller", "").replace("Handler", "").strip() or svc.name
            lines.append(f'            {sid}["{short_name}"]:::service')
            svc_ids.append(sid)
            total_nodes += 1
            
            resp = self._extract_service_responsibilities(svc.name, model)
            if resp:
                lines.append(f'            {sid}_note["{resp}"]:::note')
                lines.append(f'            {sid} --- {sid}_note')
                
        lines.append('        end')
        
        brokers = self._detect_brokers(model)
        broker_ids = []
        if brokers and total_nodes < MAX_NODES:
            lines.append('        subgraph Band4B ["Message Broker / Event Bus"]')
            for i, brk in enumerate(brokers):
                bid = f"Broker_{i}"
                lines.append(f'            {bid}["{brk} (Message Broker)"]:::broker')
                broker_ids.append(bid)
                total_nodes += 1
            lines.append('        end')
            
        externals = self._detect_external_integrations(model)
        ext_ids = []
        if externals and total_nodes < MAX_NODES:
            lines.append('        subgraph Band4C ["External Integrations"]')
            for i, ext in enumerate(externals):
                eid = f"External_{i}"
                lines.append(f'            {eid}["{ext}"]:::external')
                ext_ids.append(eid)
                total_nodes += 1
            lines.append('        end')
            
        lines.append('    end')
        lines.append('    class Band4 sgb_core')
        lines.append("")
        
        # Band 5
        lines.append('    subgraph Band5 ["Data Tier"]')
        lines.append('        direction TB')
        db_items = [d.name for d in model.database_objects] + [c.name for c in model.components if c.layer == "Infrastructure"]
        if not db_items:
            db_items = ["Primary Database"]
            
        store_ids = []
        for i, db in enumerate(db_items[:4]):
            if total_nodes >= MAX_NODES: break
            did = f"Store_{i}"
            lines.append(f'        {did}[("{db}")]:::store')
            store_ids.append(did)
            total_nodes += 1
        lines.append('    end')
        lines.append('    class Band5 sgb_data')
        lines.append("")
        
        # Band 6
        sec_classes = [c for c in model.classes if any(k in c.name.lower() for k in ["vault", "keystore", "secret", "kms", "encryption"])]
        sec_id = None
        if sec_classes and total_nodes < MAX_NODES:
            lines.append('    subgraph Band6 ["Security & Key Management"]')
            sec_id = "HSM_Store"
            lines.append(f'        {sec_id}["Key Store / HSM"]:::security')
            total_nodes += 1
            lines.append('    end')
            lines.append('    class Band6 sgb_sec')
            lines.append("")
            
        # Band 7
        obs_classes = [c for c in model.classes if any(k in c.name.lower() for k in ["logger", "metrics", "prometheus", "grafana", "elk", "datadog"])]
        obs_id = None
        if obs_classes and total_nodes < MAX_NODES:
            lines.append('    subgraph Band7 ["Observability"]')
            obs_id = "Monitoring"
            lines.append(f'        {obs_id}["Monitoring & Observability (ELK / Metrics)"]:::monitor')
            total_nodes += 1
            lines.append('    end')
            lines.append('    class Band7 sgb_obs')
            lines.append("")
            
        # Band 8 Outputs
        lines.append('    subgraph Band8 ["Outputs & Responses"]')
        lines.append('        direction TB')
        outputs_list = self._detect_outputs(model)
        out_ids = []
        for i, out in enumerate(outputs_list):
            if total_nodes >= MAX_NODES: break
            oid = f"Output_{i}"
            lines.append(f'        {oid}["{out}"]:::output')
            out_ids.append(oid)
            total_nodes += 1
        lines.append('    end')
        lines.append('    class Band8 sgb_out')
        lines.append("")
            
        # Edges
        for i, aid in enumerate(actor_ids):
            if i < len(lb_ids):
                lines.append(f'    {aid} -->|HTTPS Request| {lb_ids[i]}')
                lines.append(f'    {lb_ids[i]} -->|Route| {gw_id}')
                
        lines.append(f'    {gw_id} -->|Auth check| {idam_id}')
        
        circle_numbers = ["①", "②", "③", "④", "⑤", "⑥", "⑦", "⑧", "⑨"]
        
        if svc_ids:
            lines.append(f'    {idam_id} -->|{circle_numbers[0]} Validated Request| {svc_ids[0]}')
            
            for i in range(len(svc_ids) - 1):
                circ = circle_numbers[i+1] if (i+1) < len(circle_numbers) else "→"
                lines.append(f'    {svc_ids[i]} -->|{circ} Call| {svc_ids[i+1]}')
                
            if broker_ids:
                lines.append(f'    {svc_ids[-1]} <-->|async event| {broker_ids[0]}')
                
            if ext_ids:
                lines.append(f'    {svc_ids[-1]} -.->|external API call| {ext_ids[0]}')
                
            if store_ids:
                for sid in svc_ids:
                    lines.append(f'    {sid} -->|read/write| {store_ids[0]}')
                    
            if sec_id:
                lines.append(f'    {svc_ids[0]} -.->|key fetch / encrypt| {sec_id}')
                
            if obs_id:
                lines.append(f'    {gw_id} -.->|logs| {obs_id}')
                lines.append(f'    {idam_id} -.->|metrics| {obs_id}')
                for sid in svc_ids:
                    lines.append(f'    {sid} -.->|logs / metrics| {obs_id}')
                    
            # Edges to Outputs
            if out_ids:
                for oid in out_ids:
                    lines.append(f'    {svc_ids[-1]} -->|Returns| {oid}')
                    
        else:
            lines.append(f'    {idam_id} --> {store_ids[0]}')
            if out_ids:
                lines.append(f'    {store_ids[0]} -->|Returns| {out_ids[0]}')
            
        lines.append("")
        lines.append(self._build_legend())

        return "\n".join(lines)

    # ══════════════════════════════════════════════════════════
    #  Deployment Unit Diagram — NEW
    # ══════════════════════════════════════════════════════════

    def _generate_deployment_unit_diagram(self, model: LLDModel) -> str:
        """
        Generate a deployment topology diagram from LLDDeploymentUnit entries.
        """
        if not model.deployment_units:
            return "flowchart LR\n    Empty[No Deployment Units Detected]"

        lines = ["flowchart LR", ""]

        # Styling
        lines.append("    classDef process fill:#e3f2fd,stroke:#1976d2,stroke-width:2px,color:#0d47a1")
        lines.append("    classDef db fill:#e8f5e9,stroke:#388e3c,stroke-width:2px,color:#1b5e20")
        lines.append("")

        process_ids = []
        db_ids = []

        for unit in model.deployment_units:
            uid = self._safe_id(unit.name)
            if "database" in unit.name.lower() or (unit.runtime and unit.runtime.lower() in ("neo4j", "postgresql", "mysql", "mongodb", "sqlite", "redis")):
                lines.append(f'    {uid}[("{unit.name}")]:::db')
                db_ids.append(uid)
            else:
                port_str = f":{unit.exposed_ports[0]}" if unit.exposed_ports else ""
                lines.append(f'    {uid}["{unit.name}{port_str}"]:::process')
                process_ids.append(uid)

        lines.append("")

        # Connect process -> DB
        for pid in process_ids:
            for did in db_ids:
                lines.append(f"    {pid} --> {did}")

        # If only processes, chain them
        if not db_ids and len(process_ids) > 1:
            for i in range(len(process_ids) - 1):
                lines.append(f"    {process_ids[i]} --> {process_ids[i+1]}")

        return "\n".join(lines)