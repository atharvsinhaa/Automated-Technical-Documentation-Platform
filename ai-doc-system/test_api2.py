import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from backend.semantic_ir.ir_builder import IRBuilder
from backend.knowledge_graph.models import KGNodeType

builder = IRBuilder()
ir = builder.build("mock_repos/fastapi_crud")
kg = builder.kg
print("API endpoints in KG:")
for node in kg.nodes.values():
    if node.node_type == KGNodeType.API_ENDPOINT or node.node_type == "API_ENDPOINT":
        print(node.name)
print("Endpoints in IR:")
for ep in ir.api_endpoints:
    print(ep.method, ep.path)
print("Functions in KG:")
for node in kg.nodes.values():
    if "get" in node.name.lower() or "post" in node.name.lower():
        print(node.name, node.node_type)
        print("   Edges out:", [e.relation for e in kg.outgoing_edges(node.id)])
