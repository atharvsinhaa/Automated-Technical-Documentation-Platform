import os
import json
import re

REPOS = [
    ("backend", "/Users/sarabafna/ai-doc-system/backend"),
    ("fastapi_crud", "/Users/sarabafna/ai-doc-system/mock_repos/fastapi_crud"),
    ("ecommerce", "/Users/sarabafna/ai-doc-system/mock_repos/ecommerce")
]

def extract_mermaid_nodes(mmd_content):
    """Extract nodes from Mermaid diagram. E.g. NodeID["Node Name"] -> 'Node Name'"""
    nodes = set()
    matches = re.findall(r'\["(.*?)"\]', mmd_content)
    for m in matches:
        if m and m != "No Services Discovered" and not m.startswith("No Workflow") and not m.startswith("No Data") and not m.startswith("No Integrations") and not m.startswith("No Deployment"):
            nodes.add(m.replace("\\n", " ").split("(")[0].strip())
    return nodes

for name, path in REPOS:
    print(f"\n{'='*50}\n AUDITING: {name}\n{'='*50}")
    
    # Run pipeline
    print(f"Running pipeline for {name}...")
    os.system(f"cd /Users/sarabafna/ai-doc-system && python3 pipeline.py {path} -q")
    
    # Load AIM
    aim_path = os.path.join(path, "outputs", "hld", "architecture_intelligence_model.json")
    if not os.path.exists(aim_path):
        print(f"FAILED: No AIM JSON at {aim_path}")
        continue
        
    with open(aim_path, "r") as f:
        aim_data = json.load(f)
        
    print(f"\n--- Domain & Capabilities ---")
    print(f"Domain: {aim_data.get('domain', {}).get('primary_domain', '')}")
    caps = [c['name'] for c in aim_data.get('capabilities', {}).get('core_capabilities', [])]
    print(f"Capabilities: {caps}")
    
    aim_services = {s['name'] for s in aim_data.get('services', {}).get('services', [])}
    print(f"AIM Services: {aim_services}")
    
    # Check each diagram
    diagrams_dir = os.path.join(path, "outputs", "diagrams")
    
    diagrams_to_check = {
        "Architecture Overview": "hld_architecture_diagram.mmd",
        "Service Interaction": "hld_service_diagram.mmd",
        "Data Flow": "hld_data_flow_diagram.mmd",
        "Workflow": "hld_workflow_diagram.mmd",
        "Deployment": "hld_deployment_diagram.mmd"
    }
    
    for diag_name, diag_file in diagrams_to_check.items():
        print(f"\n--- {diag_name} ---")
        file_path = os.path.join(diagrams_dir, diag_file)
        if not os.path.exists(file_path):
            print("NOT GENERATED")
            continue
            
        with open(file_path, "r") as f:
            mmd = f.read()
            
        nodes = extract_mermaid_nodes(mmd)
        print(f"Rendered Nodes: {nodes}")
        
        # Determine success
        if len(nodes) == 0:
            print("Status: WARN (Empty diagram or fallback empty)")
            continue
            
        if diag_name in ["Architecture Overview", "Service Interaction"]:
            # All rendered nodes should be in aim_services
            # Except maybe layer names like 'Domain Layer' -> wait, layers are not nodes in mermaid but subgraphs. Subgraphs don't use [""]? 
            # Oh wait, subgraph Name["Layer Name Layer"] uses [""]!
            filtered_nodes = {n for n in nodes if not n.endswith("Layer")}
            unmatched = filtered_nodes - aim_services
            
            if unmatched:
                # Let's check if there are blueprint fallback nodes like 'Root Service'
                print(f"Status: FAIL (Unmatched nodes: {unmatched})")
            else:
                print("Status: PASS")
                
        elif diag_name == "Deployment":
            units = {u['name'] for u in aim_data.get('deployment', {}).get('deployment_units', [])}
            infra = set(aim_data.get('deployment', {}).get('infrastructure_components', []))
            valid = units | infra | {aim_data.get('deployment', {}).get('hosting_model', '')}
            unmatched = {n for n in nodes if n not in valid and n not in ["Local", "Cloud-Native", "Infrastructure"]}
            if unmatched:
                print(f"Status: FAIL (Unmatched nodes: {unmatched})")
            else:
                print("Status: PASS")
                
        elif diag_name == "Data Flow":
            assets = {a['name'] for a in aim_data.get('information', {}).get('information_assets', [])}
            # Producers/Consumers could be services
            valid = assets | aim_services
            unmatched = nodes - valid
            if unmatched:
                print(f"Status: FAIL (Unmatched nodes: {unmatched})")
            else:
                print("Status: PASS")

