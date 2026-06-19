import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from backend.dependency_extractor.graph_builder import GraphBuilder
from backend.knowledge_graph.models import KGNodeType

gb = GraphBuilder("mock_repos/fastapi_crud")
kg = gb.build()
print("API endpoints:")
for node in kg.nodes.values():
    if node.node_type == KGNodeType.API_ENDPOINT or node.node_type == "API_ENDPOINT":
        print(node.name)
print("Functions:")
for node in kg.nodes.values():
    if "get" in node.name.lower():
        print(node.name, node.node_type)
