"""
repository_intelligence/request_lifecycle_extractor.py
────────────────────────────────────────────────────────────────
Extracts end-to-end request lifecycle flows from the Knowledge Graph.

Traces:
  Controller → Service → Repository → Database

Uses:
  - Knowledge Graph (nodes + edges)
  - Dependency Graph (call chains)
  - Lineage Chains (traced paths)

Output:
  List[RequestFlow] — each with entry, steps, exit, type.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple


@dataclass
class RequestFlow:
    """A complete request lifecycle trace."""
    name: str
    flow_type: str = "api_flow"   # api_flow / data_flow / event_flow
    entry_point: str = ""          # API endpoint or trigger
    steps: List[str] = field(default_factory=list)
    step_types: List[str] = field(default_factory=list)
    exit_point: str = ""           # DB table or response
    description: str = ""
    confidence: str = "high"
    hop_count: int = 0


class RequestLifecycleExtractor:
    """
    Extracts request lifecycle flows from the Knowledge Graph.

    Traces paths from API endpoints through controllers, services,
    repositories, down to databases — producing end-to-end flows
    for LLD documentation.

    Usage:
        extractor = RequestLifecycleExtractor()
        flows = extractor.extract(kg)
    """

    # Node types for each architectural tier
    ENTRY_TYPES = {
        "API_ENDPOINT", "CONTROLLER", "ASYNC_FUNCTION",
    }
    SERVICE_TYPES = {
        "SERVICE", "CLASS", "FUNCTION", "ASYNC_FUNCTION",
    }
    REPOSITORY_TYPES = {
        "REPOSITORY", "CLASS", "FUNCTION",
    }
    DATA_TYPES = {
        "SQL_TABLE", "MONGO_COLLECTION", "DATAFRAME",
    }

    # Edge types that indicate execution flow
    FLOW_EDGES = {
        "CALLS", "INVOKES", "CALLS_API", "INVOKES_METHOD",
        "INVOKES_SERVICE", "INVOKES_API", "EXECUTES_AFTER",
        "CONTROL_FLOW", "DEPENDS_ON",
    }

    # Edge types that indicate data access
    DATA_EDGES = {
        "QUERIES_TABLE", "WRITES_TABLE", "CREATES_TABLE",
        "READS_FROM", "WRITES_TO",
        "READS_COLLECTION", "WRITES_COLLECTION",
        "AGGREGATES_COLLECTION",
    }

    def __init__(self, verbose: bool = True):
        self.verbose = verbose

    def extract(self, kg) -> List[RequestFlow]:
        """
        Extract request lifecycle flows from the Knowledge Graph.

        Strategy:
        1. Find all API_ENDPOINT and CONTROLLER nodes (entry points)
        2. For each entry, BFS forward along CALLS/INVOKES edges
        3. Classify each hop by architectural tier
        4. Stop at DATA stores or leaf nodes
        5. Return flows with >= 2 hops
        """
        flows: List[RequestFlow] = []

        # Strategy 1: From API endpoints
        for node in kg.nodes.values():
            if node.node_type in ("API_ENDPOINT",):
                flow = self._trace_from_entry(kg, node)
                if flow and flow.hop_count >= 2:
                    flows.append(flow)

        # Strategy 2: From controllers
        for node in kg.nodes.values():
            if node.node_type in ("CONTROLLER",):
                # Find methods defined in this controller
                for edge in kg.outgoing_edges(node.id):
                    if edge.relation in ("DEFINES", "CONTAINS"):
                        method_node = kg.nodes.get(edge.to_id)
                        if method_node and method_node.node_type in (
                            "FUNCTION", "ASYNC_FUNCTION", "METHOD",
                        ):
                            flow = self._trace_from_entry(
                                kg, method_node,
                                prefix=f"{node.name}.",
                            )
                            if flow and flow.hop_count >= 2:
                                flows.append(flow)

        # Strategy 3: From existing lineage chains
        if hasattr(kg, "lineage_chains"):
            for chain in kg.lineage_chains:
                if chain.chain_type in ("api", "sql") and chain.depth >= 3:
                    flow = self._lineage_to_flow(kg, chain)
                    if flow:
                        flows.append(flow)

        # Strategy 4: From business flows
        if hasattr(kg, "business_flows"):
            for bflow in kg.business_flows:
                if bflow.flow_type == "api_flow" and len(bflow.node_ids) >= 3:
                    flow = self._business_flow_to_request(kg, bflow)
                    if flow:
                        flows.append(flow)

        # Deduplicate by name
        seen = set()
        deduped = []
        for f in flows:
            key = f.name
            if key not in seen:
                seen.add(key)
                deduped.append(f)

        if self.verbose:
            print(
                f"[lifecycle-extractor] Found "
                f"{len(deduped)} request flows"
            )

        return deduped

    def _trace_from_entry(
        self, kg, entry_node, prefix: str = "",
    ) -> Optional[RequestFlow]:
        """
        BFS trace from an entry node through the call graph.

        Returns a RequestFlow with tiered steps:
        Controller → Service → Repository → Database
        """
        visited: List[str] = []
        visited_types: List[str] = []
        queue = deque([(entry_node.id, 0)])
        seen: Set[str] = set()
        max_depth = 8
        exit_point = ""

        while queue:
            node_id, depth = queue.popleft()

            if node_id in seen or depth > max_depth:
                continue
            seen.add(node_id)

            node = kg.nodes.get(node_id)
            if not node:
                continue

            visited.append(node.name)
            visited_types.append(
                self._classify_tier(node.node_type)
            )

            # Check for data store terminus
            if node.node_type in self.DATA_TYPES:
                exit_point = node.name
                break

            # Follow call/flow edges
            for edge in kg.outgoing_edges(node_id):
                if edge.relation in self.FLOW_EDGES | self.DATA_EDGES:
                    if edge.to_id not in seen:
                        queue.append((edge.to_id, depth + 1))

        if len(visited) < 2:
            return None

        name = f"{prefix}{entry_node.name}"

        return RequestFlow(
            name=name,
            flow_type="api_flow",
            entry_point=visited[0],
            steps=visited,
            step_types=visited_types,
            exit_point=exit_point or visited[-1],
            hop_count=len(visited),
            confidence="high" if len(visited) >= 3 else "medium",
        )

    def _lineage_to_flow(
        self, kg, chain,
    ) -> Optional[RequestFlow]:
        """Convert a KG LineageChain into a RequestFlow."""
        steps = []
        step_types = []

        for node_id in chain.ordered_node_ids:
            node = kg.nodes.get(node_id)
            if node:
                steps.append(node.name)
                step_types.append(
                    self._classify_tier(node.node_type)
                )

        if len(steps) < 2:
            return None

        return RequestFlow(
            name=chain.description or f"Chain: {steps[0]}",
            flow_type="api_flow" if chain.chain_type == "api" else "data_flow",
            entry_point=steps[0],
            steps=steps,
            step_types=step_types,
            exit_point=steps[-1],
            hop_count=len(steps),
            confidence=chain.confidence,
        )

    def _business_flow_to_request(
        self, kg, bflow,
    ) -> Optional[RequestFlow]:
        """Convert a KG BusinessFlow into a RequestFlow."""
        steps = []
        step_types = []

        for node_id in bflow.node_ids:
            node = kg.nodes.get(node_id)
            if node:
                steps.append(node.name)
                step_types.append(
                    self._classify_tier(node.node_type)
                )

        if len(steps) < 2:
            return None

        entry_node = kg.nodes.get(bflow.entry_node_id)
        entry_name = entry_node.name if entry_node else steps[0]

        return RequestFlow(
            name=bflow.flow_name,
            flow_type=bflow.flow_type,
            entry_point=entry_name,
            steps=steps,
            step_types=step_types,
            exit_point=steps[-1],
            hop_count=len(steps),
            description=bflow.description or "",
            confidence=bflow.confidence,
        )

    def _classify_tier(self, node_type: str) -> str:
        """Classify a node type into an architectural tier."""
        if node_type in ("API_ENDPOINT", "CONTROLLER"):
            return "Controller"
        if node_type in ("SERVICE",):
            return "Service"
        if node_type in ("REPOSITORY",):
            return "Repository"
        if node_type in (
            "SQL_TABLE", "MONGO_COLLECTION", "DATAFRAME",
        ):
            return "Database"
        if node_type in ("FUNCTION", "ASYNC_FUNCTION", "METHOD"):
            return "Function"
        if node_type in ("CLASS",):
            return "Component"
        return "Other"
