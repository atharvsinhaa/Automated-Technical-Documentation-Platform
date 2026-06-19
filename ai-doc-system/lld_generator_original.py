"""
document_generator/lld_generator.py
────────────────────────────────────────────────────────────────
Enterprise LLD Document Generator — 14-Section Architecture.

Generates a Low-Level Design document from an Object Model (LLDModel).

Output sections:
  1.  Executive Summary
  2.  System Overview
  3.  Component Architecture
  4.  Module Design
  5.  Class Design
  6.  Class Diagram
  7.  Sequence Diagrams
  8.  API Specifications
  9.  Data Model
  10. Database Design / ERD
  11. Dependency Architecture
  12. External Integrations
  13. Error Handling Strategy
  14. Deployment Units
"""

from __future__ import annotations

import os
import re
from typing import List, Dict
from collections import defaultdict

from backend.object_model_extractor.models import LLDModel


class LLDGenerator:

    def generate(
        self,
        model: LLDModel,
        diagram_paths: Dict[str, str] = None,
        repository_name: str = "Unknown"
    ) -> str:
        """
        Generate enterprise-grade LLD from LLDModel.
        """
        header_lines: List[str] = []
        self._section_title(header_lines, repository_name)

        body_lines: List[str] = []
        dp = diagram_paths or {}

        self._repo_name = repository_name
        
        # Section order matches the 14-section target
        self._section_executive_summary(body_lines, model, repository_name)       # 1
        self._section_system_overview(body_lines, model)                           # 2
        self._section_component_architecture(body_lines, model,                    # 3
            dp.get("component_architecture_diagram"))
        self._section_module_design(body_lines, model)                             # 4
        self._section_class_design(body_lines, model)                              # 5
        self._section_class_diagram(body_lines, dp.get("class_diagram"))           # 6
        self._section_sequence_diagrams(body_lines, model,                         # 7
            dp)
        self._section_api_specifications(body_lines, model)                        # 8
        self._section_data_model(body_lines, model)                                # 9
        self._section_data_types_and_tables(body_lines, model)                     # 9b
        self._section_database_design(body_lines, model,                           # 10
            dp.get("erd_diagram"))
        self._section_dependency_architecture(body_lines, model,                   # 11
            dp.get("dependency_diagram"))
        self._section_external_integrations(body_lines, model)                     # 12
        self._section_design_patterns(body_lines, model)                           # 13
        self._section_error_handling_strategy(body_lines, model)                   # 14
        self._section_deployment_units(body_lines, model,                          # 15
            dp.get("deployment_unit_diagram"))
        
        # New appended sections
        self._section_security_design(body_lines, model)
        self._section_configuration_design(body_lines, model)

        toc_lines = self._build_toc(body_lines)
        return "\n".join(header_lines + toc_lines + body_lines)

    # ══════════════════════════════════════════════════════════
    #  TOC Builder
    # ══════════════════════════════════════════════════════════

    def _build_toc(self, body_lines: List[str]) -> List[str]:
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
        return toc_lines

    # ══════════════════════════════════════════════════════════
    #  Title
    # ══════════════════════════════════════════════════════════

    def _section_title(self, lines: List[str], repository_name: str = "Unknown"):
        from datetime import datetime
        now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

        lines.append("# Low-Level Design (LLD)")
        lines.append("")
        lines.append(f"**Generated:** {now}")
        lines.append(f"**Repository:** {repository_name}")
        lines.append("**Tool:** AI Documentation Platform")
        lines.append("**Version:** 1.0")
        lines.append("")

    # ══════════════════════════════════════════════════════════
    #  SECTION 1: Executive Summary
    # ══════════════════════════════════════════════════════════

    def _section_executive_summary(self, lines: List[str], model: LLDModel, repo_name: str):
        lines.append("## Executive Summary")
        lines.append("")
        n_cls = len(model.classes)
        n_api = len(model.api_specs)
        n_mod = len(model.modules)
        n_db  = len(model.database_objects)
        lines.append(
            f"This Low-Level Design document describes the detailed technical architecture of the "
            f"**{repo_name}** system. It covers {n_mod} module(s), {n_cls} class(es), "
            f"{n_api} API endpoint(s), and {n_db} data store object(s). "
            f"The document is intended for developers, technical leads, and architects who "
            f"require implementation-level detail beyond the High-Level Design."
        )
        lines.append("")
        lines.append("| Dimension | Count |")
        lines.append("|-----------|-------|")
        lines.append(f"| Modules | {n_mod} |")
        lines.append(f"| Classes | {n_cls} |")
        lines.append(f"| Interfaces | {len(model.interfaces)} |")
        lines.append(f"| API Endpoints | {n_api} |")
        lines.append(f"| Database Objects | {n_db} |")
        lines.append(f"| Sequence Flows | {len(model.sequence_flows)} |")
        lines.append(f"| External Integrations | {len(model.external_integrations)} |")
        lines.append(f"| Deployment Units | {len(model.deployment_units)} |")
        lines.append("")

    # ══════════════════════════════════════════════════════════
    #  SECTION 2: System Overview
    # ══════════════════════════════════════════════════════════

    def _section_system_overview(self, lines: List[str], model: LLDModel):
        lines.append("## System Overview")
        lines.append("")
        if model.system_overview:
            lines.append(model.system_overview)
        else:
            lines.append(f"System type: **{model.repository_type}**")
        lines.append("")
        # Architecture pattern summary
        pattern = model.metadata.get("architecture_pattern", "")
        if pattern:
            lines.append(f"**Architecture Pattern:** {pattern}")
            lines.append("")
        # Languages and frameworks
        langs = model.metadata.get("languages", [])
        fws = model.metadata.get("frameworks", [])
        if langs:
            lines.append(f"**Languages:** {', '.join(langs)}")
        if fws:
            lines.append(f"**Frameworks:** {', '.join(fws[:4])}")
        lines.append("")

    # ══════════════════════════════════════════════════════════
    #  SECTION 3: Component Architecture
    # ══════════════════════════════════════════════════════════

    def _section_component_architecture(self, lines: List[str], model: LLDModel, mmd_code=None):
        lines.append("## Component Architecture")
        lines.append("")
        if mmd_code and "Empty[" not in mmd_code:
            lines.append("```mermaid")
            lines.append(mmd_code.strip())
            lines.append("```")
            lines.append("")
        if not model.components:
            lines.append("*No components detected.*")
            lines.append("")
            return
        # Group by layer
        by_layer = defaultdict(list)
        for c in model.components:
            by_layer[c.layer].append(c)
        LAYER_ORDER = ["Presentation", "Application", "Domain", "Infrastructure"]
        for layer in LAYER_ORDER:
            comps = by_layer.get(layer, [])
            if not comps:
                continue
            lines.append(f"### {layer} Layer")
            lines.append("")
            lines.append("| Component | Type | Responsibility |")
            lines.append("|-----------|------|----------------|")
            for c in comps:
                lines.append(f"| **{c.name}** | {c.component_type} | {c.responsibility} |")
            lines.append("")

    # ══════════════════════════════════════════════════════════
    #  SECTION 4: Module Design
    # ══════════════════════════════════════════════════════════

    def _section_module_design(self, lines: List[str], model: LLDModel):
        lines.append("## Module Design")
        lines.append("")
        if not model.modules:
            lines.append("*No modules detected.*")
            lines.append("")
            return
        for mod in model.modules:
            lines.append(f"### {mod.name}")
            lines.append("")
            lines.append(f"**Package:** `{mod.package_path}`")
            lines.append("")
            lines.append(f"**Responsibility:** {mod.responsibility}")
            lines.append("")
            if mod.classes_contained:
                lines.append(f"**Classes:** {', '.join([f'`{c}`' for c in mod.classes_contained])}")
            if mod.exposed_apis:
                lines.append(f"**Exposes:** {', '.join([f'`{a}`' for a in mod.exposed_apis])}")
            if mod.depends_on_modules:
                lines.append(f"**Depends On:** {', '.join(mod.depends_on_modules)}")
            lines.append("")

    # ══════════════════════════════════════════════════════════
    #  SECTION 5: Class Design
    # ══════════════════════════════════════════════════════════

    def _section_class_design(self, lines: List[str], model: LLDModel):
        lines.append("## Class Design")
        lines.append("")

        if not model.classes and not model.interfaces:
            lines.append("*No classes or interfaces detected.*")
            lines.append("")
            return

        # 1. Interfaces
        if model.interfaces:
            lines.append("### Interfaces")
            lines.append("")
            for iface in model.interfaces:
                lines.append(f"#### `{iface.name}`")
                if iface.description:
                    lines.append(f"_{iface.description}_")
                lines.append("")
                if iface.methods:
                    lines.append("| Method | Parameters | Returns | Description |")
                    lines.append("|--------|------------|---------|-------------|")
                    for m in iface.methods:
                        params = ", ".join(m.parameters) if m.parameters else "—"
                        ret = m.return_type or "Any"
                        desc = m.description or ""
                        lines.append(f"| `{m.name}` | {params} | {ret} | {desc} |")
                    lines.append("")

        # Bucket classes by heuristics
        exception_classes = []
        core_classes = []
        utility_classes = []

        summarizer_meta = model.metadata.get("summarizer", {})
        known_utils = set(summarizer_meta.get("utility_classes", []))

        for cls in model.classes:
            is_error = cls.name.endswith("Error") or cls.name.endswith("Exception")
            if not is_error and cls.inherits_from:
                is_error = any(b in ("Exception", "BaseException", "Error") for b in cls.inherits_from)
                
            if is_error:
                exception_classes.append(cls)
            elif cls.name in known_utils or ("util" in cls.name.lower() and len(cls.methods) <= 2):
                utility_classes.append(cls)
            else:
                core_classes.append(cls)

        if core_classes:
            lines.append("### Core Classes")
            lines.append("")
            for cls in core_classes:
                self._render_class_full(lines, cls)

        if exception_classes:
            lines.append("### Exception Types")
            lines.append("")
            for cls in exception_classes:
                self._render_class_full(lines, cls)

        if utility_classes:
            lines.append("### Utility & Helper Classes")
            lines.append("")
            # Render utils in a condensed table
            lines.append("| Class | Description |")
            lines.append("|-------|-------------|")
            for cls in utility_classes:
                desc = cls.description or "Utility class."
                lines.append(f"| `{cls.name}` | {desc} |")
            lines.append("")

    def _render_class_full(self, lines: List[str], cls):
        lines.append(f"#### `{cls.name}`")
        if cls.description:
            lines.append(f"_{cls.description}_")
        lines.append("")
        meta_parts = []
        if cls.inherits_from:
            meta_parts.append(f"**Inherits:** {', '.join(cls.inherits_from)}")
        if cls.implements:
            meta_parts.append(f"**Implements:** {', '.join(cls.implements)}")
        if cls.dependencies:
            meta_parts.append(f"**Depends On:** {', '.join(cls.dependencies[:4])}")
        for p in meta_parts:
            lines.append(p)
        if meta_parts:
            lines.append("")
            
        if cls.fields:
            lines.append("**Fields:**")
            lines.append("")
            lines.append("| Name | Type | Access |")
            lines.append("|------|------|--------|")
            for fld in cls.fields[:10]:
                raw = fld.strip()
                if ":" in raw:
                    fname, ftype = raw.split(":", 1)
                    fname = fname.strip()
                    ftype = ftype.strip()
                else:
                    fname = raw
                    ftype = "Any"
                access = "private" if fname.startswith("_") else "public"
                fname_display = fname.lstrip("_")
                lines.append(f"| `{fname_display}` | `{ftype}` | {access} |")
            lines.append("")
            
        if cls.methods:
            lines.append("**Methods:**")
            lines.append("")
            lines.append("| Method | Parameters | Returns | Description |")
            lines.append("|--------|------------|---------|-------------|")
            for m in cls.methods[:10]:
                params = ", ".join(m.parameters) if m.parameters else "—"
                ret = m.return_type or "Any"
                desc = m.description or ""
                lines.append(f"| `{m.name}` | {params} | {ret} | {desc} |")
            lines.append("")

    # ══════════════════════════════════════════════════════════
    #  SECTION 6: Class Diagram
    # ══════════════════════════════════════════════════════════

    def _section_class_diagram(self, lines: List[str], mmd_code):
        lines.append("## Class Diagram")
        lines.append("")
        if mmd_code and "EmptySystem" not in mmd_code:
            lines.append("```mermaid")
            lines.append(mmd_code.strip())
            lines.append("```")
        else:
            lines.append("*Class diagram not available.*")
        lines.append("")

    # ══════════════════════════════════════════════════════════
    #  SECTION 7: Sequence Diagrams
    # ══════════════════════════════════════════════════════════

    def _section_sequence_diagrams(
        self, lines: List[str], model: LLDModel, dp: Dict[str, str]
    ):
        lines.append("## Sequence Diagrams")
        lines.append("")

        if not model.sequence_flows:
            lines.append("*No execution flows detected.*")
            lines.append("")
            return

        lines.append(
            f"The system has **{len(model.sequence_flows)}** documented execution flow(s):"
        )
        lines.append("")

        for i, flow in enumerate(model.sequence_flows, 1):
            lines.append(f"### Flow {i}: {flow.name}")
            if flow.description:
                lines.append(f"_{flow.description}_")
            lines.append("")
            lines.append(f"**Trigger:** `{flow.trigger}`")
            lines.append("")
            
            diagram_key = "sequence_diagram" if i == 1 else f"sequence_diagram_{i}"
            mmd_code = dp.get(diagram_key)
            if mmd_code and "No execution flows detected" not in mmd_code:
                lines.append("```mermaid")
                lines.append(mmd_code.strip())
                lines.append("```")
                lines.append("")
            
            lines.append("**Step-by-Step Walkthrough:**")
            lines.append("")
            for idx, step in enumerate(flow.steps, 1):
                lines.append(f"{idx}. {step}")
            lines.append("")
            lines.append("")

            if flow.steps:
                lines.append("| Step | Action |")
                lines.append("|------|--------|")
                for j, step in enumerate(flow.steps, 1):
                    step_clean = step.replace("|", "\\|")
                    lines.append(f"| {j} | {step_clean} |")
                lines.append("")

    # ══════════════════════════════════════════════════════════
    #  SECTION 8: API Specifications
    # ══════════════════════════════════════════════════════════

    def _section_api_specifications(self, lines: List[str], model: LLDModel):
        lines.append("## API Specifications")
        lines.append("")
        if not model.api_specs:
            lines.append("*No API endpoints detected.*")
            lines.append("")
            return
        # Group by service
        by_service = defaultdict(list)
        for spec in model.api_specs:
            by_service[spec.service].append(spec)
        for service, specs in by_service.items():
            lines.append(f"### {service}")
            lines.append("")
            lines.append("| Method | Endpoint | Auth | Description |")
            lines.append("|--------|----------|------|-------------|")
            for spec in specs:
                auth = "✓" if spec.auth_required else "—"
                lines.append(f"| `{spec.method}` | `{spec.path}` | {auth} | {spec.description} |")
            lines.append("")
            # Detail per endpoint
            for spec in specs:
                lines.append(f"#### `{spec.method} {spec.path}`")
                if spec.request_body:
                    lines.append(f"**Request Body:** `{', '.join(spec.request_body)}`")
                if spec.response_body:
                    lines.append(f"**Response:** `{', '.join(spec.response_body)}`")
                if spec.error_codes:
                    lines.append(f"**Error Codes:** {', '.join(spec.error_codes)}")
                lines.append("")

    # ══════════════════════════════════════════════════════════
    #  SECTION 9: Data Model
    # ══════════════════════════════════════════════════════════

    def _section_data_model(self, lines: List[str], model: LLDModel):
        lines.append("## Data Model")
        lines.append("")
        if not model.database_objects:
            lines.append("*No database objects detected.*")
            lines.append("")
            return
        lines.append("| Object | Type | Fields | Relationships |")
        lines.append("|--------|------|--------|---------------|")
        for dbo in model.database_objects:
            fields = ", ".join([f"`{f}`" for f in dbo.fields[:4]]) or "—"
            rels = ", ".join(dbo.relationships[:3]) or "—"
            lines.append(f"| **{dbo.name}** | {dbo.type} | {fields} | {rels} |")
        lines.append("")

    def _section_data_types_and_tables(self, lines: List[str], model: LLDModel):
        """
        Section 9b: Typed schema definitions, aliases, enums, and tables.
        """
        tables = getattr(model, "data_type_tables", [])
        data_types = getattr(model, "data_types", [])
        enum_types = getattr(model, "enum_types", [])
        type_aliases = getattr(model, "type_aliases", [])

        if not any([tables, data_types, enum_types, type_aliases]):
            return

        lines.append("## Data Types & Tables")
        lines.append("")
        
        # Enums
        if enum_types:
            lines.append("### Enumerations")
            lines.append("")
            lines.append("| Enum | Members | Description |")
            lines.append("|------|---------|-------------|")
            for enum in enum_types:
                members = "<br>".join([f"`{m}`" for m in enum.members])
                desc = enum.description or "—"
                lines.append(f"| **`{enum.name}`** | {members} | {desc} |")
            lines.append("")

        # Type Aliases
        if type_aliases:
            lines.append("### Type Aliases")
            lines.append("")
            lines.append("| Alias | Resolves To |")
            lines.append("|-------|-------------|")
            for alias in type_aliases:
                lines.append(f"| **`{alias.name}`** | `{alias.alias_for}` |")
            lines.append("")

        # Structured Types
        if data_types:
            lines.append("### Data Structures")
            lines.append("")
            for dt in data_types:
                lines.append(f"#### `{dt.name}` ({dt.kind})")
                if dt.description:
                    lines.append(f"_{dt.description}_")
                lines.append("")
                lines.append("| Field | Type | Optional |")
                lines.append("|-------|------|----------|")
                for fld in dt.fields:
                    opt = "Yes" if fld.is_optional else "No"
                    lines.append(f"| `{fld.name}` | `{fld.type_str}` | {opt} |")
                lines.append("")

        if tables:
            lines.append("### Database Tables")
            lines.append("")
            # Summary index table
            lines.append("| Schema | Source Type | Columns | Relationships |")
            lines.append("|--------|------------|---------|---------------|")
            for tbl in tables:
                rel_count = len(tbl.relationships)
                lines.append(
                    f"| [`{tbl.name}`](#{tbl.name.lower().replace(' ', '-')}) "
                    f"| {tbl.source_type} | {len(tbl.columns)} "
                    f"| {rel_count} |"
                )
            lines.append("")
            lines.append("")

        # Detailed schema per table
        for tbl in tables:
            lines.append(f"### `{tbl.name}`")
            if tbl.description:
                lines.append(f"_{tbl.description}_")
            lines.append("")
            lines.append(f"**Source:** {tbl.source_type}")
            if tbl.file_path and not tbl.file_path.startswith("component://"):
                lines.append(f"**File:** `{tbl.file_path}`")
            lines.append("")

            if tbl.columns:
                lines.append("| Column | Type | PK | FK | Nullable | References |")
                lines.append("|--------|------|----|----|----------|------------|")
                for col in tbl.columns:
                    pk = "✓" if col.is_primary_key else "—"
                    fk = "✓" if col.is_foreign_key else "—"
                    null = "YES" if col.is_nullable else "NO"
                    refs = f"`{col.references}`" if col.references else "—"
                    lines.append(
                        f"| `{col.name}` | `{col.data_type}` "
                        f"| {pk} | {fk} | {null} | {refs} |"
                    )
                lines.append("")

            if tbl.indexes:
                lines.append(f"**Indexes:** {', '.join([f'`{i}`' for i in tbl.indexes])}")
                lines.append("")
            if tbl.constraints:
                lines.append(f"**Constraints:** {', '.join(tbl.constraints)}")
                lines.append("")
            if tbl.relationships:
                lines.append("**Relationships:**")
                for rel in tbl.relationships:
                    lines.append(f"- {rel}")
                lines.append("")

    # ══════════════════════════════════════════════════════════
    #  SECTION 10: Database Design / ERD
    # ══════════════════════════════════════════════════════════

    def _section_database_design(self, lines: List[str], model: LLDModel, mmd_code):
        lines.append("## Database Design / ERD")
        lines.append("")
        if mmd_code and "Empty[" not in mmd_code and "No Data Entities" not in mmd_code:
            lines.append("```mermaid")
            lines.append(mmd_code.strip())
            lines.append("```")
            lines.append("")
        elif model.database_objects:
            lines.append("*ERD diagram not generated — see Data Model section.*")
            lines.append("")
        else:
            lines.append("*No database schema detected.*")
            lines.append("")

    # ══════════════════════════════════════════════════════════
    #  SECTION 11: Dependency Architecture
    # ══════════════════════════════════════════════════════════

    def _section_dependency_architecture(self, lines: List[str], model: LLDModel, mmd_code):
        lines.append("## Dependency Architecture")
        lines.append("")
        if mmd_code and "Empty[" not in mmd_code and "No Dependencies" not in mmd_code:
            lines.append("```mermaid")
            lines.append(mmd_code.strip())
            lines.append("```")
            lines.append("")
        if model.dependencies:
            circular = [d for d in model.dependencies if d.is_circular]
            if circular:
                lines.append(f"> ⚠ **Circular dependencies detected:** "
                             f"{', '.join(set([f'{d.source}↔{d.target}' for d in circular[:3]]))}")
                lines.append("")
            lines.append("| Source | Target | Type |")
            lines.append("|--------|--------|------|")
            for dep in model.dependencies[:15]:
                flag = " ♻" if dep.is_circular else ""
                lines.append(f"| `{dep.source}` | `{dep.target}` | {dep.dependency_type}{flag} |")
            lines.append("")
        else:
            lines.append("*No dependency relationships detected.*")
            lines.append("")

    # ══════════════════════════════════════════════════════════
    #  SECTION 12: External Integrations
    # ══════════════════════════════════════════════════════════

    def _section_external_integrations(self, lines: List[str], model: LLDModel):
        lines.append("## External Integrations")
        lines.append("")
        if not model.external_integrations:
            lines.append("*No external integrations detected.*")
            lines.append("")
            return
        lines.append("| Integration | Type | Direction | Auth | Data Format |")
        lines.append("|-------------|------|-----------|------|-------------|")
        for intg in model.external_integrations:
            lines.append(
                f"| **{intg.name}** | {intg.integration_type} | {intg.direction} | "
                f"{intg.auth_mechanism or '—'} | {intg.data_format or '—'} |"
            )
        lines.append("")
        for intg in model.external_integrations:
            lines.append(f"### {intg.name}")
            lines.append(f"**Type:** {intg.integration_type}  |  **Direction:** {intg.direction}")
            if intg.used_by_components:
                lines.append(f"**Used By:** {', '.join(intg.used_by_components)}")
            if intg.endpoint_or_dsn:
                lines.append(f"**Endpoint:** `{intg.endpoint_or_dsn}`")
            lines.append("")

    # ══════════════════════════════════════════════════════════
    #  SECTION 13: Design Patterns
    # ══════════════════════════════════════════════════════════

    def _section_design_patterns(self, lines: List[str], model: LLDModel):
        if getattr(model, "design_patterns", None):
            lines.append("## Design Patterns")
            lines.append("")
            lines.append("| Pattern | Confidence | Components Involved | Description |")
            lines.append("|---------|------------|---------------------|-------------|")
            for dp in model.design_patterns:
                comps = ", ".join([f"`{c}`" for c in dp.components_involved[:5]])
                lines.append(f"| **{dp.pattern_name}** | {dp.confidence} | {comps} | {dp.description} |")
            lines.append("")

    # ══════════════════════════════════════════════════════════
    #  SECTION 14: Error Handling Strategy
    # ══════════════════════════════════════════════════════════

    def _section_error_handling_strategy(self, lines: List[str], model: LLDModel):
        lines.append("## Error Handling Strategy")
        lines.append("")
        if model.error_paths:
            lines.append("| Component | Error Type | Handler | Recovery |")
            lines.append("|-----------|------------|---------|----------|")
            for ep in model.error_paths:
                recovery = ep.recovery_strategy or "Log and propagate"
                lines.append(f"| `{ep.source}` | `{ep.error_type}` | `{ep.handler}` | {recovery} |")
            lines.append("")
        else:
            lines.append("*No explicit error handling paths detected.*")
            lines.append("")

    # ══════════════════════════════════════════════════════════
    #  SECTION 14: Deployment Units
    # ══════════════════════════════════════════════════════════

    def _section_deployment_units(self, lines: List[str], model: LLDModel, mmd_code=None):
        lines.append("## Deployment Units")
        lines.append("")
        if mmd_code and "Empty[" not in mmd_code and "No Deployment" not in mmd_code:
            lines.append("```mermaid")
            lines.append(mmd_code.strip())
            lines.append("```")
            lines.append("")
        if not model.deployment_units:
            lines.append("*No deployment units detected.*")
            lines.append("")
            return
        for unit in model.deployment_units:
            lines.append(f"### {unit.name}")
            lines.append("")
            lines.append(f"**Type:** {unit.unit_type}  |  **Runtime:** {unit.runtime}")
            if unit.entry_point:
                lines.append(f"**Entry Point:** `{unit.entry_point}`")
            if unit.exposed_ports:
                lines.append(f"**Ports:** {', '.join(map(str, unit.exposed_ports))}")
            if getattr(unit, "hosts_components", None):
                lines.append(f"**Hosts:** {', '.join([f'`{c}`' for c in unit.hosts_components[:4]])}")
            if unit.environment_variables:
                lines.append(f"**Environment Variables:** {', '.join([f'`{v}`' for v in unit.environment_variables])}")
            lines.append("")

    # ══════════════════════════════════════════════════════════
    #  Save
    # ══════════════════════════════════════════════════════════


    # ══════════════════════════════════════════════════════════
    #  SECTION 15: Security Design
    # ══════════════════════════════════════════════════════════

    def _section_security_design(self, lines: List[str], model: LLDModel):
        if getattr(model, "security", None):
            lines.append("## Security Design")
            lines.append("")
            sec = model.security
            lines.append(f"**Overview:** {sec.description}")
            lines.append("")
            if sec.mechanisms:
                lines.append("**Detected Mechanisms:**")
                for m in sec.mechanisms:
                    lines.append(f"- {m}")
                lines.append("")
            if sec.detected_evidence:
                lines.append("**Evidence Nodes:**")
                lines.append(f"{', '.join(['`' + str(e) + '`' for e in sec.detected_evidence])}")
                lines.append("")

    # ══════════════════════════════════════════════════════════
    #  SECTION 16: Configuration Design
    # ══════════════════════════════════════════════════════════

    def _section_configuration_design(self, lines: List[str], model: LLDModel):
        if getattr(model, "configuration", None):
            lines.append("## Configuration Design")
            lines.append("")
            cfg = model.configuration
            lines.append(f"**Overview:** {cfg.description}")
            lines.append("")
            if cfg.environment_variables:
                lines.append("**Environment Variables Detected:**")
                for m in cfg.environment_variables:
                    lines.append(f"- `{m}`")
                lines.append("")
            if cfg.config_files:
                lines.append("**Configuration Files:**")
                for f in cfg.config_files:
                    lines.append(f"- `{f}`")
                lines.append("")


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

        print(f"[SUCCESS] LLD generated: {output_path}")