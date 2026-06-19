"""
context_builder — Component 5: Enterprise Context Builder
Airtel Enterprise AI Documentation System

Bridges the Neo4j Knowledge Graph and offline LLM by extracting
semantically relevant subgraphs, compressing to token budget,
and generating architecture-aware, business-aware prompts.

Fully offline — zero cloud APIs, zero SaaS dependencies.
"""

from .models import (
    ContextQuery, ContextResult, ContextNode, ContextEdge,
    ArchitectureContext, BusinessContext, TelecomContext,
    LineageContext, WorkflowContext, PromptPayload,
)
from .context_builder import ContextBuilder
from .neo4j_client import Neo4jClient
from .graph_traverser import GraphTraverser
from .semantic_ranker import SemanticRanker
from .context_compressor import ContextCompressor
from .prompt_builder import PromptBuilder
from .source_loader import SourceLoader
from .token_estimator import TokenEstimator

__all__ = [
    # Models
    "ContextQuery", "ContextResult", "ContextNode", "ContextEdge",
    "ArchitectureContext", "BusinessContext", "TelecomContext",
    "LineageContext", "WorkflowContext", "PromptPayload",
    # Core
    "ContextBuilder", "Neo4jClient", "GraphTraverser",
    # Processing
    "SemanticRanker", "ContextCompressor", "PromptBuilder",
    # Utilities
    "SourceLoader", "TokenEstimator",
]
__version__ = "1.0.0"
