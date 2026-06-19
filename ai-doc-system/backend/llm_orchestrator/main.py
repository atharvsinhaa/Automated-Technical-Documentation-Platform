"""
llm_orchestrator/main.py
────────────────────────────────────────────────────────────────
CLI interface for the LLM Orchestrator (Component 6).

Usage:
  # Generate HLD + LLD + CodeComments using local Qwen
  python -m backend.llm_orchestrator.main \\
    --target-file fastapi/routing.py \\
    --model qwen2.5:7b \\
    --kg-json backend/outputs/knowledge_graph_streaming/knowledge_graph.json

  # Batch: multiple files
  python -m backend.llm_orchestrator.main \\
    --target-file fastapi/routing.py \\
    --target-file fastapi/applications.py \\
    --model qwen2.5:7b \\
    --kg-json backend/outputs/knowledge_graph_streaming/knowledge_graph.json

  # Stub mode (no LLM required — for testing)
  python -m backend.llm_orchestrator.main \\
    --target-file fastapi/routing.py \\
    --kg-json backend/outputs/knowledge_graph_streaming/knowledge_graph.json

  # Skip LLM entirely (only generate prompt JSONs)
  python -m backend.llm_orchestrator.main \\
    --target-file fastapi/routing.py \\
    --skip-llm \\
    --kg-json backend/outputs/knowledge_graph_streaming/knowledge_graph.json

  # List available Ollama models
  python -m backend.llm_orchestrator.main --list-models
"""

from __future__ import annotations

import argparse
import sys

from .models import OrchestratorJob, PromptType
from .batch_runner import BatchRunner
from .llm_client import create_llm_client, OllamaLLMClient


def main():
    p = argparse.ArgumentParser(
        description="Component 6: LLM Orchestrator — Generate HLD, LLD, Code Comments",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Real LLM: Qwen via Ollama
  python -m backend.llm_orchestrator.main \\
    --target-file fastapi/routing.py \\
    --model qwen2.5:7b \\
    --kg-json backend/outputs/knowledge_graph_streaming/knowledge_graph.json

  # Real LLM: DeepSeek Coder
  python -m backend.llm_orchestrator.main \\
    --target-file fastapi/routing.py \\
    --model deepseek-coder \\
    --kg-json backend/outputs/knowledge_graph_streaming/knowledge_graph.json

  # Stub mode (no --model flag = stub)
  python -m backend.llm_orchestrator.main \\
    --target-file fastapi/routing.py \\
    --kg-json backend/outputs/knowledge_graph_streaming/knowledge_graph.json

  # Batch: multiple targets
  python -m backend.llm_orchestrator.main \\
    --target-file fastapi/routing.py \\
    --target-file fastapi/applications.py \\
    --model qwen2.5:7b \\
    --kg-json backend/outputs/knowledge_graph_streaming/knowledge_graph.json

  # Only generate prompt JSONs (no LLM)
  python -m backend.llm_orchestrator.main \\
    --target-file fastapi/routing.py \\
    --skip-llm \\
    --kg-json backend/outputs/knowledge_graph_streaming/knowledge_graph.json

  # List available Ollama models
  python -m backend.llm_orchestrator.main --list-models
        """,
    )

    # ── Targets (repeatable) ─────────────────────────────────
    p.add_argument("--target-file", action="append", default=[],
                   help="File path(s) to process (repeatable)")
    p.add_argument("--service", action="append", default=[],
                   help="Service name(s) to process (repeatable)")
    p.add_argument("--api", action="append", default=[],
                   help="API endpoint(s) to process (repeatable)")
    p.add_argument("--workflow", action="append", default=[],
                   help="Workflow name(s) to process (repeatable)")
    p.add_argument("--domain", action="append", default=[],
                   help="Domain name(s) to process (repeatable)")

    # ── Graph options ────────────────────────────────────────
    p.add_argument("--depth", type=int, default=2,
                   help="Graph traversal depth (default: 2)")
    p.add_argument("--token-budget", type=int, default=8000,
                   help="Max tokens per prompt context (default: 8000)")
    p.add_argument("--no-source", action="store_true",
                   help="Don't include source code in context")

    # ── LLM Configuration ───────────────────────────────────
    p.add_argument("--model", default="",
                   help="Ollama model name (e.g. qwen2.5:7b, deepseek-coder). "
                        "Empty = stub mode")
    p.add_argument("--ollama-host", default="http://localhost:11434",
                   help="Ollama server URL (default: http://localhost:11434)")
    p.add_argument("--temperature", type=float, default=0.15,
                   help="LLM sampling temperature (default: 0.15 for deterministic)")
    p.add_argument("--max-tokens", type=int, default=4096,
                   help="Max tokens to generate per response (default: 4096)")
    p.add_argument("--context-window", type=int, default=32768,
                   help="Model context window size (default: 32768)")
    p.add_argument("--timeout", type=int, default=600,
                   help="LLM request timeout in seconds (default: 600)")
    p.add_argument("--max-retries", type=int, default=3,
                   help="Max retry attempts on LLM failure (default: 3)")
    p.add_argument("--skip-llm", action="store_true",
                   help="Only generate prompt JSONs, do not call LLM")
    p.add_argument("--list-models", action="store_true",
                   help="List available Ollama models and exit")

    # ── Data source ──────────────────────────────────────────
    p.add_argument("--kg-json", default="",
                   help="Path to knowledge_graph.json (offline fallback)")
    p.add_argument("--neo4j", default="bolt://localhost:7687",
                   help="Neo4j bolt URI")
    p.add_argument("--neo4j-user", default="neo4j")
    p.add_argument("--neo4j-pass", default="password")
    p.add_argument("--neo4j-db", default="neo4j")

    # ── Output ───────────────────────────────────────────────
    p.add_argument("--output", default="backend/outputs/llm_ready",
                   help="Output directory (default: backend/outputs/llm_ready)")
    p.add_argument("--source-root", default=".",
                   help="Path to source repository root")
    p.add_argument("--quiet", action="store_true")

    args = p.parse_args()
    verbose = not args.quiet

    # ── List models mode ─────────────────────────────────────
    if args.list_models:
        client = OllamaLLMClient(
            model="stub",
            host=args.ollama_host,
            verbose=True,
        )
        client.list_available_models()
        sys.exit(0)

    # ── Build jobs ───────────────────────────────────────────
    jobs = []
    common = dict(
        depth=args.depth,
        token_budget=args.token_budget,
        include_source=not args.no_source,
    )

    for fp in args.target_file:
        jobs.append(OrchestratorJob(target_file=fp, **common))

    for svc in args.service:
        jobs.append(OrchestratorJob(service=svc, **common))

    for api in args.api:
        jobs.append(OrchestratorJob(api=api, **common))

    for wf in args.workflow:
        jobs.append(OrchestratorJob(workflow=wf, **common))

    for dom in args.domain:
        jobs.append(OrchestratorJob(domain=dom, **common))

    if not jobs:
        print("Error: must specify at least one target "
              "(--target-file, --service, --api, --workflow, --domain)")
        p.print_help()
        sys.exit(1)

    # ── Create LLM client ───────────────────────────────────
    llm_client = create_llm_client(
        model=args.model,
        ollama_host=args.ollama_host,
        temperature=args.temperature,
        max_tokens=args.max_tokens,
        context_window=args.context_window,
        timeout=args.timeout,
        max_retries=args.max_retries,
        verbose=verbose,
    )

    # ── Run ──────────────────────────────────────────────────
    with BatchRunner(
        kg_json_path=args.kg_json or None,
        neo4j_uri=args.neo4j,
        neo4j_user=args.neo4j_user,
        neo4j_pass=args.neo4j_pass,
        neo4j_db=args.neo4j_db,
        source_root=args.source_root,
        output_dir=args.output,
        llm_client=llm_client,
        skip_llm=args.skip_llm,
        verbose=verbose,
    ) as runner:
        result = runner.run(jobs)

    # Exit code: 0 if all succeeded, 1 if any failed
    sys.exit(0 if result.failed == 0 else 1)


if __name__ == "__main__":
    main()
