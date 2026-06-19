"""
core/walker.py
─────────────────────────────────────────────────────────────
UniversalASTWalker — the core recursive traversal engine.

WHY the current parser misses loops/conditions/hooks
─────────────────────────────────────────────────────
Tree-sitter produces a COMPLETE syntax tree — every node is
present. The problem is that earlier parsers only looked
at TOP-LEVEL children of the root node. This misses:

  • for_statement     → nested inside function body (block)
  • if_statement      → nested inside for_statement
  • try_statement     → nested inside if_statement
  • await_expression  → nested inside assignment

You need FULL recursive traversal (DFS) to reach them.
Additionally, without a semantic taxonomy (node_taxonomy.py),
the parser doesn't know that "enhanced_for_statement" (Java),
"for_in_statement" (JS), and "for_statement" (Python) all mean LOOP.

This walker:
  1. Recursively visits every node in the tree (no depth limit)
  2. Classifies each node via the taxonomy
  3. Delegates extraction to registered extractors
  4. Builds a parent-child hierarchy
  5. Tracks scope context for name resolution
"""

from __future__ import annotations

import re
import textwrap
from typing import Callable, Dict, List, Optional, Set

from tree_sitter import Node

from .node_taxonomy import NodeCategory, RAW_TO_CATEGORY, classify, STRUCTURAL_CATEGORIES
from .models import ASTNode


# ─────────────────────────────────────────────────────────────
#  Utility helpers
# ─────────────────────────────────────────────────────────────

def _src_text(node: Node, src: bytes) -> str:
    return src[node.start_byte:node.end_byte].decode("utf-8", errors="ignore")


def _first_line(node: Node, src: bytes) -> str:
    return _src_text(node, src).split("\n")[0].strip()


def _collapse(text: str, max_len: int = 200) -> str:
    """Collapse whitespace and truncate for body_preview."""
    collapsed = " ".join(text.split())
    return textwrap.shorten(collapsed, width=max_len, placeholder="…")


def _get_identifier(node: Node, src: bytes) -> Optional[str]:
    """
    Best-effort name extraction for any node type.
    Tries named fields first, then scans direct children for identifiers.
    """
    for field in ("name", "identifier", "type_identifier",
                  "property_identifier", "field_identifier"):
        child = node.child_by_field_name(field)
        if child:
            return _src_text(child, src).strip()

    # Scan direct children for an identifier node
    for child in node.children:
        if child.type in ("identifier", "type_identifier",
                          "property_identifier", "field_identifier"):
            text = _src_text(child, src).strip()
            if text and text not in {
                "if", "for", "while", "else", "return", "import",
                "class", "def", "function", "const", "let", "var",
                "async", "await", "try", "catch", "throw", "new",
            }:
                return text
    return None


def _extract_docstring(node: Node, src: bytes, language: str) -> Optional[str]:
    """
    Extract docstring/JSDoc from a function or class node.
    Handles Python triple-quotes and JS block-comment patterns.
    """
    # Python: first statement in body is a string expression
    for child in node.children:
        if child.type in ("block", "body"):
            for stmt in child.children:
                if stmt.type == "expression_statement":
                    for sub in stmt.children:
                        if sub.type == "string":
                            raw = _src_text(sub, src)
                            return raw.strip("'\"` \n")[:500]
            break

    # JS/TS: look for a comment sibling immediately before this node
    parent = node.parent
    if parent:
        prev = None
        for child in parent.children:
            if child.id == node.id:
                if prev and prev.type == "comment":
                    text = _src_text(prev, src).strip()
                    return re.sub(r"^/\*+|^\s*\*+/?|\s*\*/$|^//\s*", "", text,
                                  flags=re.MULTILINE).strip()[:500]
                break
            prev = child
    return None


def _extract_params(node: Node, src: bytes) -> List[str]:
    """
    Extract parameter names from function/method nodes.
    Works across Python, JS/TS, Java, Go, Rust, Kotlin.
    """
    params: List[str] = []
    param_field_names = ("parameters", "formal_parameters",
                         "parameter_list", "params")

    params_node = None
    for fn in param_field_names:
        params_node = node.child_by_field_name(fn)
        if params_node:
            break

    if params_node is None:
        # scan children directly
        for child in node.children:
            if child.type in ("parameters", "formal_parameters",
                              "parameter_list", "params"):
                params_node = child
                break

    if params_node is None:
        return params

    PARAM_TYPES = {
        "identifier", "typed_parameter", "typed_default_parameter",
        "default_parameter", "list_splat_pattern", "dictionary_splat_pattern",
        "required_parameter", "optional_parameter", "rest_parameter",
        "formal_parameter", "parameter_declaration", "variadic_parameter",
        "self_parameter", "parameter", "simple_parameter",
    }

    for child in params_node.children:
        if child.type in PARAM_TYPES:
            # Get innermost identifier
            name_child = child.child_by_field_name("name") or \
                         child.child_by_field_name("pattern")
            if name_child:
                name = _src_text(name_child, src).lstrip("*& ")
            else:
                name = _src_text(child, src).lstrip("*& ").split(":")[0].split("=")[0].strip()
            if name and name not in {"(", ")", ",", "self", "cls"}:
                params.append(name)

    return params


def _extract_modifiers(node: Node, src: bytes) -> List[str]:
    """Extract visibility/modifier keywords from Java/Kotlin/Rust."""
    mods = []
    modifier_types = {"modifiers", "visibility_modifier", "function_modifiers"}
    for child in node.children:
        if child.type in modifier_types:
            for m in child.children:
                txt = _src_text(m, src).strip()
                if txt in {"public", "private", "protected", "static",
                           "final", "abstract", "override", "async",
                           "pub", "mut", "unsafe", "extern"}:
                    mods.append(txt)
        elif child.type in {"public", "private", "protected", "static",
                            "final", "abstract", "pub"}:
            mods.append(child.type)
    return mods


def _extract_decorators(node: Node, src: bytes) -> List[str]:
    """Extract decorator/annotation names."""
    decs = []
    for child in node.children:
        if child.type in ("decorator", "decorator_statement",
                          "marker_annotation", "annotation", "attribute_item"):
            text = _src_text(child, src).strip()
            # strip leading @ or #[
            text = re.sub(r"^[@#\[]+", "", text).rstrip("]").strip()
            decs.append(text)
    return decs


def _is_async(node: Node, src: bytes) -> bool:
    """Check if a function node is async."""
    for child in node.children:
        if child.type == "async" or _src_text(child, src).strip() == "async":
            return True
    return False


def _return_type(node: Node, src: bytes, language: str) -> Optional[str]:
    """Extract return type annotation."""
    # Python / Rust arrow annotation
    rt = node.child_by_field_name("return_type") or \
         node.child_by_field_name("result")
    if rt:
        return _src_text(rt, src).lstrip("->: ").strip()[:80]
    # TS type annotation on function
    ta = node.child_by_field_name("return_type") or \
         node.child_by_field_name("type")
    if ta:
        return _src_text(ta, src).lstrip(":").strip()[:80]
    return None


# ─────────────────────────────────────────────────────────────
#  Categories that define a SCOPE (for parent-name tracking)
# ─────────────────────────────────────────────────────────────
SCOPE_CATEGORIES: Set[NodeCategory] = {
    NodeCategory.CLASS,
    NodeCategory.INTERFACE,
    NodeCategory.FUNCTION,
    NodeCategory.METHOD,
    NodeCategory.CONSTRUCTOR,
    NodeCategory.ENUM,
}

# Node types we should NOT recurse into further
# (their content is captured as body_preview, not parsed deeply)
OPAQUE_TYPES: Set[str] = {
    "string", "comment", "block_comment", "line_comment",
    "template_string", "raw_string_literal",
}


# ─────────────────────────────────────────────────────────────
#  HOOK DETECTION  (React hooks by naming convention)
# ─────────────────────────────────────────────────────────────
_HOOK_RE = re.compile(r"^use[A-Z]")

def _is_react_hook_call(name: str) -> bool:
    return bool(_HOOK_RE.match(name))


# ─────────────────────────────────────────────────────────────
#  API CALL DETECTION  (common HTTP patterns)
# ─────────────────────────────────────────────────────────────
_API_PATTERNS = re.compile(
    r"\b(axios|fetch|requests|http|HttpClient|"
    r"get|post|put|patch|delete|request)\b",
    re.IGNORECASE,
)

def _is_api_call(text: str) -> bool:
    return bool(_API_PATTERNS.search(text))


# ─────────────────────────────────────────────────────────────
#  SQL DETECTION
# ─────────────────────────────────────────────────────────────
_SQL_DDL_RE = re.compile(r"^\s*(CREATE|DROP|ALTER|TRUNCATE)\b", re.IGNORECASE)
_SQL_DML_RE = re.compile(r"^\s*(INSERT|UPDATE|DELETE|MERGE)\b", re.IGNORECASE)
_SQL_QRY_RE = re.compile(r"^\s*(SELECT|WITH)\b", re.IGNORECASE)


def _sql_category(text: str) -> Optional[NodeCategory]:
    if _SQL_DDL_RE.match(text):
        return NodeCategory.SQL_DDL
    if _SQL_DML_RE.match(text):
        return NodeCategory.SQL_DML
    if _SQL_QRY_RE.match(text):
        return NodeCategory.SQL_QUERY
    return None


# ─────────────────────────────────────────────────────────────
#  NAME EXTRACTION HELPERS FOR CALL EXPRESSIONS
# ─────────────────────────────────────────────────────────────

def _call_name(node: Node, src: bytes) -> str:
    """Extract the callee name from a call_expression node."""
    func = node.child_by_field_name("function") or \
           node.child_by_field_name("name") or \
           node.child_by_field_name("method")
    if func:
        text = _src_text(func, src).strip()
        # Keep only the last segment for method chains
        return text.split(".")[-1][:60]
    # Fallback: first 60 chars
    return _src_text(node, src)[:60].split("(")[0].strip()


# ─────────────────────────────────────────────────────────────
#  THE WALKER
# ─────────────────────────────────────────────────────────────

class UniversalASTWalker:
    """
    Recursive DFS walker over a tree-sitter parse tree.

    For every node it:
      1. Classifies it via the taxonomy
      2. Determines if it's worth extracting
      3. Builds an ASTNode with all available metadata
      4. Recurses into children (maintaining scope context)
      5. Returns a flat list of ASTNode objects

    The walker is STATELESS per walk() call — safe to reuse.
    """

    # Categories worth emitting into the XML
    EMIT_CATEGORIES: Set[NodeCategory] = {
        NodeCategory.CLASS,
        NodeCategory.INTERFACE,
        NodeCategory.ENUM,
        NodeCategory.FUNCTION,
        NodeCategory.METHOD,
        NodeCategory.CONSTRUCTOR,
        NodeCategory.PROPERTY,
        NodeCategory.IMPORT,
        NodeCategory.EXPORT,
        NodeCategory.VARIABLE,
        NodeCategory.ASSIGNMENT,
        NodeCategory.CONDITION,
        NodeCategory.LOOP,
        NodeCategory.SWITCH,
        NodeCategory.TRY_BLOCK,
        NodeCategory.CATCH_BLOCK,
        NodeCategory.FINALLY_BLOCK,
        NodeCategory.RAISE,
        NodeCategory.AWAIT_EXPR,
        NodeCategory.YIELD_EXPR,
        NodeCategory.FUNCTION_CALL,
        NodeCategory.OBJECT_CREATION,
        NodeCategory.LAMBDA,
        NodeCategory.DECORATOR,
        NodeCategory.ANNOTATION,
        NodeCategory.RETURN,
        NodeCategory.JSX_ELEMENT,
        NodeCategory.HOOK,
        NodeCategory.SQL_QUERY,
        NodeCategory.SQL_DDL,
        NodeCategory.SQL_DML,
        NodeCategory.API_CALL,
        NodeCategory.ASYNC_DEF,
        NodeCategory.TYPE_ALIAS,
        NodeCategory.COMMENT,
    }

    def walk(
        self,
        root: Node,
        src: bytes,
        file_path: str,
        language: str,
    ) -> List[ASTNode]:
        """Entry point. Returns all extracted ASTNode objects."""
        results: List[ASTNode] = []
        self._visit(root, src, file_path, language,
                    parent_name=None, results=results, depth=0)
        return results

    # ── Internal recursive visitor ─────────────────────────────

    def _visit(
        self,
        node: Node,
        src: bytes,
        file_path: str,
        language: str,
        parent_name: Optional[str],
        results: List[ASTNode],
        depth: int,
    ) -> None:

        if node.type in OPAQUE_TYPES:
            return   # don't recurse into string/comment internals

        category = classify(node.type)

        # ── Special-case: async function ─────────────────────
        # Python "async" is a modifier on function_definition;
        # JS has "async" as a child keyword inside function nodes.
        # We reclassify FUNCTION/METHOD to ASYNC_DEF here.
        if category in {NodeCategory.FUNCTION, NodeCategory.METHOD}:
            if _is_async(node, src):
                category = NodeCategory.ASYNC_DEF

        # ── Special-case: SQL strings ─────────────────────────
        if language == "sql":
            text = _src_text(node, src)
            sql_cat = _sql_category(text)
            if sql_cat and category == NodeCategory.UNKNOWN:
                category = sql_cat

        # ── Special-case: call_expression → hook / api ────────
        if category == NodeCategory.FUNCTION_CALL:
            call_text = _src_text(node, src)
            name = _call_name(node, src)
            if _is_react_hook_call(name):
                category = NodeCategory.HOOK
            elif _is_api_call(call_text):
                category = NodeCategory.API_CALL

        # ── Emit this node if it's worth it ──────────────────
        if category in self.EMIT_CATEGORIES:
            ast_node = self._build_node(
                node, src, file_path, language, category, parent_name
            )
            if ast_node is not None:
                results.append(ast_node)

        # ── Determine new parent context for children ─────────
        new_parent = parent_name
        if category in SCOPE_CATEGORIES:
            name = _get_identifier(node, src)
            if name:
                new_parent = name

        # ── Recurse into children ─────────────────────────────
        # Do NOT recurse into nodes whose full content is captured as body_preview
        skip_recursion_for = {NodeCategory.IMPORT, NodeCategory.EXPORT,
                               NodeCategory.COMMENT, NodeCategory.RETURN,
                               NodeCategory.DECORATOR, NodeCategory.ANNOTATION}
        if category not in skip_recursion_for:
            for child in node.children:
                self._visit(child, src, file_path, language,
                            new_parent, results, depth + 1)

    # ── Node builder ──────────────────────────────────────────

    def _build_node(
        self,
        node: Node,
        src: bytes,
        file_path: str,
        language: str,
        category: NodeCategory,
        parent_name: Optional[str],
    ) -> Optional[ASTNode]:
        """Build an ASTNode from a raw tree-sitter node."""

        name = self._derive_name(node, src, category, language)
        if name is None:
            name = f"<{node.type}>"

        params: List[str] = []
        docstring: Optional[str] = None
        decorators: List[str] = []
        modifiers: List[str] = []
        return_type: Optional[str] = None
        body_preview: Optional[str] = None
        is_async = False

        # ── Enrich structural nodes ─────────────────────────
        if category in (STRUCTURAL_CATEGORIES | {NodeCategory.ASYNC_DEF,
                                                  NodeCategory.LAMBDA}):
            params      = _extract_params(node, src)
            decorators  = _extract_decorators(node, src)
            modifiers   = _extract_modifiers(node, src)
            docstring   = _extract_docstring(node, src, language)
            return_type = _return_type(node, src, language)
            is_async    = _is_async(node, src) or (category == NodeCategory.ASYNC_DEF)

        # Body preview for functions/methods
        if category in {NodeCategory.FUNCTION, NodeCategory.METHOD,
                        NodeCategory.CONSTRUCTOR, NodeCategory.ASYNC_DEF,
                        NodeCategory.LAMBDA, NodeCategory.CLASS,
                        NodeCategory.LOOP, NodeCategory.CONDITION,
                        NodeCategory.TRY_BLOCK, NodeCategory.SQL_QUERY,
                        NodeCategory.SQL_DDL, NodeCategory.SQL_DML}:
            raw = _src_text(node, src)
            body_preview = _collapse(raw, max_len=200)

        return ASTNode(
            category=category,
            raw_type=node.type,
            name=name,
            start_line=node.start_point[0] + 1,
            end_line=node.end_point[0] + 1,
            file_path=file_path,
            language=language,
            parent_name=parent_name,
            docstring=docstring,
            params=params,
            return_type=return_type,
            decorators=decorators,
            modifiers=modifiers,
            is_async=is_async,
            body_preview=body_preview,
        )

    def _derive_name(
        self,
        node: Node,
        src: bytes,
        category: NodeCategory,
        language: str,
    ) -> Optional[str]:
        """Derive the best possible name for a node."""

        # Structural nodes — use named identifier fields
        if category in STRUCTURAL_CATEGORIES | {NodeCategory.ASYNC_DEF,
                                                  NodeCategory.LAMBDA,
                                                  NodeCategory.TYPE_ALIAS,
                                                  NodeCategory.ENUM}:
            return _get_identifier(node, src) or "<anonymous>"

        # Import
        if category == NodeCategory.IMPORT:
            text = _src_text(node, src).strip()
            # Normalise to a short name
            text = re.sub(r"\s+", " ", text)
            return text[:120]

        # Export
        if category == NodeCategory.EXPORT:
            text = _src_text(node, src).strip()
            m = re.search(r"\b(\w+)\s*$", text.split("{")[0])
            return m.group(1) if m else text[:60]

        # Variable / assignment
        if category in {NodeCategory.VARIABLE, NodeCategory.ASSIGNMENT,
                        NodeCategory.CONSTANT}:
            name_node = node.child_by_field_name("name") or \
                        node.child_by_field_name("left")
            if name_node:
                return _src_text(name_node, src).strip()[:60]
            # Grab first identifier child
            for child in node.children:
                if child.type in ("identifier", "variable_declarator"):
                    return _src_text(child, src).split("=")[0].strip()[:60]
            return _src_text(node, src).split("=")[0].strip()[:60]

        # Control flow
        if category == NodeCategory.CONDITION:
            cond = node.child_by_field_name("condition")
            if cond:
                return _collapse(_src_text(cond, src), 80)
            return node.type   # "if_statement"

        if category == NodeCategory.LOOP:
            return node.type

        if category == NodeCategory.SWITCH:
            subj = node.child_by_field_name("value") or \
                   node.child_by_field_name("condition")
            if subj:
                return _collapse(_src_text(subj, src), 60)
            return node.type

        # Exception
        if category in {NodeCategory.TRY_BLOCK, NodeCategory.CATCH_BLOCK,
                        NodeCategory.FINALLY_BLOCK}:
            return node.type

        if category == NodeCategory.RAISE:
            return _collapse(_src_text(node, src), 80)

        # Calls
        if category in {NodeCategory.FUNCTION_CALL, NodeCategory.METHOD_CALL,
                        NodeCategory.HOOK, NodeCategory.API_CALL}:
            return _call_name(node, src)

        if category == NodeCategory.OBJECT_CREATION:
            # "new Foo()" → "Foo"
            type_node = node.child_by_field_name("constructor") or \
                        node.child_by_field_name("type")
            if type_node:
                return _src_text(type_node, src).strip()[:60]
            text = _src_text(node, src)
            m = re.search(r"new\s+(\w[\w.]*)", text)
            return m.group(1) if m else text[:60]

        # Decorators / annotations
        if category in {NodeCategory.DECORATOR, NodeCategory.ANNOTATION}:
            text = _src_text(node, src).strip()
            return re.sub(r"^[@#\[\]]+", "", text).split("(")[0].strip()[:60]

        # JSX
        if category == NodeCategory.JSX_ELEMENT:
            for child in node.children:
                if child.type in ("jsx_opening_element", "jsx_self_closing_element"):
                    tag = child.child_by_field_name("name")
                    if tag:
                        return _src_text(tag, src).strip()
            return "jsx"

        # Await / yield
        if category in {NodeCategory.AWAIT_EXPR, NodeCategory.YIELD_EXPR}:
            return _collapse(_src_text(node, src), 60)

        # Return
        if category == NodeCategory.RETURN:
            return _collapse(_src_text(node, src), 80)

        # SQL
        if category in {NodeCategory.SQL_QUERY, NodeCategory.SQL_DDL,
                        NodeCategory.SQL_DML}:
            text = _src_text(node, src).strip()
            m = re.search(r"\bFROM\s+(\w+)", text, re.IGNORECASE)
            if m:
                return f"query_{m.group(1)}"
            m2 = re.search(r"\b(?:TABLE|VIEW|INDEX|INTO|UPDATE)\s+(\w+)", text, re.IGNORECASE)
            if m2:
                return m2.group(1)
            return text.split()[0].lower()

        # Property
        if category == NodeCategory.PROPERTY:
            return _get_identifier(node, src) or "<field>"

        # Comment
        if category == NodeCategory.COMMENT:
            text = _src_text(node, src).strip()[:80]
            return re.sub(r"^[/\*# ]+", "", text).strip()

        return None
