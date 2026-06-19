"""
semantic_ir/component_builder.py
────────────────────────────────────────────────────────────────
KG-Grounded Component Builder.

Replaces the old directory-scan approach that used a hardcoded
COMPONENT_MAPPING dict. Now delegates entirely to KGToIRTranslator
to extract components from the Knowledge Graph.

Backward compatibility: build(repo_path, kg) still returns
List[IRComponent], but the repo_path is only used as a fallback.
"""

from __future__ import annotations

import os
from typing import List, Optional

from backend.semantic_ir.models import IRComponent


class ComponentBuilder:

    def build(
        self,
        repo_path: str,
        kg=None,
    ) -> List[IRComponent]:
        """
        Build component list from the Knowledge Graph.

        Args:
            repo_path: Repository root path (used only as fallback).
            kg: KnowledgeGraph instance. If provided, components
                are extracted from the graph. If None, falls back
                to directory-based scanning.

        Returns:
            List of IRComponent instances.
        """
        # ── Strategy 1: Use KG translator if KG is available ──
        if kg is not None:
            from backend.semantic_bridge.kg_to_ir_translator import (
                KGToIRTranslator,
            )
            translator = KGToIRTranslator(verbose=False)
            return translator._extract_components(kg)

        # ── Strategy 2: Directory-based fallback ──────────────
        return self._fallback_directory_scan(repo_path)

    def _fallback_directory_scan(self, repo_path: str) -> List[IRComponent]:
        """
        Fallback: scan top-level directories and create components
        from directory names. No hardcoded component descriptions.
        """
        components = []

        # Try common source roots
        source_roots = [
            os.path.join(repo_path, "backend"),
            os.path.join(repo_path, "src"),
            os.path.join(repo_path, "app"),
            os.path.join(repo_path, "lib"),
            repo_path,
        ]

        for root in source_roots:
            if not os.path.isdir(root):
                continue

            for entry in sorted(os.listdir(root)):
                entry_path = os.path.join(root, entry)
                if not os.path.isdir(entry_path):
                    continue
                if entry.startswith(".") or entry in (
                    "__pycache__", "node_modules", "venv", ".git",
                    "dist", "build", "egg-info",
                ):
                    continue

                # Collect files
                files = []
                for dirpath, _, filenames in os.walk(entry_path):
                    for fname in filenames:
                        if fname.endswith(
                            (".py", ".js", ".ts", ".java", ".go", ".cs", ".rb")
                        ):
                            rel = os.path.relpath(
                                os.path.join(dirpath, fname), repo_path
                            )
                            files.append(rel)

                if not files:
                    continue

                clean_name = entry.replace("_", " ").title()

                components.append(IRComponent(
                    name=clean_name,
                    component_type="Module",
                    description=(
                        f"{clean_name}: contains {len(files)} source file(s)"
                    ),
                    files=files,
                    confidence="low",
                ))

            if components:
                break  # Found a valid source root

        return components