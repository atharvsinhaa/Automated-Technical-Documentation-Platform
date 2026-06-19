#!/usr/bin/env python3
"""
combiner/main.py — CLI for Component 2: Simple Code Combiner
─────────────────────────────────────────────────────────────
Usage:
  python combiner/main.py --input backend.xml frontend.xml --output combined.xml
  python combiner/main.py --input ./xml_outputs/ --output combined.xml
  python combiner/main.py --input *.xml --project airtel --output combined.xml
"""

import argparse, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from combiner import SimpleCodeCombiner


def main():
    p = argparse.ArgumentParser(
        prog="combiner",
        description="Component 2: Simple Code Combiner — merges AST XMLs into unified XML",
    )
    p.add_argument("--input",  nargs="+", required=True, metavar="XML_OR_DIR",
                   help="One or more .xml files or directories containing XML files")
    p.add_argument("--output", default="combined.xml",
                   help="Output unified XML file (default: combined.xml)")
    p.add_argument("--project", default="",
                   help="Project name (default: inferred from first input)")
    p.add_argument("--quiet", action="store_true")
    args = p.parse_args()

    name = args.project or Path(args.input[0]).stem
    combiner = SimpleCodeCombiner(project_name=name, verbose=not args.quiet)
    combiner.combine(sources=args.input, output=args.output)


if __name__ == "__main__":
    main()
