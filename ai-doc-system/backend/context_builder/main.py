"""
context_builder/main.py
────────────────────────────────────────────────────────────────
CLI interface for the Enterprise Context Builder (Component 5).

Usage:
  python -m backend.context_builder.main \
    --target-file fastapi/routing.py \
    --kg-json backend/outputs/knowledge_graph_streaming/knowledge_graph.json \
    --output context.json

  python -m backend.context_builder.main \
    --target-file fastapi/routing.py \
    --prompt-type documentation \
    --kg-json backend/outputs/knowledge_graph_streaming/knowledge_graph.json \
    --output prompt.json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from .models import ContextQuery
from .context_builder import ContextBuilder


def main():
    p = argparse.ArgumentParser(
        description="Component 5: Enterprise Context Builder",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Build context for a file (JSON fallback mode)
  python -m backend.context_builder.main \\
    --target-file fastapi/routing.py \\
    --kg-json backend/outputs/knowledge_graph_streaming/knowledge_graph.json \\
    --output context.json

  # Build context + generate prompt
  python -m backend.context_builder.main \\
    --target-file fastapi/routing.py \\
    --prompt-type documentation \\
    --kg-json backend/outputs/knowledge_graph_streaming/knowledge_graph.json \\
    --output prompt.json

  # Build context for a service
  python -m backend.context_builder.main \\
    --service fastapi \\
    --depth 3 \\
    --kg-json backend/outputs/knowledge_graph_streaming/knowledge_graph.json \\
    --output context.json

  # With Neo4j
  python -m backend.context_builder.main \\
    --target-file app.py \\
    --neo4j bolt://localhost:7687 \\
    --output context.json
        """,
    )

    # Target
    p.add_argument("--target-file", default="",
                   help="File path to build context for")
    p.add_argument("--service", default="",
                   help="Service name")
    p.add_argument("--api", default="",
                   help="API endpoint path")
    p.add_argument("--workflow", default="",
                   help="Workflow/flow name")
    p.add_argument("--domain", default="",
                   help="Telecom domain name")
    p.add_argument("--module", default="",
                   help="Module name")
    p.add_argument("--node-id", default="",
                   help="Direct node ID")

    # Traversal
    p.add_argument("--depth", type=int, default=2,
                   help="Graph traversal depth (default: 2)")
    p.add_argument("--token-budget", type=int, default=8000,
                   help="Max estimated tokens (default: 8000)")
    p.add_argument("--no-source", action="store_true",
                   help="Do not include source code")

    # Prompt
    p.add_argument("--prompt-type", default="",
                   choices=["", "documentation", "hld", "lld", "code-comment", "architecture", "business"],
                   help="Generate a prompt of this type")

    # Output
    p.add_argument("--output", default="",
                   help="Output JSON file path (default: stdout)")

    # Data source
    p.add_argument("--neo4j", default="bolt://localhost:7687",
                   help="Neo4j bolt URI")
    p.add_argument("--neo4j-user", default="neo4j")
    p.add_argument("--neo4j-pass", default="password")
    p.add_argument("--neo4j-db", default="neo4j")
    p.add_argument("--kg-json", default="",
                   help="Path to knowledge_graph.json (fallback mode)")

    # Source
    p.add_argument("--source-root", default=".",
                   help="Path to source repository root")

    # Other
    p.add_argument("--quiet", action="store_true")

    args = p.parse_args()
    verbose = not args.quiet

    # Build query
    query = ContextQuery(
        target_file=args.target_file or None,
        service=args.service or None,
        api=args.api or None,
        workflow=args.workflow or None,
        domain=args.domain or None,
        module=args.module or None,
        node_id=args.node_id or None,
        depth=args.depth,
        token_budget=args.token_budget,
        include_source=not args.no_source,
        prompt_type=args.prompt_type or None,
    )

    if not query.has_target:
        print("Error: Must specify at least one target "
              "(--target-file, --service, --api, --workflow, --domain, --module, --node-id)")
        sys.exit(1)

    # Initialize builder
    builder = ContextBuilder(
        neo4j_uri=args.neo4j,
        neo4j_user=args.neo4j_user,
        neo4j_pass=args.neo4j_pass,
        neo4j_db=args.neo4j_db,
        kg_json_path=args.kg_json or None,
        source_root=args.source_root,
        verbose=verbose,
    )

    try:
        # Build context
        t0 = time.time()
        result = builder.build_context(query)

        # Optionally generate prompt
        output_data = result.to_dict()

        if args.prompt_type:
            prompt = builder.build_prompt(result, args.prompt_type)
            output_data = prompt.to_dict()
            if verbose:
                print(f"[prompt] Generated {args.prompt_type} prompt (~{prompt.estimated_tokens} tokens)")

        # Output
        output_json = json.dumps(output_data, indent=2, ensure_ascii=False, default=str)

        if args.output:
            Path(args.output).parent.mkdir(parents=True, exist_ok=True)
            Path(args.output).write_text(output_json, encoding="utf-8")
            kb = len(output_json) / 1024
            elapsed = time.time() - t0
            if verbose:
                print(f"\n  Output → {args.output}  ({kb:.1f} KB, {elapsed:.2f}s)")
        else:
            print(output_json)

    finally:
        builder.close()


if __name__ == "__main__":
    main()
