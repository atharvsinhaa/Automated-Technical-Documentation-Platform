"""
docx_service/main.py
────────────────────────────────────────────────────────────────
CLI Entry Point for Enterprise DOCX Generation.

Usage:
  # From existing markdown files (LLM output)
  python -m backend.docx_service.main \\
    --from-markdown backend/outputs/llm_ready/fastapi__routing_py/HLD.md \\
    --type hld \\
    --output backend/outputs/docs

  # From a repo path (full pipeline: IR → Markdown → DOCX)
  python -m backend.docx_service.main \\
    --repo-path ./backend/test_repo \\
    --output backend/outputs/docs \\
    --kg-json backend/outputs/knowledge_graph_streaming/knowledge_graph.json

  # Both HLD + LLD from markdown
  python -m backend.docx_service.main \\
    --from-markdown backend/outputs/llm_ready/fastapi__routing_py/HLD.md \\
    --from-markdown-lld backend/outputs/llm_ready/fastapi__routing_py/LLD.md \\
    --output backend/outputs/docs

  # Convert all markdown outputs in a directory
  python -m backend.docx_service.main \\
    --from-dir backend/outputs/llm_ready \\
    --output backend/outputs/docs
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

from .hld_docx_generator import HLDDocxGenerator
from .lld_docx_generator import LLDDocxGenerator


def main():
    p = argparse.ArgumentParser(
        description="Enterprise DOCX Document Generator — "
                    "Produces HLD.docx and LLD.docx",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # From markdown
  python -m backend.docx_service.main \\
    --from-markdown backend/outputs/llm_ready/foo/HLD.md \\
    --type hld --output backend/outputs/docs

  # From markdown directory (batch)
  python -m backend.docx_service.main \\
    --from-dir backend/outputs/llm_ready \\
    --output backend/outputs/docs

  # From SemanticIR (full pipeline)
  python -m backend.docx_service.main \\
    --repo-path ./backend/test_repo \\
    --output backend/outputs/docs
        """,
    )

    # ── Input modes ──────────────────────────────────────────
    p.add_argument(
        "--from-markdown", default="",
        help="Path to a markdown file (HLD.md or LLD.md) to convert",
    )
    p.add_argument(
        "--from-markdown-lld", default="",
        help="Path to LLD markdown file (when used with --from-markdown for HLD)",
    )
    p.add_argument(
        "--from-dir", default="",
        help="Directory containing LLM output subdirectories. "
             "Converts all HLD.md and LLD.md files found.",
    )
    p.add_argument(
        "--repo-path", default="",
        help="Repository path for full pipeline (IR → Markdown → DOCX)",
    )
    p.add_argument(
        "--kg-json", default="",
        help="Path to knowledge_graph.json (for --repo-path mode)",
    )

    # ── Document type ────────────────────────────────────────
    p.add_argument(
        "--type", default="hld",
        choices=["hld", "lld", "both"],
        help="Document type to generate (default: hld)",
    )

    # ── Output ───────────────────────────────────────────────
    p.add_argument(
        "--output", default="backend/outputs/docs",
        help="Output directory (default: backend/outputs/docs)",
    )

    # ── Metadata ─────────────────────────────────────────────
    p.add_argument("--project", default="", help="Project name")
    p.add_argument("--repo", default="", help="Repository name")
    p.add_argument("--version", default="1.0", help="Document version")

    p.add_argument("--quiet", action="store_true")

    args = p.parse_args()
    verbose = not args.quiet
    t0 = time.time()

    if verbose:
        print()
        print("=" * 60)
        print("  Enterprise DOCX Generator")
        print("=" * 60)
        print()

    project = args.project or "AI Documentation"
    repo = args.repo

    # ── Mode 1: From markdown directory (batch) ──────────────
    if args.from_dir:
        _batch_from_directory(
            input_dir=args.from_dir,
            output_dir=args.output,
            project=project,
            repo=repo,
            version=args.version,
            verbose=verbose,
        )

    # ── Mode 2: From single markdown file ────────────────────
    elif args.from_markdown:
        _from_markdown_files(
            hld_path=args.from_markdown if args.type in ("hld", "both") else "",
            lld_path=args.from_markdown_lld or (
                args.from_markdown if args.type == "lld" else ""
            ),
            output_dir=args.output,
            project=project,
            repo=repo,
            version=args.version,
            verbose=verbose,
        )

    # ── Mode 3: From repo path (full pipeline) ──────────────
    elif args.repo_path:
        _from_repo(
            repo_path=args.repo_path,
            kg_json=args.kg_json,
            output_dir=args.output,
            project=project,
            repo=repo,
            version=args.version,
            doc_type=args.type,
            verbose=verbose,
        )

    else:
        print("Error: must specify one of --from-markdown, --from-dir, or --repo-path")
        p.print_help()
        sys.exit(1)

    elapsed = time.time() - t0
    if verbose:
        print()
        print("=" * 60)
        print(f"  Done in {elapsed:.1f}s")
        print(f"  Output: {args.output}")
        print("=" * 60)
        print()


# ══════════════════════════════════════════════════════════════
#  BATCH: Convert all markdown outputs in a directory
# ══════════════════════════════════════════════════════════════

def _batch_from_directory(
    input_dir: str,
    output_dir: str,
    project: str,
    repo: str,
    version: str,
    verbose: bool,
):
    """Find all HLD.md / LLD.md in subdirectories and convert."""
    input_path = Path(input_dir)
    if not input_path.exists():
        print(f"Error: directory not found: {input_dir}")
        sys.exit(1)

    count = 0

    for subdir in sorted(input_path.iterdir()):
        if not subdir.is_dir():
            continue

        hld_md = subdir / "HLD.md"
        lld_md = subdir / "LLD.md"

        out_subdir = os.path.join(output_dir, subdir.name)
        os.makedirs(out_subdir, exist_ok=True)

        if hld_md.exists():
            if verbose:
                print(f"\n━━━ Converting HLD: {subdir.name} ━━━")

            gen = HLDDocxGenerator(
                project_name=project,
                repo_name=repo or subdir.name,
                version=version,
                verbose=verbose,
            )
            gen.generate_from_markdown(
                markdown_text=hld_md.read_text(encoding="utf-8"),
                output_path=os.path.join(out_subdir, "HLD.docx"),
            )
            count += 1

        if lld_md.exists():
            if verbose:
                print(f"\n━━━ Converting LLD: {subdir.name} ━━━")

            gen = LLDDocxGenerator(
                project_name=project,
                repo_name=repo or subdir.name,
                version=version,
                verbose=verbose,
            )
            gen.generate_from_markdown(
                markdown_text=lld_md.read_text(encoding="utf-8"),
                output_path=os.path.join(out_subdir, "LLD.docx"),
            )
            count += 1

    if verbose:
        print(f"\n  Converted {count} documents.")


# ══════════════════════════════════════════════════════════════
#  SINGLE: Convert markdown file(s)
# ══════════════════════════════════════════════════════════════

def _from_markdown_files(
    hld_path: str,
    lld_path: str,
    output_dir: str,
    project: str,
    repo: str,
    version: str,
    verbose: bool,
):
    """Convert one or two markdown files to DOCX."""
    os.makedirs(output_dir, exist_ok=True)

    if hld_path and os.path.exists(hld_path):
        if verbose:
            print(f"  Converting HLD: {hld_path}")

        gen = HLDDocxGenerator(
            project_name=project,
            repo_name=repo,
            version=version,
            verbose=verbose,
        )
        md_text = Path(hld_path).read_text(encoding="utf-8")
        gen.generate_from_markdown(
            markdown_text=md_text,
            output_path=os.path.join(output_dir, "HLD.docx"),
        )

    if lld_path and os.path.exists(lld_path):
        if verbose:
            print(f"  Converting LLD: {lld_path}")

        gen = LLDDocxGenerator(
            project_name=project,
            repo_name=repo,
            version=version,
            verbose=verbose,
        )
        md_text = Path(lld_path).read_text(encoding="utf-8")
        gen.generate_from_markdown(
            markdown_text=md_text,
            output_path=os.path.join(output_dir, "LLD.docx"),
        )


# ══════════════════════════════════════════════════════════════
#  FULL PIPELINE: Repo → IR → DOCX
# ══════════════════════════════════════════════════════════════

def _from_repo(
    repo_path: str,
    kg_json: str,
    output_dir: str,
    project: str,
    repo: str,
    version: str,
    doc_type: str,
    verbose: bool,
):
    """Full pipeline: build SemanticIR then generate DOCX."""
    from backend.semantic_ir.ir_builder import IRBuilder

    if verbose:
        print(f"  Building SemanticIR from: {repo_path}")

    ir_builder = IRBuilder(verbose=verbose)
    semantic_ir = ir_builder.build(repo_path)

    os.makedirs(output_dir, exist_ok=True)

    if doc_type in ("hld", "both"):
        if verbose:
            print(f"\n  Generating HLD.docx…")

        gen = HLDDocxGenerator(
            project_name=project,
            repo_name=repo or os.path.basename(repo_path),
            version=version,
            verbose=verbose,
        )
        gen.generate_from_semantic_ir(
            semantic_ir=semantic_ir,
            output_path=os.path.join(output_dir, "HLD.docx"),
        )

    if doc_type in ("lld", "both"):
        if verbose:
            print(f"\n  Generating LLD.docx…")

        gen = LLDDocxGenerator(
            project_name=project,
            repo_name=repo or os.path.basename(repo_path),
            version=version,
            verbose=verbose,
        )
        gen.generate_from_semantic_ir(
            semantic_ir=semantic_ir,
            output_path=os.path.join(output_dir, "LLD.docx"),
        )


if __name__ == "__main__":
    main()
