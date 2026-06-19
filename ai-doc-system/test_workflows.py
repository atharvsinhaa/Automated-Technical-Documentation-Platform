import sys
import os

from backend.semantic_ir.models import SemanticIR, IRComponent, IRRelationship
from backend.architecture_extractor.extractor import ArchitectureExtractor

def test_ecommerce():
    ir = SemanticIR(components=[], relationships=[], api_endpoints=[], data_stores=[], request_flows=[], error_paths=[], repository_type="Backend", metadata={})
    ir.components = [
        IRComponent(name="OrderController", component_type="Service", layer="Presentation", description="Handles incoming order API requests"),
        IRComponent(name="OrderValidator", component_type="Service", layer="Domain", description="Validates order payload and stock"),
        IRComponent(name="PaymentService", component_type="Service", layer="Domain", description="Processes payment with Stripe"),
        IRComponent(name="OrderRepository", component_type="Service", layer="Infrastructure", description="Persists order to SQL database"),
        IRComponent(name="NotificationService", component_type="Service", layer="Infrastructure", description="Emails receipt to customer"),
    ]
    ir.relationships = [
        IRRelationship(source="OrderController", target="OrderValidator", relationship_type="CALLS"),
        IRRelationship(source="OrderValidator", target="PaymentService", relationship_type="CALLS"),
        IRRelationship(source="PaymentService", target="OrderRepository", relationship_type="CALLS"),
        IRRelationship(source="OrderRepository", target="NotificationService", relationship_type="PUBLISHES_TO")
    ]
    extractor = ArchitectureExtractor()
    workflows = extractor._extract_workflows(ir)
    print("=== E-Commerce App ===")
    for wf in workflows:
        print(f"Name: {wf.name}")
        for step in wf.steps:
            print(f"  {step}")
    print()

def test_etl():
    ir = SemanticIR(components=[], relationships=[], api_endpoints=[], data_stores=[], request_flows=[], error_paths=[], repository_type="Backend", metadata={})
    ir.components = [
        IRComponent(name="DataIngestionService", component_type="Service", layer="Infrastructure", description="Polls Kafka for raw events"),
        IRComponent(name="DataNormalizer", component_type="Service", layer="Domain", description="Cleans and normalizes JSON payload"),
        IRComponent(name="AnalyticsMapper", component_type="Service", layer="Domain", description="Transforms data into reporting schema"),
        IRComponent(name="DataWarehouseStore", component_type="Service", layer="Infrastructure", description="Saves analytic records to BigQuery"),
        IRComponent(name="DashboardReporter", component_type="Service", layer="Presentation", description="Generates daily metrics dashboard"),
    ]
    ir.relationships = [
        IRRelationship(source="DataIngestionService", target="DataNormalizer", relationship_type="FEEDS_DATA_TO"),
        IRRelationship(source="DataNormalizer", target="AnalyticsMapper", relationship_type="FEEDS_DATA_TO"),
        IRRelationship(source="AnalyticsMapper", target="DataWarehouseStore", relationship_type="FEEDS_DATA_TO"),
        IRRelationship(source="DataWarehouseStore", target="DashboardReporter", relationship_type="CALLS")
    ]
    extractor = ArchitectureExtractor()
    workflows = extractor._extract_workflows(ir)
    print("=== ETL / Data Pipeline ===")
    for wf in workflows:
        print(f"Name: {wf.name}")
        for step in wf.steps:
            print(f"  {step}")
    print()

if __name__ == "__main__":
    test_ecommerce()
    test_etl()
