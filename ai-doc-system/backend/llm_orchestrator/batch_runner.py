"""
llm_orchestrator/batch_runner.py
────────────────────────────────────────────────────────────────
Batch processing: loops over multiple targets, runs the
orchestrator for each, handles failures gracefully, and
produces a summary report.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import List, Optional

from backend.context_builder.context_builder import ContextBuilder

from .models import (
    OrchestratorJob, PromptType, JobStatus,
    JobResult, BatchResult,
)
from .llm_client import BaseLLMClient, StubLLMClient
from .orchestrator import LLMOrchestrator


class BatchRunner:
    """
    Runs the LLM Orchestrator over a batch of targets.

    Usage:
        runner = BatchRunner(
            kg_json_path="knowledge_graph.json",
            output_dir="backend/outputs/llm_ready",
        )
        result = runner.run([
            OrchestratorJob(target_file="fastapi/routing.py"),
            OrchestratorJob(service="billing"),
        ])
    """

    def __init__(
        self,
        kg_json_path:   Optional[str] = None,
        neo4j_uri:      str = "bolt://localhost:7687",
        neo4j_user:     str = "neo4j",
        neo4j_pass:     str = "password",
        neo4j_db:       str = "neo4j",
        source_root:    str = ".",
        output_dir:     str = "backend/outputs/llm_ready",
        llm_client:     Optional[BaseLLMClient] = None,
        skip_llm:       bool = False,
        verbose:        bool = True,
    ):
        self.output_dir = Path(output_dir)
        self.verbose = verbose
        self.skip_llm = skip_llm

        # Initialize Context Builder (shared across all jobs)
        self._log("Initializing Context Builder…")
        self.ctx_builder = ContextBuilder(
            neo4j_uri=neo4j_uri,
            neo4j_user=neo4j_user,
            neo4j_pass=neo4j_pass,
            neo4j_db=neo4j_db,
            kg_json_path=kg_json_path,
            source_root=source_root,
            verbose=verbose,
        )

        # Initialize LLM client
        self.llm_client = llm_client or StubLLMClient(verbose=verbose)

        # Initialize Orchestrator
        self.orchestrator = LLMOrchestrator(
            context_builder=self.ctx_builder,
            llm_client=self.llm_client,
            output_dir=str(self.output_dir),
            skip_llm=skip_llm,
            verbose=verbose,
        )

    def run(self, jobs: List[OrchestratorJob]) -> BatchResult:
        """
        Run all jobs in the batch.

        Each job is independent — if one fails, the others continue.
        """
        t0 = time.time()
        batch = BatchResult(
            total_jobs=len(jobs),
            output_dir=str(self.output_dir),
        )

        if self.verbose:
            print(f"\n{'='*60}")
            print(f"  BATCH RUN: {len(jobs)} targets")
            print(f"  LLM: {self.llm_client.model_name()}")
            print(f"  Output: {self.output_dir}")
            print(f"  Skip LLM: {self.skip_llm}")
            print(f"{'='*60}\n")

        for i, job in enumerate(jobs, 1):
            self._log(f"━━━ Job {i}/{len(jobs)}: {job.target_description} ━━━")
            try:
                result = self.orchestrator.process_job(job)
                batch.job_results.append(result)

                if result.status == JobStatus.COMPLETED:
                    batch.completed += 1
                elif result.status == JobStatus.PARTIAL:
                    batch.partial += 1
                else:
                    batch.failed += 1

            except Exception as e:
                self._log(f"  ✗ Job CRASHED: {e}")
                failed_result = JobResult(
                    job=job,
                    status=JobStatus.FAILED,
                    error=f"Unhandled exception: {e}",
                )
                batch.job_results.append(failed_result)
                batch.failed += 1

        batch.elapsed_sec = time.time() - t0

        # Save batch summary
        self._save_batch_report(batch)

        if self.verbose:
            print(f"\n{'='*60}")
            print(f"  BATCH COMPLETE")
            print(f"  {'─'*40}")
            print(f"  Total:     {batch.total_jobs}")
            print(f"  Completed: {batch.completed}")
            print(f"  Partial:   {batch.partial}")
            print(f"  Failed:    {batch.failed}")
            print(f"  Time:      {batch.elapsed_sec:.2f}s")
            print(f"  Report:    {self.output_dir / 'batch_report.json'}")
            print(f"{'='*60}\n")

        return batch

    def run_files(self, file_paths: List[str], **kwargs) -> BatchResult:
        """
        Convenience: create jobs from a list of file paths.

        Args:
            file_paths: List of file paths to process.
            **kwargs: Additional options passed to OrchestratorJob.
        """
        jobs = [
            OrchestratorJob(target_file=fp, **kwargs)
            for fp in file_paths
        ]
        return self.run(jobs)

    def _save_batch_report(self, batch: BatchResult):
        """Save a JSON report of the entire batch run."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        report_path = self.output_dir / "batch_report.json"
        report_path.write_text(
            json.dumps(batch.to_dict(), indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
        if self.verbose:
            print(f"\n  Batch report saved: {report_path}")

    def close(self):
        """Cleanup."""
        self.ctx_builder.close()

    def _log(self, msg: str):
        if self.verbose:
            print(msg, flush=True)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
