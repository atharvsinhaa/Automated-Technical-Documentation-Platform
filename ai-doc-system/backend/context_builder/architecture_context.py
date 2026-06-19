"""
context_builder/architecture_context.py
────────────────────────────────────────────────────────────────
Extracts architecture-level context: service boundaries,
bounded contexts, layers, event buses, inter-service deps.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from .models import ArchitectureContext, ContextNode
from .neo4j_client import Neo4jClient
from .graph_traverser import GraphTraverser, _dict_to_context_node


class ArchitectureExtractor:
    """Extracts architecture context for a target node."""

    def __init__(self, client: Neo4jClient, traverser: GraphTraverser, verbose: bool = True):
        self.client = client
        self.traverser = traverser
        self.verbose = verbose

    def extract(self, target: Dict, target_id: str) -> ArchitectureContext:
        """Extract full architecture context for a target node."""
        ctx = ArchitectureContext()

        # Service boundary
        ctx.service = target.get("service_boundary")

        # Business domain → bounded context
        ctx.bounded_context = target.get("business_domain")

        # Architecture layer: check outgoing BELONGS_TO_SERVICE edges to DOMAIN_LAYER
        layer_edges = self.client.get_edges_from(target_id, ["BELONGS_TO_SERVICE"])
        for e in layer_edges:
            if e.get("to_type") == "DOMAIN_LAYER":
                ctx.architecture_layer = e.get("to_name", "").replace(" Layer", "")
                break

        # Microservice: check edges to MICROSERVICE nodes
        for e in layer_edges:
            if e.get("to_type") == "MICROSERVICE":
                ctx.microservice = e.get("to_name")
                break

        # Event buses: PUBLISHES_TO / SUBSCRIBES_FROM edges
        pub_edges = self.client.get_edges_from(target_id, ["PUBLISHES_TO"])
        sub_edges = self.client.get_edges_to(target_id, ["SUBSCRIBES_FROM"])

        for e in pub_edges:
            ctx.event_buses.append({
                "bus": e.get("to_name", ""),
                "direction": "publishes",
            })
        for e in sub_edges:
            ctx.event_buses.append({
                "bus": e.get("from_name", ""),
                "direction": "subscribes",
            })

        # Also check neighborhood for event bus nodes
        if not ctx.event_buses:
            neighborhood = self.client.get_neighborhood(target_id, depth=2, limit=50)
            for n in neighborhood.get("nodes", []):
                if n.get("node_type") == "EVENT_BUS":
                    ctx.event_buses.append({
                        "bus": n.get("name", ""),
                        "direction": "connected",
                    })

        # Data pipelines
        dp_edges = self.client.get_edges_from(target_id, ["CALLS"])
        for e in dp_edges:
            if e.get("to_type") == "DATA_PIPELINE":
                ctx.data_pipelines.append(e.get("to_name", ""))

        # Inter-service dependencies: CALLS_API / INVOKES_SERVICE across services
        api_out = self.client.get_edges_from(target_id, ["CALLS_API", "INVOKES_SERVICE"])
        api_in = self.client.get_edges_to(target_id, ["CALLS_API", "INVOKES_SERVICE"])

        for e in api_out:
            ctx.inter_service_deps.append({
                "target": e.get("to_name", ""),
                "direction": "outbound",
                "relation": e.get("relation", ""),
            })
        for e in api_in:
            ctx.inter_service_deps.append({
                "source": e.get("from_name", ""),
                "direction": "inbound",
                "relation": e.get("relation", ""),
            })

        if self.verbose and (ctx.service or ctx.event_buses or ctx.inter_service_deps):
            parts = []
            if ctx.service: parts.append(f"service={ctx.service}")
            if ctx.architecture_layer: parts.append(f"layer={ctx.architecture_layer}")
            if ctx.event_buses: parts.append(f"buses={len(ctx.event_buses)}")
            if ctx.inter_service_deps: parts.append(f"deps={len(ctx.inter_service_deps)}")
            print(f"[arch-ctx] {', '.join(parts)}")

        return ctx
