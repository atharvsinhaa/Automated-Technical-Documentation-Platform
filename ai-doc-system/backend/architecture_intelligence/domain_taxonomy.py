"""
architecture_intelligence/domain_taxonomy.py
────────────────────────────────────────────────────────────────
Domain taxonomy and signal vocabulary.

Defines 11 domain archetypes, each with:
    - Signal words (matched against repository evidence)
    - Business functions (injected into DomainModel)
    - Bounded contexts (injected into DomainModel)
    - Document theme (controls HLD framing)
"""

from __future__ import annotations

from typing import Dict, Any


DOMAIN_TAXONOMY: Dict[str, Dict[str, Any]] = {
    "E-Commerce": {
        "signals": [
            "product", "cart", "checkout", "order", "inventory", "catalog",
            "sku", "shipping", "fulfillment", "merchant", "storefront",
            "stripe", "paypal", "shopify", "woocommerce", "customer",
            "wishlist", "coupon", "discount", "price",
        ],
        "business_functions": [
            "Product Discovery", "Order Management", "Payment Processing",
            "Inventory Management", "Customer Management",
        ],
        "bounded_contexts": [
            "Catalog", "Orders", "Payments", "Customers", "Fulfillment",
        ],
        "core_information_assets": [
            "Product Catalog", "Shopping Cart", "Customer Order", "Payment Transaction", "Inventory Record",
        ],
        "primary_flows": [
            {
                "name": "Customer Purchase Flow",
                "stages": ["Product Discovery", "Cart Assembly", "Order Checkout", "Payment Capture", "Fulfillment"],
                "trigger": "Customer initiates purchase",
                "outcome": "Order fulfilled and payment collected",
            },
        ],
        "document_theme": "Platform",
    },
    "Financial Services": {
        "signals": [
            "account", "transaction", "ledger", "balance", "transfer", "payment",
            "banking", "loan", "credit", "debit", "portfolio", "trade",
            "plaid", "fintrac", "aml", "kyc", "clearing", "settlement",
            "interest", "deposit", "withdrawal", "forex",
        ],
        "business_functions": [
            "Account Management", "Transaction Processing", "Risk Management",
            "Compliance Monitoring", "Reporting & Analytics",
        ],
        "bounded_contexts": [
            "Accounts", "Transactions", "Risk", "Compliance", "Reporting",
        ],
        "core_information_assets": [
            "Account Record", "Transaction Ledger", "Customer Profile", "Loan Application", "Compliance Report",
        ],
        "primary_flows": [
            {
                "name": "Transaction Processing Flow",
                "stages": ["Transaction Initiation", "Validation & Authorization", "Settlement", "Reconciliation"],
                "trigger": "Customer initiates financial transaction",
                "outcome": "Transaction settled and ledger updated",
            },
        ],
        "document_theme": "System",
    },
    "Healthcare IT": {
        "signals": [
            "patient", "encounter", "diagnosis", "clinical", "ehr", "emr", "fhir",
            "hl7", "procedure", "medication", "prescription", "provider", "claims",
            "icd", "cpt", "hipaa", "appointment", "referral",
            "vital", "allergy", "immunization",
        ],
        "business_functions": [
            "Patient Management", "Clinical Documentation", "Claims Processing",
            "Care Coordination", "Compliance & Reporting",
        ],
        "bounded_contexts": [
            "Patients", "Encounters", "Claims", "Clinical", "Providers",
        ],
        "core_information_assets": [
            "Patient Record", "Clinical Encounter", "Medical Claim", "Prescription", "Lab Result",
        ],
        "primary_flows": [
            {
                "name": "Patient Care Flow",
                "stages": ["Patient Registration", "Clinical Encounter", "Diagnosis & Treatment", "Claims Submission", "Follow-Up"],
                "trigger": "Patient presents for care",
                "outcome": "Treatment delivered and claim filed",
            },
        ],
        "document_theme": "System",
    },
    "CRM & Sales": {
        "signals": [
            "lead", "opportunity", "contact", "deal", "pipeline", "crm", "prospect",
            "salesforce", "hubspot", "campaign", "forecast", "quota", "territory",
            "funnel", "engagement", "nurture",
        ],
        "business_functions": [
            "Lead Management", "Opportunity Tracking", "Customer Engagement",
            "Sales Forecasting", "Campaign Management",
        ],
        "bounded_contexts": [
            "Leads", "Opportunities", "Contacts", "Campaigns", "Analytics",
        ],
        "core_information_assets": [
            "Sales Lead", "Sales Opportunity", "Customer Contact", "Marketing Campaign", "Sales Forecast",
        ],
        "primary_flows": [
            {
                "name": "Sales Pipeline Flow",
                "stages": ["Lead Capture", "Qualification", "Opportunity Development", "Proposal", "Close"],
                "trigger": "New lead enters the system",
                "outcome": "Deal closed or opportunity archived",
            },
        ],
        "document_theme": "Application",
    },
    "Logistics & Supply Chain": {
        "signals": [
            "shipment", "route", "warehouse", "cargo", "freight", "tracking",
            "dispatch", "fleet", "delivery", "manifest", "consignment", "carrier",
            "logistics", "supply_chain", "dock", "pallet",
        ],
        "business_functions": [
            "Shipment Tracking", "Route Optimization", "Warehouse Management",
            "Fleet Management", "Last-Mile Delivery",
        ],
        "bounded_contexts": [
            "Shipments", "Routes", "Warehouse", "Fleet", "Delivery",
        ],
        "core_information_assets": [
            "Shipment Manifest", "Delivery Route", "Warehouse Inventory", "Carrier Contract", "Dispatch Order",
        ],
        "primary_flows": [
            {
                "name": "Order Fulfillment Flow",
                "stages": ["Order Received", "Warehouse Pick", "Shipment Dispatch", "In-Transit Tracking", "Delivery Confirmation"],
                "trigger": "Customer order placed",
                "outcome": "Package delivered to customer",
            },
        ],
        "document_theme": "Platform",
    },
    "Telecom": {
        "signals": [
            "subscriber", "subscription", "billing", "tariff", "network", "roaming",
            "provisioning", "sms", "voip", "cdr", "rating", "charging",
            "twilio", "asterisk", "sip", "imsi", "msisdn",
        ],
        "business_functions": [
            "Subscriber Management", "Network Provisioning", "Billing & Charging",
            "Service Activation", "Usage Rating",
        ],
        "bounded_contexts": [
            "Subscribers", "Products", "Billing", "Network", "Usage",
        ],
        "core_information_assets": [
            "Subscriber Profile", "Billing Record", "Call Detail Record", "Network Configuration", "Service Plan",
        ],
        "primary_flows": [
            {
                "name": "Service Activation Flow",
                "stages": ["Subscription Request", "Provisioning", "Service Activation", "Usage Rating", "Billing"],
                "trigger": "Subscriber requests new service",
                "outcome": "Service activated and billing initiated",
            },
        ],
        "document_theme": "System",
    },
    "Insurance": {
        "signals": [
            "policy", "claim", "premium", "underwriting", "insured", "coverage",
            "adjuster", "actuary", "risk", "deductible", "beneficiary", "renewal",
            "endorsement", "exclusion",
        ],
        "business_functions": [
            "Policy Management", "Claims Processing", "Underwriting",
            "Risk Assessment", "Premium Collection",
        ],
        "bounded_contexts": [
            "Policies", "Claims", "Underwriting", "Customers", "Finance",
        ],
        "core_information_assets": [
            "Insurance Policy", "Insurance Claim", "Customer Profile", "Premium Payment", "Underwriting Record",
        ],
        "primary_flows": [
            {
                "name": "Claims Processing Flow",
                "stages": ["Claim Submission", "Initial Review", "Investigation & Assessment", "Adjudication", "Settlement"],
                "trigger": "Policyholder submits a claim",
                "outcome": "Claim settled or denied with rationale",
            },
        ],
        "document_theme": "System",
    },
    "Data Platform": {
        "signals": [
            "pipeline", "etl", "ingestion", "transformation", "warehouse", "lake",
            "spark", "kafka", "airflow", "dbt", "schema", "partition", "lineage",
            "batch", "streaming", "aggregation", "mart", "tableau", "looker",
        ],
        "business_functions": [
            "Data Ingestion", "Data Transformation", "Data Serving",
            "Data Quality", "Data Governance",
        ],
        "bounded_contexts": [
            "Ingestion", "Processing", "Storage", "Serving", "Governance",
        ],
        "core_information_assets": [
            "Data Pipeline", "Data Dataset", "ETL Job", "Data Lineage", "Data Quality Report",
        ],
        "primary_flows": [
            {
                "name": "Data Processing Flow",
                "stages": ["Source Ingestion", "Staging", "Transformation", "Quality Validation", "Serving"],
                "trigger": "New data arrives from source systems",
                "outcome": "Clean, transformed data available for consumption",
            },
        ],
        "document_theme": "Platform",
    },
    "AI & ML Platform": {
        "signals": [
            "machine_learning", "training", "inference", "embedding", "vector", "llm",
            "neural", "experiment", "mlflow", "pytorch", "dataset", "tensor",
            "tensorflow", "ollama", "openai", "rag", "fine-tuning", "tokenizer",
            "prompt", "transformer", "bert", "gpt",
        ],
        "business_functions": [
            "Model Training", "Model Serving", "Feature Engineering",
            "Experiment Tracking", "Model Monitoring",
        ],
        "bounded_contexts": [
            "Models", "Training", "Inference", "Features", "Evaluation",
        ],
        "core_information_assets": [
            "Machine Learning Model", "Training Dataset", "Feature Store", "Inference Log", "Experiment Tracking Record",
        ],
        "primary_flows": [
            {
                "name": "ML Model Lifecycle Flow",
                "stages": ["Data Preparation", "Feature Engineering", "Model Training", "Evaluation", "Deployment & Serving"],
                "trigger": "New training data or model request",
                "outcome": "Model deployed and serving predictions",
            },
        ],
        "document_theme": "Platform",
    },
    "Architecture Documentation Platform": {
        "signals": [
            "architecture", "documentation", "diagram", "mermaid", "markdown",
            "docx", "hld", "lld", "extractor", "semantic", "ir", "parser",
        ],
        "business_functions": [
            "Code Analysis", "Architecture Discovery", "Knowledge Modeling",
            "Documentation Generation", "Diagram Rendering",
        ],
        "bounded_contexts": [
            "Extraction", "Modeling", "Generation", "Analysis",
        ],
        "core_information_assets": [
            "Source Code", "AST Model", "Dependency Graph", "Architecture Context", "Documentation Artifact",
        ],
        "primary_flows": [
            {
                "name": "Documentation Generation Flow",
                "stages": ["Repository Ingestion", "Code Analysis", "Architecture Discovery", "Knowledge Modeling", "Document Rendering"],
                "trigger": "Repository submitted for analysis",
                "outcome": "HLD and LLD documents generated",
            },
        ],
        "document_theme": "Platform",
    },
    "Developer Platform": {
        "signals": [
            "repository", "ci", "cd", "deployment", "artifact", "pipeline",
            "build", "test", "lint", "container", "kubernetes", "helm",
            "github", "gitlab", "webhook", "registry", "sdk", "cli",
            "documentation", "ast", "parser", "code_analysis",
        ],
        "business_functions": [
            "Build Automation", "Code Quality", "Deployment Management",
            "Artifact Management", "Developer Experience",
        ],
        "bounded_contexts": [
            "Build", "Test", "Deploy", "Artifacts", "Monitoring",
        ],
        "core_information_assets": [
            "Code Repository", "CI/CD Pipeline", "Build Artifact", "Deployment Configuration", "Test Result",
        ],
        "primary_flows": [
            {
                "name": "CI/CD Pipeline Flow",
                "stages": ["Code Commit", "Build & Compile", "Test Execution", "Artifact Packaging", "Deployment"],
                "trigger": "Developer pushes code to repository",
                "outcome": "Artifact deployed to target environment",
            },
        ],
        "document_theme": "Platform",
    },
    "Enterprise Application": {
        "signals": [
            "user", "role", "permission", "workflow", "approval", "notification",
            "report", "dashboard", "admin", "configuration", "audit", "integration",
            "tenant", "organization", "mvc", "crud", "api", "controller", "endpoint", "rest", "graphql",
        ],
        "business_functions": [
            "User Management", "Workflow Automation", "Reporting",
            "Configuration Management", "Integration Management",
        ],
        "bounded_contexts": [
            "Users", "Workflows", "Reporting", "Administration", "Integration",
        ],
        "core_information_assets": [
            "User Profile", "Role Configuration", "System Audit Log", "Workflow Definition", "Business Report",
        ],
        "primary_flows": [
            {
                "name": "User Request Flow",
                "stages": ["Authentication", "Request Validation", "Business Logic Processing", "Data Persistence", "Response Delivery"],
                "trigger": "User submits a request via API or UI",
                "outcome": "Request processed and response returned",
            },
        ],
        "document_theme": "Application",
    },
}


# ─────────────────────────────────────────────────────────────
# Scoring weights for domain classification
# ─────────────────────────────────────────────────────────────

SIGNAL_WEIGHTS: Dict[str, int] = {
    "entity_names": 3,       # class/model name match
    "table_names": 4,        # database table name match
    "api_paths": 3,          # API path segment match
    "framework_names": 5,    # framework/import match
    "config_keys": 4,        # config key match
    "vocabulary": 2,         # docstring/description vocabulary match
    "directory_names": 3,    # top-level directory name match
    "file_names": 2,         # significant file name match
    "import_names": 4,       # third-party import match
}
