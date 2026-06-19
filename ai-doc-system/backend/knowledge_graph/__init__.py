"""
knowledge_graph — Component 4: Neo4j Knowledge Graph Builder
Airtel Enterprise AI Documentation System

Transforms graph_dependencies.xml into an enterprise-grade Neo4j
knowledge graph optimized for business documentation generation,
HLD/LLD, GraphRAG retrieval, and offline LLM context extraction.

Fully offline — zero cloud APIs, zero SaaS dependencies.
"""

from .models import (
    KGNode, KGEdge, KnowledgeGraph,
    BusinessFlow, ServiceCluster, LineageChain,
    KGNodeType, KGRelationType, FlowSummary,
)
from .graph_loader import GraphXMLLoader
from .graph_builder import KnowledgeGraphBuilder
from .graph_schema import KGSchema
from .cypher_generator import CypherGenerator
from .apoc_loader import APOCLoader
from .neo4j_exporter import Neo4jExporter
from .business_mapper import BusinessMapper
from .lineage_builder import LineageBuilder
from .graph_indexer import GraphIndexer
from .graph_optimizer import GraphOptimizer
from .graph_stats import GraphStatistics

__all__ = [
    # Models
    "KGNode", "KGEdge", "KnowledgeGraph",
    "BusinessFlow", "ServiceCluster", "LineageChain",
    "KGNodeType", "KGRelationType", "FlowSummary",
    # Core
    "GraphXMLLoader", "KnowledgeGraphBuilder", "KGSchema",
    # Export
    "CypherGenerator", "APOCLoader", "Neo4jExporter",
    # Enrichment
    "BusinessMapper", "LineageBuilder",
    # Optimization
    "GraphIndexer", "GraphOptimizer", "GraphStatistics",
]
__version__ = "1.0.0"
