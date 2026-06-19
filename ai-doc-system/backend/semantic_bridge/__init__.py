"""
semantic_bridge/
────────────────────────────────────────────────────────────────
The critical missing bridge between Knowledge Graph and Semantic IR.

Translates rich graph-shaped data (nodes, edges, service clusters,
business flows, lineage chains) into the linear, structured
SemanticIR that feeds HLD/LLD/diagram generators.
"""

from .kg_to_ir_translator import KGToIRTranslator

__all__ = ["KGToIRTranslator"]
