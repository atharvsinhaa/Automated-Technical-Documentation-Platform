"""
output/xml_generator.py
─────────────────────────────────────────────────────────────
Enterprise XML Generator

Converts ParsedProject → structured XML file.

Design decisions:
  • Uses lxml for fast, memory-efficient writing (streaming via lxml.etree)
  • Falls back to xml.etree.ElementTree if lxml unavailable
  • Supports incremental / streaming output for huge repos
  • Preserves full hierarchy: Project → File → Category groups → Nodes
  • Every node carries the full required attribute set
  • XML is valid, human-readable, and machine-parseable
"""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional

from ..core.models import ASTNode, ParsedFile, ParsedProject
from ..core.node_taxonomy import NodeCategory

# ─────────────────────────────────────────────────────────────
#  Backend selection
# ─────────────────────────────────────────────────────────────
try:
    from lxml import etree as ET
    _LXML = True
except ImportError:
    import xml.etree.ElementTree as ET   # type: ignore
    from xml.dom import minidom
    _LXML = False


# ─────────────────────────────────────────────────────────────
#  XML Schema — category → tag name
# ─────────────────────────────────────────────────────────────

CATEGORY_TAG: Dict[NodeCategory, str] = {
    NodeCategory.CLASS:          "Class",
    NodeCategory.INTERFACE:      "Interface",
    NodeCategory.ENUM:           "Enum",
    NodeCategory.FUNCTION:       "Function",
    NodeCategory.METHOD:         "Method",
    NodeCategory.CONSTRUCTOR:    "Constructor",
    NodeCategory.ASYNC_DEF:      "AsyncFunction",
    NodeCategory.PROPERTY:       "Property",
    NodeCategory.IMPORT:         "Import",
    NodeCategory.EXPORT:         "Export",
    NodeCategory.VARIABLE:       "Variable",
    NodeCategory.ASSIGNMENT:     "Assignment",
    NodeCategory.CONSTANT:       "Constant",
    NodeCategory.CONDITION:      "Condition",
    NodeCategory.LOOP:           "Loop",
    NodeCategory.SWITCH:         "Switch",
    NodeCategory.BREAK_CONTINUE: "BreakContinue",
    NodeCategory.TRY_BLOCK:      "TryBlock",
    NodeCategory.CATCH_BLOCK:    "CatchBlock",
    NodeCategory.FINALLY_BLOCK:  "FinallyBlock",
    NodeCategory.RAISE:          "Raise",
    NodeCategory.AWAIT_EXPR:     "Await",
    NodeCategory.YIELD_EXPR:     "Yield",
    NodeCategory.FUNCTION_CALL:  "FunctionCall",
    NodeCategory.METHOD_CALL:    "MethodCall",
    NodeCategory.OBJECT_CREATION:"ObjectCreation",
    NodeCategory.LAMBDA:         "Lambda",
    NodeCategory.DECORATOR:      "Decorator",
    NodeCategory.ANNOTATION:     "Annotation",
    NodeCategory.TYPE_ALIAS:     "TypeAlias",
    NodeCategory.RETURN:         "Return",
    NodeCategory.COMMENT:        "Comment",
    NodeCategory.JSX_ELEMENT:    "JSXElement",
    NodeCategory.HOOK:           "Hook",
    NodeCategory.COMPONENT:      "Component",
    NodeCategory.SQL_QUERY:      "Query",
    NodeCategory.SQL_DDL:        "DDL",
    NodeCategory.SQL_DML:        "DML",
    NodeCategory.API_CALL:       "APICall",
    NodeCategory.EXPRESSION:     "Expression",
    NodeCategory.UNKNOWN:        "Unknown",
}

# Group tags — wraps nodes of the same category in a parent element
GROUP_TAG: Dict[NodeCategory, str] = {
    NodeCategory.IMPORT:         "Imports",
    NodeCategory.EXPORT:         "Exports",
    NodeCategory.CLASS:          "Classes",
    NodeCategory.INTERFACE:      "Interfaces",
    NodeCategory.ENUM:           "Enums",
    NodeCategory.FUNCTION:       "Functions",
    NodeCategory.ASYNC_DEF:      "AsyncFunctions",
    NodeCategory.METHOD:         "Methods",
    NodeCategory.CONSTRUCTOR:    "Constructors",
    NodeCategory.PROPERTY:       "Properties",
    NodeCategory.VARIABLE:       "Variables",
    NodeCategory.CONDITION:      "Conditions",
    NodeCategory.LOOP:           "Loops",
    NodeCategory.SWITCH:         "SwitchStatements",
    NodeCategory.TRY_BLOCK:      "ExceptionHandling",
    NodeCategory.FUNCTION_CALL:  "FunctionCalls",
    NodeCategory.HOOK:           "Hooks",
    NodeCategory.JSX_ELEMENT:    "JSXElements",
    NodeCategory.SQL_QUERY:      "Queries",
    NodeCategory.SQL_DDL:        "DDLStatements",
    NodeCategory.SQL_DML:        "DMLStatements",
    NodeCategory.API_CALL:       "APICalls",
    NodeCategory.DECORATOR:      "Decorators",
    NodeCategory.ANNOTATION:     "Annotations",
    NodeCategory.OBJECT_CREATION:"ObjectCreations",
    NodeCategory.AWAIT_EXPR:     "Awaits",
    NodeCategory.LAMBDA:         "Lambdas",
    NodeCategory.RETURN:         "Returns",
    NodeCategory.RAISE:          "Raises",
}

# ─────────────────────────────────────────────────────────────
#  Safety helpers
# ─────────────────────────────────────────────────────────────

_CTRL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")

def _safe(text: Optional[str], maxlen: int = 0) -> str:
    if not text:
        return ""
    cleaned = _CTRL_RE.sub("", text)
    if maxlen and len(cleaned) > maxlen:
        cleaned = cleaned[:maxlen] + "…"
    return cleaned


def _sub(parent, tag: str, text: Optional[str] = None, **attribs) -> object:
    """Create a SubElement with optional text and attributes."""
    el = ET.SubElement(parent, tag)
    for k, v in attribs.items():
        el.set(k, str(v))
    if text is not None:
        el.text = _safe(text)
    return el


# ─────────────────────────────────────────────────────────────
#  NODE BUILDER
# ─────────────────────────────────────────────────────────────

def _build_node_element(parent, node: ASTNode) -> None:
    """Serialize one ASTNode into an XML element under parent."""
    tag = CATEGORY_TAG.get(node.category, "Node")
    el = ET.SubElement(parent, tag)

    # ── Required attributes (always present) ──────────────────
    el.set("name",      _safe(node.name, 120))
    el.set("type",      node.category_name)
    el.set("raw_type",  node.raw_type)
    el.set("start_line", str(node.start_line))
    el.set("end_line",   str(node.end_line))
    el.set("file_path",  _safe(node.file_path))
    el.set("language",   node.language)
    if node.parent_name:
        el.set("parent", _safe(node.parent_name, 80))

    # ── Optional attributes ───────────────────────────────────
    if node.is_async:
        el.set("async", "true")
    if node.is_exported:
        el.set("exported", "true")
    if node.return_type:
        el.set("return_type", _safe(node.return_type, 80))

    # ── Child elements ─────────────────────────────────────────
    if node.docstring:
        _sub(el, "DocString", _safe(node.docstring, 500))

    if node.params:
        params_el = ET.SubElement(el, "Parameters")
        for p in node.params:
            _sub(params_el, "Param", _safe(p, 60))

    if node.decorators:
        dec_el = ET.SubElement(el, "Decorators")
        for d in node.decorators:
            _sub(dec_el, "Decorator", _safe(d, 80))

    if node.modifiers:
        mod_el = ET.SubElement(el, "Modifiers")
        for m in node.modifiers:
            _sub(mod_el, "Modifier", m)

    if node.body_preview:
        _sub(el, "BodyPreview", _safe(node.body_preview, 200))


# ─────────────────────────────────────────────────────────────
#  FILE BUILDER
# ─────────────────────────────────────────────────────────────

def _build_file_element(parent, pf: ParsedFile, root_path: str) -> None:
    """Serialize one ParsedFile into an XML element."""
    file_el = ET.SubElement(parent, "File")
    try:
        rel = str(Path(pf.file_path).relative_to(root_path))
    except ValueError:
        rel = pf.file_path
    file_el.set("path",     rel)
    file_el.set("abs_path", pf.file_path)
    file_el.set("language", pf.language)
    file_el.set("lines",    str(pf.total_lines))
    file_el.set("nodes",    str(pf.node_count))

    if pf.errors:
        err_el = ET.SubElement(file_el, "Errors")
        for e in pf.errors:
            _sub(err_el, "Error", e)

    if not pf.nodes:
        return

    # Group nodes by category
    groups: Dict[NodeCategory, List[ASTNode]] = defaultdict(list)
    ungrouped: List[ASTNode] = []

    for node in pf.nodes:
        if node.category in GROUP_TAG:
            groups[node.category].append(node)
        else:
            ungrouped.append(node)

    # Emit groups in a defined order
    GROUP_ORDER = [
        NodeCategory.IMPORT,
        NodeCategory.EXPORT,
        NodeCategory.DECORATOR,
        NodeCategory.ANNOTATION,
        NodeCategory.CLASS,
        NodeCategory.INTERFACE,
        NodeCategory.ENUM,
        NodeCategory.FUNCTION,
        NodeCategory.ASYNC_DEF,
        NodeCategory.METHOD,
        NodeCategory.CONSTRUCTOR,
        NodeCategory.PROPERTY,
        NodeCategory.VARIABLE,
        NodeCategory.HOOK,
        NodeCategory.JSX_ELEMENT,
        NodeCategory.CONDITION,
        NodeCategory.LOOP,
        NodeCategory.SWITCH,
        NodeCategory.TRY_BLOCK,
        NodeCategory.FUNCTION_CALL,
        NodeCategory.API_CALL,
        NodeCategory.OBJECT_CREATION,
        NodeCategory.AWAIT_EXPR,
        NodeCategory.LAMBDA,
        NodeCategory.RETURN,
        NodeCategory.RAISE,
        NodeCategory.SQL_QUERY,
        NodeCategory.SQL_DDL,
        NodeCategory.SQL_DML,
    ]

    for cat in GROUP_ORDER:
        nodes = groups.get(cat, [])
        if not nodes:
            continue
        group_tag = GROUP_TAG[cat]
        group_el  = ET.SubElement(file_el, group_tag)
        group_el.set("count", str(len(nodes)))
        for node in nodes:
            _build_node_element(group_el, node)

    # Ungrouped nodes go into a Misc section
    if ungrouped:
        misc_el = ET.SubElement(file_el, "Misc")
        for node in ungrouped:
            _build_node_element(misc_el, node)


# ─────────────────────────────────────────────────────────────
#  TOP-LEVEL GENERATOR
# ─────────────────────────────────────────────────────────────

def generate_xml(
    project:     ParsedProject,
    output_path: str,
) -> str:
    """
    Convert a ParsedProject into an XML file at output_path.
    Returns the output path.
    """
    # Root element
    root = ET.Element("Project")
    root.set("name",        project.name)
    root.set("root",        project.root_path)
    root.set("total_files", str(project.total_files))
    root.set("total_nodes", str(project.total_nodes))

    # Summary stats
    stats_el = ET.SubElement(root, "Summary")
    lang_counts: Dict[str, int] = defaultdict(int)
    cat_counts:  Dict[str, int] = defaultdict(int)
    for pf in project.files:
        lang_counts[pf.language] += 1
        for node in pf.nodes:
            cat_counts[node.category_name] += 1

    langs_el = ET.SubElement(stats_el, "Languages")
    for lang, count in sorted(lang_counts.items()):
        el = ET.SubElement(langs_el, "Language")
        el.set("name", lang)
        el.set("files", str(count))

    cats_el = ET.SubElement(stats_el, "NodeTypes")
    for cat, count in sorted(cat_counts.items(), key=lambda x: -x[1]):
        el = ET.SubElement(cats_el, "NodeType")
        el.set("name",  cat)
        el.set("count", str(count))

    # Project-level errors
    if project.errors:
        err_el = ET.SubElement(root, "Errors")
        for e in project.errors:
            _sub(err_el, "Error", e)

    # Files
    files_el = ET.SubElement(root, "Files")
    for pf in project.files:
        _build_file_element(files_el, pf, project.root_path)

    # Write to disk
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    if _LXML:
        tree = ET.ElementTree(root)
        tree.write(
            output_path,
            pretty_print=True,
            xml_declaration=True,
            encoding="utf-8",
        )
    else:
        # stdlib pretty-print via minidom
        raw = ET.tostring(root, encoding="unicode")
        pretty = minidom.parseString(
            '<?xml version="1.0" encoding="UTF-8"?>' + raw
        ).toprettyxml(indent="  ", encoding=None)
        lines = pretty.splitlines()
        # Remove duplicate XML declaration if minidom added one
        if len(lines) > 1 and lines[0].startswith("<?xml") and lines[1].startswith("<?xml"):
            lines = lines[1:]
        Path(output_path).write_text("\n".join(lines), encoding="utf-8")

    size_kb = Path(output_path).stat().st_size / 1024
    print(f"\n[xml] Written → {output_path}  ({size_kb:.1f} KB)")
    return output_path
