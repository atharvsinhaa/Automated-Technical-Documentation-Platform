from backend.semantic_ir.ir_builder import IRBuilder

from backend.diagram_generator.lld_sequence_generator import (
    LLDSequenceGenerator
)

from backend.diagram_generator.mermaid_renderer import (
    MermaidRenderer
)

from backend.document_generator.lld_generator import (
    LLDGenerator
)

# Build Semantic IR
builder = IRBuilder()

semantic_ir = builder.build("./")

# Generate Mermaid
lld_mermaid_generator = LLDSequenceGenerator()

lld_mermaid = lld_mermaid_generator.generate(
    semantic_ir
)

# Render Diagram
renderer = MermaidRenderer()

diagram_output = (
    "outputs/diagrams/lld_sequence.svg"
)

renderer.render(
    lld_mermaid,
    diagram_output
)

# Generate LLD Document
lld_generator = LLDGenerator()

lld_content = lld_generator.generate(
    semantic_ir,
    "../diagrams/lld_sequence.svg"
)

# Save LLD
lld_generator.save(
    lld_content,
    "outputs/lld/LLD.md"
)

print("\nLLD generation completed.")