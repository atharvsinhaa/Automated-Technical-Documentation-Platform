
"""
llm_orchestrator/orchestrator.py
────────────────────────────────────────────────────────────────
Core orchestrator: for a single target, extracts context ONCE
from the Knowledge Graph, generates 3 prompts (HLD, LLD,
Code-Comment), and sends each to the LLM.

This is the heart of Component 6.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Dict, Optional

from backend.context_builder.context_builder import ContextBuilder
from backend.context_builder.models import (
    ContextQuery,
    ContextResult,
    PromptPayload,
)

from .models import (
    OrchestratorJob,
    PromptType,
    JobStatus,
    PromptResult,
    JobResult,
)

from .llm_client import BaseLLMClient, StubLLMClient

from backend.docx_service.docx_builder import DocxBuilder


# Maps prompt type → output filename
OUTPUT_FILENAMES = {
    PromptType.HLD: "HLD.md",
    PromptType.LLD: "LLD.md",
    PromptType.CODE_COMMENT: "CodeComments.md",
}

PROMPT_FILENAMES = {
    PromptType.HLD: "prompt_hld.json",
    PromptType.LLD: "prompt_lld.json",
    PromptType.CODE_COMMENT: "prompt_code_comment.json",
}

# Maps prompt type → DOCX title
DOCX_TITLES = {
    PromptType.HLD: "High-Level Design",
    PromptType.LLD: "Low-Level Design",
    PromptType.CODE_COMMENT: "Code Comments",
}

DOCX_SUBTITLES = {
    PromptType.HLD: "Architecture Documentation",
    PromptType.LLD: "Detailed Technical Documentation",
    PromptType.CODE_COMMENT: "Code Documentation",
}


def save_docx(
    title: str,
    content: str,
    output_path: str,
    project_name: str = "",
    repo_name: str = "",
    doc_type: str = "hld",
):
    """
    Save markdown/text content as a professionally formatted DOCX.

    Uses the enterprise DocxBuilder to produce presentation-ready
    documents with cover page, TOC, embedded diagrams, tables,
    headers/footers, and page numbers.
    """
    builder = DocxBuilder(
        project_name=project_name or "AI Documentation",
        repo_name=repo_name,
        verbose=True,
    )

    # Cover page
    builder.add_cover_page(
        title=title,
        subtitle=DOCX_SUBTITLES.get(doc_type, "Documentation"),
        project=project_name or "AI Documentation",
        repo=repo_name,
    )

    # Revision history
    builder.add_revision_history()

    # Table of Contents
    builder.add_toc()

    # Main content (renders Mermaid, tables, etc.)
    builder.from_markdown(content)

    # Headers & footers
    builder.setup_headers_footers(title=title)

    builder.save(output_path)


class LLMOrchestrator:
    """
    The Factory Manager.

    For each target:
    1. Calls ContextBuilder.build_context() ONCE
    2. Calls ContextBuilder.build_prompt() THREE times
    3. Saves prompt JSONs to disk
    4. Sends each prompt to the LLM client
    5. Saves LLM outputs to disk
    """

    def __init__(
        self,
        context_builder: ContextBuilder,
        llm_client: Optional[BaseLLMClient] = None,
        output_dir: str = "backend/outputs/llm_ready",
        skip_llm: bool = False,
        verbose: bool = True,
    ):
        self.ctx_builder = context_builder
        self.llm_client = llm_client or StubLLMClient(verbose=verbose)
        self.output_dir = Path(output_dir)
        self.skip_llm = skip_llm
        self.verbose = verbose

    def process_job(self, job: OrchestratorJob) -> JobResult:
        """
        Process a single documentation job end-to-end.
        """

        t0 = time.time()

        result = JobResult(
            job=job,
            status=JobStatus.RUNNING,
        )

        if self.verbose:
            print(f"\n{'='*60}")
            print(f"  LLM Orchestrator: {job.target_description}")
            print(f"  Prompts: {', '.join(pt.value for pt in job.prompt_types)}")
            print(f"{'='*60}\n")

        # Create output directory
        target_dir = self.output_dir / job.target_label
        target_dir.mkdir(parents=True, exist_ok=True)

        # ─────────────────────────────────────────────────────
        # STEP 1: Extract Context
        # ─────────────────────────────────────────────────────

        self._log("[1/3] Extracting context from Knowledge Graph (ONE time)…")

        try:

            query = ContextQuery(
                target_file=job.target_file,
                service=job.service,
                api=job.api,
                workflow=job.workflow,
                domain=job.domain,
                module=job.module,
                node_id=job.node_id,
                depth=job.depth,
                token_budget=job.token_budget,
                include_source=job.include_source,
            )

            context = self.ctx_builder.build_context(query)

        except Exception as e:

            result.status = JobStatus.FAILED
            result.error = f"Context extraction failed: {e}"
            result.elapsed_sec = time.time() - t0

            self._log(f"  ✗ {result.error}")

            return result

        # Save context
        context_path = target_dir / "context.json"

        context_dict = context.to_dict()

        context_path.write_text(
            json.dumps(
                context_dict,
                indent=2,
                ensure_ascii=False,
                default=str,
            ),
            encoding="utf-8",
        )

        result.context_file = str(context_path)

        self._log(f"  → Context saved: {context_path}")

        # ─────────────────────────────────────────────────────
        # STEP 2: Generate Prompts
        # ─────────────────────────────────────────────────────

        self._log(
            f"[2/3] Generating {len(job.prompt_types)} prompts from single context…"
        )

        prompts: Dict[PromptType, PromptPayload] = {}

        for pt in job.prompt_types:

            try:

                prompt = self.ctx_builder.build_prompt(
                    context,
                    pt.value,
                )

                prompts[pt] = prompt

                prompt_path = target_dir / PROMPT_FILENAMES[pt]

                prompt_path.write_text(
                    json.dumps(
                        prompt.to_dict(),
                        indent=2,
                        ensure_ascii=False,
                        default=str,
                    ),
                    encoding="utf-8",
                )

                self._log(
                    f"  → {pt.value:12s} prompt saved "
                    f"({prompt.estimated_tokens} tokens)"
                )

            except Exception as e:

                self._log(
                    f"  ✗ {pt.value} prompt generation failed: {e}"
                )

                result.prompt_results.append(
                    PromptResult(
                        prompt_type=pt,
                        status=JobStatus.FAILED,
                        error=str(e),
                    )
                )

        # ─────────────────────────────────────────────────────
        # STEP 3: Send to LLM
        # ─────────────────────────────────────────────────────

        if self.skip_llm:

            self._log(
                "[3/3] Skipping LLM generation (--skip-llm mode)"
            )

            for pt, prompt in prompts.items():

                prompt_path = target_dir / PROMPT_FILENAMES[pt]

                result.prompt_results.append(
                    PromptResult(
                        prompt_type=pt,
                        status=JobStatus.COMPLETED,
                        prompt_file=str(prompt_path),
                        tokens_used=prompt.estimated_tokens,
                    )
                )

        else:

            self._log(
                f"[3/3] Sending {len(prompts)} prompts to LLM "
                f"({self.llm_client.model_name()})…"
            )

            for pt, prompt in prompts.items():

                pr = PromptResult(
                    prompt_type=pt,
                    prompt_file=str(
                        target_dir / PROMPT_FILENAMES[pt]
                    ),
                )

                pt_start = time.time()

                try:

                    # Call LLM
                    llm_output = self.llm_client.generate(
                        system_prompt=prompt.system_prompt,
                        user_prompt=prompt.user_prompt,
                    )

                    # Save Markdown output
                    output_path = target_dir / OUTPUT_FILENAMES[pt]

                    output_path.write_text(
                        llm_output,
                        encoding="utf-8",
                    )

                    # Save DOCX output
                    docx_name = OUTPUT_FILENAMES[pt].replace(
                        ".md",
                        ".docx",
                    )

                    save_docx(
                        title=DOCX_TITLES.get(pt, "Documentation"),
                        content=llm_output,
                        output_path=str(target_dir / docx_name),
                        project_name=job.target_description,
                        repo_name=job.target_label,
                        doc_type=pt.value,
                    )

                    pr.status = JobStatus.COMPLETED
                    pr.output_file = str(output_path)
                    pr.tokens_used = prompt.estimated_tokens
                    pr.elapsed_sec = time.time() - pt_start

                    self._log(
                        f"  → {pt.value:12s} ✓ output saved: "
                        f"{output_path.name} ({pr.elapsed_sec:.1f}s)"
                    )

                except Exception as e:

                    pr.status = JobStatus.FAILED
                    pr.error = str(e)
                    pr.elapsed_sec = time.time() - pt_start

                    self._log(
                        f"  ✗ {pt.value} LLM generation failed: {e}"
                    )

                result.prompt_results.append(pr)

        # ─────────────────────────────────────────────────────
        # Finalize
        # ─────────────────────────────────────────────────────

        elapsed = time.time() - t0

        result.elapsed_sec = elapsed

        if result.failed == 0:
            result.status = JobStatus.COMPLETED

        elif result.succeeded > 0:
            result.status = JobStatus.PARTIAL

        else:
            result.status = JobStatus.FAILED

        if self.verbose:

            print(f"\n{'─'*60}")

            print(f"  Job Complete: {job.target_description}")
            print(f"  Status:       {result.status.value}")
            print(f"  Succeeded:    {result.succeeded}/{len(job.prompt_types)}")
            print(f"  Output Dir:   {target_dir}")
            print(f"  Time:         {elapsed:.2f}s")

            print(f"{'─'*60}\n")

        return result

    def _log(self, msg: str):

        if self.verbose:
            print(msg, flush=True)
