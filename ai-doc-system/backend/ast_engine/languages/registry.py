"""
languages/registry.py
─────────────────────────────────────────────────────────────
ParserRegistry — dynamic, zero-hardcoding language loader.

Each language entry maps file extensions to:
  • a callable that returns a tree-sitter Language capsule
  • the canonical language name

Adding a new language = one line in LANGUAGE_DEFINITIONS.
The core engine never needs to change.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional
import threading


@dataclass(frozen=True)
class LanguageSpec:
    """Immutable spec for one language registration."""
    name: str
    extensions: tuple[str, ...]
    capsule_factory: Callable
    aliases: tuple[str, ...] = ()


# ─────────────────────────────────────────────────────────────
# LANGUAGE DEFINITIONS TABLE
# Add new languages HERE and nowhere else.
# ─────────────────────────────────────────────────────────────

def _build_definitions() -> List[LanguageSpec]:
    defs: List[LanguageSpec] = []

    def _try(name, extensions, factory, aliases=()):
        defs.append(
            LanguageSpec(
                name,
                tuple(extensions),
                factory,
                tuple(aliases),
            )
        )

    # Python (always available)
    try:
        import tree_sitter_python as m
        _try("python", [".py", ".pyw", ".pyx"], m.language)
    except ImportError:
        pass

    # JavaScript / TypeScript
    try:
        import tree_sitter_javascript as m
        _try("javascript", [".js", ".jsx", ".mjs"], m.language)
    except ImportError:
        pass
    try:
        import tree_sitter_typescript as m
        _try("typescript", [".ts", ".tsx"], m.language_typescript)
    except ImportError:
        pass

    # Java
    try:
        import tree_sitter_java as m
        _try("java", [".java"], m.language)
    except ImportError:
        pass

    # Go
    try:
        import tree_sitter_go as m
        _try("go", [".go"], m.language)
    except ImportError:
        pass

    # Rust
    try:
        import tree_sitter_rust as m
        _try("rust", [".rs"], m.language)
    except ImportError:
        pass

    # C / C++
    try:
        import tree_sitter_c as m
        _try("c", [".c", ".h"], m.language)
    except ImportError:
        pass
    try:
        import tree_sitter_cpp as m
        _try("cpp", [".cpp", ".cc", ".cxx", ".hpp"], m.language)
    except ImportError:
        pass

    return defs


# ─────────────────────────────────────────────────────────────
# REGISTRY
# ─────────────────────────────────────────────────────────────

class ParserRegistry:
    """
    Thread-safe registry of tree-sitter Language objects.

    Parsers are instantiated lazily (once per language)
    and cached.
    """

    def __init__(self):
        self._specs: Dict[str, LanguageSpec] = {}
        self._ext_map: Dict[str, str] = {}
        self._cache: Dict[str, object] = {}

        self._lock = threading.Lock()

        self._load_all()

    def _load_all(self):
        for spec in _build_definitions():
            self._specs[spec.name] = spec

            for ext in spec.extensions:
                self._ext_map[ext.lower()] = spec.name

            for alias in spec.aliases:
                self._ext_map[alias.lower()] = spec.name

    # ─────────────────────────────────────────────────────────

    def detect_language(self, file_path: str) -> Optional[str]:
        """Return language name from file extension."""
        ext = Path(file_path).suffix.lower()
        return self._ext_map.get(ext)

    def get_language(self, name: str) -> Optional[object]:
        """Return cached tree-sitter Language object."""
        name = name.lower()

        if name not in self._cache:
            spec = self._specs.get(name)

            if spec is None:
                return None

            with self._lock:
                if name not in self._cache:

                    from tree_sitter import Language

                    try:
                        self._cache[name] = Language(
                            spec.capsule_factory()
                        )

                    except Exception as e:
                        print(
                            f"[registry] Failed to load '{name}': {e}"
                        )
                        return None

        return self._cache[name]

    def get_parser(self, name: str) -> Optional[object]:
        """
        Return NEW tree-sitter Parser.

        Parsers are NOT thread-safe.
        """

        lang = self.get_language(name)

        if lang is None:
            return None

        from tree_sitter import Parser

        return Parser(lang)

    def supported_languages(self) -> List[str]:
        return sorted(self._specs.keys())

    def supported_extensions(self) -> Dict[str, str]:
        return dict(self._ext_map)

    def __repr__(self):
        return (
            f"ParserRegistry("
            f"languages={self.supported_languages()})"
        )


# Singleton
REGISTRY = ParserRegistry()

def get_supported_extensions() -> list:
    return list(REGISTRY._ext_map.keys())

