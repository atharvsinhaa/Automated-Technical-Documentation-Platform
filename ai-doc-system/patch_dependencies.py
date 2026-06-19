import re

with open("backend/object_model_extractor/extractor.py", "r") as f:
    code = f.read()

old_code = """for rel in node.dependencies:
                            if rel.relation_type == KGRelationType.IMPORTS:
                                target = kg.get_node(rel.target_id)"""

new_code = """for edge in kg.outgoing_edges(node.id):
                            if "IMPORT" in str(edge.relation):
                                target = kg.get_node(edge.to_id)"""

code = code.replace(old_code, new_code)

with open("backend/object_model_extractor/extractor.py", "w") as f:
    f.write(code)

print("Dependencies patched")
