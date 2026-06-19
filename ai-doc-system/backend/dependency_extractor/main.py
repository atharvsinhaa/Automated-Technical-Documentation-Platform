#!/usr/bin/env python3
"""
Component 3 CLI
Usage:
  python dependency_extractor/main.py --input combined.xml --output graph.xml
  python dependency_extractor/main.py --input combined.xml --output graph.xml --cypher graph.cypher
  python dependency_extractor/main.py --input combined.xml --output graph.xml --neo4j bolt://localhost:7687
"""
import argparse, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from dependency_extractor import DependencyExtractor
from dependency_extractor.neo4j_exporter import push_to_neo4j

def main():
    p = argparse.ArgumentParser(description="Component 3: Dependency Extractor + Graph Builder")
    p.add_argument("--input",   required=True, help="Path to combined XML (Component 2 output)")
    p.add_argument("--output",  default="graph_dependencies.xml", help="Output graph XML")
    p.add_argument("--cypher",  default="", help="Also write Neo4j Cypher batch file")
    p.add_argument("--project", default="", help="Project name")
    p.add_argument("--neo4j",   default="", help="Neo4j bolt URI (live push, optional)")
    p.add_argument("--neo4j-user", default="neo4j")
    p.add_argument("--neo4j-pass", default="password")
    p.add_argument("--quiet",   action="store_true")
    args = p.parse_args()

    name = args.project or Path(args.input).stem
    extractor = DependencyExtractor(project_name=name, verbose=not args.quiet)
    graph = extractor.extract(
        combined_xml  = args.input,
        output_xml    = args.output,
        output_cypher = args.cypher,
    )

    if args.neo4j:
        push_to_neo4j(graph, uri=args.neo4j,
                      user=args.neo4j_user, password=args.neo4j_pass)

if __name__ == "__main__":
    main()
