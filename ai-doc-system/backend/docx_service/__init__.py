"""
docx_service — Enterprise Document Generation Service.

Produces professionally formatted .docx documents (HLD, LLD)
with embedded Mermaid diagrams, cover pages, TOC, enterprise
styling, headers/footers, and page numbers.
"""

from .docx_builder import DocxBuilder
from .mermaid_renderer import MermaidToPng
from .hld_docx_generator import HLDDocxGenerator
from .lld_docx_generator import LLDDocxGenerator

__all__ = [
    "DocxBuilder",
    "MermaidToPng",
    "HLDDocxGenerator",
    "LLDDocxGenerator",
]
