"""
combiner/xml_merger.py
──────────────────────────────────────────────────────────────
XMLMerger — loads one or many Component 1 XML files and
produces a flat, unified list of FileRecord + RawNode objects.

Supports:
  • Single XML file (one Project element)
  • Directory of XML files (merged into one project)
  • Streaming parse via lxml iterparse (memory-safe for huge repos)

WHY this is non-trivial
─────────────────────────
Component 1 produces one Project per run.
For a polyglot monorepo you may have:
  - backend.xml   (Python, Java)
  - frontend.xml  (JS, TS)
  - data.xml      (SQL)
The merger loads all of them, deduplicates files by abs_path,
and produces a unified FileRecord list.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import List, Optional

try:
    from lxml import etree as ET
    _LXML = True
except ImportError:
    import xml.etree.ElementTree as ET
    _LXML = False

from .models import FileRecord, RawNode


# ── Attribute helpers ─────────────────────────────────────────

def _attr(el, key: str, default: str = "") -> str:
    return (el.get(key) or "").strip() or default

def _int(el, key: str, default: int = 0) -> int:
    try:
        return int(el.get(key, default))
    except (TypeError, ValueError):
        return default

def _bool_attr(el, key: str) -> bool:
    return el.get(key, "").lower() in ("true", "1", "yes")


# ── Node categories we care to extract (all of them) ─────────

_KNOWN_GROUP_TAGS = {
    "Imports", "Exports", "Classes", "Interfaces", "Enums",
    "Functions", "AsyncFunctions", "Methods", "Constructors",
    "Properties", "Variables", "Conditions", "Loops",
    "SwitchStatements", "ExceptionHandling", "FunctionCalls",
    "Hooks", "JSXElements", "Queries", "DDLStatements",
    "DMLStatements", "APICalls", "Decorators", "Annotations",
    "ObjectCreations", "Awaits", "Lambdas", "Returns", "Raises",
    "Misc",
}

_LEAF_TAGS = {
    "Import", "Export", "Class", "Interface", "Enum",
    "Function", "AsyncFunction", "Method", "Constructor",
    "Property", "Variable", "Assignment", "Constant",
    "Condition", "Loop", "Switch", "BreakContinue",
    "TryBlock", "CatchBlock", "FinallyBlock", "Raise",
    "Await", "Yield", "FunctionCall", "MethodCall",
    "ObjectCreation", "Lambda", "Decorator", "Annotation",
    "TypeAlias", "Return", "Comment", "JSXElement",
    "Hook", "Component", "Query", "DDL", "DML",
    "APICall", "Expression", "Unknown",
}


def _parse_node(el) -> RawNode:
    """Parse one leaf XML element into a RawNode."""
    params = [p.text or "" for p in el.findall(".//Param")]
    decs   = [d.text or "" for d in el.findall(".//Decorator")]
    mods   = [m.text or "" for m in el.findall(".//Modifier")]
    ds_el  = el.find("DocString")
    bp_el  = el.find("BodyPreview")

    return RawNode(
        tag=el.tag,
        category=_attr(el, "type"),
        name=_attr(el, "name"),
        file_path=_attr(el, "file_path"),
        rel_path=_attr(el, "file_path"),   # will be patched after
        language=_attr(el, "language"),
        start_line=_int(el, "start_line"),
        end_line=_int(el, "end_line"),
        parent=el.get("parent"),
        raw_type=el.get("raw_type"),
        is_async=_bool_attr(el, "async"),
        is_exported=_bool_attr(el, "exported"),
        return_type=el.get("return_type"),
        params=[p for p in params if p],
        decorators=[d for d in decs if d],
        modifiers=[m for m in mods if m],
        docstring=(ds_el.text or "").strip() if ds_el is not None else None,
        body_preview=(bp_el.text or "").strip() if bp_el is not None else None,
    )


def _parse_file_element(file_el) -> FileRecord:
    """Parse one <File> element into a FileRecord with all its nodes."""
    rel_path  = _attr(file_el, "path")
    abs_path  = _attr(file_el, "abs_path") or rel_path
    language  = _attr(file_el, "language")
    lines     = _int(file_el, "lines")
    node_cnt  = _int(file_el, "nodes")

    nodes: List[RawNode] = []
    errors: List[str]   = []

    # Collect errors
    for err_el in file_el.findall(".//Error"):
        errors.append(err_el.text or "")

    # Walk group containers → leaf nodes
    for child in file_el:
        if child.tag in _KNOWN_GROUP_TAGS:
            for leaf in child:
                if leaf.tag in _LEAF_TAGS:
                    node = _parse_node(leaf)
                    node.rel_path = rel_path
                    # patch file_path if empty (SQL extractor leaves abs_path set)
                    if not node.file_path:
                        node.file_path = abs_path
                    nodes.append(node)
        elif child.tag in _LEAF_TAGS:
            node = _parse_node(child)
            node.rel_path = rel_path
            nodes.append(node)

    return FileRecord(
        rel_path=rel_path,
        abs_path=abs_path,
        language=language,
        total_lines=lines,
        node_count=node_cnt or len(nodes),
        nodes=nodes,
        errors=errors,
    )


def load_xml(xml_path: str) -> List[FileRecord]:
    """
    Load a single Component 1 XML file.
    Returns a list of FileRecord objects (one per <File> element).
    """
    if not os.path.isfile(xml_path):
        raise FileNotFoundError(f"XML not found: {xml_path}")

    if _LXML:
        tree = ET.parse(xml_path)
        root = tree.getroot()
    else:
        tree = ET.parse(xml_path)
        root = tree.getroot()

    records: List[FileRecord] = []
    _fc = root.find("Files"); files_container = _fc if _fc is not None else root
    for file_el in files_container.findall("File"):
        records.append(_parse_file_element(file_el))

    return records


def load_xml_directory(xml_dir: str) -> List[FileRecord]:
    """
    Load all *.xml files in a directory (and subdirectories).
    Deduplicates FileRecords by abs_path.
    """
    seen: set = set()
    records: List[FileRecord] = []

    for dirpath, _, fnames in os.walk(xml_dir):
        for fname in sorted(fnames):
            if not fname.endswith(".xml"):
                continue
            fpath = os.path.join(dirpath, fname)
            try:
                for rec in load_xml(fpath):
                    key = rec.abs_path or rec.rel_path
                    if key not in seen:
                        seen.add(key)
                        records.append(rec)
            except Exception as e:
                print(f"[merger] Failed to load {fpath}: {e}")

    return records


def merge(sources: List[str]) -> List[FileRecord]:
    """
    Accept a mixed list of XML file paths and/or XML directory paths.
    Returns a deduplicated, sorted list of FileRecord objects.
    """
    seen: set = set()
    records: List[FileRecord] = []

    for src in sources:
        if os.path.isdir(src):
            batch = load_xml_directory(src)
        else:
            batch = load_xml(src)
        for rec in batch:
            key = rec.abs_path or rec.rel_path
            if key not in seen:
                seen.add(key)
                records.append(rec)

    records.sort(key=lambda r: r.rel_path)
    return records
