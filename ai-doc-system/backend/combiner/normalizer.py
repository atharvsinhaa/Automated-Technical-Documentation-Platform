"""
combiner/normalizer.py
──────────────────────────────────────────────────────────────
Normalizer — deterministic, rule-based name normalization.

PROBLEM IT SOLVES
──────────────────
Python:     process_data()       → snake_case
Java/JS/TS: processData()        → camelCase
Scala:      ProcessData()        → PascalCase

These are the same function in a polyglot codebase.
Without normalization, the linker misses the cross-language
call relationship.

APPROACH
─────────
1. Convert every symbol name → canonical snake_case
2. Index symbols by their canonical name
3. When linking, look up by canonical name to find cross-file matches

This is fully deterministic — no ML, no external API.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple
from .models import FileRecord, RawNode, NormalizedSymbol


# ── Conversion helpers ────────────────────────────────────────

def _camel_to_snake(name: str) -> str:
    """processData → process_data, HTMLParser → html_parser"""
    # Insert underscore before uppercase letters that follow lowercase
    s1 = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", name)
    # Insert underscore before uppercase letter followed by lowercase
    # (handles HTMLParser → HTML_Parser)
    s2 = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", s1)
    return s2.lower()


def _pascal_to_snake(name: str) -> str:
    return _camel_to_snake(name)


def _strip_noise(name: str) -> str:
    """Remove common non-semantic prefixes/suffixes."""
    # Strip leading dunders for Python special methods
    name = name.strip("_")
    # Strip language-specific type suffixes: Service, Repository, Controller, etc.
    # We preserve them for disambiguation — don't strip here
    return name


def canonical(name: str) -> str:
    """
    Return the canonical snake_case form of any symbol name.
    This is the key used for cross-file matching.
    """
    if not name or name.startswith("<"):
        return name.lower()
    clean = _strip_noise(name)
    snake = _camel_to_snake(clean)
    # Collapse multiple underscores
    snake = re.sub(r"_+", "_", snake).strip("_")
    return snake


# ── Symbol index ──────────────────────────────────────────────

STRUCTURAL_CATEGORIES = {
    "CLASS", "INTERFACE", "ENUM",
    "FUNCTION", "METHOD", "CONSTRUCTOR", "ASYNC_DEF",
}


def build_symbol_index(
    files: List[FileRecord],
) -> Dict[str, NormalizedSymbol]:
    """
    Build a canonical_name → NormalizedSymbol mapping.

    Only indexes structural symbols (functions, classes, methods)
    — not every loop or condition.
    """
    index: Dict[str, NormalizedSymbol] = {}

    for fr in files:
        for node in fr.nodes:
            if node.category not in STRUCTURAL_CATEGORIES:
                continue
            c = canonical(node.name)
            if not c or c in {"<anonymous>", "anonymous"}:
                continue
            if c not in index:
                index[c] = NormalizedSymbol(
                    canonical_name=c,
                    category=node.category,
                )
            sym = index[c]
            if node.name not in sym.original_names:
                sym.original_names.append(node.name)
            if fr.rel_path not in sym.defined_in:
                sym.defined_in.append(fr.rel_path)

    return index


def normalize_files(files: List[FileRecord]) -> List[FileRecord]:
    """
    Patch each RawNode with a canonical_name attribute.
    (We store it as a property — no mutation of existing fields.)
    We don't mutate the name; the canonical form is used only for matching.
    Returns the same list (modified in-place).
    """
    for fr in files:
        for node in fr.nodes:
            # Attach canonical name as a derived attribute
            # RawNode has no canonical_name field — we monkey-patch it
            # so downstream code can access it without schema change
            object.__setattr__(node, "_canonical", canonical(node.name)) \
                if hasattr(node, "__dict__") else None
            node.__dict__["_canonical"] = canonical(node.name)
    return files
