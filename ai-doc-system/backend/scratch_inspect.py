import json

with open('backend/outputs/knowledge_graph/knowledge_graph.json', 'r') as f:
    data = json.load(f)

for node in data.get('nodes', []):
    if node.get('parent_id') and node.get('type') in ('METHOD', 'FUNCTION', 'CONSTRUCTOR'):
        print(f"Found method {node['name']} with parent {node['parent_id']}")
        break
print("Done.")
