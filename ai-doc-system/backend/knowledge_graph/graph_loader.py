"""
knowledge_graph/graph_loader.py
────────────────────────────────────────────────────────────────
Streaming XML parser for graph_dependencies.xml (Component 3 output).

Uses iterparse for memory-efficient loading — critical for
million-node enterprise graphs.

Usage:
    loader = GraphXMLLoader()
    kg = loader.load("outputs/graph_dependencies.xml")
    print(kg.node_count, kg.edge_count)
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from .models import KGNode, KGEdge, KnowledgeGraph

try:
    from lxml import etree as ET
    _LXML = True
except ImportError:
    import xml.etree.ElementTree as ET
    _LXML = False


# ──────────────────────────────────────────────────────────────
#  Attribute helpers
# ──────────────────────────────────────────────────────────────

def _a(el, key: str, default: str = "") -> str:
    """Get string attribute with fallback."""
    return (el.get(key) or "").strip() or default


def _i(el, key: str, default: int = 0) -> int:
    """Get integer attribute with fallback."""
    try:
        return int(el.get(key, default))
    except (TypeError, ValueError):
        return default


def _b(el, key: str) -> bool:
    """Get boolean attribute."""
    return el.get(key, "").lower() in ("true", "1", "yes")


def _child_texts(el, tag: str) -> List[str]:
    """Collect text from child elements."""
    return [c.text.strip() for c in el.findall(f".//{tag}") if c.text]


# ──────────────────────────────────────────────────────────────
#  Node parser
# ──────────────────────────────────────────────────────────────

def _parse_node(el) -> KGNode:
    """Parse a <Node> XML element into a KGNode."""
    # Child element text
    docstring = None
    body_preview = None
    params: List[str] = []
    annotations: List[str] = []
    modifiers: List[str] = []

    ds_el = el.find("DocString")
    if ds_el is not None and ds_el.text:
        docstring = ds_el.text.strip()

    bp_el = el.find("BodyPreview")
    if bp_el is not None and bp_el.text:
        body_preview = bp_el.text.strip()

    params_el = el.find("Parameters")
    if params_el is not None:
        params = [p.text.strip() for p in params_el.findall("Param") if p.text]

    ann_el = el.find("Annotations")
    if ann_el is not None:
        annotations = [a.text.strip() for a in ann_el.findall("Ann") if a.text]

    mod_el = el.find("Modifiers")
    if mod_el is not None:
        modifiers = [m.text.strip() for m in mod_el.findall("Mod") if m.text]

    return KGNode(
        id=_a(el, "id"),
        node_type=_a(el, "type"),
        name=_a(el, "name"),
        language=_a(el, "language"),
        file_path=_a(el, "file_path"),
        start_line=_i(el, "start_line"),
        end_line=_i(el, "end_line"),
        is_async=_b(el, "is_async"),
        is_exported=_b(el, "is_exported"),
        in_degree=_i(el, "in_degree"),
        out_degree=_i(el, "out_degree"),
        parent_id=el.get("parent_id"),
        return_type=el.get("return_type"),
        docstring=docstring,
        body_preview=body_preview,
        params=params,
        annotations=annotations,
        modifiers=modifiers,
    )


# ──────────────────────────────────────────────────────────────
#  Edge parser
# ──────────────────────────────────────────────────────────────

def _parse_edge(el) -> KGEdge:
    """Parse an <Edge> XML element into a KGEdge."""
    line = el.get("line")
    return KGEdge(
        from_id=_a(el, "from"),
        to_id=_a(el, "to"),
        relation=_a(el, "relation"),
        weight=float(el.get("weight", "1.0")),
        confidence=_a(el, "confidence", "high"),
        evidence=el.get("evidence"),
        line_number=int(line) if line else None,
    )


# ──────────────────────────────────────────────────────────────
#  Metadata parser
# ──────────────────────────────────────────────────────────────

def _parse_metadata(meta_el) -> Dict:
    """Parse <Metadata> section for validation."""
    metadata: Dict = {
        "node_type_counts": {},
        "relation_counts": {},
        "errors": [],
    }

    ntc = meta_el.find("NodeTypeCounts")
    if ntc is not None:
        for t in ntc.findall("Type"):
            metadata["node_type_counts"][_a(t, "name")] = _i(t, "count")

    rc = meta_el.find("RelationCounts")
    if rc is not None:
        for r in rc.findall("Relation"):
            metadata["relation_counts"][_a(r, "name")] = _i(r, "count")

    err_el = meta_el.find("Errors")
    if err_el is not None:
        for e in err_el.findall("Error"):
            if e.text:
                metadata["errors"].append(e.text.strip())

    return metadata


# ══════════════════════════════════════════════════════════════
#  MAIN LOADER
# ══════════════════════════════════════════════════════════════

class GraphXMLLoader:
    """
    Streaming XML loader for graph_dependencies.xml.

    Uses iterparse for memory efficiency with large graphs.
    Falls back to full-tree parse for lxml child-element access.

    Usage:
        loader = GraphXMLLoader(verbose=True)
        kg = loader.load("graph_dependencies.xml")
    """

    def __init__(self, verbose: bool = True):
        self.verbose = verbose

    def load(
        self,
        xml_path: str,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
    ) -> KnowledgeGraph:
        """
        Load graph_dependencies.xml into a KnowledgeGraph.

        Args:
            xml_path:          Path to graph_dependencies.xml
            progress_callback: Optional fn(phase, current, total)

        Returns:
            Fully loaded KnowledgeGraph with adjacency indexes built.
        """
        if not os.path.isfile(xml_path):
            raise FileNotFoundError(f"Graph XML not found: {xml_path}")

        file_size = Path(xml_path).stat().st_size
        self._log(f"[loader] Loading {xml_path}  ({file_size / 1024 / 1024:.1f} MB)")

        t0 = time.time()

        # Parse the full tree — needed for child element access
        # within <Node> elements (DocString, Parameters, etc.)
        if _LXML:
            tree = ET.parse(xml_path)
            root = tree.getroot()
        else:
            tree = ET.parse(xml_path)
            root = tree.getroot()

        # Graph name from root attributes
        name = _a(root, "name", Path(xml_path).stem)
        expected_nodes = _i(root, "nodes")
        expected_edges = _i(root, "edges")

        kg = KnowledgeGraph(name=name, source=xml_path)

        # ── Parse metadata ───────────────────────────────────
        metadata: Dict = {}
        meta_el = root.find("Metadata")
        if meta_el is not None:
            metadata = _parse_metadata(meta_el)
            if metadata.get("errors"):
                kg.errors.extend(metadata["errors"])

        self._log(f"[loader] Expected: {expected_nodes} nodes, {expected_edges} edges")

        # ── Parse nodes ──────────────────────────────────────
        nodes_el = root.find("Nodes")
        node_count = 0
        if nodes_el is not None:
            for node_el in nodes_el.findall("Node"):
                node = _parse_node(node_el)
                if node.id:
                    # Reset degrees — we'll recount from edges
                    node.in_degree = 0
                    node.out_degree = 0
                    kg.nodes[node.id] = node
                    node_count += 1

                    if progress_callback and node_count % 5000 == 0:
                        progress_callback("nodes", node_count, expected_nodes)

        self._log(f"[loader] Loaded {node_count} nodes")

        # ── Parse edges ──────────────────────────────────────
        edges_el = root.find("Edges")
        edge_count = 0
        skipped = 0
        if edges_el is not None:
            for edge_el in edges_el.findall("Edge"):
                edge = _parse_edge(edge_el)
                if edge.from_id and edge.to_id:
                    if kg.add_edge(edge):
                        edge_count += 1
                    else:
                        skipped += 1

                    if progress_callback and (edge_count + skipped) % 5000 == 0:
                        progress_callback("edges", edge_count, expected_edges)

        elapsed = time.time() - t0
        self._log(f"[loader] Loaded {edge_count} edges  (skipped {skipped} dangling)")
        self._log(f"[loader] Total: {kg.node_count} nodes, {kg.edge_count} edges  ({elapsed:.2f}s)")

        # ── Validation ───────────────────────────────────────
        if expected_nodes and abs(kg.node_count - expected_nodes) > expected_nodes * 0.01:
            kg.errors.append(
                f"Node count mismatch: expected {expected_nodes}, loaded {kg.node_count}"
            )
        if expected_edges and abs(kg.edge_count - expected_edges) > expected_edges * 0.05:
            # Edge count may differ slightly due to dangling refs
            kg.errors.append(
                f"Edge count mismatch: expected {expected_edges}, loaded {kg.edge_count} "
                f"(skipped {skipped})"
            )

        # Store metadata for downstream consumers
        kg._metadata = metadata  # type: ignore

        return kg

    def load_streaming(
        self,
        xml_path: str,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
    ) -> KnowledgeGraph:
        """
        Memory-efficient streaming loader using iterparse.

        NOTE: This mode does NOT parse child elements of <Node>
        (DocString, Parameters, etc.) — only attributes.
        Use `load()` for full fidelity.
        Use this for million-node graphs where memory is critical.
        """
        if not os.path.isfile(xml_path):
            raise FileNotFoundError(f"Graph XML not found: {xml_path}")

        file_size = Path(xml_path).stat().st_size
        self._log(f"[loader] Streaming load: {xml_path}  ({file_size / 1024 / 1024:.1f} MB)")

        t0 = time.time()
        kg = KnowledgeGraph(name=Path(xml_path).stem, source=xml_path)

        node_count = 0
        edge_count = 0
        skipped = 0

        # iterparse: process Node and Edge elements as they are read
        context = ET.iterparse(xml_path, events=("end",))
        for event, el in context:
            tag = el.tag if isinstance(el.tag, str) else ""

            if tag == "DependencyGraph":
                kg.name = _a(el, "name", kg.name)

            elif tag == "Node":
                node = KGNode(
                    id=_a(el, "id"),
                    node_type=_a(el, "type"),
                    name=_a(el, "name"),
                    language=_a(el, "language"),
                    file_path=_a(el, "file_path"),
                    start_line=_i(el, "start_line"),
                    end_line=_i(el, "end_line"),
                    is_async=_b(el, "is_async"),
                    is_exported=_b(el, "is_exported"),
                    parent_id=el.get("parent_id"),
                    return_type=el.get("return_type"),
                )
                if node.id:
                    kg.nodes[node.id] = node
                    node_count += 1
                el.clear()  # free memory

            elif tag == "Edge":
                edge = _parse_edge(el)
                if edge.from_id and edge.to_id:
                    if kg.add_edge(edge):
                        edge_count += 1
                    else:
                        skipped += 1
                el.clear()

        elapsed = time.time() - t0
        self._log(f"[loader] Stream: {node_count} nodes, {edge_count} edges  "
                   f"(skipped {skipped})  ({elapsed:.2f}s)")

        return kg

    def _log(self, msg: str):
        if self.verbose:
            print(msg, flush=True)
