"""
llm_orchestrator/models.py
────────────────────────────────────────────────────────────────
Data models for the LLM Orchestrator (Component 6).

Defines job specifications, per-prompt results, and batch results.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class PromptType(str, Enum):
    """The three documentation outputs we generate."""
    HLD          = "hld"
    LLD          = "lld"
    CODE_COMMENT = "code-comment"


class JobStatus(str, Enum):
    PENDING   = "pending"
    RUNNING   = "running"
    COMPLETED = "completed"
    FAILED    = "failed"
    PARTIAL   = "partial"      # some prompts succeeded, some failed


# ──────────────────────────────────────────────────────────────
#  INPUT: What the user wants to generate
# ──────────────────────────────────────────────────────────────

@dataclass
class OrchestratorJob:
    """
    A single documentation generation job.

    One job = one target file/service.
    It produces 3 outputs (HLD, LLD, Code Comments).
    """
    # ── Target (same as ContextQuery) ────────────────────────
    target_file:    Optional[str] = None
    service:        Optional[str] = None
    api:            Optional[str] = None
    workflow:       Optional[str] = None
    domain:         Optional[str] = None
    module:         Optional[str] = None
    node_id:        Optional[str] = None

    # ── Options ──────────────────────────────────────────────
    depth:          int   = 2
    token_budget:   int   = 8000
    include_source: bool  = True

    # ── Which prompts to generate ────────────────────────────
    prompt_types:   List[PromptType] = field(default_factory=lambda: [
        PromptType.HLD, PromptType.LLD, PromptType.CODE_COMMENT,
    ])

    @property
    def target_label(self) -> str:
        """Human-readable label for folder naming."""
        if self.target_file:
            return self.target_file.replace("/", "__").replace(".", "_")
        if self.service:
            return f"service__{self.service}"
        if self.api:
            return f"api__{self.api.strip('/').replace('/', '__')}"
        if self.workflow:
            return f"workflow__{self.workflow.replace(' ', '_')}"
        if self.domain:
            return f"domain__{self.domain.replace(' ', '_')}"
        if self.module:
            return f"module__{self.module}"
        if self.node_id:
            return f"node__{self.node_id[:30]}"
        return "unknown_target"

    @property
    def target_description(self) -> str:
        """Human-readable description."""
        if self.target_file: return self.target_file
        if self.service:     return f"service: {self.service}"
        if self.api:         return f"api: {self.api}"
        if self.workflow:    return f"workflow: {self.workflow}"
        if self.domain:      return f"domain: {self.domain}"
        if self.module:      return f"module: {self.module}"
        if self.node_id:     return f"node: {self.node_id}"
        return "unspecified"


# ──────────────────────────────────────────────────────────────
#  OUTPUT: Results
# ──────────────────────────────────────────────────────────────

@dataclass
class PromptResult:
    """Result for a single prompt type (e.g. HLD)."""
    prompt_type:   PromptType
    status:        JobStatus       = JobStatus.PENDING
    prompt_file:   Optional[str]   = None   # path to saved prompt JSON
    output_file:   Optional[str]   = None   # path to LLM output (MD/PY)
    tokens_used:   int             = 0
    error:         Optional[str]   = None
    elapsed_sec:   float           = 0.0


@dataclass
class JobResult:
    """Result for a single orchestrator job (1 target, 3 prompts)."""
    job:            OrchestratorJob
    status:         JobStatus           = JobStatus.PENDING
    context_file:   Optional[str]       = None
    prompt_results: List[PromptResult]  = field(default_factory=list)
    elapsed_sec:    float               = 0.0
    error:          Optional[str]       = None

    @property
    def succeeded(self) -> int:
        return sum(1 for r in self.prompt_results if r.status == JobStatus.COMPLETED)

    @property
    def failed(self) -> int:
        return sum(1 for r in self.prompt_results if r.status == JobStatus.FAILED)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "target": self.job.target_description,
            "status": self.status.value,
            "context_file": self.context_file,
            "elapsed_sec": round(self.elapsed_sec, 2),
            "prompts": [
                {
                    "type": r.prompt_type.value,
                    "status": r.status.value,
                    "prompt_file": r.prompt_file,
                    "output_file": r.output_file,
                    "tokens": r.tokens_used,
                    "error": r.error,
                }
                for r in self.prompt_results
            ],
            "error": self.error,
        }


@dataclass
class BatchResult:
    """Result for a full batch run."""
    total_jobs:   int           = 0
    completed:    int           = 0
    failed:       int           = 0
    partial:      int           = 0
    job_results:  List[JobResult] = field(default_factory=list)
    elapsed_sec:  float         = 0.0
    output_dir:   str           = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "summary": {
                "total": self.total_jobs,
                "completed": self.completed,
                "failed": self.failed,
                "partial": self.partial,
                "elapsed_sec": round(self.elapsed_sec, 2),
                "output_dir": self.output_dir,
            },
            "jobs": [jr.to_dict() for jr in self.job_results],
        }
