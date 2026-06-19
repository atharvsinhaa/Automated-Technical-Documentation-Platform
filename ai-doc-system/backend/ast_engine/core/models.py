"""
core/models.py
─────────────────────────────────────────────────────────────
Immutable data models shared across the entire engine.
No dependencies on tree-sitter; pure Python dataclasses.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional
from .node_taxonomy import NodeCategory


@dataclass
class ASTNode:
    """
    Universal representation of one extracted AST construct.
    Produced by extractors; consumed by the XML generator.
    """
    category:    NodeCategory
    raw_type:    str               # original tree-sitter node type
    name:        str               # identifier / best name we can derive
    start_line:  int
    end_line:    int
    file_path:   str
    language:    str

    # Optional enrichment fields
    parent_name:    Optional[str]       = None
    docstring:      Optional[str]       = None
    params:         List[str]           = field(default_factory=list)
    return_type:    Optional[str]       = None
    decorators:     List[str]           = field(default_factory=list)
    modifiers:      List[str]           = field(default_factory=list)   # public/static/final
    is_async:       bool                = False
    is_exported:    bool                = False
    body_preview:   Optional[str]       = None   # ≤200 chars, collapsed

    # Nested children (set by the walker after extraction)
    children:       List["ASTNode"]     = field(default_factory=list)

    @property
    def category_name(self) -> str:
        return self.category.name   # e.g. "FUNCTION"


@dataclass
class ParsedFile:
    """All extraction results for one source file."""
    file_path:   str
    language:    str
    total_lines: int
    nodes:       List[ASTNode]  = field(default_factory=list)
    errors:      List[str]      = field(default_factory=list)

    @property
    def node_count(self) -> int:
        return len(self.nodes)


@dataclass
class ParsedProject:
    """Aggregation of all parsed files — the root output object."""
    name:         str
    root_path:    str
    files:        List[ParsedFile]  = field(default_factory=list)
    errors:       List[str]         = field(default_factory=list)

    @property
    def total_files(self) -> int:
        return len(self.files)

    @property
    def total_nodes(self) -> int:
        return sum(f.node_count for f in self.files)
