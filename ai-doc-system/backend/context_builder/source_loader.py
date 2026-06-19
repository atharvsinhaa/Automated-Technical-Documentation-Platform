"""
context_builder/source_loader.py
────────────────────────────────────────────────────────────────
Loads actual source code from disk for inclusion in LLM context.
Does NOT load graph files — only original source code.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

from .models import ContextNode
from .utils import truncate_source


class SourceLoader:
    """Loads source code from the repository."""

    def __init__(self, source_root: str = ".", max_lines: int = 200, verbose: bool = True):
        self.source_root = Path(source_root)
        self.max_lines = max_lines
        self.verbose = verbose

    def load_file(self, file_path: str) -> Optional[str]:
        """Load the full contents of a source file."""
        path = self._resolve_path(file_path)
        if not path or not path.exists():
            if self.verbose:
                print(f"[source] File not found: {file_path}")
            return None

        try:
            content = path.read_text(encoding="utf-8", errors="replace")
            return truncate_source(content, self.max_lines)
        except Exception as e:
            if self.verbose:
                print(f"[source] Error reading {file_path}: {e}")
            return None

    def load_function(
        self,
        file_path: str,
        start_line: int,
        end_line: int,
    ) -> Optional[str]:
        """Load a specific line range from a source file."""
        path = self._resolve_path(file_path)
        if not path or not path.exists():
            return None

        try:
            lines = path.read_text(encoding="utf-8", errors="replace").split("\n")
            # Adjust to 0-indexed
            start = max(0, start_line - 1)
            end = min(len(lines), end_line)
            if start >= end:
                return None
            return "\n".join(lines[start:end])
        except Exception:
            return None

    def load_related_functions(
        self,
        nodes: List[ContextNode],
        max_functions: int = 10,
    ) -> List[Dict]:
        """Load source code for related function nodes."""
        functions = []
        seen_files: Dict[str, str] = {}  # cache loaded files

        for node in nodes:
            if len(functions) >= max_functions:
                break
            if node.node_type not in (
                "FUNCTION", "ASYNC_FUNCTION", "METHOD",
                "CONSTRUCTOR", "API_ENDPOINT",
            ):
                continue
            if not node.file_path or not node.start_line or not node.end_line:
                continue

            # Load from cache or disk
            if node.file_path not in seen_files:
                content = self._read_raw(node.file_path)
                if content:
                    seen_files[node.file_path] = content

            source = seen_files.get(node.file_path)
            if not source:
                continue

            lines = source.split("\n")
            start = max(0, node.start_line - 1)
            end = min(len(lines), node.end_line)
            if start >= end:
                continue

            func_source = "\n".join(lines[start:end])
            if len(func_source) > 2000:
                func_source = func_source[:2000] + "\n... [truncated]"

            functions.append({
                "name": node.name,
                "type": node.node_type,
                "file": node.file_path,
                "lines": f"{node.start_line}-{node.end_line}",
                "source": func_source,
            })

        if self.verbose and functions:
            print(f"[source] Loaded {len(functions)} related functions")

        return functions

    def _resolve_path(self, file_path: str) -> Optional[Path]:
        """Resolve a file path relative to source root."""
        if not file_path:
            return None

        # Try direct path
        p = Path(file_path)
        if p.is_absolute() and p.exists():
            return p

        # Try relative to source root
        p = self.source_root / file_path
        if p.exists():
            return p

        # Try stripping leading segments
        parts = file_path.split("/")
        for i in range(len(parts)):
            candidate = self.source_root / "/".join(parts[i:])
            if candidate.exists():
                return candidate

        return None

    def _read_raw(self, file_path: str) -> Optional[str]:
        """Read raw file content."""
        path = self._resolve_path(file_path)
        if path and path.exists():
            try:
                return path.read_text(encoding="utf-8", errors="replace")
            except Exception:
                pass
        return None
