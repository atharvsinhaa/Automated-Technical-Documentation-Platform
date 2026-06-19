import re

with open("backend/document_generator/lld_generator.py", "r") as f:
    code = f.read()

old_gen = """    def generate(self, model: LLDModel, diagram_paths: dict = None, repo_path: str = "") -> str:
        dp = diagram_paths or {}
        
        # Backfill missing data
        model = SourceBackfiller().backfill(model, repo_path)
        
        flags = self._validate_document(model)
        
        lines = []
        lines.append("# Low-Level Design (LLD)")
        lines.append("")
        
        # Mandatory System Snapshot
        self._section_snapshot(lines, model, repo_path, dp)
        
        if not flags.get("suppress_arch"):
            pass  # Arch details would go here if any were separated from snapshot
            
        self._section_circular_dependencies(lines, model)
        self._section_module_map(lines, model, dp)
        self._section_enterprise_diagrams(lines, model, dp)
        
        if not flags.get("suppress_flows"):
            self._section_pipeline_flow(lines, model, repo_path, dp)
            
        self._section_dependencies(lines, model, dp)
        self._section_coupling_matrix(lines, model)
        self._section_error_analysis(lines, model)
        
        return "\\n".join(lines)"""

new_gen = """    def _build_toc(self, body_lines) -> list:
        toc_lines = ["## Table of Contents", ""]
        counter = 1
        for line in body_lines:
            if line.startswith("## ") and not line.startswith("### "):
                clean_title = line[3:].strip()
                clean_title = __import__('re').sub(r'^\\d+\\.\\s+', '', clean_title)
                anchor = clean_title.lower().replace(" ", "-")
                anchor = __import__('re').sub(r'[^\\w\\-]', '', anchor)
                toc_lines.append(f"{counter}. [{clean_title}](#{anchor})")
                counter += 1
        toc_lines.append("")
        return toc_lines

    def generate(self, model: LLDModel, diagram_paths: dict = None, repo_path: str = "") -> str:
        dp = diagram_paths or {}
        
        # Backfill missing data
        model = SourceBackfiller().backfill(model, repo_path)
        
        flags = self._validate_document(model)
        
        body_lines = []
        # Mandatory System Snapshot
        self._section_snapshot(body_lines, model, repo_path, dp)
        
        if not flags.get("suppress_arch"):
            pass
            
        self._section_circular_dependencies(body_lines, model)
        self._section_module_map(body_lines, model, dp)
        self._section_enterprise_diagrams(body_lines, model, dp)
        
        if not flags.get("suppress_flows"):
            self._section_pipeline_flow(body_lines, model, repo_path, dp)
            
        self._section_dependencies(body_lines, model, dp)
        self._section_coupling_matrix(body_lines, model)
        self._section_error_analysis(body_lines, model)
        
        toc = self._build_toc(body_lines)
        
        user_text = [
            "## 7. LLD Enterprise Accuracy & Analysis Hardening",
            "",
            "PRIMARY OBJECTIVE",
            "",
            "Accuracy > Completeness > Document Length",
            "",
            "If evidence is insufficient:",
            "- Output \\"Not enough evidence detected\\"",
            "- Omit the section",
            "- Never fabricate information",
            "- Never use generic template text",
            "",
            "An incorrect statement is a failure.",
            "A missing statement is acceptable.",
            ""
        ]

        lines = []
        lines.append("# Low-Level Design (LLD)")
        lines.append("")
        lines.extend(toc)
        lines.extend(user_text)
        lines.extend(body_lines)
        
        return "\\n".join(lines)"""

code = code.replace(old_gen, new_gen)

with open("backend/document_generator/lld_generator.py", "w") as f:
    f.write(code)

print("TOC restored")
