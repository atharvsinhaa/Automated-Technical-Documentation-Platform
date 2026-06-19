"""
context_builder/telecom_context.py
────────────────────────────────────────────────────────────────
Extracts telecom domain context: domain, sub-domain, TMF APIs.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from .models import TelecomContext
from .neo4j_client import Neo4jClient
from .graph_traverser import GraphTraverser


class TelecomExtractor:
    """Extracts telecom domain context for a target node."""

    # TMF API mapping (from telecom_ontology)
    TMF_MAPPING = {
        "Charging & Billing": ["TMF678", "TMF666"],
        "CDR & Mediation": ["TMF635"],
        "Provisioning": ["TMF641", "TMF620"],
        "Subscriber Management": ["TMF632", "TMF629"],
        "OSS": ["TMF638", "TMF642"],
        "BSS": ["TMF620", "TMF637"],
    }

    def __init__(self, client: Neo4jClient, traverser: GraphTraverser, verbose: bool = True):
        self.client = client
        self.traverser = traverser
        self.verbose = verbose

    def extract(self, target: Dict, target_id: str) -> TelecomContext:
        """Extract telecom domain, sub-domain, and TMF alignment."""
        ctx = TelecomContext()

        # Direct domain from node
        ctx.domain = target.get("business_domain")

        # Check edges to DOMAIN nodes
        domain_edges = self.client.get_edges_from(target_id, ["BELONGS_TO_SERVICE"])
        for e in domain_edges:
            if e.get("to_type") == "DOMAIN":
                ctx.domain = ctx.domain or e.get("to_name", "")
                ctx.related_nodes.append(e.get("to_name", ""))

        # Check edges to CAPABILITY_GROUP (sub-domains)
        for e in domain_edges:
            if e.get("to_type") == "CAPABILITY_GROUP":
                ctx.sub_domain = e.get("to_name", "")

        # TMF API alignment
        if ctx.domain:
            ctx.tmf_apis = self.TMF_MAPPING.get(ctx.domain, [])

        # Look at neighborhood for domain nodes
        if not ctx.domain:
            neighborhood = self.client.get_neighborhood(target_id, depth=2, limit=30)
            for n in neighborhood.get("nodes", []):
                if n.get("node_type") == "DOMAIN":
                    ctx.domain = n.get("name", "")
                    ctx.related_nodes.append(n.get("name", ""))
                    break

        # Semantic tags that relate to telecom
        tags = target.get("semantic_tags", [])
        if isinstance(tags, str):
            tags = [tags]
        telecom_tags = [t for t in tags if t in (
            "telecom", "billing", "charging", "cdr", "provisioning",
            "subscriber", "roaming", "oss", "bss", "5g",
        )]
        if telecom_tags and not ctx.domain:
            ctx.domain = telecom_tags[0].title()

        if self.verbose and ctx.domain:
            print(f"[telecom-ctx] domain={ctx.domain}, sub={ctx.sub_domain}")

        return ctx
