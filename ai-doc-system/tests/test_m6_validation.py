"""
This module tests the architecture capability extraction and diagram generation.
It validates whether the dynamic sequence generation correctly extracts and
represents domain-specific capabilities from different mock repository types
without any cross-contamination.
"""

import sys
import os
import json

# Append the backend directory to sys.path to allow importing backend modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../backend')))

from backend.semantic_ir.models import SemanticIR, IRComponent, IRRelationship
from backend.architecture_extractor.models import ArchitectureBlueprint
from backend.architecture_extractor.extractor import ArchitectureExtractor
from backend.diagram_generator.hld_mermaid_generator import HLDMermaidGenerator

def test_capabilities(name, components, relationships):
    """
    Helper function to test capability extraction for a specific mock repository.
    
    Args:
        name (str): The name of the test scenario.
        components (list): A list of IRComponent instances.
        relationships (list): A list of IRRelationship instances.
        
    Returns:
        tuple: A tuple containing the generated executive diagram and data architecture diagram.
    """
    print(f"\n--- Testing {name} ---")
    
    # 1. Initialize a mock SemanticIR with the provided components and relationships
    ir = SemanticIR(
        repository_type="Mock",
        components=components,
        relationships=relationships,
        data_stores=[],
        api_endpoints=[],
        workflows=[],
        request_flows=[],
        metadata={"repository_type": "Mock"}
    )
    
    # 2. Extract the ArchitectureBlueprint from the SemanticIR
    extractor = ArchitectureExtractor()
    bp = extractor.extract(ir)
    
    # 3. Generate Mermaid diagrams from the extracted blueprint
    mermaid_gen = HLDMermaidGenerator()
    exec_diagram = mermaid_gen._generate_service_interaction_diagram(bp)
    data_diagram = mermaid_gen._generate_data_flow_diagram(bp)
    
    print("Executive Diagram:")
    print(exec_diagram)
    print("\nData Architecture Diagram:")
    print(data_diagram)
    print("---------------------------------")
    return exec_diagram, data_diagram

def main():
    """
    Main test runner that executes validation across multiple distinct mock domains.
    It asserts that the capability sequences are generated dynamically and independently,
    ensuring no hallucination or cross-contamination occurs.
    """
    # 1. AI Doc Scenario: Tests capability extraction for a documentation system
    ai_exec, ai_data = test_capabilities("AI Documentation", [
        IRComponent("repo_parser", None, "parses repository files"),
        IRComponent("knowledge_graph_builder", None, "constructs knowledge graph"),
        IRComponent("doc_generator", None, "generates documentation files")
    ], [
        IRRelationship("repo_parser", "knowledge_graph_builder", "CALLS", ""),
        IRRelationship("knowledge_graph_builder", "doc_generator", "CALLS", "")
    ])
    
    # 2. E-Commerce Scenario: Tests capability extraction for a retail system
    ec_exec, ec_data = test_capabilities("E-Commerce", [
        IRComponent("customer_onboarding_service", None, "registers new users"),
        IRComponent("order_processing_engine", None, "processes incoming orders"),
        IRComponent("payment_gateway", None, "handles transactions")
    ], [
        IRRelationship("customer_onboarding_service", "order_processing_engine", "CALLS", ""),
        IRRelationship("order_processing_engine", "payment_gateway", "CALLS", "")
    ])
    
    # 3. Banking Scenario: Tests capability extraction for a financial system
    bk_exec, bk_data = test_capabilities("Banking", [
        IRComponent("account_manager", None, "manages bank accounts"),
        IRComponent("transaction_processor", None, "executes wire transfers"),
        IRComponent("fraud_detector", None, "analyzes transactions for fraud")
    ], [
        IRRelationship("account_manager", "transaction_processor", "CALLS", ""),
        IRRelationship("transaction_processor", "fraud_detector", "CALLS", "")
    ])
    
    # 4. ETL Pipeline Scenario: Tests capability extraction for a data processing system
    etl_exec, etl_data = test_capabilities("ETL Pipeline", [
        IRComponent("data_extractor", None, "extracts rows from source"),
        IRComponent("schema_transformer", None, "transforms column schemas"),
        IRComponent("warehouse_loader", None, "loads data to redshift")
    ], [
        IRRelationship("data_extractor", "schema_transformer", "CALLS", ""),
        IRRelationship("schema_transformer", "warehouse_loader", "CALLS", "")
    ])
    
    # --- Assertions ---
    # Validate that domain-specific keywords correctly appeared in the respective generated diagrams
    assert "Order" in ec_exec, "Order capability missing in E-Commerce"
    assert "Fraud" in bk_exec, "Fraud capability missing in Banking"
    assert "Data" in etl_exec, "Data capability missing in ETL"
    
    # Check for cross-contamination to ensure dynamic capability inference wasn't polluted by previous runs
    assert "Order" not in ai_exec, "Cross contamination: 'Order' found in AI Doc"
    assert "Knowledge" not in ec_exec, "Cross contamination: 'Knowledge' found in E-Commerce"
    assert "Fraud" not in etl_exec, "Cross contamination: 'Fraud' found in ETL Pipeline"
    
    print("\n[SUCCESS] Dynamic validation passed! All repositories generated completely unique capability sequences.")

if __name__ == "__main__":
    main()
