"""
context_builder/neo4j_client.py
────────────────────────────────────────────────────────────────
Neo4j query client for the Context Builder.

Provides a high-level interface for semantic graph traversal.
Falls back to in-memory JSON traversal when Neo4j is unavailable.
"""

from __future__ import annotations

import json
from collections import defaultdict, deque
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from .utils import cypher_escape, normalize_path


class Neo4jClient:
    """
    Query client for the knowledge graph.

    Primary: Neo4j bolt driver
    Fallback: In-memory JSON graph from knowledge_graph.json
    """

    def __init__(
        self,
        uri:      str = "bolt://localhost:7687",
        user:     str = "neo4j",
        password: str = "password",
        database: str = "neo4j",
        kg_json_path: Optional[str] = None,
        verbose:  bool = True,
    ):
        self.uri = uri
        self.user = user
        self.password = password
        self.database = database
        self.verbose = verbose
        self._driver = None
        self._mode = "neo4j"

        # Fallback in-memory graph
        self._nodes: Dict[str, Dict] = {}
        self._edges: List[Dict] = []
        self._outgoing: Dict[str, List[Dict]] = defaultdict(list)
        self._incoming: Dict[str, List[Dict]] = defaultdict(list)

        # Try Neo4j, fallback to JSON
        if kg_json_path:
            self._load_json_fallback(kg_json_path)
        else:
            if not self._try_neo4j_connect():
                self._log("[neo4j-client] Neo4j unavailable. Use --kg-json for fallback.")

    def _try_neo4j_connect(self) -> bool:
        """Attempt to connect to Neo4j."""
        try:
            from neo4j import GraphDatabase
            self._driver = GraphDatabase.driver(
                self.uri, auth=(self.user, self.password),
            )
            # Test connection
            with self._driver.session(database=self.database) as session:
                result = session.run("RETURN 1 AS ok")
                result.single()
            self._mode = "neo4j"
            self._log(f"[neo4j-client] Connected to {self.uri}")
            return True
        except Exception as e:
            self._driver = None
            self._mode = "json"
            self._log(f"[neo4j-client] Cannot connect to Neo4j: {e}")
            return False

    def _load_json_fallback(self, path: str):
        """Load knowledge_graph.json for in-memory traversal."""
        self._mode = "json"
        p = Path(path)
        if not p.exists():
            self._log(f"[neo4j-client] Warning: {path} not found")
            return

        self._log(f"[neo4j-client] Loading JSON fallback: {path}")
        data = json.loads(p.read_text(encoding="utf-8"))

        for node in data.get("nodes", []):
            nid = node.get("id", "")
            self._nodes[nid] = node

        for edge in data.get("edges", []):
            self._edges.append(edge)
            fid = edge.get("from_id", "")
            tid = edge.get("to_id", "")
            self._outgoing[fid].append(edge)
            self._incoming[tid].append(edge)

        self._log(
            f"[neo4j-client] Loaded {len(self._nodes)} nodes, "
            f"{len(self._edges)} edges (JSON mode)"
        )

    # ── Node Lookup ──────────────────────────────────────────

    def find_node(
        self,
        name: Optional[str] = None,
        file_path: Optional[str] = None,
        node_type: Optional[str] = None,
        node_id: Optional[str] = None,
    ) -> Optional[Dict]:
        """Find a node by name, file path, type, or ID."""
        if self._mode == "neo4j":
            return self._neo4j_find_node(name, file_path, node_type, node_id)
        return self._json_find_node(name, file_path, node_type, node_id)

    def _neo4j_find_node(self, name, file_path, node_type, node_id) -> Optional[Dict]:
        conditions = []
        params: Dict[str, Any] = {}

        if node_id:
            conditions.append("n.id = $node_id")
            params["node_id"] = node_id
        if name:
            conditions.append("n.name CONTAINS $name")
            params["name"] = name
        if file_path:
            fp = normalize_path(file_path)
            conditions.append("n.file_path CONTAINS $file_path")
            params["file_path"] = fp
        if node_type:
            conditions.append("n.node_type = $node_type")
            params["node_type"] = node_type

        if not conditions:
            return None

        query = f"MATCH (n) WHERE {' AND '.join(conditions)} RETURN n LIMIT 1"
        records = self._run_query(query, params)
        if records:
            node = records[0].get("n")
            return dict(node) if node else None
        return None

    def _json_find_node(self, name, file_path, node_type, node_id) -> Optional[Dict]:
        if node_id and node_id in self._nodes:
            return self._nodes[node_id]

        for node in self._nodes.values():
            match = True
            if name and name.lower() not in (node.get("name", "")).lower():
                match = False
            if file_path:
                fp = normalize_path(file_path)
                node_fp = normalize_path(node.get("file_path", ""))
                if fp not in node_fp and node_fp not in fp:
                    match = False
            if node_type and node.get("node_type") != node_type:
                match = False
            if match:
                return node
        return None

    # ── Neighborhood ─────────────────────────────────────────

    def get_neighborhood(
        self,
        node_id: str,
        depth: int = 2,
        rel_types: Optional[List[str]] = None,
        limit: int = 100,
    ) -> Dict[str, Any]:
        """
        Get neighborhood of a node (both directions).

        Returns {"nodes": [...], "edges": [...]}.
        """
        if self._mode == "neo4j":
            return self._neo4j_neighborhood(node_id, depth, rel_types, limit)
        return self._json_neighborhood(node_id, depth, rel_types, limit)

    def _neo4j_neighborhood(self, node_id, depth, rel_types, limit):
        rel_filter = ""
        if rel_types:
            rel_filter = ":" + "|".join(rel_types)

        query = (
            f"MATCH (n {{id: $node_id}})"
            f"-[r{rel_filter}*1..{depth}]-(m) "
            f"WITH DISTINCT m, r "
            f"RETURN m AS node LIMIT {limit}"
        )
        records = self._run_query(query, {"node_id": node_id})
        nodes = [dict(r["node"]) for r in records if r.get("node")]

        # Also get edges
        edge_query = (
            f"MATCH (n {{id: $node_id}})"
            f"-[r{rel_filter}*1..{depth}]-(m) "
            f"WITH DISTINCT n, m "
            f"MATCH (a)-[e]->(b) "
            f"WHERE (a.id = n.id OR a.id = m.id) AND (b.id = n.id OR b.id = m.id) "
            f"RETURN a.name AS from_name, b.name AS to_name, type(e) AS relation, "
            f"a.id AS from_id, b.id AS to_id, e.evidence AS evidence "
            f"LIMIT {limit * 2}"
        )
        edge_records = self._run_query(edge_query, {"node_id": node_id})
        edges = [dict(r) for r in edge_records]

        return {"nodes": nodes, "edges": edges}

    def _json_neighborhood(self, node_id, depth, rel_types, limit):
        visited: Set[str] = set()
        frontier = {node_id}
        all_nodes = []
        all_edges = []

        for d in range(depth):
            next_frontier: Set[str] = set()
            for nid in frontier:
                # Outgoing
                for edge in self._outgoing.get(nid, []):
                    if rel_types and edge.get("relation") not in rel_types:
                        continue
                    tid = edge.get("to_id", "")
                    if tid not in visited:
                        next_frontier.add(tid)
                    all_edges.append(edge)
                # Incoming
                for edge in self._incoming.get(nid, []):
                    if rel_types and edge.get("relation") not in rel_types:
                        continue
                    fid = edge.get("from_id", "")
                    if fid not in visited:
                        next_frontier.add(fid)
                    all_edges.append(edge)
            visited |= frontier
            frontier = next_frontier - visited

        visited |= frontier
        visited.discard(node_id)

        for nid in list(visited)[:limit]:
            if nid in self._nodes:
                all_nodes.append(self._nodes[nid])

        return {"nodes": all_nodes, "edges": all_edges[:limit * 2]}

    # ── Directional Traversal ────────────────────────────────

    def get_upstream(self, node_id: str, depth: int = 3, limit: int = 50) -> List[Dict]:
        """Trace incoming edges (who calls / depends on this?)."""
        if self._mode == "neo4j":
            query = (
                f"MATCH (m)-[r*1..{depth}]->(n {{id: $node_id}}) "
                f"RETURN DISTINCT m AS node LIMIT {limit}"
            )
            records = self._run_query(query, {"node_id": node_id})
            return [dict(r["node"]) for r in records if r.get("node")]

        return self._json_traverse_direction(node_id, depth, "incoming", limit)

    def get_downstream(self, node_id: str, depth: int = 3, limit: int = 50) -> List[Dict]:
        """Trace outgoing edges (what does this call / depend on?)."""
        if self._mode == "neo4j":
            query = (
                f"MATCH (n {{id: $node_id}})-[r*1..{depth}]->(m) "
                f"RETURN DISTINCT m AS node LIMIT {limit}"
            )
            records = self._run_query(query, {"node_id": node_id})
            return [dict(r["node"]) for r in records if r.get("node")]

        return self._json_traverse_direction(node_id, depth, "outgoing", limit)

    def _json_traverse_direction(self, node_id, depth, direction, limit):
        visited: Set[str] = set()
        frontier = {node_id}
        results = []

        for d in range(depth):
            next_frontier: Set[str] = set()
            for nid in frontier:
                edges = (
                    self._incoming.get(nid, [])
                    if direction == "incoming"
                    else self._outgoing.get(nid, [])
                )
                for edge in edges:
                    neighbor_id = (
                        edge.get("from_id", "")
                        if direction == "incoming"
                        else edge.get("to_id", "")
                    )
                    if neighbor_id and neighbor_id not in visited:
                        next_frontier.add(neighbor_id)
            visited |= frontier
            frontier = next_frontier - visited

        visited |= frontier
        visited.discard(node_id)

        for nid in list(visited)[:limit]:
            if nid in self._nodes:
                results.append(self._nodes[nid])

        return results

    # ── Specialized Queries ──────────────────────────────────

    def get_community(self, community_id: int, limit: int = 50) -> List[Dict]:
        """Get all nodes in a community cluster."""
        if self._mode == "neo4j":
            query = (
                "MATCH (n) WHERE n.community_id = $cid "
                f"RETURN n AS node LIMIT {limit}"
            )
            records = self._run_query(query, {"cid": community_id})
            return [dict(r["node"]) for r in records if r.get("node")]

        return [
            n for n in self._nodes.values()
            if n.get("community_id") == community_id
        ][:limit]

    def get_business_flow(self, flow_name: str, limit: int = 50) -> List[Dict]:
        """Get nodes participating in a business flow."""
        if self._mode == "neo4j":
            query = (
                "MATCH (flow:BusinessFlow)-[:PARTICIPATES_IN_FLOW]-(n) "
                "WHERE flow.name CONTAINS $name "
                f"RETURN n AS node LIMIT {limit}"
            )
            records = self._run_query(query, {"name": flow_name})
            return [dict(r["node"]) for r in records if r.get("node")]

        # JSON fallback: search by semantic tags or name
        results = []
        for n in self._nodes.values():
            tags = n.get("semantic_tags", [])
            if isinstance(tags, str):
                tags = [tags]
            if flow_name.lower() in (n.get("name", "")).lower() or \
               any(flow_name.lower() in t.lower() for t in tags):
                results.append(n)
        return results[:limit]

    def get_service_cluster(self, service_name: str, limit: int = 100) -> List[Dict]:
        """Get all nodes in a service cluster."""
        if self._mode == "neo4j":
            query = (
                "MATCH (n) WHERE n.service_boundary CONTAINS $svc "
                f"RETURN n AS node LIMIT {limit}"
            )
            records = self._run_query(query, {"svc": service_name})
            return [dict(r["node"]) for r in records if r.get("node")]

        return [
            n for n in self._nodes.values()
            if service_name.lower() in (n.get("service_boundary", "")).lower()
        ][:limit]

    def get_by_domain(self, domain_name: str, limit: int = 50) -> List[Dict]:
        """Get nodes tagged with a telecom/business domain."""
        if self._mode == "neo4j":
            query = (
                "MATCH (n) WHERE n.business_domain CONTAINS $domain "
                f"RETURN n AS node LIMIT {limit}"
            )
            records = self._run_query(query, {"domain": domain_name})
            return [dict(r["node"]) for r in records if r.get("node")]

        return [
            n for n in self._nodes.values()
            if domain_name.lower() in (n.get("business_domain", "")).lower()
        ][:limit]

    def get_nodes_by_type(self, node_type: str, limit: int = 50) -> List[Dict]:
        """Get nodes by type."""
        if self._mode == "neo4j":
            query = (
                "MATCH (n) WHERE n.node_type = $ntype "
                f"RETURN n AS node LIMIT {limit}"
            )
            records = self._run_query(query, {"ntype": node_type})
            return [dict(r["node"]) for r in records if r.get("node")]

        return [
            n for n in self._nodes.values()
            if n.get("node_type") == node_type
        ][:limit]

    def get_edges_from(self, node_id: str, rel_types: Optional[List[str]] = None) -> List[Dict]:
        """Get outgoing edges from a node."""
        if self._mode == "neo4j":
            if rel_types:
                rel_filter = ":" + "|".join(rel_types)
            else:
                rel_filter = ""
            query = (
                f"MATCH (n {{id: $nid}})-[r{rel_filter}]->(m) "
                f"RETURN n.name AS from_name, m.name AS to_name, type(r) AS relation, "
                f"n.id AS from_id, m.id AS to_id, r.evidence AS evidence, "
                f"m.node_type AS to_type, m.file_path AS to_file_path "
                f"LIMIT 100"
            )
            records = self._run_query(query, {"nid": node_id})
            return [dict(r) for r in records]

        results = []
        for edge in self._outgoing.get(node_id, []):
            if rel_types and edge.get("relation") not in rel_types:
                continue
            tid = edge.get("to_id", "")
            target = self._nodes.get(tid, {})
            results.append({
                "from_name": self._nodes.get(node_id, {}).get("name", ""),
                "to_name": target.get("name", ""),
                "relation": edge.get("relation", ""),
                "from_id": node_id,
                "to_id": tid,
                "evidence": edge.get("evidence", ""),
                "to_type": target.get("node_type", ""),
                "to_file_path": target.get("file_path", ""),
            })
        return results

    def get_edges_to(self, node_id: str, rel_types: Optional[List[str]] = None) -> List[Dict]:
        """Get incoming edges to a node."""
        if self._mode == "neo4j":
            if rel_types:
                rel_filter = ":" + "|".join(rel_types)
            else:
                rel_filter = ""
            query = (
                f"MATCH (m)-[r{rel_filter}]->(n {{id: $nid}}) "
                f"RETURN m.name AS from_name, n.name AS to_name, type(r) AS relation, "
                f"m.id AS from_id, n.id AS to_id, r.evidence AS evidence, "
                f"m.node_type AS from_type, m.file_path AS from_file_path "
                f"LIMIT 100"
            )
            records = self._run_query(query, {"nid": node_id})
            return [dict(r) for r in records]

        results = []
        for edge in self._incoming.get(node_id, []):
            if rel_types and edge.get("relation") not in rel_types:
                continue
            fid = edge.get("from_id", "")
            source = self._nodes.get(fid, {})
            results.append({
                "from_name": source.get("name", ""),
                "to_name": self._nodes.get(node_id, {}).get("name", ""),
                "relation": edge.get("relation", ""),
                "from_id": fid,
                "to_id": node_id,
                "evidence": edge.get("evidence", ""),
                "from_type": source.get("node_type", ""),
                "from_file_path": source.get("file_path", ""),
            })
        return results

    # ── Raw Query ────────────────────────────────────────────

    def cypher_query(self, query: str, params: Optional[Dict] = None) -> List[Dict]:
        """Execute a raw Cypher query (Neo4j mode only)."""
        if self._mode != "neo4j":
            self._log("[neo4j-client] Raw Cypher not available in JSON fallback mode")
            return []
        return self._run_query(query, params or {})

    # ── Internal ─────────────────────────────────────────────

    def _run_query(self, query: str, params: Dict) -> List[Dict]:
        """Execute a Cypher query and return records as dicts."""
        if not self._driver:
            return []
        try:
            with self._driver.session(database=self.database) as session:
                result = session.run(query, params)
                return [dict(record) for record in result]
        except Exception as e:
            self._log(f"[neo4j-client] Query error: {e}")
            return []

    def close(self):
        """Close the Neo4j driver."""
        if self._driver:
            self._driver.close()
            self._driver = None

    def _log(self, msg: str):
        if self.verbose:
            print(msg, flush=True)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
