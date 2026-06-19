"""
dependency_extractor/graph_builder.py
────────────────────────────────────────────────────────────────
GraphBuilder — creates GraphNode objects from LoadedProject data,
then applies all relationship rules.

Stage 1: NODE CREATION  (one pass over all symbols)
  • Every file         → FILE node
  • Every class        → CLASS node (or REACT_COMPONENT, SERVICE, etc.)
  • Every function     → FUNCTION / ASYNC_FUNCTION / SPARK_JOB node
  • Every SQL table    → SQL_TABLE node
  • Every hook         → REACT_HOOK node
  • Every API endpoint → API_ENDPOINT node (discovered later by rule_api_endpoints)

Stage 2: EDGE CREATION  (run all rules in RULES list)

The node-type promotion logic here is the key intelligence:
  Python function containing spark.read → SPARK_JOB
  JS function with PascalCase name + JSX return → REACT_COMPONENT
  Java class with @Service → SERVICE node
  Java class with @Repository → REPOSITORY node
"""

from __future__ import annotations

import re
from typing import Optional

from .models import (
    DependencyGraph, GraphNode,
    NodeType, make_node_id,
)
from .xml_loader import LoadedProject, RawFile, RawSymbol
from .relationship_rules import RULES


# ──────────────────────────────────────────────────────────────
#  NODE TYPE PROMOTION LOGIC
#  (from AST category → semantic NodeType)
# ──────────────────────────────────────────────────────────────

_SPARK_RE     = re.compile(r"\b(?:spark|sc|ss)\b.*\b(?:read|write|createDataFrame)\b", re.I)
_REACT_COMP_RE= re.compile(r"^[A-Z][a-zA-Z0-9]+$")
_JSX_RETURN_RE= re.compile(r"return\s+<[A-Z]", re.I)
_SPRING_RE    = re.compile(r"@(?:Service|Component|Controller|RestController|Repository"
                            r"|Injectable|Bean|Configuration)\b", re.I)

def _promote_class(sym: RawSymbol) -> str:
    """Determine the semantic NodeType for a CLASS symbol."""
    bp   = sym.body_preview or ""
    decs = " ".join(sym.decorators + sym.modifiers)
    m = _SPRING_RE.search(decs + " " + bp)
    if m:
        annot = m.group(0).lstrip("@").lower()
        if "repository" in annot:
            return NodeType.REPOSITORY
        if "controller" in annot:
            return NodeType.CONTROLLER
        return NodeType.SERVICE
    # React class component: class Foo extends React.Component
    if "extends" in bp.lower() and ("react.component" in bp.lower() or "component" in bp.lower()):
        if _REACT_COMP_RE.match(sym.name):
            return NodeType.REACT_COMPONENT
    return NodeType.CLASS


def _promote_function(sym: RawSymbol) -> str:
    """Determine the semantic NodeType for a FUNCTION/ASYNC_DEF symbol."""
    bp = sym.body_preview or ""
    # Spark job
    if _SPARK_RE.search(bp):
        return NodeType.SPARK_JOB
    # React component: PascalCase + returns JSX
    if _REACT_COMP_RE.match(sym.name) and _JSX_RETURN_RE.search(bp):
        return NodeType.REACT_COMPONENT
    # Async function
    if sym.is_async or sym.category == "ASYNC_DEF":
        return NodeType.ASYNC_FUNCTION
    return NodeType.FUNCTION


_CATEGORY_TO_NODETYPE = {
    "CLASS":       _promote_class,    # callable
    "INTERFACE":   lambda s: NodeType.INTERFACE,
    "ENUM":        lambda s: NodeType.ENUM,
    "FUNCTION":    _promote_function,
    "ASYNC_DEF":   _promote_function,
    "METHOD":      lambda s: NodeType.METHOD,
    "CONSTRUCTOR": lambda s: NodeType.CONSTRUCTOR,
    "HOOK":        lambda s: NodeType.REACT_HOOK,
    "VARIABLE":    lambda s: NodeType.VARIABLE,
    "CONSTANT":    lambda s: NodeType.CONSTANT,
    "PROPERTY":    lambda s: NodeType.PROPERTY,
    "ASSIGNMENT":  lambda s: NodeType.PROPERTY,
    "DECORATOR":   lambda s: NodeType.DECORATOR,
    "ANNOTATION":  lambda s: NodeType.DECORATOR,
    "LAMBDA":      lambda s: NodeType.LAMBDA,
    "IMPORT":      lambda s: NodeType.IMPORT,
}

_EMIT_CATEGORIES = frozenset({
    "CLASS", "INTERFACE", "ENUM",
    "FUNCTION", "ASYNC_DEF", "METHOD", "CONSTRUCTOR",
    "HOOK", "VARIABLE", "CONSTANT", "PROPERTY", "ASSIGNMENT",
    "DECORATOR", "ANNOTATION", "LAMBDA", "IMPORT",
    "SQL_QUERY", "SQL_DDL", "SQL_DML",
    "API_CALL",
})


def _node_type_for(sym: RawSymbol) -> Optional[str]:
    factory = _CATEGORY_TO_NODETYPE.get(sym.category)
    if factory:
        return factory(sym)
    return None


# ──────────────────────────────────────────────────────────────
#  FILE NODE CREATION
# ──────────────────────────────────────────────────────────────

def _file_node(fr: RawFile) -> GraphNode:
    return GraphNode(
        id=make_node_id(NodeType.FILE, fr.rel_path),
        node_type=NodeType.FILE,
        name=fr.rel_path,
        language=fr.language,
        file_path=fr.rel_path,
    )


# ──────────────────────────────────────────────────────────────
#  SYMBOL NODE CREATION
# ──────────────────────────────────────────────────────────────

def _symbol_node(sym: RawSymbol) -> Optional[GraphNode]:
    """Convert a RawSymbol to a GraphNode. Returns None for uninteresting symbols."""
    if sym.category not in _EMIT_CATEGORIES:
        return None
    if not sym.name or sym.name.startswith("<"):
        return None

    node_type = _node_type_for(sym)
    if node_type is None:
        return None

    node_id = make_node_id(node_type, sym.name, sym.rel_path)

    # Determine parent_id
    parent_id = None
    if sym.parent:
        # Try class first, then function
        for ptype in (NodeType.CLASS, NodeType.INTERFACE, NodeType.FUNCTION,
                      NodeType.ASYNC_FUNCTION, NodeType.REACT_COMPONENT):
            pid = make_node_id(ptype, sym.parent, sym.rel_path)
            parent_id = pid
            break

    return GraphNode(
        id=node_id,
        node_type=node_type,
        name=sym.name,
        language=sym.language,
        file_path=sym.rel_path,
        start_line=sym.start_line,
        end_line=sym.end_line,
        parent_id=parent_id,
        docstring=sym.docstring,
        return_type=sym.return_type,
        is_async=sym.is_async,
        is_exported=sym.is_exported,
        annotations=sym.decorators,
        modifiers=sym.modifiers,
        params=sym.params,
        body_preview=sym.body_preview,
    )


# ──────────────────────────────────────────────────────────────
#  SQL TABLE NODE CREATION
# ──────────────────────────────────────────────────────────────

def _sql_table_node(table) -> GraphNode:
    return GraphNode(
        id=make_node_id(NodeType.SQL_TABLE, table.name),
        node_type=NodeType.SQL_TABLE,
        name=table.name,
        language="sql",
        file_path=table.defined_in or "",
    )


# ──────────────────────────────────────────────────────────────
#  MAIN BUILDER
# ──────────────────────────────────────────────────────────────

class GraphBuilder:
    """
    Two-phase graph construction:
      Phase 1: create_nodes()   — all vertices
      Phase 2: apply_rules()    — all edges via relationship_rules.RULES
    """

    def __init__(self, verbose: bool = True):
        self.verbose = verbose

    def build(self, project: LoadedProject) -> DependencyGraph:
        graph = DependencyGraph(name=project.name, source="")
        self._log(f"[builder] Phase 1: creating nodes…")
        self._create_nodes(project, graph)
        self._log(f"          {graph.node_count} nodes created")

        self._log(f"[builder] Phase 2: applying {len(RULES)} relationship rules…")
        self._apply_rules(project, graph)
        self._log(f"          {graph.edge_count} edges created")

        return graph

    # ── Phase 1 ──────────────────────────────────────────────

    def _create_nodes(self, project: LoadedProject, graph: DependencyGraph):
        # FILE nodes
        for fr in project.files:
            graph.add_node(_file_node(fr))

        # SYMBOL nodes (deduplicated by ID)
        for fr in project.files:
            for sym in fr.symbols:
                node = _symbol_node(sym)
                if node:
                    graph.add_node(node)

        # SQL TABLE nodes
        for table in project.sql_tables:
            if table.name and table.name not in {"IF"} and len(table.name) > 1:
                graph.add_node(_sql_table_node(table))

    # ── Phase 2 ──────────────────────────────────────────────

    def _apply_rules(self, project: LoadedProject, graph: DependencyGraph):
        for rule_fn in RULES:
            before = graph.edge_count
            try:
                rule_fn(project, graph)
            except Exception as e:
                graph.errors.append(f"Rule {rule_fn.__name__} failed: {e}")
                if self.verbose:
                    import traceback
                    print(f"  [warn] Rule {rule_fn.__name__}: {e}")
            added = graph.edge_count - before
            if self.verbose and added:
                self._log(f"  ✓ {rule_fn.__name__:<35} +{added} edges")

    def _log(self, msg: str):
        if self.verbose:
            print(msg, flush=True)
