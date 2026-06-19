"""
combiner/exporter.py
──────────────────────────────────────────────────────────────
Exports a CombinedProject → unified XML file.

Output schema
─────────────
<CombinedProject name="…" total_files="…" total_nodes="…"
                 total_dependencies="…" generated_at="…">

  <Summary>
    <Languages> … </Languages>
    <NodeTypes>  … </NodeTypes>
    <DependencyTypes> … </DependencyTypes>
  </Summary>

  <Files>
    <File path="…" language="…" lines="…" nodes="…">
      <Functions> <Function …/> </Functions>
      <Classes>   <Class …/>   </Classes>
      … (same structure as Component 1, ALL node groups preserved)
    </File>
  </Files>

  <AllFunctions>       (cross-file flat index for quick lookup)
    <Function file="…" …/>
  </AllFunctions>

  <AllClasses> … </AllClasses>
  <AllInterfaces> … </AllInterfaces>
  <AllEnums> … </AllEnums>

  <Dependencies>
    <Dependency source="…" target="…" type="…"
                source_symbol="…" target_symbol="…"
                confidence="…" evidence="…"/>
  </Dependencies>

  <SQLTables>
    <Table name="…" defined_in="…" operations="…">
      <ReferencedIn file="…"/>
    </Table>
  </SQLTables>

  <SymbolIndex>
    <Symbol canonical="…" category="…" originals="…">
      <DefinedIn file="…"/>
    </Symbol>
  </SymbolIndex>

</CombinedProject>
"""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

from .models import (
    CombinedProject, Dependency, FileRecord,
    NormalizedSymbol, RawNode, SQLTable,
)
from .normalizer import build_symbol_index

try:
    from lxml import etree as ET
    _LXML = True
except ImportError:
    import xml.etree.ElementTree as ET
    from xml.dom import minidom
    _LXML = False


# ─────────────────────────────────────────────────────────────
#  Safety helpers
# ─────────────────────────────────────────────────────────────

_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")

def _s(text, maxlen=0) -> str:
    if not text:
        return ""
    t = _CTRL.sub("", str(text))
    if maxlen and len(t) > maxlen:
        t = t[:maxlen] + "…"
    return t

def _sub(parent, tag: str, text=None, **kw):
    el = ET.SubElement(parent, tag)
    for k, v in kw.items():
        el.set(k.rstrip("_"), _s(str(v)))
    if text is not None:
        el.text = _s(text)
    return el


# ─────────────────────────────────────────────────────────────
#  Category → XML group tag mappings (mirrors xml_generator.py)
# ─────────────────────────────────────────────────────────────

_GROUP_TAGS: Dict[str, str] = {
    "IMPORT":          "Imports",
    "EXPORT":          "Exports",
    "CLASS":           "Classes",
    "INTERFACE":       "Interfaces",
    "ENUM":            "Enums",
    "FUNCTION":        "Functions",
    "ASYNC_DEF":       "AsyncFunctions",
    "METHOD":          "Methods",
    "CONSTRUCTOR":     "Constructors",
    "PROPERTY":        "Properties",
    "VARIABLE":        "Variables",
    "ASSIGNMENT":      "Assignments",
    "CONDITION":       "Conditions",
    "LOOP":            "Loops",
    "SWITCH":          "SwitchStatements",
    "TRY_BLOCK":       "ExceptionHandling",
    "CATCH_BLOCK":     "CatchBlocks",
    "FINALLY_BLOCK":   "FinallyBlocks",
    "RAISE":           "Raises",
    "FUNCTION_CALL":   "FunctionCalls",
    "METHOD_CALL":     "MethodCalls",
    "HOOK":            "Hooks",
    "JSX_ELEMENT":     "JSXElements",
    "DECORATOR":       "Decorators",
    "ANNOTATION":      "Annotations",
    "SQL_QUERY":       "Queries",
    "SQL_DDL":         "DDLStatements",
    "SQL_DML":         "DMLStatements",
    "API_CALL":        "APICalls",
    "OBJECT_CREATION": "ObjectCreations",
    "AWAIT_EXPR":      "Awaits",
    "LAMBDA":          "Lambdas",
    "RETURN":          "Returns",
}

# ORDER in which groups appear in the <File> element
_GROUP_ORDER = [
    "IMPORT", "EXPORT", "DECORATOR", "ANNOTATION",
    "CLASS", "INTERFACE", "ENUM",
    "FUNCTION", "ASYNC_DEF", "METHOD", "CONSTRUCTOR",
    "PROPERTY", "VARIABLE", "ASSIGNMENT",
    "HOOK", "JSX_ELEMENT",
    "CONDITION", "LOOP", "SWITCH",
    "TRY_BLOCK", "CATCH_BLOCK", "FINALLY_BLOCK",
    "FUNCTION_CALL", "METHOD_CALL", "API_CALL",
    "OBJECT_CREATION", "AWAIT_EXPR", "LAMBDA",
    "RETURN", "RAISE",
    "SQL_QUERY", "SQL_DDL", "SQL_DML",
]

# Global indexes (flat, cross-file)
_GLOBAL_CATEGORIES = {
    "FUNCTION":   "AllFunctions",
    "ASYNC_DEF":  "AllFunctions",
    "METHOD":     "AllMethods",
    "CLASS":      "AllClasses",
    "INTERFACE":  "AllInterfaces",
    "ENUM":       "AllEnums",
    "SQL_QUERY":  "AllSQLQueries",
    "SQL_DDL":    "AllSQLDDL",
    "SQL_DML":    "AllSQLDML",
    "API_CALL":   "AllAPICalls",
    "HOOK":       "AllHooks",
}


def _node_element(parent, node: RawNode, include_file: bool = False):
    """Serialize one RawNode to XML."""
    tag = node.tag or node.category.capitalize()
    el = ET.SubElement(parent, tag)

    el.set("name",       _s(node.name, 120))
    el.set("type",       _s(node.category))
    el.set("start_line", str(node.start_line))
    el.set("end_line",   str(node.end_line))
    el.set("language",   node.language)

    if include_file:
        el.set("file", _s(node.rel_path))

    if node.parent:
        el.set("parent", _s(node.parent, 80))
    if node.raw_type:
        el.set("raw_type", node.raw_type)
    if node.is_async:
        el.set("async", "true")
    if node.is_exported:
        el.set("exported", "true")
    if node.return_type:
        el.set("return_type", _s(node.return_type, 80))

    if node.docstring:
        _sub(el, "DocString", _s(node.docstring, 400))
    if node.params:
        pe = ET.SubElement(el, "Parameters")
        for p in node.params:
            _sub(pe, "Param", _s(p, 60))
    if node.decorators:
        de = ET.SubElement(el, "Decorators")
        for d in node.decorators:
            _sub(de, "Decorator", _s(d, 80))
    if node.modifiers:
        me = ET.SubElement(el, "Modifiers")
        for m in node.modifiers:
            _sub(me, "Modifier", m)
    if node.body_preview:
        _sub(el, "BodyPreview", _s(node.body_preview, 200))
    return el


def _file_element(parent, fr: FileRecord):
    """Serialize one FileRecord → <File> element with all grouped nodes."""
    fe = ET.SubElement(parent, "File")
    fe.set("path",     _s(fr.rel_path))
    fe.set("abs_path", _s(fr.abs_path))
    fe.set("language", fr.language)
    fe.set("lines",    str(fr.total_lines))
    fe.set("nodes",    str(fr.node_count))

    if fr.errors:
        ee = ET.SubElement(fe, "Errors")
        for e in fr.errors:
            _sub(ee, "Error", e)

    # Group nodes by category
    groups: Dict[str, List[RawNode]] = defaultdict(list)
    ungrouped: List[RawNode] = []
    for node in fr.nodes:
        cat = node.category
        if cat in _GROUP_TAGS:
            groups[cat].append(node)
        else:
            ungrouped.append(node)

    for cat in _GROUP_ORDER:
        nodes = groups.get(cat, [])
        if not nodes:
            continue
        group_tag = _GROUP_TAGS[cat]
        ge = ET.SubElement(fe, group_tag)
        ge.set("count", str(len(nodes)))
        for node in nodes:
            _node_element(ge, node)

    if ungrouped:
        me = ET.SubElement(fe, "Misc")
        for node in ungrouped:
            _node_element(me, node)

    return fe


def _write(root, output_path: str):
    """Write XML tree to file (lxml or stdlib)."""
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    if _LXML:
        ET.ElementTree(root).write(
            output_path, pretty_print=True,
            xml_declaration=True, encoding="utf-8",
        )
    else:
        raw = ET.tostring(root, encoding="unicode")
        pretty = minidom.parseString(
            '<?xml version="1.0" encoding="UTF-8"?>' + raw
        ).toprettyxml(indent="  ", encoding=None)
        lines = pretty.splitlines()
        if len(lines) > 1 and lines[0].startswith("<?xml") and lines[1].startswith("<?xml"):
            lines = lines[1:]
        Path(output_path).write_text("\n".join(lines), encoding="utf-8")


# ─────────────────────────────────────────────────────────────
#  MAIN EXPORT FUNCTION
# ─────────────────────────────────────────────────────────────

def export_xml(project: CombinedProject, output_path: str) -> str:
    """
    Serialize the full CombinedProject into a unified XML file.
    Returns the output path.
    """
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    root = ET.Element("CombinedProject")
    root.set("name",               _s(project.name))
    root.set("total_files",        str(len(project.files)))
    root.set("total_nodes",        str(project.total_nodes))
    root.set("total_dependencies", str(len(project.dependencies)))
    root.set("total_sql_tables",   str(len(project.sql_tables)))
    root.set("generated_at",       now)

    # ── Summary ───────────────────────────────────────────────
    summary = ET.SubElement(root, "Summary")
    lang_counts:  Dict[str, int] = defaultdict(int)
    cat_counts:   Dict[str, int] = defaultdict(int)
    dep_counts:   Dict[str, int] = defaultdict(int)

    for fr in project.files:
        lang_counts[fr.language] += 1
        for node in fr.nodes:
            cat_counts[node.category] += 1
    for dep in project.dependencies:
        dep_counts[dep.dep_type] += 1

    langs_el = ET.SubElement(summary, "Languages")
    for lang, cnt in sorted(lang_counts.items()):
        el = ET.SubElement(langs_el, "Language")
        el.set("name", lang); el.set("files", str(cnt))

    nt_el = ET.SubElement(summary, "NodeTypes")
    for cat, cnt in sorted(cat_counts.items(), key=lambda x: -x[1]):
        el = ET.SubElement(nt_el, "NodeType")
        el.set("name", cat); el.set("count", str(cnt))

    dt_el = ET.SubElement(summary, "DependencyTypes")
    for dtype, cnt in sorted(dep_counts.items(), key=lambda x: -x[1]):
        el = ET.SubElement(dt_el, "DependencyType")
        el.set("type", dtype); el.set("count", str(cnt))

    # ── Files (full node detail) ───────────────────────────────
    files_el = ET.SubElement(root, "Files")
    for fr in project.files:
        _file_element(files_el, fr)

    # ── Global flat indexes ────────────────────────────────────
    global_buckets: Dict[str, List[RawNode]] = defaultdict(list)
    for fr in project.files:
        for node in fr.nodes:
            gkey = _GLOBAL_CATEGORIES.get(node.category)
            if gkey:
                global_buckets[gkey].append(node)

    for gkey, nodes in sorted(global_buckets.items()):
        ge = ET.SubElement(root, gkey)
        ge.set("count", str(len(nodes)))
        for node in nodes:
            _node_element(ge, node, include_file=True)

    # ── Dependencies ──────────────────────────────────────────
    deps_el = ET.SubElement(root, "Dependencies")
    deps_el.set("count", str(len(project.dependencies)))
    for dep in sorted(project.dependencies,
                      key=lambda d: (d.dep_type, d.source_file)):
        de = ET.SubElement(deps_el, "Dependency")
        de.set("source",         _s(dep.source_file))
        de.set("target",         _s(dep.target_file))
        de.set("type",           dep.dep_type)
        de.set("confidence",     dep.confidence)
        if dep.source_symbol:
            de.set("source_symbol", _s(dep.source_symbol, 100))
        if dep.target_symbol:
            de.set("target_symbol", _s(dep.target_symbol, 60))
        if dep.evidence:
            de.set("evidence", _s(dep.evidence, 200))

    # ── SQL Tables ────────────────────────────────────────────
    sql_el = ET.SubElement(root, "SQLTables")
    sql_el.set("count", str(len(project.sql_tables)))
    for t in sorted(project.sql_tables, key=lambda x: x.name):
        te = ET.SubElement(sql_el, "Table")
        te.set("name",       t.name)
        te.set("operations", ", ".join(t.operations))
        if t.defined_in:
            te.set("defined_in", _s(t.defined_in))
        for ref in t.referenced_in:
            _sub(te, "ReferencedIn", file=ref)

    # ── Symbol Index ──────────────────────────────────────────
    syms_el = ET.SubElement(root, "SymbolIndex")
    syms_el.set("count", str(len(project.symbols)))
    for sym in sorted(project.symbols, key=lambda s: s.canonical_name):
        se = ET.SubElement(syms_el, "Symbol")
        se.set("canonical", sym.canonical_name)
        se.set("category",  sym.category)
        se.set("originals", ", ".join(sym.original_names))
        for fp in sym.defined_in:
            _sub(se, "DefinedIn", file=fp)
        for fp in sym.called_from:
            _sub(se, "CalledFrom", file=fp)

    # ── Write ─────────────────────────────────────────────────
    _write(root, output_path)
    size_kb = Path(output_path).stat().st_size / 1024
    print(f"[exporter] Written → {output_path}  ({size_kb:.1f} KB)")
    return output_path
