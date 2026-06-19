from backend.semantic_ir.ir_builder import IRBuilder

from backend.diagram_generator.hld_mermaid_generator import (
    HLDMermaidGenerator
)

from backend.diagram_generator.lld_sequence_generator import (
    LLDSequenceGenerator
)

builder = IRBuilder()

semantic_ir = builder.build("./")

# HLD Diagram
hld_generator = HLDMermaidGenerator()

hld_mermaid = hld_generator.generate(
    semantic_ir
)

print("\n===== HLD MERMAID =====\n")

print(hld_mermaid)

# LLD Diagram
lld_generator = LLDSequenceGenerator()

lld_mermaid = lld_generator.generate(
    semantic_ir
)

print("\n===== LLD SEQUENCE MERMAID =====\n")

print(lld_mermaid)