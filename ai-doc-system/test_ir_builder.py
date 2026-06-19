from backend.semantic_ir.ir_builder import IRBuilder

builder = IRBuilder()

ir = builder.build("./")

print("\n===== SEMANTIC IR =====\n")

print("Repository Type:")
print(ir.repository_type)

print("\nCOMPONENTS:\n")

for component in ir.components:

    print("Component:", component.name)

    print("Type:", component.component_type)

    print("Description:", component.description)

    print("Files:", len(component.files))

    print("-" * 50)

print("\nRELATIONSHIPS:\n")

for rel in ir.relationships:

    print(
        f"{rel.source} "
        f"--[{rel.relationship_type}]--> "
        f"{rel.target}"
    )

print("\nWORKFLOWS:\n")

for wf in ir.workflows:

    print("Workflow:", wf.name)

    for step in wf.steps:
        print("  ->", step)