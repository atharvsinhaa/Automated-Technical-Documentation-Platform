"""
knowledge_graph/architecture_mapper.py
────────────────────────────────────────────────────────────────
Enterprise Architecture Inference Engine.

Infers HLD and LLD architecture from the semantic graph:

HLD:
  - MICROSERVICE: Promoted from ServiceClusters
  - BOUNDED_CONTEXT: Clustered by business_domain
  - DOMAIN_LAYER: Presentation / Application / Domain / Infrastructure
  - EVENT_BUS: Kafka / RabbitMQ / message broker detection
  - DATA_PIPELINE: Spark / ETL inference

LLD:
  - CONTROL_FLOW: If/else/switch/try-catch branching
  - EXECUTES_AFTER: Ordered call sequence within handlers
  - RETURNS_TO: Exception flow → catch blocks
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Dict, List, Optional, Set

from .models import (
    KnowledgeGraph, KGNode, KGEdge,
    KGNodeType, KGRelationType, make_kg_node_id,
)


class ArchitectureMapper:
    """Infers HLD/LLD architecture from semantic graph patterns."""

    def __init__(self, verbose: bool = True):
        self.verbose = verbose

        # Layer inference keywords (directory/module name patterns)
        self.layer_patterns = {
            "Presentation": [
                "controller", "handler", "view", "route", "endpoint",
                "api", "rest", "graphql", "grpc", "pages", "components",
                "ui", "frontend", "templates",
            ],
            "Application": [
                "service", "usecase", "use_case", "application", "facade",
                "orchestrator", "workflow", "command", "query",
            ],
            "Domain": [
                "model", "entity", "domain", "aggregate", "value_object",
                "repository", "specification", "event",
            ],
            "Infrastructure": [
                "repository_impl", "adapter", "gateway", "client",
                "config", "migration", "middleware", "util", "helper",
                "db", "cache", "queue", "kafka", "rabbit",
            ],
        }

        # Message broker / Event bus patterns
        self.event_bus_patterns = [
            re.compile(r"\b(kafka|KafkaProducer|KafkaConsumer)\b", re.I),
            re.compile(r"\b(rabbit|RabbitMQ|amqp)\b", re.I),
            re.compile(r"\b(celery|dramatiq|huey)\b", re.I),
            re.compile(r"\b(EventBus|MessageBus|eventbus)\b", re.I),
            re.compile(r"\b(pubsub|publish|subscribe|emit|on_event)\b", re.I),
            re.compile(r"\b(redis_queue|bull|nats)\b", re.I),
        ]

        # Data pipeline patterns
        self.pipeline_patterns = [
            re.compile(r"\b(spark|pyspark|SparkSession)\b", re.I),
            re.compile(r"\b(airflow|dag|luigi)\b", re.I),
            re.compile(r"\b(etl|extract_transform|data_pipeline)\b", re.I),
            re.compile(r"\b(beam|flink|dataflow)\b", re.I),
        ]

    def map_architecture(self, kg: KnowledgeGraph) -> int:
        """
        Run full HLD + LLD architecture inference.
        Returns total new nodes + edges created.
        """
        total = 0
        total += self._map_hld(kg)
        total += self._map_lld(kg)
        return total

    def _map_hld(self, kg: KnowledgeGraph) -> int:
        """Map High-Level Design architecture."""
        hld_nodes = 0
        hld_edges = 0

        # 1. Promote ServiceClusters → MICROSERVICE nodes
        #    Confidence gate: skip weak clusters (low confidence + few files)
        for cluster in kg.service_clusters:
            # Skip low-confidence clusters with trivial file count
            if (
                cluster.confidence == "low"
                and len(cluster.file_paths) < 3
            ):
                if self.verbose:
                    print(
                        f"  [arch-mapper] Skipping weak cluster: "
                        f"{cluster.cluster_name} "
                        f"(confidence={cluster.confidence}, "
                        f"files={len(cluster.file_paths)})"
                    )
                continue

            ms_id = make_kg_node_id(KGNodeType.MICROSERVICE, cluster.cluster_name)
            ms_node = KGNode(
                id=ms_id,
                node_type=KGNodeType.MICROSERVICE,
                name=cluster.cluster_name,
                language=",".join(sorted(cluster.languages)) if cluster.languages else "multi",
                file_path=cluster.root_path,
                docstring=f"Microservice: {cluster.cluster_name} ({len(cluster.file_paths)} files)",
                semantic_tags=["microservice", "hld"],
            )
            kg.add_node(ms_node)
            hld_nodes += 1

            # Link cluster → microservice
            if kg.safe_add_edge(
                cluster.cluster_id, ms_id,
                KGRelationType.MAPS_TO,
                confidence="high",
                evidence="Service cluster promoted to Microservice (HLD)",
            ):
                hld_edges += 1

        # 2. BOUNDED_CONTEXT: group by business_domain
        domain_groups: Dict[str, Set[str]] = defaultdict(set)
        for node in kg.nodes.values():
            if node.business_domain:
                domain_groups[node.business_domain].add(node.id)

        for domain, member_ids in domain_groups.items():
            if len(member_ids) < 2:
                continue
            bc_id = make_kg_node_id(KGNodeType.BOUNDED_CONTEXT, domain)
            bc_node = KGNode(
                id=bc_id,
                node_type=KGNodeType.BOUNDED_CONTEXT,
                name=f"{domain} Context",
                language="multi",
                docstring=f"Bounded Context: {domain} ({len(member_ids)} entities)",
                semantic_tags=["ddd", "bounded_context", "hld"],
            )
            kg.add_node(bc_node)
            hld_nodes += 1

        # 3. EVENT_BUS: detect message brokers
        for node in list(kg.nodes.values()):
            text = f"{node.name} {node.body_preview or ''} {node.file_path or ''}"
            bus_type = self._detect_event_bus(text)
            if bus_type:
                bus_id = make_kg_node_id(KGNodeType.EVENT_BUS, f"{bus_type}_{node.file_path or node.name}")
                bus_node = KGNode(
                    id=bus_id,
                    node_type=KGNodeType.EVENT_BUS,
                    name=f"{bus_type} Event Bus",
                    language=node.language,
                    file_path=node.file_path,
                    docstring=f"Event Bus ({bus_type}) detected in {node.file_path}",
                    semantic_tags=["event_bus", "messaging", "hld"],
                )
                kg.add_node(bus_node)
                hld_nodes += 1

                # Determine publish vs subscribe
                is_pub = any(kw in text.lower() for kw in
                             ("produce", "publish", "send", "emit", "dispatch"))
                is_sub = any(kw in text.lower() for kw in
                             ("consume", "subscribe", "on_", "listener", "handler"))

                if is_pub:
                    if kg.safe_add_edge(
                        node.id, bus_id, KGRelationType.PUBLISHES_TO,
                        confidence="medium",
                        evidence=f"Publishes to {bus_type}",
                    ):
                        hld_edges += 1
                if is_sub:
                    if kg.safe_add_edge(
                        bus_id, node.id, KGRelationType.SUBSCRIBES_FROM,
                        confidence="medium",
                        evidence=f"Subscribes from {bus_type}",
                    ):
                        hld_edges += 1

        # 4. DOMAIN_LAYER: classify files into architectural layers
        for node in list(kg.nodes.values()):
            if node.node_type != KGNodeType.FILE:
                continue
            layer = self._classify_layer(node)
            if layer:
                layer_id = make_kg_node_id(KGNodeType.DOMAIN_LAYER, f"layer_{layer}")
                if layer_id not in kg.nodes:
                    layer_node = KGNode(
                        id=layer_id,
                        node_type=KGNodeType.DOMAIN_LAYER,
                        name=f"{layer} Layer",
                        language="arch",
                        docstring=f"Architecture Layer: {layer}",
                        semantic_tags=["hld", "ddd", "layer"],
                    )
                    kg.add_node(layer_node)
                    hld_nodes += 1

                if kg.safe_add_edge(
                    node.id, layer_id,
                    KGRelationType.BELONGS_TO_SERVICE,
                    confidence="low",
                    evidence=f"File classified as {layer} layer",
                ):
                    hld_edges += 1

        # 5. DATA_PIPELINE: detect Spark/ETL patterns
        for node in list(kg.nodes.values()):
            text = f"{node.name} {node.body_preview or ''} {node.file_path or ''}"
            pipeline_type = self._detect_pipeline(text)
            if pipeline_type:
                dp_id = make_kg_node_id(KGNodeType.DATA_PIPELINE, f"pipeline_{node.name}")
                dp_node = KGNode(
                    id=dp_id,
                    node_type=KGNodeType.DATA_PIPELINE,
                    name=f"{pipeline_type} Pipeline: {node.name}",
                    language=node.language,
                    file_path=node.file_path,
                    docstring=f"Data Pipeline ({pipeline_type}) from {node.name}",
                    semantic_tags=["data_pipeline", "etl", "hld"],
                )
                kg.add_node(dp_node)
                hld_nodes += 1
                if kg.safe_add_edge(
                    node.id, dp_id, KGRelationType.CALLS,
                    confidence="medium",
                    evidence=f"{pipeline_type} pipeline detected",
                ):
                    hld_edges += 1

        if self.verbose:
            print(f"[arch-mapper] HLD: Created {hld_nodes} architecture nodes and {hld_edges} edges.")

        return hld_nodes + hld_edges

    def _map_lld(self, kg: KnowledgeGraph) -> int:
        """Map Low-Level Design: control flow, execution order, exception flows."""
        lld_edges = 0

        # 1. EXECUTES_AFTER: Ordered call sequence within function bodies
        for node in kg.nodes.values():
            if node.node_type not in (
                KGNodeType.FUNCTION, KGNodeType.ASYNC_FUNCTION,
                KGNodeType.METHOD, KGNodeType.CONSTRUCTOR,
            ):
                continue
            if not node.body_preview:
                continue

            # Find all function calls in body, in order
            callees = kg.outgoing_edges(node.id)
            call_edges = [e for e in callees if e.relation in (
                KGRelationType.CALLS, KGRelationType.CALLS_API,
            )]

            # Create EXECUTES_AFTER chains between consecutive calls
            call_targets = [e.to_id for e in call_edges]
            for i in range(len(call_targets) - 1):
                if kg.safe_add_edge(
                    call_targets[i], call_targets[i + 1],
                    KGRelationType.EXECUTES_AFTER,
                    confidence="medium",
                    evidence=f"Sequential call in {node.name}",
                    business_context=f"Called in order by {node.name}",
                ):
                    lld_edges += 1

        # 2. CONTROL_FLOW: if/else/try-catch patterns
        for node in kg.nodes.values():
            if not node.body_preview:
                continue

            bp = node.body_preview.lower()

            # Detect branching patterns
            has_if = "if " in bp or "if(" in bp
            has_try = "try " in bp or "try:" in bp or "try{" in bp
            has_switch = "switch " in bp or "match " in bp

            if has_if or has_try or has_switch:
                # Check if node calls other functions — those are control flow targets
                call_edges = [
                    e for e in kg.outgoing_edges(node.id)
                    if e.relation == KGRelationType.CALLS
                ]
                for edge in call_edges:
                    if kg.safe_add_edge(
                        node.id, edge.to_id,
                        KGRelationType.CONTROL_FLOW,
                        confidence="low",
                        evidence=f"Conditional call from {node.name}",
                    ):
                        lld_edges += 1

            # 3. Exception flow: try→catch returns
            if has_try:
                for edge in kg.outgoing_edges(node.id):
                    target = kg.nodes.get(edge.to_id)
                    if target and any(kw in target.name.lower() for kw in
                                       ("error", "exception", "catch", "handler", "fallback")):
                        if kg.safe_add_edge(
                            node.id, target.id,
                            KGRelationType.RETURNS_TO,
                            confidence="low",
                            evidence=f"Exception flow from {node.name} to {target.name}",
                        ):
                            lld_edges += 1

        if self.verbose:
            print(f"[arch-mapper] LLD: Mapped {lld_edges} control flow edges.")

        return lld_edges

    def _detect_event_bus(self, text: str) -> Optional[str]:
        """Detect message bus type from text."""
        for pat in self.event_bus_patterns:
            m = pat.search(text)
            if m:
                token = m.group(1).lower()
                if "kafka" in token:
                    return "Kafka"
                if "rabbit" in token or "amqp" in token:
                    return "RabbitMQ"
                if "celery" in token or "dramatiq" in token:
                    return "TaskQueue"
                if "redis" in token:
                    return "Redis"
                if "nats" in token:
                    return "NATS"
                return "EventBus"
        return None

    def _detect_pipeline(self, text: str) -> Optional[str]:
        """Detect data pipeline type from text."""
        for pat in self.pipeline_patterns:
            m = pat.search(text)
            if m:
                token = m.group(1).lower()
                if "spark" in token or "pyspark" in token:
                    return "Spark"
                if "airflow" in token or "dag" in token:
                    return "Airflow"
                if "beam" in token:
                    return "Beam"
                if "flink" in token:
                    return "Flink"
                return "ETL"
        return None

    def _classify_layer(self, node: KGNode) -> Optional[str]:
        """Classify a file node into an architectural layer."""
        text = f"{node.file_path or ''} {node.name}".lower()
        for layer, keywords in self.layer_patterns.items():
            for kw in keywords:
                if kw in text:
                    return layer
        return None
