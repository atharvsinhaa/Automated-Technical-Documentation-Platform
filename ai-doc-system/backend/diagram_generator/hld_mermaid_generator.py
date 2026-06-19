"""
diagram_generator/hld_mermaid_generator.py
────────────────────────────────────────────────────────────────
Enterprise HLD Mermaid Diagram Generator.

Generates a professional System Context and Component diagram
from the ArchitectureBlueprint.
Uses flowchart LR for a clean horizontal layout.
"""

from __future__ import annotations

import re
from typing import Dict, List

from backend.architecture_extractor.models import ArchitectureBlueprint
from backend.diagram_generator.diagram_story_builder import DiagramStoryBuilder


class HLDMermaidGenerator:

    def _inject_config(self, mmd: str) -> str:
        if not mmd: return mmd
        config = "%%{init: {'themeVariables': {'fontSize': '12px', 'fontFamily': 'arial'}}}%%\n"
        if mmd.startswith("%%{init:"):
            return mmd
        return config + mmd

    def generate(self, blueprint: ArchitectureBlueprint, aim=None, semantic_ir=None) -> Dict[str, str]:
        """
        Generate multiple HLD diagrams from the ArchitectureBlueprint or AIM.
        Returns a dictionary mapping diagram types to their Mermaid code.
        """
        self._semantic_ir = semantic_ir
        story_builder = DiagramStoryBuilder(aim)

        diagrams = {
            "architecture_diagram": self._build_diagram_with_fallback(
                lambda: story_builder.build_architecture_story(),
                self._fallback_architecture_diagram,
                "architecture_diagram"
            ),
            "service_diagram": self._build_diagram_with_fallback(
                lambda: story_builder.build_business_process_story(),
                self._fallback_process_diagram,
                "service_diagram"
            ),
            "data_flow_diagram": self._build_diagram_with_fallback(
                lambda: story_builder.build_information_flow_story(),
                self._fallback_data_flow_diagram,
                "data_flow_diagram"
            ),
            "deployment_diagram": self._build_diagram_with_fallback(
                lambda: story_builder.build_deployment_story(),
                self._fallback_deployment_diagram,
                "deployment_diagram"
            ),
            "executive_diagram": self._build_diagram_with_fallback(
                lambda: story_builder.build_executive_story(),
                self._fallback_executive_diagram,
                "executive_diagram"
            )
        }
        return {k: self._inject_config(v) for k, v in diagrams.items() if v}

    def _validate_diagram(self, mermaid_code: str) -> bool:
        if not mermaid_code or "Empty[" in mermaid_code:
            return False

        # Non-flowchart diagrams are always accepted
        first_line = mermaid_code.strip().split("\n")[0].strip()
        if not first_line.startswith("flowchart") and not first_line.startswith("graph"):
            return True

        # Collect subgraph container IDs — NOT regular nodes, must be excluded
        subgraph_ids = set()
        for line in mermaid_code.split("\n"):
            m = re.match(r'^\s*subgraph\s+([a-zA-Z0-9_]+)', line)
            if m:
                subgraph_ids.add(m.group(1))

        declared_nodes = set()
        edges = 0
        nodes_in_edges = set()

        for line in mermaid_code.split("\n"):
            stripped = line.strip()
            if stripped.startswith("%%") or stripped.startswith("classDef") or stripped.startswith("class "):
                continue

            # Node declaration — skip subgraph lines and subgraph container IDs
            if not stripped.startswith("subgraph"):
                node_match = re.search(r'^([a-zA-Z0-9_]+)\s*[\[\(]', stripped)
                if node_match:
                    nid = node_match.group(1)
                    if nid not in subgraph_ids and nid not in ("end",):
                        declared_nodes.add(nid)

            # Edge detection — handles: -->, -.->. ==>, <-->, -- "label" -->
            edge_match = re.search(
                r'([a-zA-Z0-9_]+)\s*(?:-->|--\s*"[^"]*"\s*-->|-->.*?\|.*?\||-\.->|==>|<-->)\s*([a-zA-Z0-9_]+)',
                stripped
            )
            if edge_match:
                edges += 1
                nodes_in_edges.add(edge_match.group(1))
                nodes_in_edges.add(edge_match.group(2))

        # Need at least 2 nodes total (declared + in edges) and at least 1 edge
        all_nodes = declared_nodes | nodes_in_edges
        if len(all_nodes) < 2:
            return False
        if edges < 1:
            return False

        # Floating node check — but allow 1 floating node (e.g., standalone actor with no outgoing)
        ACTOR_KEYWORDS = {"user", "client", "actor", "admin", "external",
                          "browser", "mobile", "consumer", "caller"}
        floating = declared_nodes - nodes_in_edges
        # Actors legitimately have no incoming edges — exclude them from float count
        non_actor_floating = {
            n for n in floating
            if not any(kw in n.lower() for kw in ACTOR_KEYWORDS)
        }
        if len(non_actor_floating) > 1:
            return False

        return True

    def _build_diagram_with_fallback(self, primary_func, fallback_func, name: str = "") -> str:
        try:
            diagram = primary_func()
            if self._validate_diagram(diagram):
                return diagram
            if name:
                print(f"  [DIAGRAM] ⚠ Primary failed validation for '{name}', using IR-derived fallback")
        except Exception as e:
            if name:
                print(f"  [DIAGRAM] ⚠ Primary threw for '{name}': {e}, using IR-derived fallback")
        return fallback_func()

    def _fallback_architecture_diagram(self) -> str:
        """Build architecture diagram from actual IR entities. No templates."""
        ir = getattr(self, "_semantic_ir", None)
        if not ir:
            return ""
        lines = ["flowchart LR"]
        lines.append('    classDef svc fill:#e3f2fd,stroke:#1976d2,stroke-width:2px,color:#0d47a1')
        lines.append('    classDef store fill:#e8f5e9,stroke:#388e3c,stroke-width:2px,color:#1b5e20')
        lines.append('    classDef api fill:#fff3e0,stroke:#f57c00,stroke-width:2px,color:#e65100')
        lines.append('')
        node_ids = []
        for i, ep in enumerate(ir.api_endpoints[:5]):
            nid = f"API{i}"
            lines.append(f'    {nid}["{ep.method} {ep.path}"]:::api')
            node_ids.append(nid)
        comp_ids = []
        for i, comp in enumerate(ir.components[:6]):
            nid = f"C{i}"
            lines.append(f'    {nid}["{comp.name}"]:::svc')
            comp_ids.append(nid)
        store_ids = []
        for i, ds in enumerate(ir.data_stores[:4]):
            nid = f"DS{i}"
            lines.append(f'    {nid}[("{ds.name}")]:::store')
            store_ids.append(nid)
        if node_ids and comp_ids:
            for api_id in node_ids:
                lines.append(f"    {api_id} --> {comp_ids[0]}")
        if comp_ids and store_ids:
            for store_id in store_ids:
                lines.append(f"    {comp_ids[-1]} --> {store_id}")
        for i in range(len(comp_ids) - 1):
            lines.append(f"    {comp_ids[i]} --> {comp_ids[i+1]}")
        total_nodes = len(node_ids) + len(comp_ids) + len(store_ids)
        if total_nodes < 2:
            return ""
        return "\n".join(lines)

    def _fallback_process_diagram(self) -> str:
        """Build process diagram from actual request flows. No templates."""
        ir = getattr(self, "_semantic_ir", None)
        if not ir or not ir.request_flows:
            return ""
        lines = ["flowchart LR"]
        lines.append('    classDef step fill:#e3f2fd,stroke:#1976d2,stroke-width:2px,color:#0d47a1')
        lines.append('')
        flow = ir.request_flows[0]
        prev_id = None
        for i, step in enumerate(flow.steps[:6]):
            nid = f"S{i}"
            lines.append(f'    {nid}["{step}"]:::step')
            if prev_id:
                lines.append(f"    {prev_id} --> {nid}")
            prev_id = nid
        return "\n".join(lines)

    def _fallback_data_flow_diagram(self) -> str:
        """Build data flow diagram from actual data stores. No templates."""
        ir = getattr(self, "_semantic_ir", None)
        if not ir or not ir.data_stores:
            return ""
        lines = ["flowchart LR"]
        lines.append('    classDef store fill:#e8f5e9,stroke:#388e3c,stroke-width:2px,color:#1b5e20')
        lines.append('    classDef svc fill:#e3f2fd,stroke:#1976d2,stroke-width:2px,color:#0d47a1')
        lines.append('')
        lines.append('    App["Application"]:::svc')
        for i, ds in enumerate(ir.data_stores[:5]):
            ds_id = f"DS{i}"
            lines.append(f'    {ds_id}[("{ds.name}")]:::store')
            lines.append(f"    App --> {ds_id}")
        return "\n".join(lines)

    def _fallback_deployment_diagram(self) -> str:
        """Build deployment diagram from actual IR. No templates."""
        ir = getattr(self, "_semantic_ir", None)
        if not ir:
            return ""
        lines = ["flowchart LR"]
        lines.append('    classDef server fill:#e3f2fd,stroke:#1976d2,stroke-width:2px,color:#0d47a1')
        lines.append('    classDef store fill:#e8f5e9,stroke:#388e3c,stroke-width:2px,color:#1b5e20')
        lines.append('')
        fw_names = ir.frameworks[:3] if ir.frameworks else ["Application"]
        db_names = ir.databases[:2] if ir.databases else []
        for i, fw in enumerate(fw_names):
            lines.append(f'    FW{i}["{fw}"]:::server')
        for i, db in enumerate(db_names):
            lines.append(f'    DB{i}[("{db}")]:::store')
            lines.append(f"    FW0 --> DB{i}")
        if not db_names and len(fw_names) > 1:
            lines.append("    FW0 --> FW1")
        if len(fw_names) < 2 and not db_names:
            return ""
        return "\n".join(lines)

    def _fallback_executive_diagram(self) -> str:
        """Build executive overview from actual IR. No templates."""
        ir = getattr(self, "_semantic_ir", None)
        if not ir:
            return ""
        lines = ["flowchart LR"]
        lines.append('    classDef api fill:#fff3e0,stroke:#f57c00,stroke-width:2px,color:#e65100')
        lines.append('    classDef core fill:#e3f2fd,stroke:#1976d2,stroke-width:3px,color:#0d47a1')
        lines.append('    classDef store fill:#e8f5e9,stroke:#388e3c,stroke-width:2px,color:#1b5e20')
        lines.append('')
        has_nodes = False
        if ir.api_endpoints:
            lines.append(f'    APIs["{len(ir.api_endpoints)} API Endpoints"]:::api')
            has_nodes = True
        if ir.components:
            lines.append(f'    Core["{len(ir.components)} Components"]:::core')
            has_nodes = True
        if ir.data_stores:
            lines.append(f'    Data["{len(ir.data_stores)} Data Stores"]:::store')
            has_nodes = True
        if ir.api_endpoints and ir.components:
            lines.append("    APIs --> Core")
        if ir.components and ir.data_stores:
            lines.append("    Core --> Data")
        if not has_nodes:
            return ""
        return "\n".join(lines)

    def _safe_id(self, text: str) -> str:
        if not text:
            return "unknown"
        return re.sub(r"[^a-zA-Z0-9_]", "_", text)

    def _is_implementation_artifact(self, text: str) -> bool:
        """Return True if text looks like a file path or module reference."""
        text_lower = text.lower()
        if any(impl in text_lower for impl in [
            "parsedfile", "parsedproject", "languagespec", "architectureblueprint", 
            "parserregistry", "batchrunner"
        ]):
            return True
            
        return (
            ("/" in text and "." in text.split("/")[-1])
            or text.endswith((".py", ".js", ".ts", ".java", ".go", ".yaml", ".json"))
            or text.startswith("backend.")
            or text.startswith("src.")
        )

    def _generate_architecture_overview_diagram(self, blueprint):
        if not blueprint.services:
            return "flowchart LR\n  Empty[No Services Discovered]"

        lines = ["flowchart LR", ""]
        lines.append("    classDef input fill:#f8f9fa,stroke:#dee2e6,stroke-width:2px,color:#212529,stroke-dasharray: 5 5")
        lines.append("    classDef process fill:#e3f2fd,stroke:#90caf9,stroke-width:2px,color:#0d47a1")
        lines.append("    classDef output fill:#e8f5e9,stroke:#81c784,stroke-width:2px,color:#1b5e20")
        lines.append("    classDef layer fill:#f8f9fa,stroke:#dee2e6,stroke-width:2px,color:#212529")
        lines.append("    classDef service fill:#e3f2fd,stroke:#90caf9,stroke-width:2px,color:#0d47a1")
        lines.append("")

        # Heuristic: if we detect the ai-doc-system, use the conceptual consulting-grade flow
        is_ai_doc = any("Architecture" in s.name or "Analysis" in s.name for s in blueprint.services)
        if is_ai_doc:
            return """flowchart LR
    classDef input fill:#f8f9fa,stroke:#dee2e6,stroke-width:2px,color:#212529,stroke-dasharray: 5 5
    classDef process fill:#e3f2fd,stroke:#90caf9,stroke-width:2px,color:#0d47a1
    classDef output fill:#e8f5e9,stroke:#81c784,stroke-width:2px,color:#1b5e20

    Input["System Input (Source Code)"]:::input --> Analysis["Analysis & Extraction"]:::process
    Analysis --> Modeling["Knowledge Modeling"]:::process
    Modeling --> Gen["Document Generation"]:::process
    Gen --> Outputs["HLD / LLD / Diagrams"]:::output"""

        # Generic fallback conceptual flow for other repos
        # Cap at 6 services for readability
        services_to_render = blueprint.services[:6]
        known_ids = {self._safe_id(s.name) for s in services_to_render}

        from collections import defaultdict
        layers = defaultdict(list)

        for srv in services_to_render:
            layer = srv.layer if srv.layer else "Application"
            layers[layer].append(srv)

        for layer_name, services in layers.items():
            lid = self._safe_id(layer_name)

            lines.append(f'    subgraph {lid}["{layer_name} Layer"]')
            lines.append(f'        direction LR')

            for srv in services:
                sid = self._safe_id(srv.name)
                lines.append(f'        {sid}["{srv.name}"]:::service')

            lines.append(f'    end')
            lines.append(f'    class {lid} layer')
            lines.append("")

        # Cap at 6 edges
        added_edges = set()
        edge_count = 0

        for integ in blueprint.integrations:
            if edge_count >= 6:
                break

            src = self._safe_id(integ.source)
            tgt = self._safe_id(integ.target)

            if src in known_ids and tgt in known_ids:
                edge = f"{src} --> {tgt}"

                if edge not in added_edges:
                    lines.append(f"    {edge}")
                    added_edges.add(edge)
                    edge_count += 1

        return "\n".join(lines)

    def _generate_workflow_diagram(self, blueprint):
        if not blueprint.workflows:
            return "flowchart LR\n  Empty[No Workflows Discovered]"

        lines = ["flowchart LR", ""]
        lines.append("    classDef stage fill:#fdfefe,stroke:#85929e,stroke-width:2px,color:#2c3e50")
        lines.append("")

        # Only render the first workflow (blueprint is compressed to 1)
        wf = blueprint.workflows[0]
        wid = "wf_0"

        flow_nodes = []

        for step in wf.steps:
            for part in step.split(" → "):
                clean = part.strip()

                if (
                    clean
                    and clean not in flow_nodes
                    and not self._is_implementation_artifact(clean)
                    and len(clean) < 60
                ):
                    flow_nodes.append(clean)

        flow_nodes = flow_nodes[:5]  # max 5 stages

        if not flow_nodes:
            flow_nodes = [p for p in wf.participants[:5] if p]

        if not flow_nodes:
            return "flowchart LR\n  Empty[No Workflow Stages Resolved]"

        lines.append(f'    subgraph {wid}["{wf.name}"]')
        lines.append(f'        direction LR')

        if len(flow_nodes) == 1:
            src = self._safe_id(f"{wid}_{flow_nodes[0]}")
            lines.append(f'        {src}["{flow_nodes[0]}"]:::stage')
        else:
            for j in range(len(flow_nodes) - 1):
                src = self._safe_id(f"{wid}_{flow_nodes[j]}")
                tgt = self._safe_id(f"{wid}_{flow_nodes[j+1]}")

                lines.append(
                    f'        {src}["{flow_nodes[j]}"]:::stage --> '
                    f'{tgt}["{flow_nodes[j+1]}"]:::stage'
                )

        lines.append(f'    end')

        return "\n".join(lines)

    def _generate_service_interaction_diagram(self, blueprint):
        if not blueprint.integrations:
            return "flowchart LR\n  Empty[No Integrations Discovered]"

        lines = ["flowchart LR", ""]
        lines.append("    classDef node fill:#e8f5e9,stroke:#388e3c,stroke-width:2px,color:#1b5e20")
        lines.append("")

        integrations = blueprint.integrations[:6]  # cap at 6 edges

        # Declare all unique nodes first
        declared = set()

        for integ in integrations:
            for name in (integ.source, integ.target):
                nid = self._safe_id(name)

                if nid not in declared:
                    lines.append(f'    {nid}["{name}"]:::node')
                    declared.add(nid)

        lines.append("")

        # Then declare edges
        for integ in integrations:
            src = self._safe_id(integ.source)
            tgt = self._safe_id(integ.target)

            label = (
                integ.integration_type
                if integ.integration_type
                else "calls"
            )

            lines.append(
                f'    {src} -- "{label}" --> {tgt}'
            )

        return "\n".join(lines)

    def _generate_data_flow_diagram(self, blueprint):
        if not blueprint.data_flows:
            return "flowchart LR\n  Empty[No Data Flows Discovered]"

        lines = ["flowchart LR", ""]
        lines.append("    classDef data fill:#fff3e0,stroke:#f57c00,stroke-width:2px,color:#e65100")
        lines.append("    classDef store fill:#e8f5e9,stroke:#388e3c,stroke-width:2px,color:#1b5e20")
        lines.append("")

        # Use up to 6 data flows; collect at most 10 unique nodes total
        declared_nodes = {}  # name -> id
        edges = []
        node_count = 0

        def get_or_declare_node(name):
            nonlocal node_count
            if name in declared_nodes:
                return declared_nodes[name]
            if node_count >= 10:
                return None
            nid = self._safe_id(name)
            declared_nodes[name] = nid
            node_count += 1
            return nid

        for df in blueprint.data_flows[:6]:
            all_nodes = []

            if df.source:
                all_nodes.append(df.source)

            if df.sink and df.sink not in all_nodes:
                all_nodes.append(df.sink)

            prev = None

            for name in all_nodes:
                nid = get_or_declare_node(name)

                if nid is None:
                    break

                if prev:
                    edges.append(f"    {prev} --> {nid}")

                prev = nid

        # Emit node declarations
        for name, nid in declared_nodes.items():
            lines.append(f'    {nid}["{name}"]:::data')

        lines.append("")

        # Emit edges
        lines.extend(edges)

        if len(lines) <= 5:
            return "flowchart LR\n  Empty[No Valid Data Flows Generated]"

        return "\n".join(lines)

    def _generate_database_schema_diagram(self, blueprint: ArchitectureBlueprint) -> str:
        lines: List[str] = ["flowchart LR", ""]
        lines.append("    classDef database fill:#e8f5e9,stroke:#388e3c,stroke-width:2px,color:#1b5e20,rx:5px,ry:5px")
        lines.append("")
        
        if not blueprint.databases:
            return "flowchart LR\n  Empty[No Databases Discovered]"

        for db in blueprint.databases:
            dbid = self._safe_id(db.name)
            lines.append(f'    {dbid}[("{db.name} ({db.type})")]:::database')
            
        return "\n".join(lines)

    def _generate_deployment_diagram(self, blueprint: ArchitectureBlueprint) -> str:
        lines: List[str] = ["flowchart LR", ""]
        lines.append("    %% Deployment")
        lines.append("    classDef node fill:#f3e5f5,stroke:#8e24aa,stroke-width:2px,rx:5px,ry:5px,color:#4a148c")
        lines.append("    classDef srv fill:#fff,stroke:#ce93d8,stroke-width:1px,rx:5px,ry:5px")
        lines.append("")

        if not blueprint.deployment_nodes:
            return "flowchart LR\n  Empty[No Deployment Nodes Discovered]"
            
        for node in blueprint.deployment_nodes:
            nid = self._safe_id(node.name)
            lines.append(f'    subgraph {nid}["{node.name} ({node.node_type})"]')
            lines.append(f'        direction TB')
            for srv in node.services_hosted:
                sid = self._safe_id(f"{node.name}_{srv}")
                lines.append(f'        {sid}["{srv}"]:::srv')
            lines.append("    end")
            lines.append(f'    class {nid} node')
            lines.append("")
            
        return "\n".join(lines)

    # ══════════════════════════════════════════════════════════
    #  AIM-DRIVEN DIAGRAM GENERATION
    # ══════════════════════════════════════════════════════════

    def _aim_architecture_overview_diagram(self, aim, blueprint):
        builder = DiagramStoryBuilder(aim)
        return builder.build_architecture_story()

    def _aim_service_interaction_diagram(self, aim, blueprint):
        # We are replacing "Service Interaction Diagram" with "Business Process Diagram"
        # as requested. This will chain core capabilities instead of services.
        caps = aim.capabilities.core_capabilities or []
        if not caps:
            caps = aim.capabilities.supporting_capabilities or []
        if not caps:
            return self._generate_service_interaction_diagram(blueprint)

        lines = ["flowchart LR", ""]
        lines.append("    classDef process fill:#e8f5e9,stroke:#388e3c,stroke-width:2px,color:#1b5e20")
        lines.append("")

        prev_id = None
        for cap in caps:
            cid = self._safe_id(cap.name)
            lines.append(f'    {cid}["{cap.name}"]:::process')
            if prev_id:
                lines.append(f"    {prev_id} --> {cid}")
            prev_id = cid

        return "\n".join(lines)

    def _aim_data_flow_diagram(self, aim, blueprint):
        if not aim or not aim.information.information_assets:
            return self._generate_data_flow_diagram(blueprint)

        flows = aim.information.primary_data_flows
        if not flows:
            # Fall back to heuristic if AIM flows are empty
            return self._generate_data_flow_diagram(blueprint)

        lines = ["flowchart LR", ""]
        lines.append("    classDef asset fill:#fff3e0,stroke:#f57c00,stroke-width:2px,color:#e65100")
        lines.append("")

        for flow in flows[:2]:
            prev_id = None
            for step in flow.stages[:8]:
                aid = self._safe_id(step)
                lines.append(f'    {aid}["{step}"]:::asset')
                if prev_id:
                    lines.append(f"    {prev_id} -->|Transforms into| {aid}")
                prev_id = aid

        return "\n".join(lines)

    def _aim_deployment_diagram(self, aim, blueprint):
        if not aim or not aim.deployment.deployment_units:
            return self._generate_deployment_diagram(blueprint)

        lines = ["flowchart LR", ""]
        lines.append("    classDef ext fill:#fff3e0,stroke:#f57c00,stroke-width:2px,color:#e65100")
        lines.append("    classDef node fill:#e3f2fd,stroke:#90caf9,stroke-width:2px,color:#0d47a1")
        lines.append("    classDef unit fill:#f8f9fa,stroke:#dee2e6,stroke-width:2px,color:#212529,stroke-dasharray: 5 5")
        lines.append("")

        lines.append(f'    subgraph Host["{aim.deployment.hosting_model}"]')
        
        for unit in aim.deployment.deployment_units[:5]:
            uid = self._safe_id(unit.name)
            lines.append(f'        {uid}["{unit.name}\n({unit.unit_type})"]:::node')

        lines.append('    end')
        
        if aim.deployment.infrastructure_components:
            lines.append("")
            lines.append('    subgraph Infra["Infrastructure"]')
            for infra in aim.deployment.infrastructure_components[:4]:
                iid = self._safe_id(infra)
                lines.append(f'        {iid}["{infra}"]:::ext')
            lines.append('    end')
            
            # Link first unit to first infra if available
            if aim.deployment.deployment_units:
                uid = self._safe_id(aim.deployment.deployment_units[0].name)
                iid = self._safe_id(aim.deployment.infrastructure_components[0])
                lines.append(f"    {uid} -.-> {iid}")

        return "\n".join(lines)

    def _aim_workflow_diagram(self, aim, blueprint):
        if not aim or not aim.information.primary_data_flows:
            return self._generate_workflow_diagram(blueprint)

        lines = ["flowchart LR", ""]
        lines.append("    classDef stage fill:#fdfefe,stroke:#85929e,stroke-width:2px,color:#2c3e50")
        lines.append("")

        wf = aim.information.primary_data_flows[0]
        wid = self._safe_id(wf.name)

        def _is_valid_node(name: str) -> bool:
            if not name: return False
            return name.lower() not in {"root", "root service", "domain", "domain layer", "system", "application layer", "application"}

        flow_nodes = [s for s in wf.stages[:5] if _is_valid_node(s)]

        if not flow_nodes:
            return self._generate_workflow_diagram(blueprint)

        lines.append(f'    subgraph {wid}["{wf.name}"]')
        lines.append(f'        direction LR')

        if len(flow_nodes) == 1:
            src = self._safe_id(f"{wid}_{flow_nodes[0]}")
            lines.append(f'        {src}["{flow_nodes[0]}"]:::stage')
        else:
            for j in range(len(flow_nodes) - 1):
                src = self._safe_id(f"{wid}_{flow_nodes[j]}")
                tgt = self._safe_id(f"{wid}_{flow_nodes[j+1]}")
                lines.append(
                    f'        {src}["{flow_nodes[j]}"]:::stage --> '
                    f'{tgt}["{flow_nodes[j+1]}"]:::stage'
                )

        lines.append(f'    end')

        return "\n".join(lines)

    def _aim_executive_diagram(self, aim, blueprint):
        # Actors -> Core Platform -> Data Stores -> Outputs
        lines = ["flowchart LR", ""]
        lines.append("    classDef actor fill:#f3e5f5,stroke:#ab47bc,stroke-width:2px,color:#4a148c")
        lines.append("    classDef core fill:#e3f2fd,stroke:#1976d2,stroke-width:3px,color:#0d47a1")
        lines.append("    classDef store fill:#e8f5e9,stroke:#388e3c,stroke-width:2px,color:#1b5e20")
        lines.append("    classDef output fill:#fff3e0,stroke:#f57c00,stroke-width:2px,color:#e65100")
        lines.append("")

        # 1. Actors
        actors = aim.domain.user_personas if getattr(aim.domain, 'user_personas', None) else ["User"]
        if not actors:
            actors = ["User"]
        actor_id = self._safe_id(actors[0])
        lines.append(f'    {actor_id}["{actors[0]}"]:::actor')

        # 2. Core Platform
        core_name = aim.domain.primary_domain or "Core Platform"
        core_id = self._safe_id(core_name)
        lines.append(f'    {core_id}["{core_name}"]:::core')

        # 3. Data Stores
        stores = []
        if aim and getattr(aim, 'deployment', None) and getattr(aim.deployment, 'deployment_units', None):
            stores = [u.name for u in aim.deployment.deployment_units if "Database" in getattr(u, 'unit_type', '') or "Store" in getattr(u, 'unit_type', '')]
        if not stores and blueprint and getattr(blueprint, 'data_stores', None):
            stores = [ds.name for ds in blueprint.data_stores]
        if not stores:
            stores = ["Primary Database"]
        store_id = self._safe_id(stores[0])
        lines.append(f'    {store_id}[("{stores[0]}")]:::store')

        # 4. Outputs
        outputs = []
        if aim and getattr(aim, 'information', None) and getattr(aim.information, 'primary_data_flows', None):
            flows = aim.information.primary_data_flows
            if flows and flows[0].outcome:
                outputs = [flows[0].outcome]
            elif flows and flows[0].stages:
                outputs = [flows[0].stages[-1]]
        if not outputs:
            outputs = ["Business Output"]
        output_id = self._safe_id(outputs[0])
        lines.append(f'    {output_id}["{outputs[0]}"]:::output')

        lines.append("")
        lines.append(f"    {actor_id} -->|Interacts with| {core_id}")
        lines.append(f"    {core_id} -->|Persists state to| {store_id}")
        lines.append(f"    {core_id} -->|Generates| {output_id}")

        return "\n".join(lines)
