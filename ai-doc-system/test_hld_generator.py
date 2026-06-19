from backend.semantic_ir.ir_builder import IRBuilder

from backend.diagram_generator.hld_mermaid_generator import (
    HLDMermaidGenerator
)

from backend.diagram_generator.mermaid_renderer import (
    MermaidRenderer
)

from backend.document_generator.hld_generator import (
    HLDGenerator
)

# Build Semantic IR
builder = IRBuilder()

semantic_ir = builder.build("./")

# Generate Mermaid
hld_mermaid_generator = HLDMermaidGenerator()

hld_mermaid = hld_mermaid_generator.generate(
    semantic_ir
)

# Render Diagram
renderer = MermaidRenderer()

diagram_output = (
    "outputs/diagrams/hld_architecture.svg"
)

renderer.render(
    hld_mermaid,
    diagram_output
)

# Generate HLD Document
hld_generator = HLDGenerator()

hld_content = hld_generator.generate(
    semantic_ir,
    "../diagrams/hld_architecture.svg"
)

# Save HLD
hld_generator.save(
    hld_content,
    "outputs/hld/HLD.md"
)

print("\nHLD generation completed.")