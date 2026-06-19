"""
dependency_extractor/relationship_rules.py
────────────────────────────────────────────────────────────────
ALL relationship detection rules live here.

Design principles:
  1. Each rule is a pure function: (project, graph) → None  (mutates graph)
  2. Rules are completely independent — no shared mutable state
  3. Every rule is documented with the relationship it creates
  4. Adding a new rule = adding one function + registering it in RULES list
  5. Zero LLM, zero cloud, zero regex hacks — only AST-grounded logic

Rule categories:
  ● STRUCTURAL   — FILE→CONTAINS→SYMBOL, FILE→DEFINES→CLASS, etc.
  ● IMPORT       — FILE→IMPORTS→FILE
  ● CALL GRAPH   — FUNCTION→CALLS→FUNCTION
  ● HIERARCHY    — CLASS→EXTENDS→CLASS, CLASS→IMPLEMENTS→INTERFACE
  ● SQL          — FUNCTION→QUERIES_TABLE→SQL_TABLE
  ● REACT        — COMPONENT→RENDERS→COMPONENT, COMPONENT→USES_HOOK→HOOK
  ● SPARK        — SPARK_JOB→READS_FROM→DATAFRAME
  ● API          — COMPONENT→CALLS_API→ENDPOINT
  ● ANNOTATION   — CLASS→ANNOTATED_BY→DECORATOR
  ● C2_PROMOTED  — promote Component 2 dependency edges into typed graph edges
"""

from __future__ import annotations

import re
from typing import List, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from .xml_loader import LoadedProject
    from .graph_builder import GraphBuilder

from .models import (
    GraphNode, GraphEdge, DependencyGraph,
    NodeType, RelationType, make_node_id
)


# ══════════════════════════════════════════════════════════════
#  UTILITY REGEX (compiled once at module load)
# ══════════════════════════════════════════════════════════════

# SQL table references in body_preview
_SQL_FROM  = re.compile(r"\bFROM\s+(\w+)", re.IGNORECASE)
_SQL_JOIN  = re.compile(r"\bJOIN\s+(\w+)",  re.IGNORECASE)
_SQL_INTO  = re.compile(r"\bINTO\s+(\w+)",  re.IGNORECASE)
_SQL_UPDATE= re.compile(r"\bUPDATE\s+(\w+)",re.IGNORECASE)
_SQL_CREATE= re.compile(r"\bCREATE\s+(?:TABLE|VIEW)\s+(?:IF\s+NOT\s+EXISTS\s+)?(\w+)", re.IGNORECASE)

# HTTP calls in body_preview
_HTTP_CALL = re.compile(
    r"(?:axios|fetch|requests|http|HttpClient|got|superagent)"
    r"[\.\(]+\s*['\"]([^'\"]+)['\"]",
    re.IGNORECASE,
)
_HTTP_METHOD = re.compile(
    r"(?:axios|requests|http)\s*\.\s*(get|post|put|patch|delete)\s*\(",
    re.IGNORECASE,
)

# Flask/FastAPI/Express route decorators
_FLASK_ROUTE  = re.compile(r"""@(?:app|bp|router)\.(?:route|get|post|put|patch|delete)\s*\(\s*['"]([^'"]+)['"]""", re.I)
_FASTAPI_ROUTE= re.compile(r"""@(?:app|router)\.(?:get|post|put|patch|delete)\s*\(\s*['"]([^'"]+)['"]""", re.I)
_EXPRESS_ROUTE= re.compile(r"""(?:app|router)\.(?:get|post|put|patch|delete|use)\s*\(\s*['"]([^'"]+)['"]""", re.I)

# Spark patterns
_SPARK_READ   = re.compile(r"(?:spark|sc|ss)\.read\.\w+\s*\(", re.I)
_SPARK_WRITE  = re.compile(r"\.write\.\w+\s*\(", re.I)
_DF_VAR       = re.compile(r"(\w+_df|\w+_data|df_\w+)\s*=", re.I)

# React component detection (PascalCase name + JSX/function return)
_REACT_COMP   = re.compile(r"^[A-Z][a-zA-Z0-9]+$")
_JSX_TAG      = re.compile(r"<([A-Z][a-zA-Z0-9]*)\s*/?>", re.I)

# Class inheritance patterns
_EXTENDS_RE   = re.compile(r"(?:class|extends)\s+(\w+)\s*(?:extends|implements)\s+([\w, ]+)")
_JAVA_EXT     = re.compile(r"class\s+\w+\s+extends\s+(\w+)")
_JAVA_IMPL    = re.compile(r"class\s+\w+\s+(?:extends\s+\w+\s+)?implements\s+([\w, ]+)")
_TS_EXTENDS   = re.compile(r"(?:class|interface)\s+\w+\s+extends\s+([\w, ]+)")
_TS_IMPLEMENTS= re.compile(r"class\s+\w+\s+(?:extends\s+\w+\s+)?implements\s+([\w, ]+)")

# Spring / Angular annotations
_SPRING_ANNOT = re.compile(r"@(Service|Repository|Controller|RestController|Component"
                             r"|Injectable|Entity|Configuration|Bean)", re.I)

# common non-table SQL keywords to skip
_SQL_KEYWORDS = frozenset({
    "SELECT","WHERE","AND","OR","NOT","IN","ON","AS","SET","ALL","DISTINCT",
    "GROUP","ORDER","BY","HAVING","LIMIT","OFFSET","UNION","EXCEPT","INTERSECT",
    "CASE","WHEN","THEN","ELSE","END","NULL","EXISTS","COUNT","SUM","AVG",
    "MAX","MIN","COALESCE","CURRENT_DATE","CURRENT_TIMESTAMP","INTERVAL",
    "PRIMARY","KEY","UNIQUE","INDEX","CONSTRAINT","DEFAULT","REFERENCES",
    "IF","NOT","WITH","VALUES","INTO", "TRUE","FALSE","IS","LIKE","BETWEEN",
})


# ══════════════════════════════════════════════════════════════
#  RULE 1 — STRUCTURAL: FILE → CONTAINS → SYMBOL
# ══════════════════════════════════════════════════════════════

STRUCTURAL_CATEGORIES = {
    "CLASS", "INTERFACE", "ENUM",
    "FUNCTION", "ASYNC_DEF", "METHOD", "CONSTRUCTOR",
    "SQL_QUERY", "SQL_DDL", "SQL_DML",
    "API_CALL", "HOOK", "JSX_ELEMENT",
    "VARIABLE", "CONSTANT", "ASSIGNMENT", "PROPERTY",
    "DECORATOR", "ANNOTATION",
}

def rule_structural_contains(project, graph: DependencyGraph):
    """
    FILE --[CONTAINS]--> every top-level structural symbol.
    FILE --[DEFINES]-->  classes, functions, interfaces (primary definitions).
    """
    # Pre-index nodes by (name, file_path) to handle promoted node types
    nodes_by_name_file = {}
    for node in graph.nodes.values():
        nodes_by_name_file[(node.name, node.file_path)] = node.id
        
    for fr in project.files:
        file_id = make_node_id(NodeType.FILE, fr.rel_path)
        if file_id not in graph.nodes:
            continue
        for sym in fr.symbols:
            if sym.category not in STRUCTURAL_CATEGORIES:
                continue
            
            sym_id = nodes_by_name_file.get((sym.name, fr.rel_path))
            if not sym_id:
                continue

            graph.safe_add_edge(file_id, sym_id,
                RelationType.CONTAINS,
                evidence=f"{fr.rel_path} contains {sym.category} '{sym.name}'")

            # DEFINES for primary structural definitions
            if sym.category in {"CLASS", "INTERFACE", "ENUM",
                                 "FUNCTION", "ASYNC_DEF"}:
                graph.safe_add_edge(file_id, sym_id,
                    RelationType.DEFINES,
                    evidence=f"{fr.rel_path} defines {sym.category} '{sym.name}'")

        # CLASS → CONTAINS → METHOD
        class_ids_by_name = {s.name: nodes_by_name_file.get((s.name, fr.rel_path))
                             for s in fr.symbols if s.category in {"CLASS","INTERFACE"}
                             and nodes_by_name_file.get((s.name, fr.rel_path))}
                             
        for sym in fr.symbols:
            if sym.category in {"METHOD","CONSTRUCTOR","PROPERTY","ASSIGNMENT","VARIABLE"} and sym.parent:
                class_id = class_ids_by_name.get(sym.parent)
                sym_id   = nodes_by_name_file.get((sym.name, fr.rel_path))
                if class_id and sym_id:
                    graph.safe_add_edge(class_id, sym_id,
                        RelationType.CONTAINS,
                        evidence=f"class '{sym.parent}' contains member '{sym.name}'")
                    graph.safe_add_edge(class_id, sym_id,
                        RelationType.DEFINES,
                        evidence=f"class '{sym.parent}' defines member '{sym.name}'")


# ══════════════════════════════════════════════════════════════
#  RULE 2 — IMPORT LINKS  (promote Component 2 imports)
# ══════════════════════════════════════════════════════════════

def rule_import_links(project, graph: DependencyGraph):
    """
    Promote Component 2 IMPORT dependencies into graph edges.
    FILE --[IMPORTS]--> FILE
    """
    for dep in project.dependencies:
        if dep.dep_type != "IMPORT":
            continue
        src_id = make_node_id(NodeType.FILE, dep.source)
        tgt_id = make_node_id(NodeType.FILE, dep.target)
        graph.safe_add_edge(src_id, tgt_id,
            RelationType.IMPORTS,
            confidence=dep.confidence,
            evidence=dep.evidence or f"{dep.source} imports from {dep.target}")


# ══════════════════════════════════════════════════════════════
#  RULE 3 — CALL GRAPH  (FUNCTION → CALLS → FUNCTION)
# ══════════════════════════════════════════════════════════════

def rule_call_graph(project, graph: DependencyGraph):
    """
    FUNCTION/METHOD --[CALLS]--> FUNCTION/METHOD
    Uses Component 2 FUNCTION_CALL dependencies + symbol index.
    """
    # Map canonical name → set of node IDs that define that symbol
    canon_to_ids: dict = {}
    for sym_idx in project.symbol_index:
        for file_path in sym_idx.defined_in:
            n_type = _category_to_nodetype(sym_idx.category)
            node_id = make_node_id(n_type, sym_idx.originals[0] if sym_idx.originals else sym_idx.canonical, file_path)
            if node_id in graph.nodes:
                canon_to_ids.setdefault(sym_idx.canonical, set()).add(node_id)

    # Use Component 2 FUNCTION_CALL edges
    for dep in project.dependencies:
        if dep.dep_type not in {"FUNCTION_CALL", "INVOKES"}:
            continue
        fr_src = project.file_by_rel.get(dep.source)
        fr_tgt = project.file_by_rel.get(dep.target)
        if not fr_src or not fr_tgt:
            continue

        # Find the caller node (best match by file)
        caller_id = _find_best_function_node(graph, dep.source, dep.source_symbol or "")
        callee_id = _find_best_function_node(graph, dep.target, dep.target_symbol or "")

        if caller_id and callee_id:
            graph.safe_add_edge(caller_id, callee_id,
                RelationType.CALLS,
                confidence=dep.confidence,
                evidence=dep.evidence or f"'{dep.source_symbol}' calls '{dep.target_symbol}'")
        elif caller_id:
            # At least emit FILE→CALLS→FILE
            src_file_id = make_node_id(NodeType.FILE, dep.source)
            tgt_file_id = make_node_id(NodeType.FILE, dep.target)
            graph.safe_add_edge(src_file_id, tgt_file_id,
                RelationType.DEPENDS_ON,
                confidence=dep.confidence,
                evidence=dep.evidence)

    # Intra-file: scan body_preview for function call patterns
    for fr in project.files:
        local_funcs = {s.name: make_node_id(s.category, s.name, fr.rel_path)
                       for s in fr.symbols
                       if s.category in {"FUNCTION","ASYNC_DEF","METHOD"}}
        for sym in fr.symbols:
            if sym.category not in {"FUNCTION", "ASYNC_DEF", "METHOD"}:
                continue
            bp = sym.body_preview or ""
            caller_id = make_node_id(sym.category, sym.name, fr.rel_path)
            if caller_id not in graph.nodes:
                continue
            for fname, callee_id in local_funcs.items():
                if fname == sym.name:
                    continue
                # Simple name-in-body check
                if re.search(r"\b" + re.escape(fname) + r"\s*\(", bp):
                    if callee_id in graph.nodes:
                        graph.safe_add_edge(caller_id, callee_id,
                            RelationType.CALLS,
                            confidence="medium",
                            evidence=f"'{sym.name}' body references '{fname}'")


def _find_best_function_node(graph: DependencyGraph, file_path: str, name: str) -> str | None:
    if not name:
        return None
    for ntype in ("FUNCTION","ASYNC_DEF","METHOD","ASYNC_FUNCTION"):
        nid = make_node_id(ntype, name, file_path)
        if nid in graph.nodes:
            return nid
    return None


def _category_to_nodetype(cat: str) -> str:
    return {
        "FUNCTION":  NodeType.FUNCTION,
        "ASYNC_DEF": NodeType.ASYNC_FUNCTION,
        "METHOD":    NodeType.METHOD,
        "CLASS":     NodeType.CLASS,
        "INTERFACE": NodeType.INTERFACE,
        "ENUM":      NodeType.ENUM,
    }.get(cat, NodeType.FUNCTION)


# ══════════════════════════════════════════════════════════════
#  RULE 4 — CLASS HIERARCHY  (EXTENDS / IMPLEMENTS)
# ══════════════════════════════════════════════════════════════

def rule_class_hierarchy(project, graph: DependencyGraph):
    """
    CLASS --[EXTENDS]--> CLASS
    CLASS --[IMPLEMENTS]--> INTERFACE
    Detected from body_preview and decorators.
    """
    # Build name → node_id index for classes and interfaces
    class_name_idx: dict = {}
    for nid, node in graph.nodes.items():
        if node.node_type in {NodeType.CLASS, NodeType.INTERFACE}:
            class_name_idx[node.name] = nid
            class_name_idx[node.name.lower()] = nid

    for fr in project.files:
        for sym in fr.symbols:
            if sym.category not in {"CLASS", "INTERFACE"}:
                continue
            bp = sym.body_preview or ""
            sym_id = make_node_id(sym.category, sym.name, fr.rel_path)
            if sym_id not in graph.nodes:
                continue

            # Java extends
            for m in _JAVA_EXT.finditer(bp):
                parent_cls = m.group(1)
                target_id  = class_name_idx.get(parent_cls)
                if target_id and target_id != sym_id:
                    graph.safe_add_edge(sym_id, target_id,
                        RelationType.EXTENDS,
                        evidence=f"'{sym.name}' extends '{parent_cls}'")

            # Java implements
            for m in _JAVA_IMPL.finditer(bp):
                for iface in m.group(1).split(","):
                    iface = iface.strip()
                    target_id = class_name_idx.get(iface)
                    if target_id and target_id != sym_id:
                        graph.safe_add_edge(sym_id, target_id,
                            RelationType.IMPLEMENTS,
                            evidence=f"'{sym.name}' implements '{iface}'")

            # TypeScript extends
            for m in _TS_EXTENDS.finditer(bp):
                for parent in m.group(1).split(","):
                    parent = parent.strip()
                    target_id = class_name_idx.get(parent)
                    if target_id and target_id != sym_id:
                        graph.safe_add_edge(sym_id, target_id,
                            RelationType.EXTENDS,
                            evidence=f"TS '{sym.name}' extends '{parent}'")


# ══════════════════════════════════════════════════════════════
#  RULE 5 — SQL LINEAGE
# ══════════════════════════════════════════════════════════════

def rule_sql_lineage(project, graph: DependencyGraph):
    """
    FUNCTION/METHOD --[QUERIES_TABLE]--> SQL_TABLE  (SELECT/WITH)
    FUNCTION/METHOD --[WRITES_TABLE]-->  SQL_TABLE  (INSERT/UPDATE)
    SQL_DDL         --[CREATES_TABLE]--> SQL_TABLE
    """
    # Build SQL table name → node_id index
    table_idx: dict = {}
    for nid, node in graph.nodes.items():
        if node.node_type == NodeType.SQL_TABLE:
            table_idx[node.name.upper()] = nid

    if not table_idx:
        return

    for fr in project.files:
        for sym in fr.symbols:
            bp = (sym.body_preview or "").upper()
            if not bp:
                continue
            sym_id = make_node_id(sym.category, sym.name, fr.rel_path)
            if sym_id not in graph.nodes:
                # Fall back to file node
                sym_id = make_node_id(NodeType.FILE, fr.rel_path)

            # SELECT / FROM references
            for m in _SQL_FROM.finditer(bp):
                tname = m.group(1).upper()
                if tname in _SQL_KEYWORDS:
                    continue
                if tname in table_idx:
                    graph.safe_add_edge(sym_id, table_idx[tname],
                        RelationType.QUERIES_TABLE,
                        evidence=f"'{sym.name}' queries table '{tname}'")

            # JOIN references
            for m in _SQL_JOIN.finditer(bp):
                tname = m.group(1).upper()
                if tname in _SQL_KEYWORDS or tname not in table_idx:
                    continue
                graph.safe_add_edge(sym_id, table_idx[tname],
                    RelationType.QUERIES_TABLE,
                    evidence=f"'{sym.name}' joins table '{tname}'")

            # INSERT INTO / UPDATE
            for m in list(_SQL_INTO.finditer(bp)) + list(_SQL_UPDATE.finditer(bp)):
                tname = m.group(1).upper()
                if tname in _SQL_KEYWORDS or tname not in table_idx:
                    continue
                graph.safe_add_edge(sym_id, table_idx[tname],
                    RelationType.WRITES_TABLE,
                    evidence=f"'{sym.name}' writes table '{tname}'")

            # CREATE TABLE
            for m in _SQL_CREATE.finditer(bp):
                tname = m.group(1).upper()
                if tname in table_idx:
                    graph.safe_add_edge(sym_id, table_idx[tname],
                        RelationType.CREATES_TABLE,
                        evidence=f"DDL creates table '{tname}'")

    # Also: C2 sql_use deps
    for dep in project.dependencies:
        if dep.dep_type != "SQL_USE":
            continue
        src_id = make_node_id(NodeType.FILE, dep.source)
        tname  = (dep.target_symbol or "").upper()
        if tname in table_idx and src_id in graph.nodes:
            graph.safe_add_edge(src_id, table_idx[tname],
                RelationType.QUERIES_TABLE,
                confidence=dep.confidence,
                evidence=dep.evidence)


# ══════════════════════════════════════════════════════════════
#  RULE 6 — REACT / FRONTEND
# ══════════════════════════════════════════════════════════════

def rule_react_relationships(project, graph: DependencyGraph):
    """
    REACT_COMPONENT --[USES_HOOK]--> REACT_HOOK
    REACT_COMPONENT --[RENDERS]--> REACT_COMPONENT
    REACT_COMPONENT --[CALLS_API]--> API_ENDPOINT
    """
    # Build component and hook indexes
    comp_idx:  dict = {}
    hook_idx:  dict = {}
    api_idx:   dict = {}

    for nid, node in graph.nodes.items():
        if node.node_type == NodeType.REACT_COMPONENT:
            comp_idx[node.name] = nid
        elif node.node_type == NodeType.REACT_HOOK:
            hook_idx[node.name] = nid
        elif node.node_type == NodeType.API_ENDPOINT:
            api_idx[node.name] = nid  # name is the URL pattern

    for fr in project.files:
        if fr.language not in {"javascript", "typescript", "tsx"}:
            continue

        # Hook usage: look at HOOK symbols
        for sym in fr.symbols:
            if sym.category == "HOOK":
                comp_id = _find_parent_component(fr, sym, graph)
                hook_id = hook_idx.get(sym.name) or make_node_id(NodeType.REACT_HOOK, sym.name, "")
                if comp_id and hook_id in graph.nodes:
                    graph.safe_add_edge(comp_id, hook_id,
                        RelationType.USES_HOOK,
                        evidence=f"component uses hook '{sym.name}'")

        # JSX renders: look at JSX_ELEMENT symbols
        for sym in fr.symbols:
            if sym.category == "JSX_ELEMENT":
                comp_id = _find_parent_component(fr, sym, graph)
                rendered_comp = comp_idx.get(sym.name)
                if comp_id and rendered_comp and comp_id != rendered_comp:
                    graph.safe_add_edge(comp_id, rendered_comp,
                        RelationType.RENDERS,
                        evidence=f"component renders <{sym.name} />")

        # API calls: look at API_CALL symbols + body_previews
        for sym in fr.symbols:
            if sym.category == "API_CALL":
                comp_id = _find_parent_component(fr, sym, graph) or \
                          make_node_id(NodeType.FILE, fr.rel_path)
                if comp_id not in graph.nodes:
                    continue
                # Try to match URL
                bp = sym.body_preview or sym.name or ""
                for m in _HTTP_CALL.finditer(bp):
                    url = m.group(1)
                    matched_api = _match_url(url, api_idx)
                    if matched_api:
                        graph.safe_add_edge(comp_id, matched_api,
                            RelationType.CALLS_API,
                            confidence="medium",
                            evidence=f"calls API '{url}'")
                    else:
                        # Create a virtual API endpoint node and edge
                        ep_id = make_node_id(NodeType.API_ENDPOINT, url)
                        if ep_id not in graph.nodes:
                            graph.add_node(GraphNode(
                                id=ep_id,
                                node_type=NodeType.API_ENDPOINT,
                                name=url, language="http",
                            ))
                        graph.safe_add_edge(comp_id, ep_id,
                            RelationType.CALLS_API,
                            confidence="medium",
                            evidence=f"HTTP call to '{url}'")


def _find_parent_component(fr, sym, graph: DependencyGraph) -> str | None:
    """Find the React component node ID that owns a given symbol."""
    # If sym has a parent, look for a component with that name
    if sym.parent:
        cid = make_node_id(NodeType.REACT_COMPONENT, sym.parent, fr.rel_path)
        if cid in graph.nodes:
            return cid
        # Try class
        cid2 = make_node_id(NodeType.CLASS, sym.parent, fr.rel_path)
        if cid2 in graph.nodes:
            return cid2
    # Fall back to the file node
    return make_node_id(NodeType.FILE, fr.rel_path)


def _match_url(url: str, api_idx: dict) -> str | None:
    """Try to find the best matching API endpoint node ID for a URL."""
    url = url.rstrip("/")
    for pattern, nid in api_idx.items():
        p = pattern.rstrip("/")
        if url == p or url.startswith(p) or p.startswith(url):
            return nid
    return None


# ══════════════════════════════════════════════════════════════
#  RULE 7 — SPARK / DATA PIPELINE
# ══════════════════════════════════════════════════════════════

def rule_spark_pipeline(project, graph: DependencyGraph):
    """
    SPARK_JOB --[READS_FROM]-->  DATAFRAME
    SPARK_JOB --[WRITES_TO]-->   DATAFRAME
    FILE      --[DEPENDS_ON]-->  FILE  (for Spark-heavy files)
    """
    for fr in project.files:
        if fr.language != "python":
            continue

        for sym in fr.symbols:
            bp = sym.body_preview or ""
            if not (_SPARK_READ.search(bp) or _SPARK_WRITE.search(bp)):
                continue

            spark_id = make_node_id(NodeType.SPARK_JOB, sym.name, fr.rel_path)
            if spark_id not in graph.nodes:
                # Promote this function to a SPARK_JOB
                existing = graph.nodes.get(make_node_id(sym.category, sym.name, fr.rel_path))
                if existing:
                    spark_id = existing.id
                else:
                    continue

            # Find dataframe variables in body
            for m in _DF_VAR.finditer(bp):
                df_name = m.group(1)
                df_id   = make_node_id(NodeType.DATAFRAME, df_name, fr.rel_path)
                if df_id not in graph.nodes:
                    graph.add_node(GraphNode(
                        id=df_id, node_type=NodeType.DATAFRAME,
                        name=df_name, language="python",
                        file_path=fr.rel_path,
                    ))
                rel = RelationType.WRITES_TO if _SPARK_WRITE.search(bp) else RelationType.READS_FROM
                graph.safe_add_edge(spark_id, df_id, rel,
                    evidence=f"Spark job '{sym.name}' {'writes to' if rel == RelationType.WRITES_TO else 'reads from'} dataframe '{df_name}'")


# ══════════════════════════════════════════════════════════════
#  RULE 8 — API ENDPOINTS  (route definitions)
# ══════════════════════════════════════════════════════════════

def rule_api_endpoints(project, graph: DependencyGraph):
    """
    Scan decorators and body_previews for route definitions.
    Creates API_ENDPOINT nodes and links them to handler functions.
    FUNCTION --[DEFINES_ROUTE]--> API_ENDPOINT
    """
    # 1. Regex approach on bodies/names
    for fr in project.files:
        for sym in fr.symbols:
            bp   = sym.body_preview or ""
            name = sym.name or ""

            urls = []
            for pattern in (_FLASK_ROUTE, _FASTAPI_ROUTE, _EXPRESS_ROUTE):
                for m in pattern.finditer(bp + " " + name):
                    urls.append(m.group(1))

            for url in urls:
                ep_id = make_node_id(NodeType.API_ENDPOINT, url)
                if ep_id not in graph.nodes:
                    graph.add_node(GraphNode(
                        id=ep_id, node_type=NodeType.API_ENDPOINT,
                        name=url, language=fr.language,
                        file_path=fr.rel_path,
                    ))
                handler_id = make_node_id(sym.category, sym.name, fr.rel_path)
                if handler_id in graph.nodes:
                    graph.safe_add_edge(handler_id, ep_id,
                        RelationType.DEFINES,
                        evidence=f"function '{sym.name}' handles route '{url}'")

    # 2. Extract from DECORATOR nodes structurally
    decorators = [n for n in graph.nodes.values() if n.node_type == NodeType.DECORATOR]
    functions = [n for n in graph.nodes.values() if n.node_type in (NodeType.FUNCTION, NodeType.METHOD, NodeType.ASYNC_FUNCTION)]
    
    from collections import defaultdict
    funcs_by_file = defaultdict(list)
    for f in functions:
        funcs_by_file[f.file_path].append(f)
        
    for dec in decorators:
        dec_lower = dec.name.lower()
        if any(v in dec_lower for v in ("get", "post", "put", "patch", "delete", "route", "mapping")):
            file_funcs = funcs_by_file.get(dec.file_path, [])
            subsequent_funcs = [f for f in file_funcs if f.start_line >= dec.start_line]
            if subsequent_funcs:
                target_func = min(subsequent_funcs, key=lambda f: f.start_line)
                url = f"/{target_func.name.replace('_', '-')}"
                ep_id = make_node_id(NodeType.API_ENDPOINT, url)
                if ep_id not in graph.nodes:
                    graph.add_node(GraphNode(
                        id=ep_id, node_type=NodeType.API_ENDPOINT,
                        name=url, language=dec.language,
                        file_path=dec.file_path,
                    ))
                
                graph.safe_add_edge(target_func.id, ep_id,
                    RelationType.DEFINES,
                    evidence=f"function '{target_func.name}' handles inferred route '{url}'")
                
                file_id = make_node_id(NodeType.FILE, dec.file_path)
                graph.safe_add_edge(file_id, ep_id, RelationType.DEFINES)


# ══════════════════════════════════════════════════════════════
#  RULE 9 — ANNOTATION / SERVICE DETECTION
# ══════════════════════════════════════════════════════════════

def rule_annotations(project, graph: DependencyGraph):
    """
    CLASS --[ANNOTATED_BY]--> SERVICE/REPOSITORY/CONTROLLER
    Spring, Angular, and similar annotation-driven frameworks.
    """
    annot_node_cache: dict = {}

    for fr in project.files:
        for sym in fr.symbols:
            if sym.category not in {"CLASS", "INTERFACE"}:
                continue
            sym_id = make_node_id(sym.category, sym.name, fr.rel_path)
            if sym_id not in graph.nodes:
                continue

            all_annots = sym.decorators + sym.modifiers
            for annot_text in all_annots:
                m = _SPRING_ANNOT.search(annot_text)
                if not m:
                    continue
                annot_name = m.group(1)
                ann_id = annot_node_cache.get(annot_name)
                if not ann_id:
                    ann_id = make_node_id(NodeType.SERVICE, annot_name)
                    if ann_id not in graph.nodes:
                        graph.add_node(GraphNode(
                            id=ann_id, node_type=NodeType.SERVICE,
                            name=annot_name, language="annotation",
                        ))
                    annot_node_cache[annot_name] = ann_id

                graph.safe_add_edge(sym_id, ann_id,
                    RelationType.ANNOTATED_BY,
                    evidence=f"'{sym.name}' annotated with @{annot_name}")


# ══════════════════════════════════════════════════════════════
#  RULE 10 — PROMOTE ALL C2 DEPENDENCIES
# ══════════════════════════════════════════════════════════════

_C2_TYPE_TO_RELATION = {
    "IMPORT":         RelationType.IMPORTS,
    "EXPORT_USE":     RelationType.DEPENDS_ON,
    "API_CALL":       RelationType.CALLS_API,
    "FUNCTION_CALL":  RelationType.CALLS,
    "SQL_USE":        RelationType.QUERIES_TABLE,
    "MODULE_USE":     RelationType.DEPENDS_ON,
    "CLASS_USE":      RelationType.REFERENCES,
}

def rule_promote_c2_deps(project, graph: DependencyGraph):
    """
    Promote remaining Component 2 dependency edges that aren't
    already handled by more specific rules.
    These become FILE → DEPENDS_ON/CALLS/etc → FILE edges.
    """
    for dep in project.dependencies:
        relation = _C2_TYPE_TO_RELATION.get(dep.dep_type, RelationType.DEPENDS_ON)
        if relation == RelationType.IMPORTS:
            continue    # already handled by rule_import_links

        src_id = make_node_id(NodeType.FILE, dep.source)
        tgt_id = make_node_id(NodeType.FILE, dep.target)

        if src_id in graph.nodes and tgt_id in graph.nodes:
            graph.safe_add_edge(src_id, tgt_id,
                relation,
                confidence=dep.confidence,
                evidence=dep.evidence or f"{dep.dep_type}: {dep.source} → {dep.target}")


# ══════════════════════════════════════════════════════════════
#  RULE REGISTRY
# ══════════════════════════════════════════════════════════════

RULES: List[Callable] = [
    rule_structural_contains,    # must be first (establishes CONTAINS/DEFINES)
    rule_import_links,
    rule_promote_c2_deps,
    rule_call_graph,
    rule_class_hierarchy,
    rule_sql_lineage,
    rule_api_endpoints,
    rule_react_relationships,
    rule_spark_pipeline,
    rule_annotations,
]
