"""
dependency_extractor/exporter.py
────────────────────────────────────────────────────────────────
Exports DependencyGraph → graph_dependencies.xml

XML Schema:
──────────
<DependencyGraph name="…" nodes="…" edges="…" generated_at="…">

  <Metadata>
    <NodeTypeCounts>  <Type name="FILE" count="5"/> … </NodeTypeCounts>
    <RelationCounts>  <Relation name="CONTAINS" count="42"/> … </RelationCounts>
  </Metadata>

  <Nodes>
    <Node
        id="file__app_py"
        type="FILE"
        name="app.py"
        language="python"
        file_path="app.py"
        start_line="0"
        end_line="0"
        is_async="false"
        is_exported="false"
        in_degree="3"
        out_degree="7"
    >
      <DocString>…</DocString>        <!-- optional -->
      <Parameters><Param>x</Param></Parameters>
      <ReturnType>str</ReturnType>
      <Annotations><Ann>Service</Ann></Annotations>
      <BodyPreview>…</BodyPreview>
    </Node>
  </Nodes>

  <Edges>
    <Edge
        from="file__app_py"
        to="func__get_users__app_py"
        relation="DEFINES"
        weight="1.0"
        confidence="high"
        evidence="…"
    />
  </Edges>

</DependencyGraph>

Neo4j APOC compatibility:
  apoc.import.xml(file, {relType:'relation', label:'type'})
  maps directly to this structure.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from .models import DependencyGraph, GraphNode, GraphEdge

try:
    from lxml import etree as ET
    _LXML = True
except ImportError:
    import xml.etree.ElementTree as ET
    from xml.dom import minidom
    _LXML = False


_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")

def _s(v, maxlen: int = 0) -> str:
    if v is None: return ""
    t = _CTRL.sub("", str(v))
    return t[:maxlen] + "…" if maxlen and len(t) > maxlen else t


def _sub(parent, tag, text=None, **kw):
    el = ET.SubElement(parent, tag)
    for k, v in kw.items():
        el.set(k.rstrip("_"), _s(str(v)))
    if text is not None:
        el.text = _s(text)
    return el


def export_xml(graph: DependencyGraph, output_path: str) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    root = ET.Element("DependencyGraph")
    root.set("name",         _s(graph.name))
    root.set("nodes",        str(graph.node_count))
    root.set("edges",        str(graph.edge_count))
    root.set("generated_at", now)

    # ── Metadata ─────────────────────────────────────────────
    meta    = ET.SubElement(root, "Metadata")
    ntc     = ET.SubElement(meta, "NodeTypeCounts")
    rel_cnt = ET.SubElement(meta, "RelationCounts")
    err_el  = ET.SubElement(meta, "Errors")

    node_type_counts = Counter(n.node_type for n in graph.nodes.values())
    for nt, cnt in sorted(node_type_counts.items(), key=lambda x: -x[1]):
        e = ET.SubElement(ntc, "Type"); e.set("name", nt); e.set("count", str(cnt))

    rel_counts = Counter(e.relation for e in graph.edges)
    for rel, cnt in sorted(rel_counts.items(), key=lambda x: -x[1]):
        e = ET.SubElement(rel_cnt, "Relation"); e.set("name", rel); e.set("count", str(cnt))

    for err in graph.errors:
        _sub(err_el, "Error", err)

    # ── Nodes ─────────────────────────────────────────────────
    nodes_el = ET.SubElement(root, "Nodes")
    nodes_el.set("count", str(graph.node_count))

    # Sort: FILEs first, then by type, then by name
    def _sort_key(n: GraphNode):
        order = {"FILE": 0, "CLASS": 1, "INTERFACE": 2, "FUNCTION": 3,
                 "ASYNC_FUNCTION": 3, "METHOD": 4, "SQL_TABLE": 5}
        return (order.get(n.node_type, 9), n.node_type, n.name)

    for node in sorted(graph.nodes.values(), key=_sort_key):
        n_el = ET.SubElement(nodes_el, "Node")
        n_el.set("id",          node.id)
        n_el.set("type",        node.node_type)
        n_el.set("name",        _s(node.name, 120))
        n_el.set("language",    node.language)
        n_el.set("file_path",   _s(node.file_path))
        n_el.set("start_line",  str(node.start_line))
        n_el.set("end_line",    str(node.end_line))
        n_el.set("is_async",    str(node.is_async).lower())
        n_el.set("is_exported", str(node.is_exported).lower())
        n_el.set("in_degree",   str(node.in_degree))
        n_el.set("out_degree",  str(node.out_degree))
        if node.parent_id:
            n_el.set("parent_id", node.parent_id)
        if node.return_type:
            n_el.set("return_type", _s(node.return_type, 80))

        if node.docstring:
            _sub(n_el, "DocString", _s(node.docstring, 400))
        if node.params:
            pe = ET.SubElement(n_el, "Parameters")
            for p in node.params: _sub(pe, "Param", _s(p, 60))
        if node.annotations:
            ae = ET.SubElement(n_el, "Annotations")
            for a in node.annotations: _sub(ae, "Ann", _s(a, 80))
        if node.modifiers:
            me = ET.SubElement(n_el, "Modifiers")
            for m in node.modifiers: _sub(me, "Mod", m)
        if node.body_preview:
            _sub(n_el, "BodyPreview", _s(node.body_preview, 200))

    # ── Edges ─────────────────────────────────────────────────
    edges_el = ET.SubElement(root, "Edges")
    edges_el.set("count", str(graph.edge_count))

    for edge in sorted(graph.edges, key=lambda e: (e.relation, e.from_id, e.to_id)):
        e_el = ET.SubElement(edges_el, "Edge")
        e_el.set("from",       edge.from_id)
        e_el.set("to",         edge.to_id)
        e_el.set("relation",   edge.relation)
        e_el.set("weight",     str(edge.weight))
        e_el.set("confidence", edge.confidence)
        if edge.evidence:
            e_el.set("evidence", _s(edge.evidence, 200))
        if edge.line_number:
            e_el.set("line", str(edge.line_number))

    # ── Write ─────────────────────────────────────────────────
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    if _LXML:
        ET.ElementTree(root).write(
            output_path, pretty_print=True,
            xml_declaration=True, encoding="utf-8",
        )
    else:
        raw    = ET.tostring(root, encoding="unicode")
        pretty = minidom.parseString(
            '<?xml version="1.0" encoding="UTF-8"?>' + raw
        ).toprettyxml(indent="  ", encoding=None)
        lines  = pretty.splitlines()
        if len(lines) > 1 and lines[0].startswith("<?xml") and lines[1].startswith("<?xml"):
            lines = lines[1:]
        Path(output_path).write_text("\n".join(lines), encoding="utf-8")

    kb = Path(output_path).stat().st_size / 1024
    print(f"[exporter] {output_path}  ({kb:.1f} KB,  "
          f"{graph.node_count} nodes,  {graph.edge_count} edges)")
    return output_path

