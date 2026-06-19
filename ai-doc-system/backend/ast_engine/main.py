#!/usr/bin/env python3
"""
main.py — CLI entry point for the Universal AST Parsing Engine
─────────────────────────────────────────────────────────────
Usage:
  python main.py --dir  ./my_repo           --output repo.xml
  python main.py --github https://...       --output repo.xml
  python main.py --files a.py b.js c.sql   --output out.xml
  python main.py --stdin --lang python      --output snippet.xml
  python main.py --source "def foo(): pass" --lang python --output out.xml
"""

import argparse
import sys
import textwrap
from pathlib import Path

# Allow running as: python main.py OR python -m ast_engine.main
sys.path.insert(0, str(Path(__file__).parent.parent))

from ast_engine import ASTEngine, generate_xml


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="ast_engine",
        description="Universal Multi-Language AST Parser → XML",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""
        Examples:
          # Parse a full repository
          python main.py --dir ./backend --project airtel_backend --output backend.xml

          # Parse a GitHub repo
          python main.py --github https://github.com/org/repo --output repo.xml

          # Parse specific files
          python main.py --files app.py Dashboard.jsx queries.sql --output project.xml

          # Parse pasted code from stdin
          cat myfile.py | python main.py --stdin --lang python --output out.xml

          # Adjust parallelism for large repos
          python main.py --dir ./huge_monorepo --workers 16 --output mono.xml
        """),
    )

    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--dir",    metavar="PATH",  help="Directory to parse recursively")
    src.add_argument("--github", metavar="URL",   help="GitHub repo URL to clone and parse")
    src.add_argument("--files",  metavar="FILE", nargs="+", help="Explicit file list")
    src.add_argument("--stdin",  action="store_true", help="Read source from stdin")
    src.add_argument("--source", metavar="CODE",  help="Inline source code string")

    p.add_argument("--lang",    default="python",  help="Language for --stdin/--source")
    p.add_argument("--name",    default="snippet",  help="Name for --stdin/--source snippet")
    p.add_argument("--project", default="",         help="Project name (default: inferred)")
    p.add_argument("--output",  default="output.xml", help="Output XML file path")
    p.add_argument("--workers", type=int, default=4,  help="Parallel workers (default: 4)")
    p.add_argument("--max-file-mb", type=float, default=10.0,
                   help="Skip files larger than this (MB)")
    p.add_argument("--quiet",   action="store_true", help="Suppress per-file output")
    return p


def main():
    ap = build_parser()
    args = ap.parse_args()

    engine = ASTEngine(
        workers=args.workers,
        max_file_size_mb=args.max_file_mb,
        verbose=not args.quiet,
    )

    if args.dir:
        project_name = args.project or Path(args.dir).name
        project = engine.parse_directory(args.dir, project_name)

    elif args.github:
        project_name = args.project or args.github.rstrip("/").split("/")[-1]
        project = engine.parse_github(args.github, project_name)

    elif args.files:
        project_name = args.project or "project"
        project = engine.parse_files(args.files, project_name)

    elif args.stdin:
        print(f"[input] Paste {args.lang} code. Press Ctrl-D (Ctrl-Z on Windows) when done:\n")
        source = sys.stdin.read()
        project = engine.parse_source(source, args.lang, args.name)
        project.name = args.project or args.name

    elif args.source:
        project = engine.parse_source(args.source, args.lang, args.name)
        project.name = args.project or args.name

    else:
        ap.print_help()
        sys.exit(1)

    # Print summary
    print(f"\n[summary] {project.name}")
    print(f"  Files  : {project.total_files}")
    print(f"  Nodes  : {project.total_nodes}")
    if project.errors:
        print(f"  Errors : {len(project.errors)}")
        for e in project.errors[:5]:
            print(f"    • {e}")

    # Generate XML
    generate_xml(project, args.output)


if __name__ == "__main__":
    main()
