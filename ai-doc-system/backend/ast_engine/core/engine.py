"""
core/engine.py
─────────────────────────────────────────────────────────────
ASTEngine — orchestrates parsing at file and repository scale.

Responsibilities:
  • Accept input (single file, directory, GitHub URL, raw source)
  • Collect files, detect languages
  • Parse each file using the ParserRegistry
  • Walk AST using UniversalASTWalker
  • Return ParsedProject ready for XML generation

Parallel processing via ThreadPoolExecutor (tree-sitter parsers
are NOT thread-safe — we create a fresh parser per file/thread).
"""

from __future__ import annotations

import os
import sys
import tempfile
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import List, Optional

from ..languages.registry import REGISTRY
from ..core.models import ASTNode, ParsedFile, ParsedProject
from ..core.walker import UniversalASTWalker


# ─────────────────────────────────────────────────────────────
#  File collection
# ─────────────────────────────────────────────────────────────

_SKIP_DIRS = frozenset({
    "__pycache__", ".git", ".svn", ".hg", "node_modules",
    ".venv", "venv", ".env", "env",
    "dist", "build", "target", "out", ".output",
    ".mypy_cache", ".pytest_cache", ".tox",
    "eggs", ".eggs", "htmlcov", ".nyc_output", "coverage",
    ".idea", ".vscode", ".gradle", ".m2",
})

_SKIP_FILES = frozenset({
    "package-lock.json", "yarn.lock", "Pipfile.lock",
    "poetry.lock", "Cargo.lock", "go.sum",
    ".DS_Store", "Thumbs.db",
})


def collect_files(root: str, max_file_size_mb: float = 10.0) -> List[str]:
    """
    Recursively collect all parseable files under root.
    Skips hidden dirs, build artifacts, and oversized files.
    """
    max_bytes = int(max_file_size_mb * 1024 * 1024)
    paths: List[str] = []

    for dirpath, dirnames, filenames in os.walk(root):
        ALWAYS_SKIP = {"__pycache__", ".git", "venv", ".venv", "node_modules",
                       "dist", "build", ".pytest_cache", ".mypy_cache",
                       "outputs", "-docs", "commented_code", "test_repo",
                       "mock_repos", "fixtures", "samples", "examples", "tests"}
        dirnames[:] = [d for d in dirnames if d not in ALWAYS_SKIP
                   and not d.endswith("-docs") and not d.startswith(".")]

        for fname in sorted(filenames):
            if fname in _SKIP_FILES:
                continue
            fpath = os.path.join(dirpath, fname)
            if REGISTRY.detect_language(fpath) is None:
                continue
            try:
                if os.path.getsize(fpath) > max_bytes:
                    print(f"[skip] {fpath} exceeds {max_file_size_mb}MB")
                    continue
            except OSError:
                continue
            paths.append(fpath)

    return paths


# ─────────────────────────────────────────────────────────────
#  Single-file parsing (called in parallel)
# ─────────────────────────────────────────────────────────────

def parse_one_file(file_path: str) -> ParsedFile:
    """
    Parse a single file:
      1. Detect language
      2. Read source
      3. Get a tree-sitter parser from registry (new instance = thread-safe)
      4. Walk the parse tree
      5. Return ParsedFile
    """
    language = REGISTRY.detect_language(file_path)
    if language is None:
        return ParsedFile(file_path=file_path, language="unknown",
                          total_lines=0, errors=["unsupported language"])

    try:
        source = Path(file_path).read_text(encoding="utf-8", errors="ignore")
    except OSError as e:
        return ParsedFile(file_path=file_path, language=language,
                          total_lines=0, errors=[f"read error: {e}"])

    total_lines = source.count("\n") + 1
    result = ParsedFile(file_path=file_path, language=language,
                        total_lines=total_lines)

    # SQL: tree-sitter SQL grammar not universally available;
    # use our lightweight SQL extractor
    if language == "sql":
        from ..extractors.sql_extractor import extract_sql
        result.nodes = extract_sql(file_path, source)
        return result

    parser = REGISTRY.get_parser(language)
    if parser is None:
        result.errors.append(f"no tree-sitter parser for '{language}'")
        return result

    try:
        src_bytes = source.encode("utf-8")
        tree = parser.parse(src_bytes)
        walker = UniversalASTWalker()
        result.nodes = walker.walk(tree.root_node, src_bytes, file_path, language)
    except Exception as e:
        result.errors.append(f"parse error: {e}")

    return result


# ─────────────────────────────────────────────────────────────
#  GitHub clone helper
# ─────────────────────────────────────────────────────────────

def _clone_github(url: str, dest: str) -> str:
    try:
        import git
        print(f"[git] Cloning {url} → {dest} …", flush=True)
        git.Repo.clone_from(url, dest, depth=1, no_single_branch=False)
        print(f"[git] Clone complete.")
        return dest
    except ImportError:
        raise RuntimeError(
            "gitpython not installed.\n"
            "Run: pip install gitpython\n"
            "Or clone the repo manually and use directory input."
        )


# ─────────────────────────────────────────────────────────────
#  ENGINE
# ─────────────────────────────────────────────────────────────

class ASTEngine:
    """
    Top-level orchestrator.

    Usage:
        engine = ASTEngine(workers=8)
        project = engine.parse_directory("./my_repo", "my_project")
        project = engine.parse_github("https://github.com/org/repo")
        project = engine.parse_files(["a.py", "b.js"])
        project = engine.parse_source("def foo(): pass", "python", "snippet.py")
    """

    def __init__(
        self,
        workers:          int   = 4,
        max_file_size_mb: float = 10.0,
        verbose:          bool  = True,
    ):
        self.workers          = workers
        self.max_file_size_mb = max_file_size_mb
        self.verbose          = verbose

    # ── Public parse methods ───────────────────────────────────

    def parse_directory(self, root: str, project_name: str = "") -> ParsedProject:
        """Parse all files in a directory recursively."""
        if not os.path.isdir(root):
            raise FileNotFoundError(f"Directory not found: {root}")
        name = project_name or Path(root).name
        files = collect_files(root, self.max_file_size_mb)
        if self.verbose:
            print(f"[engine] {len(files)} file(s) found in '{root}'")
        return self._run(files, name, root)

    def parse_github(self, url: str, project_name: str = "") -> ParsedProject:
        """Clone a GitHub repo and parse it."""
        tmp = tempfile.mkdtemp(prefix="ast_engine_")
        try:
            repo_dir = os.path.join(tmp, "repo")
            _clone_github(url, repo_dir)
            name = project_name or url.rstrip("/").split("/")[-1]
            return self.parse_directory(repo_dir, name)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def parse_files(
        self, file_paths: List[str], project_name: str = "project"
    ) -> ParsedProject:
        """Parse a specific list of files."""
        existing = [f for f in file_paths if os.path.isfile(f)]
        missing  = [f for f in file_paths if not os.path.isfile(f)]
        project  = ParsedProject(name=project_name, root_path="<explicit>")
        project.errors.extend([f"not found: {f}" for f in missing])
        if self.verbose:
            print(f"[engine] Parsing {len(existing)} file(s)")
        parsed = self._run(existing, project_name, "<explicit>")
        parsed.errors.extend(project.errors)
        return parsed

    def parse_source(
        self,
        source: str,
        language: str,
        name: str = "snippet",
    ) -> ParsedProject:
        """Parse a string of source code directly."""
        import tempfile, os
        suffix = {"python":".py","javascript":".js","typescript":".ts",
                  "java":".java","go":".go","rust":".rs","sql":".sql"}.get(language,".txt")
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False,
                                         mode="w", encoding="utf-8") as f:
            f.write(source)
            tmp_path = f.name
        try:
            result = self._run([tmp_path], name, "<source>")
            # Fix up the file_path to show the intended name
            for pf in result.files:
                pf.file_path = name
                for node in pf.nodes:
                    node.file_path = name
            return result
        finally:
            os.unlink(tmp_path)

    # ── Internal ───────────────────────────────────────────────

    def _run(
        self, file_paths: List[str], project_name: str, root_path: str
    ) -> ParsedProject:
        project = ParsedProject(name=project_name, root_path=root_path)

        if not file_paths:
            project.errors.append("no parseable files found")
            return project

        # Parallel parsing
        with ThreadPoolExecutor(max_workers=self.workers) as pool:
            future_map = {pool.submit(parse_one_file, fp): fp
                          for fp in file_paths}
            for future in as_completed(future_map):
                fp = future_map[future]
                try:
                    pf = future.result()
                    project.files.append(pf)
                    if self.verbose:
                        ok = "✓" if not pf.errors else "⚠"
                        rel = os.path.relpath(fp, root_path) if root_path != "<explicit>" else fp
                        print(f"  {ok}  {pf.language:<14} {rel:<55} nodes={pf.node_count}")
                except Exception as e:
                    project.errors.append(f"{fp}: {e}")
                    if self.verbose:
                        print(f"  ✗  {fp}: {e}")

        # Sort files deterministically for consistent XML output
        project.files.sort(key=lambda pf: pf.file_path)
        return project
