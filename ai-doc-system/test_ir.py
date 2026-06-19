from backend.ir_builder.builder import IRBuilder
from backend.knowledge_graph.models import KGNodeType

builder = IRBuilder()
ir = builder.build("mock_repos/fastapi_crud")
kg = getattr(builder, "kg", None)
print("KG:", kg is not None)
if kg:
    print("API_ENDPOINTS:", len(kg.nodes_by_type(KGNodeType.API_ENDPOINT)))
    print("DECORATORS:", len(kg.nodes_by_type(KGNodeType.DECORATOR)))
    for n in kg.nodes_by_type(KGNodeType.DECORATOR):
        print("Dec:", n.name)
    for n in kg.nodes_by_type(KGNodeType.API_ENDPOINT):
        print("API:", n.name)
