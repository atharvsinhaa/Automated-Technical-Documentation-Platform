from backend.semantic_ir.ir_builder import IRBuilder

from backend.diagram_generator.hld_mermaid_generator import (
    HLDMermaidGenerator
)

from backend.diagram_generator.lld_sequence_generator import (
    LLDSequenceGenerator
)

from backend.diagram_generator.mermaid_renderer import (
    MermaidRenderer
)

builder = IRBuilder()

semantic_ir = builder.build("./")

renderer = MermaidRenderer()

# Generate HLD Mermaid
hld_generator = HLDMermaidGenerator()

hld_mermaid = hld_generator.generate(
    semantic_ir
)

# Render HLD
renderer.render(
    hld_mermaid,
    "outputs/diagrams/hld_architecture.svg"
)

# Generate LLD Mermaid
lld_generator = LLDSequenceGenerator()

lld_mermaid = lld_generator.generate(
    semantic_ir
)

# Render LLD
renderer.render(
    lld_mermaid,
    "outputs/diagrams/lld_sequence.svg"
)

print("\nDiagrams generated successfully.")