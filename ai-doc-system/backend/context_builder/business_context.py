"""
context_builder/business_context.py
────────────────────────────────────────────────────────────────
Extracts business-level context: flows, capabilities, workflows.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from .models import BusinessContext
from .neo4j_client import Neo4jClient
from .graph_traverser import GraphTraverser


class BusinessExtractor:
    """Extracts business context for a target node."""

    def __init__(self, client: Neo4jClient, traverser: GraphTraverser, verbose: bool = True):
        self.client = client
        self.traverser = traverser
        self.verbose = verbose

    def extract(self, target: Dict, target_id: str) -> BusinessContext:
        """Extract business flows, capabilities, and workflows."""
        ctx = BusinessContext()

        # Business flows the target participates in
        flow_edges = self.client.get_edges_to(target_id, ["PARTICIPATES_IN_FLOW"])
        flow_edges += self.client.get_edges_from(target_id, ["PARTICIPATES_IN_FLOW"])

        seen_flows = set()
        for e in flow_edges:
            flow_name = e.get("from_name") or e.get("to_name", "")
            if flow_name and flow_name not in seen_flows:
                seen_flows.add(flow_name)
                ctx.flows.append({
                    "flow_name": flow_name,
                    "relation": "participates",
                })

        # Also check for TRIGGERS_WORKFLOW edges
        wf_edges = self.client.get_edges_from(target_id, ["TRIGGERS_WORKFLOW"])
        for e in wf_edges:
            wf_name = e.get("to_name", "")
            if wf_name and wf_name not in seen_flows:
                seen_flows.add(wf_name)
                ctx.flows.append({
                    "flow_name": wf_name,
                    "relation": "triggers",
                })

        # Capability groups
        cap_edges = self.client.get_edges_from(target_id, ["BELONGS_TO_SERVICE"])
        for e in cap_edges:
            if e.get("to_type") == "CAPABILITY_GROUP":
                ctx.capabilities.append(e.get("to_name", ""))

        # Workflow steps: check neighborhood for BUSINESS_FLOW nodes
        neighborhood = self.client.get_neighborhood(target_id, depth=2, limit=30)
        for n in neighborhood.get("nodes", []):
            if n.get("node_type") in ("BUSINESS_FLOW", "WORKFLOW"):
                name = n.get("name", "")
                if name not in seen_flows:
                    ctx.workflow_steps.append(name)

        if self.verbose and (ctx.flows or ctx.capabilities):
            parts = []
            if ctx.flows: parts.append(f"flows={len(ctx.flows)}")
            if ctx.capabilities: parts.append(f"caps={len(ctx.capabilities)}")
            print(f"[biz-ctx] {', '.join(parts)}")

        return ctx
