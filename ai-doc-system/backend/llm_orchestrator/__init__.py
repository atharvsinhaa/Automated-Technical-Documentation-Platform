"""
llm_orchestrator — Component 6: LLM Orchestrator
Airtel Enterprise AI Documentation System

Automates the full documentation pipeline: extracts context once
from the Knowledge Graph, generates HLD/LLD/Code Comment prompts,
and sends them to an offline LLM for final document generation.

Supports: Ollama + Qwen, DeepSeek Coder, Llama 3, Mistral.
Fully offline — zero cloud APIs, zero SaaS dependencies.
"""

from .models import (
    OrchestratorJob, PromptType, JobStatus,
    PromptResult, JobResult, BatchResult,
)
from .llm_client import (
    BaseLLMClient, StubLLMClient, OllamaLLMClient,
    OllamaError, create_llm_client,
)
from .orchestrator import LLMOrchestrator
from .batch_runner import BatchRunner

__all__ = [
    # Models
    "OrchestratorJob", "PromptType", "JobStatus",
    "PromptResult", "JobResult", "BatchResult",
    # LLM
    "BaseLLMClient", "StubLLMClient", "OllamaLLMClient",
    "OllamaError", "create_llm_client",
    # Core
    "LLMOrchestrator", "BatchRunner",
]
__version__ = "1.1.0"
