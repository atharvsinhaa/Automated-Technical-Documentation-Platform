from backend.universal_ast.normalizer import (
    UniversalASTNormalizer
)

normalizer = UniversalASTNormalizer()

nodes = normalizer.normalize_file(
    "backend/ast_engine/main.py"
)

print("\n===== UNIVERSAL AST =====\n")

for node in nodes:

    print(
        f"{node.node_type} | "
        f"{node.name} | "
        f"{node.semantic_role}"
    )