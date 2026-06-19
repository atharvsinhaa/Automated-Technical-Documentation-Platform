"""
knowledge_graph/business_mapper.py
────────────────────────────────────────────────────────────────
Extracts business semantics from the code graph.

Detects:
  - Microservice boundaries (directory / annotation / package based)
  - Business flows (API → handler → logic → data access)
  - Module ownership
  - Service-to-service dependency maps

All detection is heuristic-based — zero LLM, zero cloud.
"""

from __future__ import annotations

import os
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

from .models import (
    KGNode, KGEdge, KnowledgeGraph,
    BusinessFlow, ServiceCluster, FlowSummary,
    KGNodeType, KGRelationType, make_kg_node_id,
)


# ──────────────────────────────────────────────────────────────
#  HEURISTIC PATTERNS
# ──────────────────────────────────────────────────────────────

# Directory patterns that indicate service boundaries
_SERVICE_DIR_PATTERNS = [
    re.compile(r"^(?:services?|apps?|modules?|packages?)/([^/]+)", re.I),
    re.compile(r"^(?:src|lib)/(?:services?|apps?|modules?)/([^/]+)", re.I),
    re.compile(r"^(?:microservices?|ms)/([^/]+)", re.I),
    re.compile(r"^([^/]+)-(?:service|api|server|worker|app)\b", re.I),
]

# Annotation patterns for service detection
_SERVICE_ANNOTATIONS = re.compile(
    r"@(?:Service|Module|Injectable|Component|Controller|RestController"
    r"|SpringBootApplication|NestModule|Bean|Configuration)\b", re.I
)

# Business domain keywords for semantic tagging
_DOMAIN_KEYWORDS: Dict[str, List[str]] = {
    "auth":        ["auth", "login", "logout", "token", "jwt", "session", "oauth",
                    "password", "credential", "permission", "role", "access"],
    "user":        ["user", "profile", "account", "registration", "signup"],
    "payment":     ["payment", "billing", "invoice", "charge", "refund",
                    "subscription", "stripe", "razorpay", "wallet", "transaction"],
    "notification": ["notification", "email", "sms", "push", "alert", "message",
                     "template", "mailer", "sendgrid"],
    "data":        ["data", "analytics", "report", "dashboard", "metric",
                    "aggregate", "etl", "pipeline", "warehouse"],
    "api":         ["api", "endpoint", "route", "handler", "middleware",
                    "interceptor", "gateway", "proxy"],
    "storage":     ["storage", "upload", "download", "file", "s3", "blob",
                    "media", "image", "asset"],
    "search":      ["search", "index", "elasticsearch", "solr", "query", "filter"],
    "config":      ["config", "settings", "environment", "env", "feature_flag"],
    "test":        ["test", "spec", "mock", "fixture", "stub", "e2e"],
    "infra":       ["docker", "kubernetes", "deploy", "ci", "cd", "terraform",
                    "helm", "ansible"],
    "cache":       ["cache", "redis", "memcached", "invalidate"],
    "queue":       ["queue", "worker", "job", "celery", "kafka", "rabbitmq",
                    "pubsub", "event"],
}

# Route pattern → flow name mapping
_ROUTE_TO_FLOW: Dict[str, str] = {
    r"/users?":          "User Management",
    r"/auth":            "Authentication",
    r"/login":           "User Login",
    r"/register":        "User Registration",
    r"/payments?":       "Payment Processing",
    r"/orders?":         "Order Management",
    r"/products?":       "Product Management",
    r"/notifications?":  "Notification Delivery",
    r"/reports?":        "Report Generation",
    r"/search":          "Search",
    r"/upload":          "File Upload",
    r"/download":        "File Download",
    r"/admin":           "Administration",
    r"/health":          "Health Check",
    r"/metrics":         "Metrics",
}


# ══════════════════════════════════════════════════════════════
#  BUSINESS MAPPER
# ══════════════════════════════════════════════════════════════

class BusinessMapper:
    """
    Extracts business-aware semantics from the code graph.

    Usage:
        mapper = BusinessMapper()
        clusters = mapper.detect_service_boundaries(kg)
        flows = mapper.extract_business_flows(kg)
        ownership = mapper.map_module_ownership(kg, clusters)
        mapper.map_business_capabilities(kg)
    """

    def __init__(self, verbose: bool = True):
        self.verbose = verbose

    # ── Service Boundary Detection ───────────────────────────

    def detect_service_boundaries(
        self,
        kg: KnowledgeGraph,
    ) -> List[ServiceCluster]:
        """
        Detect microservice boundaries using multi-signal analysis:
          1. Directory structure patterns
          2. Annotation scanning
          3. Package hierarchy analysis
        """
        clusters: Dict[str, ServiceCluster] = {}

        # ── Signal 1: Directory structure ────────────────────
        dir_clusters = self._detect_by_directory(kg)
        for cluster in dir_clusters:
            clusters[cluster.cluster_id] = cluster

        # ── Signal 2: Annotation-based ───────────────────────
        ann_clusters = self._detect_by_annotations(kg)
        for cluster in ann_clusters:
            if cluster.cluster_id not in clusters:
                clusters[cluster.cluster_id] = cluster
            else:
                # Merge into existing
                existing = clusters[cluster.cluster_id]
                existing.node_ids.extend(cluster.node_ids)
                existing.file_paths.extend(cluster.file_paths)
                existing.languages.update(cluster.languages)

        # ── Signal 3: Package hierarchy ──────────────────────
        pkg_clusters = self._detect_by_package(kg)
        for cluster in pkg_clusters:
            if cluster.cluster_id not in clusters:
                clusters[cluster.cluster_id] = cluster

        # Deduplicate file paths in each cluster
        for cluster in clusters.values():
            cluster.file_paths = list(set(cluster.file_paths))
            cluster.node_ids = list(set(cluster.node_ids))

        result = list(clusters.values())
        self._log(f"[business] Detected {len(result)} service clusters")
        return result

    def _detect_by_directory(self, kg: KnowledgeGraph) -> List[ServiceCluster]:
        """Detect services from directory structure patterns."""
        service_files: Dict[str, List[str]] = defaultdict(list)
        service_languages: Dict[str, Set[str]] = defaultdict(set)

        for node in kg.nodes.values():
            if node.node_type != KGNodeType.FILE:
                continue
            fp = node.file_path
            for pattern in _SERVICE_DIR_PATTERNS:
                m = pattern.search(fp)
                if m:
                    service_name = m.group(1)
                    service_files[service_name].append(fp)
                    if node.language:
                        service_languages[service_name].add(node.language)
                    break

        clusters = []
        for svc_name, files in service_files.items():
            if len(files) < 2:
                continue  # single-file not a service
            cluster_id = make_kg_node_id(KGNodeType.SERVICE_CLUSTER, svc_name)
            clusters.append(ServiceCluster(
                cluster_id=cluster_id,
                cluster_name=svc_name,
                detection_method="directory",
                root_path=os.path.commonprefix(files).rstrip("/"),
                file_paths=files,
                node_ids=[make_kg_node_id(KGNodeType.FILE, fp) for fp in files],
                languages=service_languages.get(svc_name, set()),
                confidence="high",
            ))

        return clusters

    def _detect_by_annotations(self, kg: KnowledgeGraph) -> List[ServiceCluster]:
        """Detect services from framework annotations."""
        annotated_services: Dict[str, List[str]] = defaultdict(list)

        for node in kg.nodes.values():
            if node.node_type not in (KGNodeType.SERVICE, KGNodeType.CONTROLLER,
                                       KGNodeType.REPOSITORY):
                continue
            # Use file path directory as service name
            if node.file_path:
                parts = node.file_path.split("/")
                if len(parts) >= 2:
                    svc_name = parts[0]
                    annotated_services[svc_name].append(node.id)

        clusters = []
        for svc_name, node_ids in annotated_services.items():
            if len(node_ids) < 1:
                continue
            cluster_id = make_kg_node_id(KGNodeType.SERVICE_CLUSTER, f"ann_{svc_name}")
            clusters.append(ServiceCluster(
                cluster_id=cluster_id,
                cluster_name=svc_name,
                detection_method="annotation",
                root_path=svc_name,
                node_ids=node_ids,
                confidence="medium",
            ))

        return clusters

    def _detect_by_package(self, kg: KnowledgeGraph) -> List[ServiceCluster]:
        """Detect services from top-level package/module hierarchy."""
        pkg_files: Dict[str, List[str]] = defaultdict(list)
        pkg_languages: Dict[str, Set[str]] = defaultdict(set)

        for node in kg.nodes.values():
            if node.node_type != KGNodeType.FILE:
                continue
            fp = node.file_path
            parts = fp.split("/")
            if len(parts) >= 2:
                top_pkg = parts[0]
                pkg_files[top_pkg].append(fp)
                if node.language:
                    pkg_languages[top_pkg].add(node.language)

        clusters = []
        for pkg_name, files in pkg_files.items():
            if len(files) < 3:
                continue  # too small
            cluster_id = make_kg_node_id(KGNodeType.SERVICE_CLUSTER, f"pkg_{pkg_name}")
            clusters.append(ServiceCluster(
                cluster_id=cluster_id,
                cluster_name=pkg_name,
                detection_method="package",
                root_path=pkg_name,
                file_paths=files,
                node_ids=[make_kg_node_id(KGNodeType.FILE, fp) for fp in files],
                languages=pkg_languages.get(pkg_name, set()),
                confidence="low",
            ))

        return clusters

    # ── Business Flow Extraction ─────────────────────────────

    def extract_business_flows(
        self,
        kg: KnowledgeGraph,
    ) -> List[BusinessFlow]:
        """
        Extract business flows by tracing from API endpoints
        through handler chains to data stores.

        Each flow represents a complete request→response path.
        """
        flows: List[BusinessFlow] = []
        seen_entries: Set[str] = set()

        # Find all API endpoint nodes
        api_nodes = kg.nodes_by_type(KGNodeType.API_ENDPOINT)

        for api_node in api_nodes:
            if api_node.id in seen_entries:
                continue
            seen_entries.add(api_node.id)

            # Trace the flow from this endpoint
            flow = self._trace_flow_from_endpoint(kg, api_node)
            if flow and len(flow.node_ids) >= 2:
                flows.append(flow)

        # Also detect flows from controller methods
        for node in kg.nodes.values():
            if node.node_type in (KGNodeType.CONTROLLER,) and node.id not in seen_entries:
                seen_entries.add(node.id)
                flow = self._trace_flow_from_controller(kg, node)
                if flow and len(flow.node_ids) >= 2:
                    flows.append(flow)

        self._log(f"[business] Extracted {len(flows)} business flows")
        return flows

    def _trace_flow_from_endpoint(
        self,
        kg: KnowledgeGraph,
        api_node: KGNode,
    ) -> Optional[BusinessFlow]:
        """Trace a business flow starting from an API endpoint."""
        visited: Set[str] = set()
        flow_nodes: List[str] = []
        flow_rels: List[str] = []

        # BFS from the API endpoint's connected nodes
        # First, find who DEFINES this endpoint (handler function)
        handlers = []
        for edge in kg.incoming_edges(api_node.id):
            if edge.relation in (KGRelationType.DEFINES, KGRelationType.EXPOSES_API):
                handlers.append(edge.from_id)

        if not handlers:
            return None

        # Start the flow with the API endpoint
        flow_nodes.append(api_node.id)
        visited.add(api_node.id)

        # BFS through handlers
        queue = list(handlers)
        for handler_id in handlers:
            if handler_id not in visited:
                flow_nodes.append(handler_id)
                visited.add(handler_id)
                flow_rels.append("HANDLES")

        max_depth = 10
        depth = 0
        while queue and depth < max_depth:
            next_queue: List[str] = []
            for node_id in queue:
                for edge in kg.outgoing_edges(node_id):
                    if edge.to_id in visited:
                        continue
                    if edge.relation in (
                        KGRelationType.CALLS, KGRelationType.INVOKES,
                        KGRelationType.QUERIES_TABLE, KGRelationType.WRITES_TABLE,
                        KGRelationType.CALLS_API, KGRelationType.DEPENDS_ON,
                        KGRelationType.READS_FROM, KGRelationType.WRITES_TO,
                    ):
                        flow_nodes.append(edge.to_id)
                        flow_rels.append(edge.relation)
                        visited.add(edge.to_id)
                        next_queue.append(edge.to_id)
            queue = next_queue
            depth += 1

        # Name the flow
        flow_name = self._name_flow(api_node.name)
        flow_id = make_kg_node_id(KGNodeType.BUSINESS_FLOW, flow_name)

        return BusinessFlow(
            flow_id=flow_id,
            flow_name=flow_name,
            flow_type="api_flow",
            entry_node_id=api_node.id,
            node_ids=flow_nodes,
            edge_relations=flow_rels,
            confidence="high",
            description=f"API flow starting from {api_node.name}",
        )

    def _trace_flow_from_controller(
        self,
        kg: KnowledgeGraph,
        ctrl_node: KGNode,
    ) -> Optional[BusinessFlow]:
        """Trace a business flow from a controller node."""
        visited: Set[str] = {ctrl_node.id}
        flow_nodes: List[str] = [ctrl_node.id]
        flow_rels: List[str] = []

        # BFS through outgoing edges
        queue = [ctrl_node.id]
        max_depth = 8
        depth = 0

        while queue and depth < max_depth:
            next_queue: List[str] = []
            for node_id in queue:
                for edge in kg.outgoing_edges(node_id):
                    if edge.to_id in visited:
                        continue
                    if edge.relation in (
                        KGRelationType.CALLS, KGRelationType.CONTAINS,
                        KGRelationType.DEFINES, KGRelationType.DEPENDS_ON,
                    ):
                        flow_nodes.append(edge.to_id)
                        flow_rels.append(edge.relation)
                        visited.add(edge.to_id)
                        next_queue.append(edge.to_id)
            queue = next_queue
            depth += 1

        flow_name = f"{ctrl_node.name} Flow"
        flow_id = make_kg_node_id(KGNodeType.BUSINESS_FLOW, flow_name)

        return BusinessFlow(
            flow_id=flow_id,
            flow_name=flow_name,
            flow_type="controller_flow",
            entry_node_id=ctrl_node.id,
            node_ids=flow_nodes,
            edge_relations=flow_rels,
            confidence="medium",
            description=f"Controller flow from {ctrl_node.name}",
        )

    def _name_flow(self, endpoint_name: str) -> str:
        """Generate a human-readable flow name from an endpoint."""
        for pattern, name in _ROUTE_TO_FLOW.items():
            if re.search(pattern, endpoint_name, re.I):
                return f"{name} Flow"
        # Fallback: clean up the endpoint name
        clean = endpoint_name.strip("/").replace("/", " ").replace("_", " ")
        clean = re.sub(r"\{[^}]+\}", "", clean).strip()
        if clean:
            return f"{clean.title()} Flow"
        return "Unknown Flow"

    # ── Module Ownership ─────────────────────────────────────

    def map_module_ownership(
        self,
        kg: KnowledgeGraph,
        clusters: List[ServiceCluster],
    ) -> Dict[str, str]:
        """
        Map each file node to its owning service/module.

        Returns:
            Dict[node_id → service_cluster_name]
        """
        ownership: Dict[str, str] = {}

        for cluster in clusters:
            for node_id in cluster.node_ids:
                if node_id in kg.nodes:
                    ownership[node_id] = cluster.cluster_name
                    kg.nodes[node_id].service_boundary = cluster.cluster_name

        return ownership

    # ── Semantic Capability Mapping ──────────────────────────

    def map_business_capabilities(self, kg: KnowledgeGraph) -> int:
        """
        Groups workflows and services by domain to infer high-level
        BUSINESS_CAPABILITY nodes.
        """
        added_nodes = 0
        added_edges = 0
        
        # Group domains
        domain_to_flows = defaultdict(list)
        for flow in kg.business_flows:
            flow_node = kg.nodes.get(flow.flow_id)
            if flow_node and flow_node.business_domain:
                domain_to_flows[flow_node.business_domain].append(flow.flow_id)
                
        domain_to_svcs = defaultdict(list)
        for cluster in kg.service_clusters:
            cluster_node = kg.nodes.get(cluster.cluster_id)
            if cluster_node and cluster_node.business_domain:
                domain_to_svcs[cluster_node.business_domain].append(cluster.cluster_id)
                
        domains = set(domain_to_flows.keys()).union(domain_to_svcs.keys())
        
        for domain in domains:
            cap_name = f"{domain.title()} Capability"
            cap_id = make_kg_node_id(KGNodeType.BUSINESS_CAPABILITY, domain)
            
            cap_node = KGNode(
                id=cap_id,
                node_type=KGNodeType.BUSINESS_CAPABILITY,
                name=cap_name,
                language="domain",
                docstring=f"Enterprise Capability: {cap_name}",
                business_domain=domain,
                semantic_tags=["capability"],
            )
            kg.add_node(cap_node)
            added_nodes += 1
            
            for f_id in domain_to_flows[domain]:
                if kg.safe_add_edge(f_id, cap_id, KGRelationType.BELONGS_TO_SERVICE, evidence="Flow belongs to capability"):
                    added_edges += 1
            for s_id in domain_to_svcs[domain]:
                if kg.safe_add_edge(s_id, cap_id, KGRelationType.BELONGS_TO_SERVICE, evidence="Service belongs to capability"):
                    added_edges += 1
                    
        if self.verbose:
            print(f"[business] Mapped {added_nodes} Business Capabilities with {added_edges} edges.")
            
        return added_edges

    # ── Service Dependency Map ───────────────────────────────

    def generate_service_dependency_map(
        self,
        kg: KnowledgeGraph,
        clusters: List[ServiceCluster],
    ) -> Dict[str, Dict[str, int]]:
        """
        Generate service-to-service dependency matrix.

        Returns:
            Dict[service_name → Dict[dependent_service → edge_count]]
        """
        # Build node → service lookup
        node_to_service: Dict[str, str] = {}
        for cluster in clusters:
            for node_id in cluster.node_ids:
                node_to_service[node_id] = cluster.cluster_name

        # Count cross-service edges
        dep_map: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))

        for edge in kg.edges:
            src_svc = node_to_service.get(edge.from_id)
            tgt_svc = node_to_service.get(edge.to_id)
            if src_svc and tgt_svc and src_svc != tgt_svc:
                dep_map[src_svc][tgt_svc] += 1

        return dict(dep_map)

    # ── Semantic Tagging ─────────────────────────────────────

    def apply_semantic_tags(self, kg: KnowledgeGraph):
        """
        Apply business domain tags to nodes based on naming
        conventions and connected node patterns.
        """
        for node in kg.nodes.values():
            tags: Set[str] = set()
            searchable = (
                (node.name or "").lower() + " " +
                (node.file_path or "").lower() + " " +
                (node.docstring or "").lower()
            )

            for domain, keywords in _DOMAIN_KEYWORDS.items():
                for kw in keywords:
                    if kw in searchable:
                        tags.add(domain)
                        break

            if tags:
                node.semantic_tags = list(tags)
                if not node.business_domain:
                    # Use the most specific domain
                    node.business_domain = sorted(tags)[0]

    # ── Flow Summaries ───────────────────────────────────────

    def generate_flow_summaries(
        self,
        kg: KnowledgeGraph,
        flows: List[BusinessFlow],
    ) -> List[FlowSummary]:
        """Generate human-readable summaries for each business flow."""
        summaries: List[FlowSummary] = []

        for flow in flows:
            languages: Set[str] = set()
            services: Set[str] = set()
            tables: Set[str] = set()

            for node_id in flow.node_ids:
                node = kg.nodes.get(node_id)
                if not node:
                    continue
                if node.language:
                    languages.add(node.language)
                if node.service_boundary:
                    services.add(node.service_boundary)
                if node.node_type == KGNodeType.SQL_TABLE:
                    tables.add(node.name)

            entry_node = kg.nodes.get(flow.entry_node_id)
            entry_name = entry_node.name if entry_node else flow.entry_node_id

            # Find exit points (nodes with no outgoing flow edges)
            exit_points = []
            flow_node_set = set(flow.node_ids)
            for nid in flow.node_ids:
                has_outgoing = any(
                    e.to_id in flow_node_set
                    for e in kg.outgoing_edges(nid)
                )
                if not has_outgoing and nid != flow.entry_node_id:
                    node = kg.nodes.get(nid)
                    if node:
                        exit_points.append(node.name)

            summaries.append(FlowSummary(
                flow_id=flow.flow_id,
                flow_name=flow.flow_name,
                description=flow.description or f"Flow from {entry_name}",
                entry_point=entry_name,
                exit_points=exit_points[:10],
                node_count=len(flow.node_ids),
                languages=sorted(languages),
                services=sorted(services),
                tables_touched=sorted(tables),
            ))

        return summaries

    def _log(self, msg: str):
        if self.verbose:
            print(msg, flush=True)
