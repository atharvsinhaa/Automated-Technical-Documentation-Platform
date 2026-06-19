import sys
import os
import json

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../backend')))

from backend.architecture_intelligence.models import (
    ArchitectureIntelligenceModel,
    DomainModel,
    CapabilityModel,
    ServiceModel,
    ArchitecturalService,
    InformationModel,
    DeploymentModel,
    IntegrationModel,
    NarrativeContext
)
from backend.diagram_generator.hld_mermaid_generator import HLDMermaidGenerator

def test_aim_diagram_cohesion():
    print("Testing AIM Diagram Cohesion...")
    
    # Mock AIM
    services = ServiceModel(
        services=[
            ArchitecturalService(
                name="User Management Service",
                service_type="Domain",
                responsibility="Manages users",
                capabilities_served=[],
                dependencies=[],
                consumers=[],
                layer="Application",
                technology_notes="",
                is_external=False
            )
        ],
        interaction_summary="",
        architecture_style="Microservices"
    )
    
    aim = ArchitectureIntelligenceModel(
        repository_name="test_repo",
        domain=DomainModel("Test", "", [], [], [], [], [], []),
        capabilities=CapabilityModel([], [], [], ""),
        services=services,
        information=InformationModel([], [], ""),
        deployment=DeploymentModel("Local", [], [], ""),
        integration=IntegrationModel([], "", ""),
        narrative=NarrativeContext("", "", {}, "", "", "", "", "")
    )
    
    gen = HLDMermaidGenerator()
    from backend.architecture_extractor.models import ArchitectureBlueprint
    bp = ArchitectureBlueprint(
        repository_type="Test",
        architecture_pattern="Test",
        capabilities=[],
        services=[],
        databases=[],
        apis=[],
        workflows=[],
        data_flows=[],
        integrations=[],
        deployment_nodes=[]
    )
    diagrams = gen.generate(blueprint=bp, aim=aim)
    
    arch_diagram = diagrams["architecture_diagram"]
    
    assert "User Management Service" in arch_diagram, "Service name from AIM not found in architecture diagram!"
    assert "Root Service" not in arch_diagram, "Legacy/Fallback service name found in architecture diagram!"
    
    print("[SUCCESS] Architecture diagram matches AIM narrative exactly.")

if __name__ == "__main__":
    test_aim_diagram_cohesion()
