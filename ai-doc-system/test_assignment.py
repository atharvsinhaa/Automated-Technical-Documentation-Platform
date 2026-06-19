from backend.semantic_ir.ir_builder import IRBuilder
from backend.knowledge_graph.models import KGNodeType

builder = IRBuilder()
builder.build("mock_repos/fastapi_crud")
kg = builder.kg
print("ASSIGNMENT nodes in KG:")
for node in kg.nodes.values():
    if node.node_type in (KGNodeType.ASSIGNMENT, KGNodeType.PROPERTY, KGNodeType.VARIABLE, "ASSIGNMENT"):
        print(node.name, node.node_type)
        print("  In:", [e.relation for e in kg.incoming_edges(node.id)])
