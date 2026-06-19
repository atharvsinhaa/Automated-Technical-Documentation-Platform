"""
combiner/linker.py
──────────────────────────────────────────────────────────────
CrossFileLinker — purely deterministic dependency detection.

NO machine learning. NO external APIs. Fully offline.

DETECTION STRATEGIES (in priority order)
──────────────────────────────────────────
1. IMPORT_LINK
   File A imports from File B (same project, resolved by path)
   "from .user_service import UserService"
   → A depends on user_service.py

2. RELATIVE_IMPORT_LINK
   Explicit relative imports (JS/TS: import from './service')
   → Resolved against the importing file's directory

3. EXPORT_USAGE_LINK
   A uses a symbol that B exports
   Matched via canonical symbol names

4. API_CALL_LINK
   Frontend calls a URL pattern; backend defines a route matching that pattern
   e.g. axios.get('/api/users') ↔ @app.route('/api/users')

5. SQL_TABLE_LINK
   Code file references a SQL table that is defined/used in a .sql file

6. FUNCTION_CALL_LINK
   File A calls a function whose canonical name matches a definition in File B
   (fuzzy, medium confidence)

7. CLASS_USE_LINK
   File A instantiates or inherits a class defined in File B
"""

from __future__ import annotations

import os
import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from .models import Dependency, FileRecord, RawNode, SQLTable
from .normalizer import canonical, build_symbol_index


# ─────────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────────

def _basename(path: str) -> str:
    """'backend/user_service.py' → 'user_service'"""
    return Path(path).stem


def _dir(path: str) -> str:
    return str(Path(path).parent)


def _rel_resolve(importer: str, import_spec: str) -> Optional[str]:
    """
    Try to resolve a relative import specifier to a project-relative path.
    E.g.  importer="frontend/Dashboard.jsx"
          import_spec="./Chart"
          → "frontend/Chart" (will be matched against known file basenames)
    """
    if not import_spec.startswith("."):
        return None
    base = _dir(importer)
    resolved = os.path.normpath(os.path.join(base, import_spec))
    return resolved.replace("\\", "/")


def _extract_import_specs(node: RawNode) -> List[str]:
    """
    From an IMPORT node's name, extract what is being imported.
    'from .user_service import UserService' → ['user_service']
    "import { ChartComponent } from './Chart'" → ['./Chart']
    'import java.util.List;' → ['java.util.List']
    """
    name = node.name or ""
    specs = []

    # Python: from X import Y
    m = re.match(r"from\s+([\w./]+)\s+import", name)
    if m:
        specs.append(m.group(1).replace(".", "/"))
        return specs

    # Python/Java: import X
    m = re.match(r"import\s+([\w./]+)", name)
    if m:
        specs.append(m.group(1).replace(".", "/"))
        return specs

    # JS/TS: import ... from './path' or "path"
    m = re.search(r"""from\s+['"]([^'"]+)['"]""", name)
    if m:
        specs.append(m.group(1))
        return specs

    # Java: import com.airtel.service.X
    m = re.match(r"import\s+([\w.]+);?", name)
    if m:
        parts = m.group(1).split(".")
        specs.append("/".join(parts))
        return specs

    return specs


# ─────────────────────────────────────────────────────────────
#  SQL TABLE INDEX
# ─────────────────────────────────────────────────────────────

_SQL_TABLE_RE = re.compile(
    r"\b(?:FROM|JOIN|INTO|UPDATE|TABLE|VIEW)\s+(?:\w+\.)?(\w+)",
    re.IGNORECASE,
)
_CREATE_TABLE_RE = re.compile(
    r"\bCREATE\s+(?:TEMP(?:ORARY)?\s+)?(?:TABLE|VIEW)\s+"
    r"(?:IF\s+NOT\s+EXISTS\s+)?(?:\w+\.)?(\w+)",
    re.IGNORECASE,
)
# Common non-table keywords to skip
_SQL_KEYWORDS = frozenset({
    "SELECT", "WHERE", "AND", "OR", "NOT", "IN", "ON", "AS",
    "SET", "ALL", "DISTINCT", "GROUP", "ORDER", "BY", "HAVING",
    "LIMIT", "OFFSET", "UNION", "EXCEPT", "INTERSECT",
    "CASE", "WHEN", "THEN", "ELSE", "END", "NULL",
    "COUNT", "SUM", "AVG", "MAX", "MIN", "COALESCE",
    "CURRENT_DATE", "CURRENT_TIMESTAMP", "INTERVAL",
    "PRIMARY", "KEY", "UNIQUE", "INDEX", "CONSTRAINT",
    "DEFAULT", "NOT", "NULL", "REFERENCES",
})


def build_sql_table_index(files: List[FileRecord]) -> Dict[str, SQLTable]:
    """Scan SQL files and build a table-name → SQLTable index."""
    tables: Dict[str, SQLTable] = {}

    for fr in files:
        if fr.language != "sql":
            continue
        for node in fr.nodes:
            bp = node.body_preview or ""

            # Find CREATE TABLE definitions
            for m in _CREATE_TABLE_RE.finditer(bp):
                tname = m.group(1).upper()
                if tname in _SQL_KEYWORDS:
                    continue
                if tname not in tables:
                    tables[tname] = SQLTable(name=tname, defined_in=fr.rel_path)
                t = tables[tname]
                if "CREATE" not in t.operations:
                    t.operations.append("CREATE")
                if fr.rel_path not in t.referenced_in:
                    t.referenced_in.append(fr.rel_path)

            # Find all table references
            for m in _SQL_TABLE_RE.finditer(bp):
                tname = m.group(1).upper()
                if tname in _SQL_KEYWORDS or len(tname) <= 1:
                    continue
                if tname not in tables:
                    tables[tname] = SQLTable(name=tname)
                t = tables[tname]
                # Determine operation from node category
                op_map = {
                    "SQL_QUERY": "SELECT",
                    "SQL_DML":   "DML",
                    "SQL_DDL":   "DDL",
                }
                op = op_map.get(node.category, "REF")
                if op not in t.operations:
                    t.operations.append(op)
                if fr.rel_path not in t.referenced_in:
                    t.referenced_in.append(fr.rel_path)

    return tables


def find_sql_references_in_code(
    fr: FileRecord,
    table_index: Dict[str, SQLTable],
) -> List[str]:
    """Return table names referenced in a non-SQL source file."""
    found = []
    for node in fr.nodes:
        bp = (node.body_preview or "") + " " + (node.name or "")
        for m in _SQL_TABLE_RE.finditer(bp):
            tname = m.group(1).upper()
            if tname in table_index and tname not in found:
                found.append(tname)
    return found


# ─────────────────────────────────────────────────────────────
#  ROUTE / API DETECTION
# ─────────────────────────────────────────────────────────────

_ROUTE_DECORATORS = re.compile(
    r"""(?:app|router|blueprint|Router|Controller)\s*\.\s*"""
    r"""(?:get|post|put|patch|delete|route|use)\s*\(\s*['"]([^'"]+)['"]""",
    re.IGNORECASE,
)
_HTTP_CALL_RE = re.compile(
    r"""(?:axios|fetch|http|HttpClient|requests|got|superagent)\s*"""
    r"""[\.\(]+\s*['"]([^'"]+)['"]""",
    re.IGNORECASE,
)
_FASTAPI_ROUTE = re.compile(
    r"""@\s*(?:app|router)\s*\.\s*(?:get|post|put|patch|delete)\s*"""
    r"""\(\s*['"]([^'"]+)['"]""",
    re.IGNORECASE,
)


def build_route_index(files: List[FileRecord]) -> Dict[str, str]:
    """Return path_pattern → rel_path mapping for backend route definitions."""
    routes: Dict[str, str] = {}
    for fr in files:
        for node in fr.nodes:
            bp = node.body_preview or ""
            name = node.name or ""
            # FastAPI / Flask / Express style
            for pattern_re in (_ROUTE_DECORATORS, _FASTAPI_ROUTE):
                for m in pattern_re.finditer(bp + " " + name):
                    routes[m.group(1)] = fr.rel_path
    return routes


def match_api_calls(
    caller: FileRecord,
    route_index: Dict[str, str],
) -> List[Tuple[str, str, str]]:
    """
    For each API_CALL node in caller, try to match against route_index.
    Returns list of (caller_path, target_path, url_pattern).
    """
    hits = []
    for node in caller.nodes:
        if node.category not in {"API_CALL", "FUNCTION_CALL"}:
            continue
        bp = (node.body_preview or "") + " " + (node.name or "")
        for m in _HTTP_CALL_RE.finditer(bp):
            url = m.group(1)
            # Try to match against known routes
            for route_pat, target_file in route_index.items():
                if target_file == caller.rel_path:
                    continue
                # Normalize: strip trailing slash, match prefix
                u = url.rstrip("/")
                r = route_pat.rstrip("/")
                if u == r or u.startswith(r) or r.startswith(u):
                    hits.append((caller.rel_path, target_file, url))
                    break
    return hits


# ─────────────────────────────────────────────────────────────
#  MAIN LINKER
# ─────────────────────────────────────────────────────────────

class CrossFileLinker:
    """
    Builds all Dependency objects by running multiple
    deterministic detection strategies.
    """

    def __init__(self, files: List[FileRecord]):
        self.files = files
        self._file_map: Dict[str, FileRecord] = {
            fr.rel_path: fr for fr in files
        }
        # basename → list of rel_paths (multiple files can share a basename)
        self._basename_map: Dict[str, List[str]] = defaultdict(list)
        for fr in files:
            self._basename_map[_basename(fr.rel_path)].append(fr.rel_path)

        self._symbol_index = build_symbol_index(files)
        self._sql_tables   = build_sql_table_index(files)
        self._route_index  = build_route_index(files)

    # ── Public ────────────────────────────────────────────────

    def detect_all(self) -> Tuple[List[Dependency], List[SQLTable]]:
        deps: List[Dependency] = []
        seen: Set[Tuple] = set()

        def _add(d: Dependency):
            key = (d.source_file, d.target_file, d.dep_type, d.source_symbol or "")
            if key not in seen and d.source_file != d.target_file:
                seen.add(key)
                deps.append(d)

        for fr in self.files:
            for d in self._import_links(fr):   _add(d)
            for d in self._export_links(fr):   _add(d)
            for d in self._api_links(fr):      _add(d)
            for d in self._sql_links(fr):      _add(d)
            for d in self._call_links(fr):     _add(d)

        tables = list(self._sql_tables.values())
        return deps, tables

    # ── Strategy 1: Import-based links ────────────────────────

    def _import_links(self, fr: FileRecord) -> List[Dependency]:
        deps = []
        for node in fr.nodes:
            if node.category != "IMPORT":
                continue
            for spec in _extract_import_specs(node):
                targets = self._resolve_to_files(spec, fr.rel_path)
                for t in targets:
                    deps.append(Dependency(
                        source_file=fr.rel_path,
                        target_file=t,
                        dep_type="IMPORT",
                        source_symbol=node.name[:80],
                        evidence=f"'{node.name}' imports from '{t}'",
                        confidence="high",
                    ))
        return deps

    def _resolve_to_files(self, spec: str, importer: str) -> List[str]:
        """Try to resolve an import specifier to actual file paths."""
        found = []

        # 1. Relative import
        if spec.startswith("."):
            rel = _rel_resolve(importer, spec)
            if rel:
                # Try with common extensions
                for ext in [".py", ".js", ".jsx", ".ts", ".tsx", ".java", ""]:
                    candidate = rel + ext
                    if candidate in self._file_map:
                        found.append(candidate)
                        break
                # Also try basename match
                stem = _basename(rel)
                for path in self._basename_map.get(stem, []):
                    if path not in found and path != importer:
                        found.append(path)
            return found

        # 2. Absolute/package import — match by basename
        parts = spec.strip("/").split("/")
        # Try full path first
        for ext in [".py", ".js", ".jsx", ".ts", ".tsx", ".java", ""]:
            candidate = spec + ext
            if candidate in self._file_map:
                found.append(candidate)
                return found

        # Try basename only (last component)
        for stem_candidate in reversed(parts):
            stem_candidate = stem_candidate.replace("-", "_")
            matches = self._basename_map.get(stem_candidate, [])
            for m in matches:
                if m != importer and m not in found:
                    found.append(m)
            if found:
                break

        return found[:3]   # cap at 3 to avoid false positives

    # ── Strategy 2: Export-to-usage links ─────────────────────

    def _export_links(self, fr: FileRecord) -> List[Dependency]:
        """If file A exports symbol S, find files that import/use S."""
        deps = []
        exported_names = set()
        for node in fr.nodes:
            if node.category == "EXPORT":
                # Extract the exported symbol name
                m = re.search(r"\b(\w+)\s*$", (node.name or "").split("{")[0])
                if m:
                    exported_names.add(m.group(1))
                    exported_names.add(canonical(m.group(1)))

        if not exported_names:
            return deps

        for other in self.files:
            if other.rel_path == fr.rel_path:
                continue
            for node in other.nodes:
                if node.category == "IMPORT":
                    for spec in _extract_import_specs(node):
                        # Check if the spec mentions any exported name
                        for ename in exported_names:
                            if ename in spec or ename in (node.name or ""):
                                deps.append(Dependency(
                                    source_file=other.rel_path,
                                    target_file=fr.rel_path,
                                    dep_type="EXPORT_USE",
                                    source_symbol=node.name[:80],
                                    target_symbol=ename,
                                    evidence=f"'{other.rel_path}' uses export '{ename}' from '{fr.rel_path}'",
                                    confidence="medium",
                                ))
                            break
        return deps

    # ── Strategy 3: API call ↔ route matching ─────────────────

    def _api_links(self, fr: FileRecord) -> List[Dependency]:
        deps = []
        for (src, tgt, url) in match_api_calls(fr, self._route_index):
            deps.append(Dependency(
                source_file=src,
                target_file=tgt,
                dep_type="API_CALL",
                source_symbol=url,
                evidence=f"HTTP call to '{url}' defined in '{tgt}'",
                confidence="medium",
            ))
        return deps

    # ── Strategy 4: SQL table references ──────────────────────

    def _sql_links(self, fr: FileRecord) -> List[Dependency]:
        if fr.language == "sql":
            return []
        deps = []
        tables_used = find_sql_references_in_code(fr, self._sql_tables)
        for tname in tables_used:
            t = self._sql_tables[tname]
            if t.defined_in and t.defined_in != fr.rel_path:
                deps.append(Dependency(
                    source_file=fr.rel_path,
                    target_file=t.defined_in,
                    dep_type="SQL_USE",
                    target_symbol=tname,
                    evidence=f"'{fr.rel_path}' references SQL table '{tname}'",
                    confidence="medium",
                ))
        return deps

    # ── Strategy 5: Function-call → definition ────────────────

    def _call_links(self, fr: FileRecord) -> List[Dependency]:
        """
        If file A calls function F, and file B defines F (by canonical name),
        emit a FUNCTION_CALL dependency. Confidence = low (name collisions exist).
        """
        deps = []
        for node in fr.nodes:
            if node.category not in {"FUNCTION_CALL", "METHOD_CALL"}:
                continue
            c = canonical(node.name)
            sym = self._symbol_index.get(c)
            if sym is None:
                continue
            for def_file in sym.defined_in:
                if def_file == fr.rel_path:
                    continue
                deps.append(Dependency(
                    source_file=fr.rel_path,
                    target_file=def_file,
                    dep_type="FUNCTION_CALL",
                    source_symbol=node.name,
                    target_symbol=sym.original_names[0] if sym.original_names else c,
                    evidence=f"'{fr.rel_path}' calls '{node.name}' defined in '{def_file}'",
                    confidence="low",
                ))
        return deps
