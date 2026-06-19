"""
combiner/models.py
──────────────────────────────────────────────────────────────
Pure Python dataclasses — no external dependencies.
These are the intermediate representations the combiner works with.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class RawNode:
    """
    One extracted AST node as read from a Component 1 XML file.
    Mirrors the attributes Component 1 writes onto every element.
    """
    tag:          str            # XML element tag: Function, Class, Loop, …
    category:     str            # type attribute: FUNCTION, CLASS, LOOP, …
    name:         str
    file_path:    str            # abs_path attribute
    rel_path:     str            # path attribute (relative)
    language:     str
    start_line:   int
    end_line:     int
    parent:       Optional[str]  = None
    raw_type:     Optional[str]  = None
    is_async:     bool           = False
    is_exported:  bool           = False
    return_type:  Optional[str]  = None
    params:       List[str]      = field(default_factory=list)
    decorators:   List[str]      = field(default_factory=list)
    modifiers:    List[str]      = field(default_factory=list)
    docstring:    Optional[str]  = None
    body_preview: Optional[str]  = None

    @property
    def qualified_name(self) -> str:
        """parent.name or just name."""
        if self.parent:
            return f"{self.parent}.{self.name}"
        return self.name

    @property
    def file_key(self) -> str:
        return self.rel_path or self.file_path


@dataclass
class FileRecord:
    """Metadata + all nodes for one source file."""
    rel_path:   str
    abs_path:   str
    language:   str
    total_lines: int
    node_count:  int
    nodes:       List[RawNode] = field(default_factory=list)
    errors:      List[str]     = field(default_factory=list)


@dataclass
class Dependency:
    """A directed cross-file relationship."""
    source_file:  str
    target_file:  str
    dep_type:     str            # IMPORT | API_CALL | FUNCTION_CALL | SQL_USE
                                 # | EXPORT_USE | CLASS_USE | MODULE_USE
    source_symbol: Optional[str] = None   # which symbol in source triggers this
    target_symbol: Optional[str] = None   # which symbol in target is referenced
    confidence:    str           = "high" # high | medium | low
    evidence:      Optional[str] = None   # human-readable explanation


@dataclass
class SQLTable:
    """A SQL table/view referenced across the project."""
    name:        str
    defined_in:  Optional[str]         = None  # file where CREATE TABLE appears
    operations:  List[str]             = field(default_factory=list)  # CREATE/INSERT/SELECT…
    referenced_in: List[str]           = field(default_factory=list)  # files that reference it


@dataclass
class NormalizedSymbol:
    """
    A function/class/method after name normalisation.
    snake_case and camelCase variants of the same symbol are unified here.
    """
    canonical_name:  str          # always snake_case
    original_names:  List[str]    = field(default_factory=list)
    category:        str          = ""
    defined_in:      List[str]    = field(default_factory=list)   # rel_paths
    called_from:     List[str]    = field(default_factory=list)   # rel_paths


@dataclass
class CombinedProject:
    """Root model — the complete output of the combiner."""
    name:         str
    source_files: List[str]          = field(default_factory=list)
    files:        List[FileRecord]   = field(default_factory=list)
    dependencies: List[Dependency]   = field(default_factory=list)
    sql_tables:   List[SQLTable]     = field(default_factory=list)
    symbols:      List[NormalizedSymbol] = field(default_factory=list)
    errors:       List[str]          = field(default_factory=list)

    @property
    def total_nodes(self) -> int:
        return sum(f.node_count for f in self.files)
