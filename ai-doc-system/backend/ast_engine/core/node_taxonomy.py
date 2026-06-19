"""
core/node_taxonomy.py
─────────────────────────────────────────────────────────────
UNIVERSAL NODE TAXONOMY

This is the semantic heart of the engine.

WHY this file exists
────────────────────
Tree-sitter gives you raw AST node types like:
  "function_definition"   (Python)
  "function_declaration"  (JavaScript, Java, Go)
  "function_item"         (Rust)
  "method_declaration"    (Java)
  "method_definition"     (JS/TS)

None of these carry semantic meaning on their own.
Tree-sitter is a SYNTAX parser — it describes FORM, not MEANING.

Without this mapping:
  • A loop in Python  → "for_statement"
  • A loop in Java    → "enhanced_for_statement"
  • A loop in Go      → "for_statement" (same keyword, different semantics!)
  • A loop in Rust    → "for_expression"
  The engine can't know they all mean the same universal concept: LOOP.

This taxonomy maps every language-specific node type
to a UNIVERSAL SEMANTIC CATEGORY that the extractor layer
understands regardless of language.

Design principles
─────────────────
1. Flat enum of universal categories
2. A mapping table: raw_node_type → UniversalCategory
3. Extractors operate only on UniversalCategory
4. Adding a new language = adding its node types to this table
"""

from __future__ import annotations
from enum import Enum, auto
from typing import Dict, FrozenSet, Optional, Tuple


class NodeCategory(Enum):
    """
    Universal semantic categories — language-agnostic.
    Every AST node encountered maps to one of these (or UNKNOWN).
    """
    # ── Structure ──────────────────────────────────────────────
    MODULE          = auto()   # file-level / package / namespace
    CLASS           = auto()   # class, struct (semantic object type)
    INTERFACE       = auto()   # interface, trait, protocol, abstract class
    ENUM            = auto()   # enum, union (discriminated)
    FUNCTION        = auto()   # top-level function / free function
    METHOD          = auto()   # function inside a class/impl/object
    CONSTRUCTOR     = auto()   # __init__, constructor, new()
    PROPERTY        = auto()   # @property, getter/setter, public field

    # ── Imports / Exports ──────────────────────────────────────
    IMPORT          = auto()   # import, use, require, #include
    EXPORT          = auto()   # export, pub, module.exports

    # ── Variables & Assignments ────────────────────────────────
    VARIABLE        = auto()   # local_variable_declaration, let, const, var
    ASSIGNMENT      = auto()   # assignment_expression / statement
    CONSTANT        = auto()   # UPPER_CASE variables, final, const

    # ── Control Flow ──────────────────────────────────────────
    CONDITION       = auto()   # if / else / elif / ternary
    LOOP            = auto()   # for / while / do-while / loop
    SWITCH          = auto()   # switch, match (Rust/Python)
    BREAK_CONTINUE  = auto()   # break, continue, next

    # ── Exception Handling ─────────────────────────────────────
    TRY_BLOCK       = auto()   # try / try-with-resources
    CATCH_BLOCK     = auto()   # except / catch
    FINALLY_BLOCK   = auto()   # finally
    RAISE           = auto()   # raise / throw

    # ── Async / Concurrent ─────────────────────────────────────
    ASYNC_DEF       = auto()   # async def / async function
    AWAIT_EXPR      = auto()   # await
    YIELD_EXPR      = auto()   # yield / yield from

    # ── Calls & Expressions ────────────────────────────────────
    FUNCTION_CALL   = auto()   # call_expression / method_invocation
    METHOD_CALL     = auto()   # chained call on an object
    OBJECT_CREATION = auto()   # new Foo() / Foo::new() / object()
    LAMBDA          = auto()   # lambda, arrow_function, closure

    # ── Decorators / Annotations ───────────────────────────────
    DECORATOR       = auto()   # @decorator (Python), @Annotation (Java)
    ANNOTATION      = auto()   # @Override, @Service, #[derive]

    # ── Type System ────────────────────────────────────────────
    TYPE_ALIAS      = auto()   # type X = Y, typedef, newtype
    GENERIC         = auto()   # type parameters / generics

    # ── Return ─────────────────────────────────────────────────
    RETURN          = auto()   # return statement

    # ── Comments / Docs ────────────────────────────────────────
    DOCSTRING       = auto()   # triple-quoted strings, JSDoc
    COMMENT         = auto()   # // /* # single-line / block comments

    # ── React / Frontend Specifics ─────────────────────────────
    JSX_ELEMENT     = auto()   # <Component />, <div>
    HOOK            = auto()   # useState, useEffect (detected by name pattern)
    COMPONENT       = auto()   # functional/class React component

    # ── Database / API ─────────────────────────────────────────
    SQL_QUERY       = auto()   # SELECT / INSERT / UPDATE / DELETE / WITH
    SQL_DDL         = auto()   # CREATE / DROP / ALTER / TRUNCATE
    SQL_DML         = auto()   # INSERT / UPDATE / DELETE / MERGE
    API_CALL        = auto()   # HTTP fetch / axios / requests.get

    # ── Catch-all ──────────────────────────────────────────────
    EXPRESSION      = auto()   # generic expression_statement
    UNKNOWN         = auto()   # unmapped / irrelevant syntax node


# ─────────────────────────────────────────────────────────────
#  UNIVERSAL NODE TYPE MAP
#  raw tree-sitter node type → NodeCategory
#  This covers ALL languages registered in the ParserRegistry.
# ─────────────────────────────────────────────────────────────

RAW_TO_CATEGORY: Dict[str, NodeCategory] = {

    # ══ MODULE / PACKAGE ══════════════════════════════════════
    "module":                    NodeCategory.MODULE,   # Python root
    "program":                   NodeCategory.MODULE,   # JS/TS root
    "source_file":               NodeCategory.MODULE,   # Rust/Go root
    "package_declaration":       NodeCategory.MODULE,   # Java
    "package_clause":            NodeCategory.MODULE,   # Go

    # ══ CLASS / STRUCT ════════════════════════════════════════
    "class_definition":          NodeCategory.CLASS,    # Python
    "class_declaration":         NodeCategory.CLASS,    # JS/TS/Java
    "struct_item":               NodeCategory.CLASS,    # Rust
    "struct_type":               NodeCategory.CLASS,    # Go
    "type_declaration":          NodeCategory.CLASS,    # Go (type X struct)
    "object_type":               NodeCategory.CLASS,    # TS
    "record_declaration":        NodeCategory.CLASS,    # Java 16+
    "enum_class_declaration":    NodeCategory.CLASS,    # Java (enum class)

    # ══ INTERFACE / TRAIT / PROTOCOL ═════════════════════════
    "interface_declaration":     NodeCategory.INTERFACE,  # Java/TS
    "trait_item":                NodeCategory.INTERFACE,  # Rust
    "abstract_class_declaration":NodeCategory.INTERFACE,  # TS
    "protocol_declaration":      NodeCategory.INTERFACE,  # Swift-like

    # ══ ENUM ══════════════════════════════════════════════════
    "enum_declaration":          NodeCategory.ENUM,     # Java/TS
    "enum_item":                 NodeCategory.ENUM,     # Rust
    "enum_definition":           NodeCategory.ENUM,     # Python (not TS node)

    # ══ FUNCTION (top-level / free) ═══════════════════════════
    "function_definition":       NodeCategory.FUNCTION,  # Python
    "function_declaration":      NodeCategory.FUNCTION,  # JS/TS/Java/Go
    "function_item":             NodeCategory.FUNCTION,  # Rust
    "func_literal":              NodeCategory.FUNCTION,  # Go anonymous func
    "subroutine_declaration":    NodeCategory.FUNCTION,  # Bash (func)
    "function_declarator":       NodeCategory.FUNCTION,  # C/C++

    # ══ METHOD (inside class / impl) ══════════════════════════
    "method_definition":         NodeCategory.METHOD,   # JS/TS
    "method_declaration":        NodeCategory.METHOD,   # Java
    "method_declaration_body":   NodeCategory.METHOD,   # Kotlin
    "function_declaration_body": NodeCategory.METHOD,   # Kotlin method
    "impl_item":                 NodeCategory.METHOD,   # Rust impl block
    "method":                    NodeCategory.METHOD,   # Ruby
    "function_method":           NodeCategory.METHOD,   # generic

    # ══ CONSTRUCTOR ═══════════════════════════════════════════
    "constructor_declaration":   NodeCategory.CONSTRUCTOR,  # Java
    "constructor_definition":    NodeCategory.CONSTRUCTOR,  # TS
    "constructor":               NodeCategory.CONSTRUCTOR,  # JS (method named "constructor")

    # ══ PROPERTY / FIELD ══════════════════════════════════════
    "field_declaration":         NodeCategory.PROPERTY,   # Java/Go/Rust
    "public_field_definition":   NodeCategory.PROPERTY,   # TS class field
    "attribute":                 NodeCategory.PROPERTY,   # Python class attr
    "property_signature":        NodeCategory.PROPERTY,   # TS interface prop
    "property_definition":       NodeCategory.PROPERTY,   # JS object prop

    # ══ IMPORT ════════════════════════════════════════════════
    "import_statement":          NodeCategory.IMPORT,   # Python/JS/TS
    "import_from_statement":     NodeCategory.IMPORT,   # Python "from x import y"
    "import_declaration":        NodeCategory.IMPORT,   # Java
    "use_declaration":           NodeCategory.IMPORT,   # Rust
    "import_spec":               NodeCategory.IMPORT,   # Go
    "preproc_include":           NodeCategory.IMPORT,   # C/C++ #include
    "require_call":              NodeCategory.IMPORT,   # CommonJS require()

    # ══ EXPORT ════════════════════════════════════════════════
    "export_statement":          NodeCategory.EXPORT,   # JS/TS
    "export_default":            NodeCategory.EXPORT,   # JS/TS
    "module_item":               NodeCategory.EXPORT,   # Rust pub mod

    # ══ VARIABLE ══════════════════════════════════════════════
    "local_variable_declaration":NodeCategory.VARIABLE,  # Java
    "variable_declaration":      NodeCategory.VARIABLE,  # JS/TS var
    "lexical_declaration":       NodeCategory.VARIABLE,  # JS/TS let/const
    "let_declaration":           NodeCategory.VARIABLE,  # Rust
    "var_declaration":           NodeCategory.VARIABLE,  # Go
    "var_spec":                  NodeCategory.VARIABLE,  # Go var spec
    "assignment_statement":      NodeCategory.VARIABLE,  # Go :=
    "short_var_declaration":     NodeCategory.VARIABLE,  # Go
    "named_parameter":           NodeCategory.VARIABLE,  # Kotlin named param

    # ══ ASSIGNMENT ════════════════════════════════════════════
    "assignment":                NodeCategory.ASSIGNMENT,  # Python
    "assignment_expression":     NodeCategory.ASSIGNMENT,  # Java/JS
    "augmented_assignment":      NodeCategory.ASSIGNMENT,  # Python +=

    # ══ CONDITION ════════════════════════════════════════════
    "if_statement":              NodeCategory.CONDITION,  # all languages
    "if_expression":             NodeCategory.CONDITION,  # Rust
    "conditional_expression":    NodeCategory.CONDITION,  # ternary C/Java
    "ternary_expression":        NodeCategory.CONDITION,  # JS ternary
    "else_clause":               NodeCategory.CONDITION,  # Python else
    "elif_clause":               NodeCategory.CONDITION,  # Python elif
    "when_expression":           NodeCategory.CONDITION,  # Kotlin when

    # ══ LOOP ══════════════════════════════════════════════════
    "for_statement":             NodeCategory.LOOP,      # Python/Go/Java/JS
    "for_in_statement":          NodeCategory.LOOP,      # JS for-in
    "for_of_statement":          NodeCategory.LOOP,      # JS for-of
    "enhanced_for_statement":    NodeCategory.LOOP,      # Java for-each
    "while_statement":           NodeCategory.LOOP,      # all languages
    "do_statement":              NodeCategory.LOOP,      # JS/Java do-while
    "loop_expression":           NodeCategory.LOOP,      # Rust loop{}
    "for_expression":            NodeCategory.LOOP,      # Rust for
    "while_expression":          NodeCategory.LOOP,      # Rust while
    "repeat_while_statement":    NodeCategory.LOOP,      # Swift

    # ══ SWITCH / MATCH ════════════════════════════════════════
    "switch_statement":          NodeCategory.SWITCH,
    "switch_expression":         NodeCategory.SWITCH,    # Java 14+
    "match_expression":          NodeCategory.SWITCH,    # Rust match
    "match_statement":           NodeCategory.SWITCH,    # Python 3.10+

    # ══ BREAK / CONTINUE ══════════════════════════════════════
    "break_statement":           NodeCategory.BREAK_CONTINUE,
    "continue_statement":        NodeCategory.BREAK_CONTINUE,

    # ══ EXCEPTION HANDLING ════════════════════════════════════
    "try_statement":             NodeCategory.TRY_BLOCK,
    "try_expression":            NodeCategory.TRY_BLOCK,    # Rust ?
    "except_clause":             NodeCategory.CATCH_BLOCK,  # Python
    "catch_clause":              NodeCategory.CATCH_BLOCK,  # JS/Java
    "finally_clause":            NodeCategory.FINALLY_BLOCK,
    "raise_statement":           NodeCategory.RAISE,        # Python
    "throw_statement":           NodeCategory.RAISE,        # JS/Java

    # ══ ASYNC / CONCURRENT ════════════════════════════════════
    "await_expression":          NodeCategory.AWAIT_EXPR,
    "yield":                     NodeCategory.YIELD_EXPR,   # Python
    "yield_expression":          NodeCategory.YIELD_EXPR,
    "yield_from_statement":      NodeCategory.YIELD_EXPR,   # Python yield from
    "generator_expression":      NodeCategory.YIELD_EXPR,

    # ══ FUNCTION CALLS ════════════════════════════════════════
    "call":                      NodeCategory.FUNCTION_CALL,  # Python
    "call_expression":           NodeCategory.FUNCTION_CALL,  # JS/TS/Go/Rust
    "method_invocation":         NodeCategory.FUNCTION_CALL,  # Java
    "function_call_expression":  NodeCategory.FUNCTION_CALL,  # Kotlin

    # ══ OBJECT CREATION ═══════════════════════════════════════
    "object_creation_expression":NodeCategory.OBJECT_CREATION,  # Java
    "new_expression":            NodeCategory.OBJECT_CREATION,  # JS/TS
    "struct_expression":         NodeCategory.OBJECT_CREATION,  # Rust Foo{..}

    # ══ LAMBDA / ARROW / CLOSURE ══════════════════════════════
    "lambda":                    NodeCategory.LAMBDA,          # Python
    "arrow_function":            NodeCategory.LAMBDA,          # JS/TS
    "closure_expression":        NodeCategory.LAMBDA,          # Rust
    "anonymous_function":        NodeCategory.LAMBDA,          # PHP
    "lambda_expression":         NodeCategory.LAMBDA,          # Java/Kotlin

    # ══ DECORATOR / ANNOTATION ════════════════════════════════
    "decorator":                 NodeCategory.DECORATOR,    # Python/TS
    "decorator_statement":       NodeCategory.DECORATOR,
    "marker_annotation":         NodeCategory.ANNOTATION,   # Java @Override
    "annotation":                NodeCategory.ANNOTATION,   # Java
    "attribute_item":            NodeCategory.ANNOTATION,   # Rust #[derive]

    # ══ TYPE ALIAS ════════════════════════════════════════════
    "type_alias":                NodeCategory.TYPE_ALIAS,
    "type_alias_declaration":    NodeCategory.TYPE_ALIAS,   # TS type X = Y

    # ══ RETURN ════════════════════════════════════════════════
    "return_statement":          NodeCategory.RETURN,
    "return_expression":         NodeCategory.RETURN,

    # ══ JSX ═══════════════════════════════════════════════════
    "jsx_element":               NodeCategory.JSX_ELEMENT,
    "jsx_self_closing_element":  NodeCategory.JSX_ELEMENT,
    "jsx_fragment":              NodeCategory.JSX_ELEMENT,

    # ══ COMMENTS ══════════════════════════════════════════════
    "comment":                   NodeCategory.COMMENT,
    "block_comment":             NodeCategory.COMMENT,
    "line_comment":              NodeCategory.COMMENT,

    # ══ EXPRESSIONS ═══════════════════════════════════════════
    "expression_statement":      NodeCategory.EXPRESSION,
    "binary_expression":         NodeCategory.EXPRESSION,
    "unary_expression":          NodeCategory.EXPRESSION,

    # ══ SCALA ════════════════════════════════════════════════
"class_definition":         NodeCategory.CLASS,
"object_definition":        NodeCategory.CLASS,
"trait_definition":         NodeCategory.INTERFACE,
"function_definition":      NodeCategory.FUNCTION,
"call_expression":          NodeCategory.FUNCTION_CALL,
"import_declaration":       NodeCategory.IMPORT,
"val_definition":           NodeCategory.VARIABLE,
"var_definition":           NodeCategory.VARIABLE,
"if_expression":            NodeCategory.CONDITION,
"for_expression":           NodeCategory.LOOP,
"match_expression":         NodeCategory.SWITCH,

}


def classify(node_type: str) -> NodeCategory:
    """Map a raw tree-sitter node type to a universal category."""
    return RAW_TO_CATEGORY.get(node_type, NodeCategory.UNKNOWN)


# ── Sets used by extractors for fast membership tests ─────────

STRUCTURAL_CATEGORIES: FrozenSet[NodeCategory] = frozenset({
    NodeCategory.CLASS,
    NodeCategory.INTERFACE,
    NodeCategory.ENUM,
    NodeCategory.FUNCTION,
    NodeCategory.METHOD,
    NodeCategory.CONSTRUCTOR,
})

CONTROL_FLOW_CATEGORIES: FrozenSet[NodeCategory] = frozenset({
    NodeCategory.CONDITION,
    NodeCategory.LOOP,
    NodeCategory.SWITCH,
    NodeCategory.BREAK_CONTINUE,
})

EXCEPTION_CATEGORIES: FrozenSet[NodeCategory] = frozenset({
    NodeCategory.TRY_BLOCK,
    NodeCategory.CATCH_BLOCK,
    NodeCategory.FINALLY_BLOCK,
    NodeCategory.RAISE,
})

ASYNC_CATEGORIES: FrozenSet[NodeCategory] = frozenset({
    NodeCategory.ASYNC_DEF,
    NodeCategory.AWAIT_EXPR,
    NodeCategory.YIELD_EXPR,
})

