import sys
from backend.dependency_extractor.ast_parser import PythonASTParser
from backend.dependency_extractor.graph_builder import GraphBuilder
from backend.knowledge_graph.models import KGNodeType

gb = GraphBuilder("mock_repos/fastapi_crud")
kg = gb.build()
print("API_ENDPOINTS:", len(kg.nodes_by_type(KGNodeType.API_ENDPOINT)))
print("DECORATORS:", len(kg.nodes_by_type(KGNodeType.DECORATOR)))
for n in kg.nodes_by_type(KGNodeType.DECORATOR):
    print("Dec:", n.name)
for n in kg.nodes_by_type(KGNodeType.API_ENDPOINT):
    print("API:", n.name)
