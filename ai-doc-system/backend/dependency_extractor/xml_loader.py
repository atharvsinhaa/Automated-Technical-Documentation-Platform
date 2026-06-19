"""
dependency_extractor/xml_loader.py
────────────────────────────────────────────────────────────────
Loads enterprise_combined.xml (Component 2 output) into a structured
intermediate representation optimised for graph building.

Key design:
  - All data is read once into memory as Python dicts
  - No repeated XML traversal in later stages
  - All abs_path / rel_path inconsistencies resolved here
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

try:
    from lxml import etree as ET
    _LXML = True
except ImportError:
    import xml.etree.ElementTree as ET
    _LXML = False


# ──────────────────────────────────────────────────────────────
#  Intermediate structs  (thin; graph models built later)
# ──────────────────────────────────────────────────────────────

@dataclass
class RawSymbol:
    tag:          str
    category:     str
    name:         str
    rel_path:     str
    abs_path:     str
    language:     str
    start_line:   int
    end_line:     int
    parent:       Optional[str]
    raw_type:     Optional[str]
    is_async:     bool
    is_exported:  bool
    return_type:  Optional[str]
    params:       List[str]
    decorators:   List[str]
    modifiers:    List[str]
    docstring:    Optional[str]
    body_preview: Optional[str]


@dataclass
class RawFile:
    rel_path:    str
    abs_path:    str
    language:    str
    total_lines: int
    symbols:     List[RawSymbol] = field(default_factory=list)
    errors:      List[str]       = field(default_factory=list)


@dataclass
class RawDependency:
    source:        str
    target:        str
    dep_type:      str
    confidence:    str
    source_symbol: Optional[str]
    target_symbol: Optional[str]
    evidence:      Optional[str]


@dataclass
class RawSQLTable:
    name:        str
    defined_in:  Optional[str]
    operations:  List[str]
    referenced_in: List[str]


@dataclass
class RawSymbolIndex:
    canonical:   str
    category:    str
    originals:   List[str]
    defined_in:  List[str]


@dataclass
class LoadedProject:
    name:         str
    files:        List[RawFile]
    dependencies: List[RawDependency]
    sql_tables:   List[RawSQLTable]
    symbol_index: List[RawSymbolIndex]

    # Quick lookup maps built post-load
    file_by_rel:  Dict[str, RawFile]       = field(default_factory=dict)
    file_by_abs:  Dict[str, RawFile]       = field(default_factory=dict)
    symbols_by_canonical: Dict[str, RawSymbolIndex] = field(default_factory=dict)


# ──────────────────────────────────────────────────────────────
#  Parser helpers
# ──────────────────────────────────────────────────────────────

def _a(el, key: str, default: str = "") -> str:
    return (el.get(key) or "").strip() or default

def _i(el, key: str, default: int = 0) -> int:
    try: return int(el.get(key, default))
    except (TypeError, ValueError): return default

def _b(el, key: str) -> bool:
    return el.get(key, "").lower() in ("true", "1", "yes")

def _child_texts(el, tag: str) -> List[str]:
    return [c.text.strip() for c in el.findall(f".//{tag}") if c.text]


# XML tags that carry symbol nodes
_SYMBOL_TAGS = frozenset({
    "Import", "Export", "Class", "Interface", "Enum",
    "Function", "AsyncFunction", "Method", "Constructor",
    "Property", "Variable", "Assignment", "Constant",
    "Condition", "Loop", "Switch",
    "TryBlock", "CatchBlock", "FinallyBlock", "Raise",
    "Await", "Yield", "FunctionCall", "MethodCall",
    "ObjectCreation", "Lambda", "Decorator", "Annotation",
    "TypeAlias", "Return", "Comment", "JSXElement",
    "Hook", "Component", "Query", "DDL", "DML",
    "APICall", "Expression",
})


def _parse_symbol(el, rel_path: str, abs_path: str, language: str) -> RawSymbol:
    ds = el.find("DocString")
    bp = el.find("BodyPreview")
    return RawSymbol(
        tag=el.tag,
        category=_a(el, "type", el.tag.upper()),
        name=_a(el, "name"),
        rel_path=rel_path,
        abs_path=abs_path,
        language=language,
        start_line=_i(el, "start_line"),
        end_line=_i(el, "end_line"),
        parent=el.get("parent"),
        raw_type=el.get("raw_type"),
        is_async=_b(el, "async"),
        is_exported=_b(el, "exported"),
        return_type=el.get("return_type"),
        params=_child_texts(el, "Param"),
        decorators=_child_texts(el, "Decorator"),
        modifiers=_child_texts(el, "Modifier"),
        docstring=(ds.text or "").strip() if ds is not None else None,
        body_preview=(bp.text or "").strip() if bp is not None else None,
    )


def _parse_file(file_el) -> RawFile:
    rel_path  = _a(file_el, "path")
    abs_path  = _a(file_el, "abs_path") or rel_path
    language  = _a(file_el, "language", "unknown")
    lines     = _i(file_el, "lines")
    errors    = [e.text or "" for e in file_el.findall(".//Error")]
    symbols: List[RawSymbol] = []

    # Walk all descendants — capture every symbol tag
    for el in file_el.iter():
        if el.tag in _SYMBOL_TAGS:
            sym = _parse_symbol(el, rel_path, abs_path, language)
            symbols.append(sym)

    return RawFile(
        rel_path=rel_path,
        abs_path=abs_path,
        language=language,
        total_lines=lines,
        symbols=symbols,
        errors=errors,
    )


# ──────────────────────────────────────────────────────────────
#  Public loader
# ──────────────────────────────────────────────────────────────

def load(xml_path: str) -> LoadedProject:
    """
    Load a combined XML file (Component 2 output) into a LoadedProject.
    This is the only function the graph builder calls.
    """
    if not os.path.isfile(xml_path):
        raise FileNotFoundError(f"Combined XML not found: {xml_path}")

    if _LXML:
        root = ET.parse(xml_path).getroot()
    else:
        root = ET.parse(xml_path).getroot()

    name = _a(root, "name", Path(xml_path).stem)

    # ── Files ────────────────────────────────────────────────
    files: List[RawFile] = []
    fc = root.find("Files")
    if fc is not None:
        for file_el in fc.findall("File"):
            files.append(_parse_file(file_el))

    # ── Dependencies ─────────────────────────────────────────
    deps: List[RawDependency] = []
    dc = root.find("Dependencies")
    if dc is not None:
        for d in dc.findall("Dependency"):
            deps.append(RawDependency(
                source=_a(d, "source"),
                target=_a(d, "target"),
                dep_type=_a(d, "type"),
                confidence=_a(d, "confidence", "medium"),
                source_symbol=d.get("source_symbol"),
                target_symbol=d.get("target_symbol"),
                evidence=d.get("evidence"),
            ))

    # ── SQL Tables ───────────────────────────────────────────
    sql_tables: List[RawSQLTable] = []
    sc = root.find("SQLTables")
    if sc is not None:
        for t in sc.findall("Table"):
            sql_tables.append(RawSQLTable(
                name=_a(t, "name"),
                defined_in=t.get("defined_in"),
                operations=[o.strip() for o in _a(t, "operations").split(",") if o.strip()],
                referenced_in=[r.get("file", "") for r in t.findall("ReferencedIn")],
            ))

    # ── Symbol Index ─────────────────────────────────────────
    symbol_index: List[RawSymbolIndex] = []
    si = root.find("SymbolIndex")
    if si is not None:
        for s in si.findall("Symbol"):
            symbol_index.append(RawSymbolIndex(
                canonical=_a(s, "canonical"),
                category=_a(s, "category"),
                originals=[o.strip() for o in _a(s, "originals").split(",") if o.strip()],
                defined_in=[d.get("file", "") for d in s.findall("DefinedIn")],
            ))

    # ── Build lookup maps ────────────────────────────────────
    project = LoadedProject(
        name=name,
        files=files,
        dependencies=deps,
        sql_tables=sql_tables,
        symbol_index=symbol_index,
    )
    for fr in files:
        project.file_by_rel[fr.rel_path] = fr
        if fr.abs_path:
            project.file_by_abs[fr.abs_path] = fr
    for sym in symbol_index:
        project.symbols_by_canonical[sym.canonical] = sym

    return project
