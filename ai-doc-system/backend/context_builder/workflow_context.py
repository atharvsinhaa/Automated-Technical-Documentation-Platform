"""
context_builder/workflow_context.py
────────────────────────────────────────────────────────────────
Extracts workflow execution context: steps, control flow,
entry/exit points, exception handling.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from .models import WorkflowContext
from .neo4j_client import Neo4jClient
from .graph_traverser import GraphTraverser


class WorkflowExtractor:
    """Extracts workflow context for a target node."""

    def __init__(self, client: Neo4jClient, traverser: GraphTraverser, verbose: bool = True):
        self.client = client
        self.traverser = traverser
        self.verbose = verbose

    def extract(self, target: Dict, target_id: str) -> WorkflowContext:
        """Extract workflow steps, control flow, and entry/exit points."""
        ctx = WorkflowContext()

        # Check for EXECUTES_AFTER chains (LLD execution order)
        exec_after_out = self.client.get_edges_from(target_id, ["EXECUTES_AFTER"])
        exec_after_in = self.client.get_edges_to(target_id, ["EXECUTES_AFTER"])

        # Build the execution chain
        chain_steps = []
        if exec_after_in:
            # Target is called after something
            for e in exec_after_in:
                chain_steps.append({
                    "step": e.get("from_name", ""),
                    "position": "before_target",
                })
        chain_steps.append({
            "step": target.get("name", ""),
            "position": "target",
        })
        if exec_after_out:
            for e in exec_after_out:
                chain_steps.append({
                    "step": e.get("to_name", ""),
                    "position": "after_target",
                })

        if len(chain_steps) > 1:
            ctx.steps = chain_steps

        # Control flow: CONTROL_FLOW edges
        cf_edges = self.client.get_edges_from(target_id, ["CONTROL_FLOW"])
        for e in cf_edges:
            ctx.control_flow.append({
                "target": e.get("to_name", ""),
                "type": "conditional_call",
                "evidence": e.get("evidence", ""),
            })

        # Exception flow: RETURNS_TO edges
        ret_edges = self.client.get_edges_from(target_id, ["RETURNS_TO"])
        for e in ret_edges:
            ctx.control_flow.append({
                "target": e.get("to_name", ""),
                "type": "exception_handler",
                "evidence": e.get("evidence", ""),
            })

        # Entry/exit points: check what CALLS this function
        callers = self.client.get_edges_to(target_id, ["CALLS", "CALLS_API"])
        if callers:
            # If this node is called by API_ENDPOINT or CONTROLLER, it's an entry point
            for c in callers:
                if c.get("from_type") in ("API_ENDPOINT", "CONTROLLER"):
                    ctx.entry_point = c.get("from_name", "")
                    break

        # Exit points: what does this function call that ends the flow
        callees = self.client.get_edges_from(target_id, ["CALLS", "CALLS_API"])
        for c in callees:
            if c.get("to_type") in ("API_CALL", "RETURNS_RESPONSE"):
                ctx.exit_points.append(c.get("to_name", ""))

        # Try to find the workflow name from business flows
        flow_edges = self.client.get_edges_from(target_id, ["PARTICIPATES_IN_FLOW"])
        flow_edges += self.client.get_edges_to(target_id, ["PARTICIPATES_IN_FLOW"])
        for e in flow_edges:
            name = e.get("to_name") or e.get("from_name", "")
            if name:
                ctx.workflow_name = name
                break

        if self.verbose and (ctx.steps or ctx.control_flow):
            parts = []
            if ctx.steps: parts.append(f"steps={len(ctx.steps)}")
            if ctx.control_flow: parts.append(f"cf={len(ctx.control_flow)}")
            if ctx.entry_point: parts.append(f"entry={ctx.entry_point}")
            if parts:
                print(f"[workflow-ctx] {', '.join(parts)}")

        return ctx
