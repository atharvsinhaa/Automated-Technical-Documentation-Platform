"""
combiner/combiner.py
──────────────────────────────────────────────────────────────
SimpleCodeCombiner — top-level orchestrator for Component 2.

This is the single entry point for the entire combiner pipeline:

  Input XML(s)
      ↓
  XMLMerger        → List[FileRecord]
      ↓
  Normalizer       → canonical symbol names
      ↓
  CrossFileLinker  → List[Dependency], List[SQLTable]
      ↓
  SymbolIndex      → List[NormalizedSymbol]
      ↓
  XMLExporter      → combined_output.xml

Fully offline. No external APIs. No AI.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import List, Optional

from .xml_merger  import merge
from .normalizer  import normalize_files, build_symbol_index
from .linker      import CrossFileLinker
from .exporter    import export_xml
from .models      import CombinedProject


class SimpleCodeCombiner:
    """
    Usage:
        combiner = SimpleCodeCombiner(project_name="airtel_backend")

        # Option A: pass XML file paths directly
        combiner.combine(
            sources=["backend.xml", "frontend.xml"],
            output="combined.xml"
        )

        # Option B: pass a directory of XML files
        combiner.combine(
            sources=["./xml_outputs/"],
            output="combined.xml"
        )
    """

    def __init__(
        self,
        project_name: str = "project",
        verbose:      bool = True,
    ):
        self.project_name = project_name
        self.verbose      = verbose

    def combine(
        self,
        sources: List[str],
        output:  str = "combined.xml",
    ) -> CombinedProject:
        """
        Run the full combiner pipeline.
        sources: list of .xml file paths or directories containing .xml files.
        output: path to write the unified XML output.
        Returns the populated CombinedProject.
        """
        self._log(f"=== Simple Code Combiner: {self.project_name} ===")

        # ── 1. Load + merge XML ───────────────────────────────
        self._log(f"[1/4] Loading XML from {len(sources)} source(s)…")
        files = merge(sources)
        if not files:
            raise ValueError("No FileRecord objects loaded from provided sources.")
        self._log(f"      Loaded {len(files)} file(s)")

        # ── 2. Normalize ──────────────────────────────────────
        self._log("[2/4] Normalizing symbol names…")
        files = normalize_files(files)
        symbol_index = build_symbol_index(files)
        symbols = list(symbol_index.values())
        self._log(f"      {len(symbols)} unique canonical symbols")

        # ── 3. Link ───────────────────────────────────────────
        self._log("[3/4] Detecting cross-file dependencies…")
        linker = CrossFileLinker(files)
        deps, sql_tables = linker.detect_all()

        if self.verbose:
            from collections import Counter
            by_type = Counter(d.dep_type for d in deps)
            for dtype, cnt in sorted(by_type.items(), key=lambda x: -x[1]):
                self._log(f"      {dtype:<20} {cnt}")
            self._log(f"      SQL tables found: {len(sql_tables)}")

        # ── 4. Build model ────────────────────────────────────
        project = CombinedProject(
            name=self.project_name,
            source_files=sources,
            files=files,
            dependencies=deps,
            sql_tables=sql_tables,
            symbols=symbols,
        )

        # ── 5. Export XML ─────────────────────────────────────
        self._log(f"[4/4] Exporting unified XML → {output}")
        export_xml(project, output)

        # Print final summary
        self._log("")
        self._log(f"  Files       : {len(files)}")
        self._log(f"  Total nodes : {project.total_nodes}")
        self._log(f"  Dependencies: {len(deps)}")
        self._log(f"  SQL tables  : {len(sql_tables)}")
        self._log(f"  Symbols     : {len(symbols)}")
        self._log(f"  Output      : {output}")

        return project

    def _log(self, msg: str):
        if self.verbose:
            print(msg, flush=True)
