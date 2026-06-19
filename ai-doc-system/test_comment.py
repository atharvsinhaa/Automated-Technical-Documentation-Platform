import ast
from backend.comment_engine.inline_commentor import ASTInlineCommentor

class MockNode:
    def __init__(self, name, node_type, line):
        self.name = name
        self.node_type = node_type
        self.line = line
        self.semantic_role = ""

class MockNormalizer:
    def normalize_file(self, file_path):
        with open(file_path, "r") as f:
            code = f.read()
        tree = ast.parse(code)
        nodes = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                nodes.append(MockNode(node.name, "class", node.lineno))
            elif isinstance(node, ast.FunctionDef):
                nodes.append(MockNode(node.name, "function", node.lineno))
        return nodes

commentor = ASTInlineCommentor(llm_client=None, kg=None)
commentor.normalizer = MockNormalizer()
commentor.inject_comments("backend/diagram_generator/mermaid_renderer.py", "outputs/commented_code/mermaid_renderer.py")
