"""
extractors/sql_extractor.py
─────────────────────────────────────────────────────────────
Lightweight SQL extractor (tree-sitter SQL grammar not in pip).
Parses SQL into ASTNode objects using a statement-level approach.
Extracts: queries, DDL, DML, CTEs, subqueries, indexes.
"""

from __future__ import annotations

import re
from typing import List, Optional

from ..core.models import ASTNode
from ..core.node_taxonomy import NodeCategory


_DDL_RE = re.compile(r"^\s*(CREATE|DROP|ALTER|TRUNCATE)\b", re.IGNORECASE)
_DML_RE = re.compile(r"^\s*(INSERT|UPDATE|DELETE|MERGE)\b", re.IGNORECASE)
_QRY_RE = re.compile(r"^\s*(SELECT|WITH)\b",                re.IGNORECASE)
_IDX_RE = re.compile(r"CREATE\s+(?:UNIQUE\s+)?INDEX\s+(?:IF\s+NOT\s+EXISTS\s+)?(\w+)",
                     re.IGNORECASE)
_TBL_RE = re.compile(r"(?:TABLE|VIEW|PROCEDURE|FUNCTION|SEQUENCE)\s+"
                     r"(?:IF\s+NOT\s+EXISTS\s+)?(?:\w+\.)?(\w+)", re.IGNORECASE)
_FROM_RE = re.compile(r"\bFROM\s+(?:\w+\.)?(\w+)", re.IGNORECASE)
_INTO_RE = re.compile(r"\b(?:INTO|UPDATE|MERGE\s+INTO)\s+(?:\w+\.)?(\w+)", re.IGNORECASE)


def _classify_sql(stmt: str) -> NodeCategory:
    if _DDL_RE.match(stmt):
        return NodeCategory.SQL_DDL
    if _DML_RE.match(stmt):
        return NodeCategory.SQL_DML
    if _QRY_RE.match(stmt):
        return NodeCategory.SQL_QUERY
    return NodeCategory.EXPRESSION


def _name_sql(stmt: str, idx: int, cat: NodeCategory) -> str:
    if cat == NodeCategory.SQL_DDL:
        m = _IDX_RE.search(stmt) or _TBL_RE.search(stmt)
        return m.group(1) if m else f"ddl_{idx}"
    if cat == NodeCategory.SQL_DML:
        m = _INTO_RE.search(stmt)
        first = stmt.strip().split()[0].lower()
        return f"{first}_{m.group(1)}" if m else f"dml_{idx}"
    if cat == NodeCategory.SQL_QUERY:
        m = _FROM_RE.search(stmt)
        return f"query_{m.group(1)}" if m else f"query_{idx}"
    return f"stmt_{idx}"


def extract_sql(file_path: str, source: str) -> List[ASTNode]:
    """Split SQL source on semicolons and extract structured nodes."""
    statements = re.split(r";\s*(?:\n|$)", source, flags=re.MULTILINE)
    nodes: List[ASTNode] = []
    line_cursor = 1

    for i, raw_stmt in enumerate(statements, 1):
        stmt = raw_stmt.strip()
        if not stmt:
            line_cursor += raw_stmt.count("\n") + 1
            continue

        cat  = _classify_sql(stmt)
        name = _name_sql(stmt, i, cat)
        collapsed = " ".join(stmt.split())

        nodes.append(ASTNode(
            category=cat,
            raw_type="sql_statement",
            name=name,
            start_line=line_cursor,
            end_line=line_cursor + stmt.count("\n"),
            file_path=file_path,
            language="sql",
            body_preview=collapsed[:200],
        ))
        line_cursor += raw_stmt.count("\n") + 1

    return nodes
