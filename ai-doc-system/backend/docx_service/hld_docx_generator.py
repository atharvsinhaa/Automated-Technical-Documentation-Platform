"""
docx_service/hld_docx_generator.py
────────────────────────────────────────────────────────────────
HLD-Specific DOCX Generator.

Generates professional HLD.docx from either:
  - A SemanticIR object (via document_generator + diagram_generator)
  - Raw markdown text (from LLM output)

HLD DOCX Structure:
  1.  Cover Page
  2.  Revision History
  3.  Table of Contents
  4.  Executive Summary
  5.  Business Overview
  6.  System Overview
  7.  Architecture Overview
  8.  Component Architecture
  9.  Service Architecture
  10. Data Flow Diagrams
  11. API Architecture
  12. Integration Architecture
  13. Security Architecture
  14. Scalability Architecture
  15. Deployment Architecture
  16. Operational Architecture
  17. Risks and Assumptions
  18. Appendix
"""

from __future__ import annotations

import os
from typing import Optional

from .docx_builder import DocxBuilder


class HLDDocxGenerator:
    """
    Generates enterprise-grade HLD DOCX documents.
    """

    def __init__(
        self,
        project_name: str = "AI Documentation",
        repo_name: str = "",
        version: str = "1.0",
        verbose: bool = True,
    ):
        self.project_name = project_name
        self.repo_name = repo_name
        self.version = version
        self.verbose = verbose

    def generate_from_markdown(
        self,
        markdown_text: str,
        output_path: str,
    ) -> str:
        """
        Generate HLD.docx from LLM-generated markdown.

        The markdown is parsed, Mermaid diagrams are rendered to PNG,
        tables are converted to Word tables, and everything is
        assembled with enterprise formatting.
        """
        builder = DocxBuilder(
            project_name=self.project_name,
            repo_name=self.repo_name,
            version=self.version,
            verbose=self.verbose,
        )

        # Cover page
        builder.add_cover_page(
            title="High-Level Design",
            subtitle="Architecture Documentation",
            project=self.project_name,
            repo=self.repo_name,
            version=self.version,
            page_break=False,
        )

        builder.add_revision_history()

        # Table of Contents
        builder.add_toc(page_break=False)

        # Strip Markdown TOC so we don't have duplicate TOCs
        import re
        markdown_text = re.sub(r'## Table of Contents\n+.*?(?=\n## |\Z)', '', markdown_text, flags=re.DOTALL)

        # Main content from markdown
        builder.from_markdown(markdown_text)
        is_large = len(markdown_text) > 40000



        # Headers & footers
        builder.setup_headers_footers(
            title="High-Level Design (HLD)",
            version=f"v{self.version}",
        )

        return builder.save(output_path)

    def generate_from_semantic_ir(
        self,
        semantic_ir,
        output_path: str,
    ) -> str:
        """
        Generate HLD.docx from SemanticIR using the existing
        HLDGenerator and HLDMermaidGenerator.

        This produces the full structured HLD with embedded
        architecture diagrams.
        """
        from backend.document_generator.hld_generator import HLDGenerator
        from backend.diagram_generator.hld_mermaid_generator import (
            HLDMermaidGenerator,
        )
        from backend.architecture_extractor.extractor import ArchitectureExtractor

        # Extract Architecture Blueprint
        extractor = ArchitectureExtractor()
        blueprint = extractor.extract(semantic_ir)

        # Apply compression layer
        from backend.document_generator.summarizer import DocumentationSummarizer
        blueprint = DocumentationSummarizer().summarize_hld(blueprint)

        # Generate architecture diagram first
        mermaid_gen = HLDMermaidGenerator()
        mermaid_code = mermaid_gen.generate(blueprint)

        # Generate markdown content with embedded diagrams
        hld_gen = HLDGenerator()
        md_content = hld_gen.generate(blueprint, diagram_paths=mermaid_code)

        # Build document
        builder = DocxBuilder(
            project_name=self.project_name,
            repo_name=self.repo_name,
            version=self.version,
            verbose=self.verbose,
        )

        is_large = len(md_content) > 40000

        # Cover page
        builder.add_cover_page(
            title="High-Level Design",
            subtitle="Architecture Documentation",
            project=self.project_name,
            repo=self.repo_name,
            version=self.version,
            page_break=is_large,
        )

        builder.add_revision_history()

        # Table of Contents
        builder.add_toc(page_break=is_large)

        # Strip Markdown TOC so we don't have duplicate TOCs
        import re
        md_content = re.sub(r'## Table of Contents\n+.*?(?=\n## |\Z)', '', md_content, flags=re.DOTALL)

        # Main content from generated markdown
        builder.from_markdown(md_content)





        # Headers & footers
        builder.setup_headers_footers(
            title="High-Level Design (HLD)",
            version=f"v{self.version}",
        )

        return builder.save(output_path)

    def generate_from_aim(
        self,
        aim,
        output_path: str,
        diagram_paths: Dict[str, str] = None,
    ) -> str:
        """
        Generate HLD.docx from ArchitectureIntelligenceModel.

        Uses the AIE-powered generate_from_aim path for
        consulting-grade narratives.
        """
        from backend.document_generator.hld_generator import HLDGenerator
        from backend.diagram_generator.hld_mermaid_generator import (
            HLDMermaidGenerator,
        )
        from backend.architecture_extractor.extractor import ArchitectureExtractor

        # Still need diagrams — generate from a rebuilt blueprint
        # (AIE doesn't replace diagram generation yet)
        mermaid_code = diagram_paths or {}

        # Generate markdown content via AIM path
        hld_gen = HLDGenerator()
        md_content = hld_gen.generate_from_aim(aim, diagram_paths=mermaid_code)

        # Build document
        builder = DocxBuilder(
            project_name=self.project_name,
            repo_name=self.repo_name,
            version=self.version,
            verbose=self.verbose,
        )

        is_large = len(md_content) > 40000

        # Cover page
        builder.add_cover_page(
            title="High-Level Design",
            subtitle="Architecture Documentation",
            project=self.project_name,
            repo=self.repo_name,
            version=self.version,
            page_break=is_large,
        )

        builder.add_revision_history()

        # Table of Contents
        builder.add_toc(page_break=is_large)

        # Strip Markdown TOC so we don't have duplicate TOCs
        import re
        md_content = re.sub(r'## Table of Contents\n+.*?(?=\n## |\Z)', '', md_content, flags=re.DOTALL)

        # Main content from generated markdown
        builder.from_markdown(md_content)



        # Headers & footers
        builder.setup_headers_footers(
            title="High-Level Design (HLD)",
            version=f"v{self.version}",
        )

        return builder.save(output_path)

    def _log(self, msg: str):
        if self.verbose:
            print(msg, flush=True)

