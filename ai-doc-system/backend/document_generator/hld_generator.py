"""
document_generator/hld_generator.py
────────────────────────────────────────────────────────────────
Enterprise HLD Document Generator.

Generates a complete High-Level Design document from an
Architecture Blueprint, abstracting away from raw files.

Output sections:
  1. Executive Summary
  2. Architecture Overview
  3. Service Catalogue
  4. Data Architecture
  5. Integration Architecture
  6. Infrastructure & Deployment
  7. Security Boundaries
"""

from __future__ import annotations

import os
from typing import List, Dict

from backend.architecture_extractor.models import ArchitectureBlueprint


class HLDGenerator:

    def generate(
        self,
        blueprint: ArchitectureBlueprint,
        diagram_paths: Dict[str, str] = None,
        repository_name: str = "Unknown"
    ) -> str:
        """
        Generate enterprise-grade HLD from ArchitectureBlueprint.
        """
        header_lines: List[str] = []
        body_lines: List[str] = []
        self._section_executive_summary(body_lines, blueprint)
        self._section_system_context(body_lines, blueprint)
        self._section_business_capabilities(body_lines, blueprint)
        self._section_architecture_overview(body_lines, blueprint, diagram_paths.get("architecture_diagram") if diagram_paths else None)
        self._section_modules_and_components(body_lines, blueprint, diagram_paths.get("service_diagram") if diagram_paths else None)
        self._section_data_architecture(body_lines, blueprint, diagram_paths.get("data_flow_diagram") if diagram_paths else None)
        self._section_integration_architecture(body_lines, blueprint)
        self._section_technology_stack(body_lines, blueprint)
        self._section_non_functional_requirements(body_lines, blueprint)
        self._section_deployment_architecture(body_lines, blueprint, diagram_paths.get("deployment_diagram") if diagram_paths else None)

        # Generate TOC
        toc_lines: List[str] = ["## Table of Contents", ""]
        counter = 1
        for line in body_lines:
            if line.startswith("## ") and not line.startswith("### "):
                clean_title = line[3:].strip()
                import re
                clean_title = re.sub(r'^\d+\.\s+', '', clean_title) # Just in case
                
                # Format anchor link
                anchor = clean_title.lower().replace(" ", "-")
                anchor = re.sub(r'[^\w\-]', '', anchor)
                
                toc_lines.append(f"{counter}. [{clean_title}](#{anchor})")
                counter += 1
        toc_lines.append("")

        return "\n".join(header_lines + toc_lines + body_lines)

    # ══════════════════════════════════════════════════════════
    #  SECTION: Title
    # ══════════════════════════════════════════════════════════



    # ══════════════════════════════════════════════════════════
    #  SECTION 1: Executive Summary
    # ══════════════════════════════════════════════════════════

    def _section_executive_summary(self, lines, bp):
        lines.append("## Executive Summary")
        lines.append("")

        # 1. What the system does — derived from repository_type
        repo_type = bp.repository_type or "software system"
        lines.append(
            f"This document describes the high-level architecture of a **{repo_type}**. "
            f"It is intended for technical leads, solution architects, and business stakeholders "
            f"who need to understand the system's structure, major components, and data flows "
            f"without requiring implementation-level knowledge."
        )
        lines.append("")

        # 2. Architecture pattern
        if bp.architecture_pattern:
            lines.append(f"The system follows a **{bp.architecture_pattern}** architectural pattern.")
            lines.append("")

        # 3. Key capabilities — max 5 bullets
        capabilities = getattr(bp, "capabilities", [])
        if capabilities:
            lines.append("**Key Capabilities:**")
            lines.append("")
            for cap in capabilities[:5]:
                desc = cap.description if cap.description else cap.name
                lines.append(f"- **{cap.name}:** {desc}")
            lines.append("")

        # 4. Compact scale summary — single table, no Discovered/Documented split
        lines.append("**System Scale:**")
        lines.append("")
        lines.append("| Dimension | Count |")
        lines.append("|-----------|-------|")
        lines.append(f"| Services | {len(bp.services)} |")
        lines.append(f"| Data Stores | {len(bp.databases)} |")
        lines.append(f"| API Endpoints | {len(bp.apis)} |")
        lines.append(f"| External Integrations | {len(bp.integrations)} |")
        lines.append("")

    # ══════════════════════════════════════════════════════════
    #  SECTION: System Context
    # ══════════════════════════════════════════════════════════

    def _section_system_context(self, lines: List[str], bp: ArchitectureBlueprint):
        lines.append("## System Context Diagram")
        lines.append("")
        
        lines.append("```mermaid")
        lines.append("C4Context")
        lines.append('  title System Context diagram for ' + (bp.repository_type or 'System'))
        lines.append('  Person(user, "User", "A user of the system.")')
        lines.append('  System(system, "' + (bp.repository_type or 'Core System') + '", "The core system being analyzed.")')
        
        for i, intg in enumerate(bp.integrations[:5]):
            if intg.target:
                sys_id = f"ext_{i}"
                lines.append(f'  System_Ext({sys_id}, "{intg.target}", "{intg.integration_type}")')
                lines.append(f'  Rel(system, {sys_id}, "Uses", "{intg.purpose}")')
                
        for i, db in enumerate(bp.databases[:5]):
            db_id = f"db_{i}"
            lines.append(f'  SystemDb({db_id}, "{db.name}", "{db.type}")')
            lines.append(f'  Rel(system, {db_id}, "Reads from and writes to", "")')
            
        lines.append('  Rel(user, system, "Uses", "")')
        lines.append("```")
        lines.append("")
        
    # ══════════════════════════════════════════════════════════
    #  SECTION: Business Capabilities
    # ══════════════════════════════════════════════════════════

    def _section_business_capabilities(self, lines: List[str], bp: ArchitectureBlueprint):
        lines.append("## Business Capability Map")
        lines.append("")
        if not bp.capabilities:
            lines.append("*Not confidently detected.*")
            lines.append("")
            return
            
        lines.append("| Capability | Description | Supporting Components |")
        lines.append("|------------|-------------|-----------------------|")
        for cap in bp.capabilities:
            desc = cap.description if cap.description else cap.name
            comps = ", ".join(cap.supporting_components) if cap.supporting_components else "None detected"
            lines.append(f"| **{cap.name}** | {desc} | {comps} |")
        lines.append("")

    # ══════════════════════════════════════════════════════════
    #  SECTION: Technology Stack
    # ══════════════════════════════════════════════════════════

    def _section_technology_stack(
        self, lines: List[str], bp: ArchitectureBlueprint
    ):
        lines.append("## Technology Stack")
        lines.append("")

        meta = bp.metadata
        languages = meta.get("languages", [])
        frameworks = meta.get("frameworks", [])
        databases = meta.get("databases", [])
        messaging = meta.get("messaging_systems", [])
        infra = meta.get("infrastructure", [])
        ai_ml = meta.get("ai_ml_tools", [])
        code_analysis = meta.get("code_analysis_tools", [])

        if not any([languages, frameworks, databases, messaging, infra, ai_ml, code_analysis]):
            lines.append("Technology stack could not be determined.")
            lines.append("")
            return

        def _format_tech(tech: str) -> str:
            tech_lower = tech.lower()
            desc = ""
            if "neo4j" in tech_lower:
                desc = " – Graph database used for architecture relationships."
            elif "ollama" in tech_lower:
                desc = " – Local language model runtime used for documentation synthesis."
            elif "tree-sitter" in tech_lower:
                desc = " – Multi-language parser used for code structure analysis."
            return f"- {tech}{desc}"

        if languages:
            lines.append("Languages:")
            for lang in languages:
                lines.append(_format_tech(lang))
            lines.append("")

        if frameworks:
            lines.append("Frameworks:")
            for fw in frameworks:
                lines.append(_format_tech(fw))
            lines.append("")

        if databases:
            lines.append("Databases:")
            for db in databases:
                lines.append(_format_tech(db))
            lines.append("")

        if messaging:
            lines.append("Messaging:")
            for msg in messaging:
                lines.append(_format_tech(msg))
            lines.append("")

        if infra:
            lines.append("Infrastructure:")
            for inf in infra:
                lines.append(_format_tech(inf))
            lines.append("")

        if ai_ml:
            lines.append("AI / LLM:")
            for tool in ai_ml:
                lines.append(_format_tech(tool))
            lines.append("")

        if code_analysis:
            lines.append("Code Analysis:")
            for tool in code_analysis:
                lines.append(_format_tech(tool))
            lines.append("")

    # ══════════════════════════════════════════════════════════
    #  SECTION 2: Architecture Overview
    # ══════════════════════════════════════════════════════════

    def _section_architecture_overview(
        self, lines: List[str], bp: ArchitectureBlueprint, mmd_code: str = None
    ):
        lines.append("## System Architecture")
        lines.append("")
        
        if mmd_code and "Empty[" not in mmd_code:
            lines.append("```mermaid")
            lines.append(mmd_code.strip())
            lines.append("```")
            lines.append("")

        capabilities = getattr(bp, "capabilities", [])
        if capabilities:
            lines.append(f"The platform provides {len(capabilities)} primary capabilities:")
            lines.append("")
            for i, cap in enumerate(capabilities):
                lines.append(f"{i+1}. **{cap.name}**")
            lines.append("")
            if bp.repository_type == "AI-powered Architecture Documentation Platform":
                lines.append(
                    "These capabilities collaborate through a semantic processing pipeline "
                    "that transforms source code into structured architecture documentation artifacts."
                )
            else:
                lines.append("These capabilities collaborate through a layered architecture.")
            lines.append("")
        elif bp.architecture_pattern:
            lines.append(
                f"This system follows a **{bp.architecture_pattern}** "
                f"architecture with {len(bp.services)} identified service(s) "
                f"and {len(bp.components)} component(s)."
            )
            lines.append("")

        # Only render layer overview if layers resolve cleanly:
        if bp.services:
            from collections import defaultdict
            layer_groups = defaultdict(list)
            for s in bp.services:
                layer = getattr(s, "layer", "None") or "None"
                if layer and layer != "None" and layer != "Unclassified" and layer != "Analysis":
                    layer_groups[layer].append(s)
            
            if layer_groups:
                lines.append("### Layered Architecture Overview")
                lines.append("")
                layer_order = ["Presentation", "Application", "Domain", "Infrastructure"]
                for layer in layer_order:
                    if layer in layer_groups:
                        lines.append(f"#### {layer} Layer")
                        for s in layer_groups[layer]:
                            lines.append(f"- **{s.name}**: {s.purpose}")
                        lines.append("")

    # ══════════════════════════════════════════════════════════
    #  SECTION 3: Service Catalogue
    # ══════════════════════════════════════════════════════════

    def _section_modules_and_components(self, lines, bp, mmd_code=None):
        lines.append("## Modules & Components")
        lines.append("")

        if mmd_code and "Empty[" not in mmd_code:
            lines.append("### Inter-module Dependency Diagram")
            lines.append("")
            lines.append("```mermaid")
            lines.append(mmd_code.strip())
            lines.append("```")
            lines.append("")

        if not bp.services:
            lines.append("*Not confidently detected.*")
            lines.append("")
            return

        # Group by Business Domain (Domain Boundaries)
        from collections import defaultdict
        domains = defaultdict(list)
        for srv in bp.services:
            domain = getattr(srv, "business_domain", None) or "Core Domain"
            domains[domain].append(srv)
            
        for domain, services in domains.items():
            lines.append(f"### Domain Boundary: {domain}")
            lines.append("")
            lines.append("| Component | Layer | Purpose |")
            lines.append("|-----------|-------|---------|")
            for srv in services:
                purpose = getattr(srv, "purpose", "Component of the system.") or "Component of the system."
                if len(purpose) > 120:
                    purpose = purpose[:117] + "..."
                layer = getattr(srv, "layer", "Application")
                lines.append(f"| **{srv.name}** | {layer} | {purpose} |")
            lines.append("")

    # ══════════════════════════════════════════════════════════

    #  SECTION 5: Data Architecture
    # ══════════════════════════════════════════════════════════
    
    def _section_data_architecture(
        self, lines: List[str], bp: ArchitectureBlueprint, mmd_code: str = None
    ):
        lines.append("## Data Flow Architecture")
        lines.append("")
        
        if mmd_code and "Empty[" not in mmd_code:
            lines.append("```mermaid")
            lines.append(mmd_code.strip())
            lines.append("```")
            lines.append("")

        if bp.data_flows:
            lines.append("### High-Level Data Flow")
            lines.append("")
            valid_flows = []
            for df in bp.data_flows:
                if self._is_implementation_artifact(df.source) or self._is_implementation_artifact(df.sink):
                    continue
                # Omit explicit SQL file paths to conform to M3.4
                if ".sql" in df.source or ".sql" in df.sink or "queries" in df.name.lower():
                    continue
                valid_flows.append(f"- **{df.source} → {df.sink}**")
            
            if valid_flows:
                for vf in valid_flows:
                    lines.append(vf)
            else:
                lines.append("*No high-level data flows resolved.*")
            lines.append("")

        if bp.databases:
            lines.append("### Key Information Assets")
            lines.append("")
            lines.append("| Asset | Type | Lifecycle | Sensitivity |")
            lines.append("|-------|------|-----------|-------------|")
            for db in bp.databases[:6]:
                operations = ", ".join(db.operations[:3]) if getattr(db, 'operations', []) else "CRUD"
                lines.append(
                    f"| **{db.name}** | {db.type} | {operations} | Internal |"
                )
            lines.append("")


    # ══════════════════════════════════════════════════════════
    #  SECTION 6: Integration Architecture
    # ══════════════════════════════════════════════════════════
    def _section_integration_architecture(
        self, lines: List[str], bp: ArchitectureBlueprint
    ):
        if not bp.integrations and not getattr(bp, 'apis', []):
            lines.append("## External Integrations")
            lines.append("")
            if bp.repository_type == "AI-powered Architecture Documentation Platform":
                lines.append(
                    "The platform operates as an internal processing pipeline and does not expose "
                    "external REST or GraphQL interfaces. Interactions occur through internal "
                    "processing services and shared architectural models."
                )
            else:
                lines.append(
                    "No external interfaces or integration boundaries "
                    "were detected within the analyzed repository."
                )
            lines.append("")
            return

        lines.append("## External Integrations")
        lines.append("")
        lines.append("### Integration Points")
        lines.append("")
        valid_intgs = []
        for intg in bp.integrations:
            if self._is_implementation_artifact(intg.source) or self._is_implementation_artifact(intg.target):
                continue
            purpose = getattr(intg, 'purpose', 'Orchestrates component execution.')
            valid_intgs.append(f"| **{intg.source}** | **{intg.target}** | {intg.integration_type} | {purpose} |")
            
        if valid_intgs:
            lines.append("| Source | Target | Type | Purpose |")
            lines.append("|--------|--------|------|---------|")
            for vi in valid_intgs:
                lines.append(vi)
        else:
            lines.append("*Not confidently detected.*")
        lines.append("")

    # ══════════════════════════════════════════════════════════
    #  SECTION: Non-Functional Requirements
    # ══════════════════════════════════════════════════════════
    def _section_non_functional_requirements(self, lines: List[str], bp: ArchitectureBlueprint):
        lines.append("## Non-Functional Requirements (NFRs)")
        lines.append("")
        lines.append("> **Note:** These NFRs are implicitly derived from the detected architecture patterns, deployment topologies, and technology stack.")
        lines.append("")
        
        lines.append("### Security")
        if bp.security_boundaries:
            for sb in bp.security_boundaries:
                lines.append(f"- **{sb.name} ({sb.zone_type}):** {sb.description or 'Security boundary enforcement.'}")
        else:
            lines.append("- Implicit security boundaries defined by the deployment topology.")
        lines.append("")
        
        lines.append("### Scalability & Availability")
        nodes = [n.node_type for n in bp.deployment_nodes]
        if "Container" in nodes or "Serverless" in nodes:
            lines.append("- Designed for horizontal scalability via stateless containerized/serverless components.")
        else:
            lines.append("- Scalability profile bound to instance limits; vertical scaling recommended based on discovered topology.")
        lines.append("")
        
        lines.append("### Performance & Maintainability")
        lines.append(f"- **Architecture Alignment:** The {bp.architecture_pattern or 'current'} pattern drives maintainability through separation of concerns.")
        lines.append("")
    # ══════════════════════════════════════════════════════════
    #  SECTION 7: Infrastructure Overview
    # ══════════════════════════════════════════════════════════

    def _section_deployment_architecture(self, lines, bp, mmd_code=None):
        lines.append("## Deployment Architecture")
        lines.append("")
        
        if mmd_code and "Empty[" not in mmd_code:
            lines.append("```mermaid")
            lines.append(mmd_code.strip())
            lines.append("```")
            lines.append("")
        elif bp.deployment_nodes:
            lines.append("### Deployment Nodes")
            lines.append("")
            lines.append("| Node Name | Type | Services Hosted |")
            lines.append("|-----------|------|-----------------|")
            for node in bp.deployment_nodes:
                hosted = ", ".join(node.services_hosted) if node.services_hosted else "None detected"
                lines.append(f"| **{node.name}** | {node.node_type} | {hosted} |")
            lines.append("")
        else:
            if bp.repository_type == "AI-powered Architecture Documentation Platform":
                lines.append("```mermaid")
                lines.append("flowchart TB")
                lines.append("    Developer --> Documentation_Platform[Documentation Platform]")
                lines.append("    Documentation_Platform --> Neo4j[(Neo4j Graph Database)]")
                lines.append("    Documentation_Platform --> Generated_Documents[Generated Documents]")
                lines.append("```")
                lines.append("")
                lines.append("The system is typically deployed locally as a command-line utility or embedded library.")
            else:
                lines.append("*Not confidently detected.*")
            lines.append("")


    def _is_implementation_artifact(self, text: str) -> bool:
        """Return True if the text looks like a file path or module import."""
        text_lower = text.lower()
        if any(impl in text_lower for impl in [
            "parsedfile", "parsedproject", "languagespec", "architectureblueprint", 
            "parserregistry", "batchrunner"
        ]):
            return True
            
        return (
            ("/" in text and "." in text.split("/")[-1])  # file path
            or text.endswith((".py", ".js", ".ts", ".java", ".go", ".yaml", ".json"))
            or text.startswith("backend.")
            or text.startswith("src.")
        )

    #  SAVE
    # ══════════════════════════════════════════════════════════

    def save(
        self,
        content: str,
        output_path: str,
    ):
        os.makedirs(
            os.path.dirname(output_path),
            exist_ok=True,
        )
        with open(
            output_path, "w", encoding="utf-8",
        ) as f:
            f.write(content)

        print(f"[SUCCESS] HLD generated: {output_path}")

    # ══════════════════════════════════════════════════════════
    #  AIM-BASED GENERATION (Architecture Intelligence Engine)
    # ══════════════════════════════════════════════════════════

    def generate_from_aim(
        self,
        aim,
        diagram_paths: Dict[str, str] = None,
    ) -> str:
        """
        Generate HLD from ArchitectureIntelligenceModel.
        This is the preferred path when the AIE layer is active.
        """
        body_lines: List[str] = []

        self._section_executive_summary_from_aim(
            body_lines, aim,
            diagram_paths.get("executive_diagram") if diagram_paths else None
        )
        self._section_system_architecture_from_aim(
            body_lines, aim,
            diagram_paths.get("architecture_diagram") if diagram_paths else None
        )
        self._section_modules_from_aim(
            body_lines, aim,
            diagram_paths.get("service_diagram") if diagram_paths else None
        )
        self._section_data_flow_from_aim(
            body_lines, aim,
            diagram_paths.get("data_flow_diagram") if diagram_paths else None
        )
        self._section_interface_from_aim(body_lines, aim)
        self._section_technology_from_aim(body_lines, aim)
        self._section_deployment_from_aim(
            body_lines, aim,
            diagram_paths.get("deployment_diagram") if diagram_paths else None
        )

        # Generate TOC
        import re
        toc_lines: List[str] = ["## Table of Contents", ""]
        counter = 1
        for line in body_lines:
            if line.startswith("## ") and not line.startswith("### "):
                clean_title = line[3:].strip()
                clean_title = re.sub(r'^\d+\.\s+', '', clean_title)
                anchor = clean_title.lower().replace(" ", "-")
                anchor = re.sub(r'[^\w\-]', '', anchor)
                toc_lines.append(f"{counter}. [{clean_title}](#{anchor})")
                counter += 1
        toc_lines.append("")

        return "\n".join(toc_lines + body_lines)

    # ── AIM Section: Executive Summary ───────────────────────

    def _section_executive_summary_from_aim(self, lines: List[str], aim, mmd_code=None) -> None:
        lines.append("## Executive Summary")
        lines.append("")
        lines.append(aim.narrative.executive_summary)
        lines.append("")

        if mmd_code and "Empty[" not in mmd_code:
            lines.append("```mermaid")
            lines.append(mmd_code.strip())
            lines.append("```")
            lines.append("")

        # System scale table
        svc_count = len(aim.services.services)
        asset_count = len(aim.information.information_assets)
        integ_count = len(aim.integration.integration_points)

        lines.append("**System Scale:**")
        lines.append("")
        lines.append("| Dimension | Count |")
        lines.append("|-----------|-------|")
        lines.append(f"| Services | {svc_count} |")
        lines.append(f"| Information Assets | {asset_count} |")
        lines.append(f"| Integration Points | {integ_count} |")
        lines.append("")

    # ── AIM Section: System Architecture ─────────────────────

    def _section_system_architecture_from_aim(self, lines: List[str], aim, mmd_code=None) -> None:
        lines.append("## System Architecture")
        lines.append("")

        if mmd_code and "Empty[" not in mmd_code:
            lines.append("```mermaid")
            lines.append(mmd_code.strip())
            lines.append("```")
            lines.append("")

        arch_style = aim.services.architecture_style
        if arch_style in ("Unknown", "Layered Architecture"):
            tech_stack = getattr(aim.narrative, 'technology_stack', '')
            if isinstance(tech_stack, list):
                tech_stack = " ".join(tech_stack)
            if "SQL" in str(tech_stack).upper() or "SQL" in aim.narrative.system_architecture_narrative.upper() or getattr(aim, 'lang_str', '') == "SQL":
                arch_style = "Database-Centric Batch/ETL Architecture"
                aim.narrative.system_architecture_narrative = "The system follows a Database-Centric Batch/ETL Architecture. It is primarily composed of SQL stored procedures and database tables, with minimal application-layer code."
                
        lines.append(aim.narrative.system_architecture_narrative)
        lines.append("")
        lines.append(f"The system follows a **{arch_style}** architectural pattern.")
        if getattr(aim.services, 'architecture_rationale', None):
            lines.append(f"")
            lines.append(f"**Rationale:** {aim.services.architecture_rationale}")
        lines.append("")

    # ── AIM Section: Modules & Components ────────────────────

    def _section_modules_from_aim(self, lines: List[str], aim, mmd_code=None) -> None:
        lines.append("## Modules & Components")
        lines.append("")

        if mmd_code and "Empty[" not in mmd_code:
            lines.append("### Business Process Flow")
            lines.append("")
            lines.append("```mermaid")
            lines.append(mmd_code.strip())
            lines.append("```")
            lines.append("")

        if not aim.services.services:
            lines.append("*No architectural modules detected.*")
            lines.append("")
            return

        # Table: Component | Purpose
        lines.append("| Component | Purpose |")
        lines.append("|-----------|---------|")
        for srv in aim.services.services:
            resp = srv.responsibility
            if len(resp) > 120:
                resp = resp[:117] + "..."
            lines.append(f"| **{srv.name}** | {resp} |")
        lines.append("")

        # Per-module description from narrative
        for srv in aim.services.services:
            desc = aim.narrative.module_descriptions.get(srv.name, "")
            if desc:
                lines.append(f"**{srv.name}**")
                lines.append("")
                lines.append(desc)
                lines.append("")

    # ── AIM Section: Data Flow Architecture ──────────────────

    def _section_data_flow_from_aim(self, lines: List[str], aim, mmd_code=None) -> None:
        lines.append("## Data Flow Architecture")
        lines.append("")

        if mmd_code and "Empty[" not in mmd_code:
            lines.append("```mermaid")
            lines.append(mmd_code.strip())
            lines.append("```")
            lines.append("")

        lines.append(aim.information.data_model_summary)
        lines.append("")

        # Information assets table
        if aim.information.information_assets:
            lines.append("### Key Information Assets")
            lines.append("")
            lines.append("| Asset | Type | Lifecycle | Sensitivity |")
            lines.append("|-------|------|-----------|-------------|")
            for asset in aim.information.information_assets[:6]:
                lifecycle = " → ".join(asset.lifecycle_stages[:3])
                lines.append(
                    f"| **{asset.name}** | {asset.asset_type} | {lifecycle} | {asset.sensitivity} |"
                )
            lines.append("")

        # Primary data flows
        if aim.information.primary_data_flows:
            lines.append("### Primary Data Flows")
            lines.append("")
            for flow in aim.information.primary_data_flows[:3]:
                lines.append(f"**{flow.name}:** {' → '.join(flow.stages)}")
                lines.append("")

    # ── AIM Section: Interface Design ────────────────────────

    def _section_interface_from_aim(self, lines: List[str], aim) -> None:
        lines.append("## Interface Design")
        lines.append("")
        lines.append(aim.integration.integration_narrative)
        lines.append("")

        non_internal = [
            ip for ip in aim.integration.integration_points
            if ip.is_external or ip.protocol not in ("Internal", "Function Call")
        ]
        if non_internal:
            lines.append("### Integration Points")
            lines.append("")
            lines.append("| Integration | Direction | Protocol | Purpose |")
            lines.append("|-------------|-----------|----------|---------|")
            for ip in non_internal[:6]:
                purpose = ip.purpose
                if len(purpose) > 100:
                    purpose = purpose[:97] + "..."
                lines.append(
                    f"| **{ip.name}** | {ip.direction} | {ip.protocol} | {purpose} |"
                )
            lines.append("")

    # ── AIM Section: Technology Stack ────────────────────────

    def _section_technology_from_aim(self, lines: List[str], aim) -> None:
        lines.append("## Technology Stack")
        lines.append("")
        lines.append(aim.narrative.technology_narrative)
        lines.append("")

        # Build structured table from generation_metadata
        metadata = getattr(aim, 'generation_metadata', {}) or {}
        rows = []

        languages = metadata.get("languages", [])
        frameworks = metadata.get("frameworks", [])
        databases = metadata.get("databases", [])
        ai_tools = metadata.get("ai_ml_tools", [])

        if languages:
            rows.append(("Languages", ", ".join(languages[:4])))
        if frameworks:
            rows.append(("Frameworks & Libraries", ", ".join(frameworks[:4])))
        if databases:
            rows.append(("Data Stores", ", ".join(databases[:3])))
        if ai_tools:
            rows.append(("AI / ML Runtime", ", ".join(ai_tools[:2])))
        if aim.deployment.hosting_model and aim.deployment.hosting_model != "Local":
            rows.append(("Infrastructure", aim.deployment.hosting_model))

        if rows:
            lines.append("| Category | Technologies |")
            lines.append("|----------|--------------|")
            for category, tech in rows:
                lines.append(f"| {category} | {tech} |")
            lines.append("")

        # Infrastructure components
        if aim.deployment.infrastructure_components:
            lines.append("### Infrastructure Components")
            lines.append("")
            for comp in aim.deployment.infrastructure_components:
                lines.append(f"- {comp}")
            lines.append("")

    # ── AIM Section: Deployment Architecture ─────────────────

    def _section_deployment_from_aim(self, lines: List[str], aim, mmd_code=None) -> None:
        lines.append("## Deployment Architecture")
        lines.append("")

        if mmd_code and "Empty[" not in mmd_code:
            lines.append("```mermaid")
            lines.append(mmd_code.strip())
            lines.append("```")
            lines.append("")

        lines.append(aim.narrative.deployment_narrative)
        lines.append("")

        # Deployment units table
        if aim.deployment.deployment_units:
            lines.append("### Deployment Units")
            lines.append("")
            lines.append("| Unit | Type | Runtime | Services |")
            lines.append("|------|------|---------|----------|")
            for unit in aim.deployment.deployment_units:
                services = ", ".join(unit.hosted_services[:3])
                lines.append(
                    f"| **{unit.name}** | {unit.unit_type} | {unit.runtime} | {services} |"
                )
            lines.append("")
        else:
            # Fallback: generate a minimal deployment summary from known info
            lines.append("### Runtime Environment")
            lines.append("")
            lines.append("| Attribute | Value |")
            lines.append("|-----------|-------|")
            lines.append(f"| Hosting Model | {aim.deployment.hosting_model} |")
            if aim.deployment.infrastructure_components:
                lines.append(f"| Infrastructure | {', '.join(aim.deployment.infrastructure_components[:3])} |")
            lines.append(f"| Services | {len(aim.services.services)} |")
            lines.append("")