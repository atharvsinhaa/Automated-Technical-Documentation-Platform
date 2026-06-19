from backend.semantic_ir.ir_builder import IRBuilder
from backend.knowledge_graph.models import KGNodeType, KGRelationType

builder = IRBuilder()
builder.build("mock_repos/fastapi_crud")
kg = builder.kg

for node in kg.nodes.values():
    if node.name == "User":
        print(f"User node: {node.id}")
        for edge in kg.outgoing_edges(node.id):
            target = kg.nodes[edge.to_id]
            print(f"  Out: {edge.relation} -> {target.node_type} {target.name}")
        for edge in kg.incoming_edges(node.id):
            source = kg.nodes[edge.from_id]
            print(f"  In: {edge.relation} <- {source.node_type} {source.name}")
