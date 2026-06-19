"""
docx_service/lld_docx_generator.py
────────────────────────────────────────────────────────────────
LLD-Specific DOCX Generator.

Generates professional LLD.docx from either:
  - A SemanticIR object (via document_generator + diagram_generator)
  - Raw markdown text (from LLM output)

LLD DOCX Structure (14 sections):
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
from typing import Optional

from .docx_builder import DocxBuilder


class LLDDocxGenerator:
    """
    Generates enterprise-grade LLD DOCX documents.
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
        Generate LLD.docx from LLM-generated markdown.

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

        is_large = len(markdown_text) > 40000

        # Cover page
        builder.add_cover_page(
            title="Low-Level Design",
            subtitle="Detailed Technical Documentation",
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
        markdown_text = re.sub(r'## Table of Contents\n+.*?(?=\n## )', '', markdown_text, flags=re.DOTALL)

        # Main content from markdown
        builder.from_markdown(markdown_text)



        # Headers & footers
        builder.setup_headers_footers(
            title="Low-Level Design (LLD)",
            version=f"v{self.version}",
        )

        return builder.save(output_path)

    def generate_from_semantic_ir(
        self,
        semantic_ir,
        output_path: str,
        kg=None,
        repo_path: str = "",
        lld_model=None,
    ) -> str:
        """
        Generate LLD.docx from SemanticIR using the existing
        LLDGenerator and LLDSequenceGenerator.

        This produces the full structured LLD with embedded
        sequence diagrams.
        """
        from backend.document_generator.lld_generator import LLDGenerator
        from backend.diagram_generator.lld_sequence_generator import (
            LLDSequenceGenerator,
        )
        from backend.object_model_extractor.extractor import ObjectModelExtractor

        # Extract Object Model (LLDModel)
        # 1. Transform SemanticIR + KG -> LLD Model if not provided
        if lld_model is None:
            obj_extractor = ObjectModelExtractor()
            lld_model = obj_extractor.extract(semantic_ir, kg)
            
            # Summarize the raw LLD model so docx has cleaner content
            from backend.document_generator.summarizer import DocumentationSummarizer
            lld_model = DocumentationSummarizer().summarize_lld(lld_model)

        # Generate diagrams (6 types)
        seq_gen = LLDSequenceGenerator()
        mermaid_codes = seq_gen.generate(lld_model)

        # Generate markdown content with diagram paths
        lld_gen = LLDGenerator()
        md_content = lld_gen.generate(
            lld_model, 
            diagram_paths=mermaid_codes, 
            repo_path=repo_path
        )

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
            title="Low-Level Design",
            subtitle="Detailed Technical Documentation",
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
        md_content = re.sub(r'## Table of Contents\n+.*?(?=\n## )', '', md_content, flags=re.DOTALL)

        # Main content from generated markdown (includes embedded mermaid blocks)
        builder.from_markdown(md_content)



        # Headers & footers
        builder.setup_headers_footers(
            title="Low-Level Design (LLD)",
            version=f"v{self.version}",
        )

        return builder.save(output_path)

    def _log(self, msg: str):
        if self.verbose:
            print(msg, flush=True)
