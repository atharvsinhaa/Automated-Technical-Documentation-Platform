"""
dependency_extractor — Component 3: Advanced Dependency Extractor
Airtel Enterprise AI Documentation System
"""
from .extractor     import DependencyExtractor
from .models        import DependencyGraph, GraphNode, GraphEdge, NodeType, RelationType
from .exporter      import export_xml
from .neo4j_exporter import export_cypher, push_to_neo4j

__all__ = [
    "DependencyExtractor",
    "DependencyGraph", "GraphNode", "GraphEdge", "NodeType", "RelationType",
    "export_xml", "export_cypher", "push_to_neo4j",
]
__version__ = "1.0.0"
