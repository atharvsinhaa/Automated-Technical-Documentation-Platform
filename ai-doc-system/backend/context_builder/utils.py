"""
context_builder/utils.py
────────────────────────────────────────────────────────────────
Shared utilities for the Context Builder.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Optional


_CTRL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def safe_str(s: Any, max_len: int = 500) -> str:
    """Safely convert to string, strip control chars, truncate."""
    if s is None:
        return ""
    text = _CTRL_RE.sub("", str(s))
    if len(text) > max_len:
        text = text[:max_len] + "…"
    return text


def cypher_escape(s: str) -> str:
    """Escape a string for safe Cypher embedding."""
    if s is None:
        return ""
    s = _CTRL_RE.sub("", str(s))
    return s.replace("\\", "\\\\").replace("'", "\\'").replace('"', '\\"')


def node_record_to_dict(record: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert a Neo4j node record to a flat dict.
    Handles both bolt driver records and dicts.
    """
    if hasattr(record, "data"):
        return dict(record.data())
    return dict(record)


def normalize_path(path: str) -> str:
    """Normalize file path for comparison."""
    if not path:
        return ""
    # Remove leading ./ or /
    path = path.lstrip("./")
    # Normalize separators
    path = path.replace("\\", "/")
    return path


def truncate_source(source: str, max_lines: int = 200) -> str:
    """Truncate source code to max lines."""
    if not source:
        return ""
    lines = source.split("\n")
    if len(lines) > max_lines:
        return "\n".join(lines[:max_lines]) + f"\n\n... ({len(lines) - max_lines} more lines)"
    return source
