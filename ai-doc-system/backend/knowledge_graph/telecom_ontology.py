"""
knowledge_graph/telecom_ontology.py
────────────────────────────────────────────────────────────────
Enterprise Telecom Ontology Mapper.

Maps code entities and services to standard Telecom domains,
sub-domains, and capabilities. Aligned with TM Forum (TMF)
Open API naming conventions where applicable.

15+ domain categories covering OSS, BSS, Core Network,
5G, Revenue Assurance, Fraud, and more.
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Dict, List, Set

from .models import (
    KnowledgeGraph, KGNode,
    KGNodeType, KGRelationType, make_kg_node_id
)


class TelecomOntologyMapper:
    """Maps graph components to Telecom domains with multi-level ontology."""

    def __init__(self, verbose: bool = True):
        self.verbose = verbose

        # Multi-level ontology: Domain → Sub-domains → Keywords
        self.ontology = {
            "Charging & Billing": {
                "keywords": ["charging", "billing", "invoice", "payment", "recharge",
                             "tariff", "ocf", "abmf", "ocs", "cbs", "prepaid", "postpaid",
                             "topup", "balance"],
                "sub_domains": ["Online Charging", "Offline Charging", "Rating", "Invoicing"],
                "tmf_apis": ["TMF678", "TMF666"],
            },
            "CDR & Mediation": {
                "keywords": ["cdr", "mediation", "call_detail", "edr", "usage_record",
                             "xdr", "ipdr", "event_record", "correlation"],
                "sub_domains": ["CDR Processing", "Mediation", "Rating Input"],
                "tmf_apis": ["TMF635"],
            },
            "Provisioning": {
                "keywords": ["provisioning", "activation", "sim_activate", "hss_prov",
                             "hlr_prov", "service_activation", "fulfilment", "fulfillment",
                             "catalog", "order_management"],
                "sub_domains": ["Service Provisioning", "Network Provisioning", "SIM Activation"],
                "tmf_apis": ["TMF641", "TMF620"],
            },
            "Subscriber Management": {
                "keywords": ["subscriber", "crm", "customer", "profile", "kyc",
                             "churn", "segment", "loyalty", "subscriber_data",
                             "party", "individual", "organization"],
                "sub_domains": ["CRM", "Customer Lifecycle", "KYC", "Churn Prevention"],
                "tmf_apis": ["TMF632", "TMF629"],
            },
            "Core Network": {
                "keywords": ["hss", "hlr", "pcrf", "smsc", "mme", "pgw", "sgw",
                             "upf", "amf", "smf", "ausf", "nrf", "nssf",
                             "diameter", "gtp", "s1ap", "ngap"],
                "sub_domains": ["EPC", "5G Core", "IMS", "Signaling"],
                "tmf_apis": [],
            },
            "OSS": {
                "keywords": ["oss", "inventory", "topology", "alarm", "fault", "pm",
                             "fm", "performance_management", "fault_management",
                             "network_inventory", "nms", "ems"],
                "sub_domains": ["Fault Management", "Performance Management", "Inventory"],
                "tmf_apis": ["TMF638", "TMF642"],
            },
            "BSS": {
                "keywords": ["bss", "revenue", "business_support", "product_catalog",
                             "offer", "bundle", "promotion", "discount"],
                "sub_domains": ["Product Catalog", "Revenue Management", "Partner Management"],
                "tmf_apis": ["TMF620", "TMF637"],
            },
            "Roaming": {
                "keywords": ["roaming", "tap", "nrtrde", "clearing", "ireg",
                             "visited_network", "home_network", "aa14", "aa19"],
                "sub_domains": ["TAP Processing", "Clearing & Settlement", "Steering"],
                "tmf_apis": [],
            },
            "5G & Network Slicing": {
                "keywords": ["5g", "nr", "slice", "nssai", "qos_flow", "urllc",
                             "embb", "mmtc", "network_slice", "ran", "gnb",
                             "open_ran", "o_ran"],
                "sub_domains": ["RAN", "Network Slicing", "QoS Management"],
                "tmf_apis": [],
            },
            "SIM & eSIM": {
                "keywords": ["sim", "esim", "euicc", "iccid", "imsi", "msisdn",
                             "sim_swap", "sim_activation", "profile_download"],
                "sub_domains": ["SIM Lifecycle", "eSIM Management", "MSISDN Management"],
                "tmf_apis": [],
            },
            "Revenue Assurance": {
                "keywords": ["revenue_assurance", "leakage", "reconciliation",
                             "audit", "margin", "assurance", "ra_"],
                "sub_domains": ["Leakage Detection", "Reconciliation", "Audit"],
                "tmf_apis": [],
            },
            "Fraud Detection": {
                "keywords": ["fraud", "fms", "anomaly", "suspicious", "blacklist",
                             "whitelist", "rule_engine", "threshold", "alert_fraud"],
                "sub_domains": ["Real-time Fraud", "Offline Analysis", "SIM Box Detection"],
                "tmf_apis": [],
            },
            "Interconnect": {
                "keywords": ["interconnect", "settlement", "peering", "transit",
                             "wholesale", "carrier", "ixc", "termination"],
                "sub_domains": ["Interconnect Billing", "Partner Settlement"],
                "tmf_apis": [],
            },
            "Device Management": {
                "keywords": ["device", "handset", "firmware", "ota", "fota",
                             "device_management", "imei", "tac"],
                "sub_domains": ["OTA Updates", "Device Lifecycle", "IMEI Management"],
                "tmf_apis": [],
            },
            "Self-Care Portal": {
                "keywords": ["selfcare", "self_care", "portal", "myaccount",
                             "self_service", "customer_portal", "mobile_app"],
                "sub_domains": ["Web Portal", "Mobile App", "USSD Self-Service"],
                "tmf_apis": [],
            },
        }

        # Precompile regexes with weighted matching
        self.domain_regexes = {}
        for domain, config in self.ontology.items():
            keywords = config["keywords"]
            self.domain_regexes[domain] = re.compile(
                r'\b(' + '|'.join(re.escape(kw) for kw in keywords) + r')\b',
                re.IGNORECASE,
            )

    def map_ontology(self, kg: KnowledgeGraph) -> int:
        """
        Creates DOMAIN nodes, links services/flows, and builds
        multi-level ontology structure.

        Returns the number of relationships created.
        """
        added_nodes = 0
        added_edges = 0
        domain_nodes: Dict[str, KGNode] = {}

        # 1. Create domain nodes
        for domain_name, config in self.ontology.items():
            domain_id = make_kg_node_id(KGNodeType.DOMAIN, domain_name)
            tmf_info = ", ".join(config.get("tmf_apis", [])) or "N/A"
            sub_domains = ", ".join(config.get("sub_domains", []))

            node = KGNode(
                id=domain_id,
                node_type=KGNodeType.DOMAIN,
                name=domain_name,
                language="domain",
                docstring=(
                    f"Telecom Domain: {domain_name}\n"
                    f"Sub-domains: {sub_domains}\n"
                    f"TMF APIs: {tmf_info}"
                ),
                semantic_tags=["telecom", "ontology"],
            )
            kg.add_node(node)
            domain_nodes[domain_name] = node
            added_nodes += 1

        # 2. Map Service Clusters with weighted scoring
        for cluster in kg.service_clusters:
            matches = self._match_weighted(cluster.cluster_name)
            for domain, score in matches:
                conf = "high" if score >= 3 else "medium" if score >= 2 else "low"
                if kg.safe_add_edge(
                    cluster.cluster_id, domain_nodes[domain].id,
                    KGRelationType.BELONGS_TO_SERVICE,
                    confidence=conf, evidence=f"Ontology match (score={score})"
                ):
                    added_edges += 1

        # 3. Map Business Flows
        for flow in kg.business_flows:
            text = f"{flow.flow_name} {flow.description or ''}"
            matches = self._match_weighted(text)
            for domain, score in matches:
                if kg.safe_add_edge(
                    flow.flow_id, domain_nodes[domain].id,
                    KGRelationType.PARTICIPATES_IN_FLOW,
                    confidence="medium", evidence=f"Ontology match (score={score})"
                ):
                    added_edges += 1

        # 4. Map high-value files (FILE, PACKAGE, SERVICE, CONTROLLER)
        for node in kg.nodes.values():
            if node.node_type not in (
                KGNodeType.FILE, KGNodeType.PACKAGE,
                KGNodeType.SERVICE, KGNodeType.CONTROLLER
            ):
                continue

            # Score: file_path matches weighted higher than name
            text_fp = node.file_path or ""
            text_name = node.name or ""
            matches_fp = self._match_text(text_fp)
            matches_name = self._match_text(text_name)

            # Combine with fp getting 2x weight
            combined: Dict[str, int] = defaultdict(int)
            for d in matches_fp:
                combined[d] += 2
            for d in matches_name:
                combined[d] += 1

            for domain, score in combined.items():
                if score >= 2:
                    if kg.safe_add_edge(
                        node.id, domain_nodes[domain].id,
                        KGRelationType.BELONGS_TO_SERVICE,
                        confidence="low",
                        evidence=f"File/path ontology match (score={score})"
                    ):
                        added_edges += 1

        # 5. Create CAPABILITY_GROUP nodes for domains with sub-domains
        for domain_name, config in self.ontology.items():
            for sub in config.get("sub_domains", []):
                cap_id = make_kg_node_id(KGNodeType.CAPABILITY_GROUP, f"{domain_name}_{sub}")
                cap_node = KGNode(
                    id=cap_id,
                    node_type=KGNodeType.CAPABILITY_GROUP,
                    name=sub,
                    language="domain",
                    docstring=f"Sub-domain: {sub} (under {domain_name})",
                    semantic_tags=["telecom", "capability"],
                )
                kg.add_node(cap_node)
                added_nodes += 1
                kg.safe_add_edge(
                    cap_id, domain_nodes[domain_name].id,
                    KGRelationType.BELONGS_TO_SERVICE,
                    confidence="high", evidence="Sub-domain hierarchy",
                )
                added_edges += 1

        if self.verbose:
            print(f"[telecom] Mapped {added_nodes} domain/capability nodes and {added_edges} ontological edges.")

        return added_edges

    def _match_text(self, text: str) -> List[str]:
        """Return list of domain names that match the text."""
        if not text:
            return []
        return [
            domain for domain, regex in self.domain_regexes.items()
            if regex.search(text)
        ]

    def _match_weighted(self, text: str) -> List[tuple]:
        """Return [(domain, score)] with weighted matching."""
        if not text:
            return []
        results = []
        for domain, regex in self.domain_regexes.items():
            matches = regex.findall(text)
            if matches:
                results.append((domain, len(matches)))
        return results
