"""
comment_engine/inline_commentor.py
────────────────────────────────────────────────────────────────
LLM-Powered Inline Comment Injector.

Replaces the old version that used a canned role→string map
(9 hardcoded comment strings). Now uses the Universal AST to
identify functions/classes, builds context from the Knowledge
Graph (when available), and generates meaningful, code-specific
comments via the LLM orchestrator.

Falls back to context-aware template comments when no LLM
is available, using actual function signatures, parameter names,
and return types from the AST.

Backward compatibility: inject_comments(source_file, output_file)
"""

from __future__ import annotations

import os
import re
import shutil
from typing import List, Optional, Tuple

from backend.universal_ast.normalizer import (
    UniversalASTNormalizer,
)


class ASTInlineCommentor:

    def __init__(self, llm_client=None, kg=None):
        """
        Initialize the inline commentor.

        Args:
            llm_client: Optional LLM client (BaseLLMClient).
                        If provided, uses LLM for comment generation.
                        If None, uses intelligent template comments.
            kg: Optional KnowledgeGraph instance.
                If provided, uses graph context for richer comments.
        """
        self.normalizer = UniversalASTNormalizer()
        self.llm_client = llm_client
        self.kg = kg

    # ==========================================
    # MAIN COMMENT INJECTION
    # ==========================================

    def inject_comments(
        self,
        source_file: str,
        output_file: str,
    ):
        """
        Read a source file, generate semantic comments for each
        function/class, and write the commented file to output.
        """
        ext = os.path.splitext(source_file)[1].lower()
        if ext in (".sql", ".txt", ""):
            # Maybe it's SQL or sniffed extensionless
            try:
                # Basic check to avoid breaking non-SQL extensionless files
                with open(source_file, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read(4096).upper()
                if re.search(r'\b(?:CREATE\s+(?:DEFINER|OR\s+REPLACE|PROCEDURE|FUNCTION)|BEGIN|DELIMITER|INSERT\s+INTO|SELECT|UPDATE)\b', content, re.IGNORECASE):
                    self._inject_sql_comments(source_file, output_file)
                    return
            except Exception:
                pass

        # =========================
        # READ SOURCE FILE
        # =========================

        with open(
            source_file,
            "r",
            encoding="utf-8",
            errors="ignore",
        ) as file:
            source_code = file.read()

        original_lines = source_code.splitlines()
        lines = list(original_lines)  # work on a copy

        # =========================
        # UNIVERSAL AST NODES
        # =========================

        universal_nodes = self.normalizer.normalize_file(
            source_file,
        )

        inserts: List[Tuple[int, str]] = []

        # =========================
        # GENERATE COMMENTS
        # =========================

        for node in universal_nodes:
            comment = self._generate_comment(
                node, source_code, source_file,
            )
            if comment:
                inserts.append(
                    (node.line - 1, comment)
                )

        # =========================
        # INSERT COMMENTS
        # =========================
        # Track which line indices in the output are
        # injected comment lines (for integrity check).

        injected_line_indices: set = set()
        offset = 0
        for lineno, comment in sorted(inserts):
            comment_lines = comment.split("\n")
            insert_pos = lineno + offset
            for i, cl in enumerate(comment_lines):
                lines.insert(insert_pos + i, cl)
                injected_line_indices.add(insert_pos + i)
            offset += len(comment_lines)

        final_code = "\n".join(lines)

        # =========================
        # CREATE OUTPUT DIRECTORY
        # =========================

        os.makedirs(
            os.path.dirname(output_file),
            exist_ok=True,
        )

        # =========================
        # INTEGRITY VERIFICATION
        # (before writing: compare non-injected lines
        #  against the original source)
        # =========================

        non_injected = [
            line for idx, line in enumerate(lines)
            if idx not in injected_line_indices
        ]

        if non_injected != original_lines:
            # Code was altered — log bug, write original
            for i, (orig, got) in enumerate(
                zip(original_lines, non_injected), start=1,
            ):
                if orig != got:
                    print(
                        f"[BUG] Code integrity violation in "
                        f"{source_file} at line {i}:\n"
                        f"  ORIGINAL: {orig!r}\n"
                        f"  GOT:      {got!r}"
                    )
                    break
            else:
                if len(non_injected) != len(original_lines):
                    print(
                        f"[BUG] Code integrity violation in "
                        f"{source_file}: line count mismatch "
                        f"(original={len(original_lines)}, "
                        f"filtered={len(non_injected)})"
                    )

            # Fall back: copy the original unmodified
            os.makedirs(
                os.path.dirname(output_file),
                exist_ok=True,
            )
            shutil.copy2(source_file, output_file)
            print(
                f"[FALLBACK] Copied original (integrity fail): "
                f"{output_file}"
            )
            return

        # =========================
        # WRITE OUTPUT FILE
        # =========================

        with open(
            output_file,
            "w",
            encoding="utf-8",
        ) as file:
            file.write(final_code)

        print(
            f"[SUCCESS] Semantic comments injected: "
            f"{output_file}"
        )

    # ==========================================
    # COMMENT GENERATION (LLM or Template)
    # ==========================================

    def _generate_comment(
        self,
        universal_node,
        source_code: str,
        source_file: str,
    ) -> str:
        """
        Generate a comment for a single AST node.

        Strategy:
        1. If LLM client is available → send to LLM with context
        2. Else → generate context-aware template comment using
           actual function name, parameters, node type, and
           Knowledge Graph context
        """
        if self.llm_client:
            return self._llm_comment(
                universal_node, source_code, source_file,
            )

        return self._template_comment(
            universal_node, source_file,
        )

    def _llm_comment(
        self,
        node,
        source_code: str,
        source_file: str,
    ) -> str:
        """Generate a comment using the LLM."""
        # Build context from KG if available
        kg_context = ""
        if self.kg:
            kg_context = self._build_kg_context(
                node, source_file,
            )

        # Extract the function/class body (up to 30 lines)
        body = self._extract_body(
            source_code, node.line, max_lines=30,
        )

        system_prompt = (
            "You are a senior software engineer adding inline code comments. "
            "Generate a concise, business-meaningful comment (2-4 lines) "
            "that explicitly explains INTENT, ASSUMPTIONS, SIDE EFFECTS, and ARCHITECTURAL PURPOSE. "
            "Do NOT merely restate the function name. Focus on the 'why' and 'how it fits into the broader system'. "
            "Return ONLY the comment lines prefixed with #."
        )

        user_prompt = (
            f"Generate a comment for this {node.node_type}:\n\n"
            f"Name: {node.name}\n"
            f"File: {os.path.basename(source_file)}\n"
            f"Language: {node.language}\n\n"
            f"Code:\n```\n{body}\n```\n"
        )

        if kg_context:
            user_prompt += f"\nSystem Context:\n{kg_context}\n"

        try:
            response = self.llm_client.generate(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                max_tokens=150,
                temperature=0.15,
            )
            # Ensure each line starts with #
            comment_lines = []
            for line in response.strip().split("\n"):
                line = line.strip()
                if line and not line.startswith("#"):
                    line = f"# {line}"
                if line:
                    comment_lines.append(line)
            return "\n".join(comment_lines[:3])

        except Exception as e:
            print(f"[WARN] LLM comment failed for {node.name}: {e}")
            return self._template_comment(node, source_file)

    def _template_comment(
        self,
        node,
        source_file: str,
    ) -> str:
        """
        Generate a context-aware template comment.

        Uses the actual function/class name, semantic role,
        and file context to produce a meaningful comment —
        NOT a canned string.
        """
        name = node.name
        node_type = node.node_type
        role = node.semantic_role
        filename = os.path.basename(source_file)
        prefix = self._comment_prefix(source_file)

        if node_type == "function":
            purpose = self._infer_function_purpose(name)
            
            # Suppress if purpose is just the name restated
            name_words = set(re.sub(r'_', ' ', name.lower()).split())
            purpose_words = set(purpose.lower().split())
            overlap = name_words & purpose_words - {"the", "a", "an", "of", "in", "to", "for", "with", "and"}
            
            # Stricter suppression: if it merely restates function name e.g. "gets user" for `get_user`
            if len(overlap) >= len(name_words) * 0.5:
                return ""   # Don't inject — adds no value
                
            return (
                f"{prefix} {purpose}\n"
                f"{prefix} Function: {name} (in {filename})"
            )

        elif node_type == "class":
            purpose = self._infer_class_purpose(name)
            return (
                f"{prefix} Class: {name}\n"
                f"{prefix} {purpose}\n"
                f"{prefix} Defined in: {filename}"
            )

        elif node_type == "import":
            purpose = self._infer_import_purpose(name)
            return f"{prefix} {purpose}"

        return f"{prefix} {name}: {self._infer_general_purpose(name, role)}"

    # ==========================================
    # PURPOSE INFERENCE FROM NAMING
    # ==========================================

    def _infer_function_purpose(self, name: str) -> str:
        """Infer function purpose from naming conventions."""
        name_lower = name.lower()

        # Common verb prefixes
        if name_lower.startswith("get_") or name_lower.startswith("fetch_"):
            subject = name.split("_", 1)[1] if "_" in name else name
            return f"Retrieves {subject.replace('_', ' ')}"

        if name_lower.startswith("set_") or name_lower.startswith("update_"):
            subject = name.split("_", 1)[1] if "_" in name else name
            return f"Updates {subject.replace('_', ' ')}"

        if name_lower.startswith("create_") or name_lower.startswith("add_"):
            subject = name.split("_", 1)[1] if "_" in name else name
            return f"Creates new {subject.replace('_', ' ')}"

        if name_lower.startswith("delete_") or name_lower.startswith("remove_"):
            subject = name.split("_", 1)[1] if "_" in name else name
            return f"Removes {subject.replace('_', ' ')}"

        if name_lower.startswith("is_") or name_lower.startswith("has_"):
            subject = name.split("_", 1)[1] if "_" in name else name
            return f"Checks whether {subject.replace('_', ' ')}"

        if name_lower.startswith("validate_") or name_lower.startswith("check_"):
            subject = name.split("_", 1)[1] if "_" in name else name
            return f"Validates {subject.replace('_', ' ')}"

        if name_lower.startswith("process_") or name_lower.startswith("handle_"):
            subject = name.split("_", 1)[1] if "_" in name else name
            return f"Processes {subject.replace('_', ' ')}"

        if name_lower.startswith("parse_"):
            subject = name.split("_", 1)[1] if "_" in name else name
            return f"Parses {subject.replace('_', ' ')} into structured data"

        if name_lower.startswith("build_") or name_lower.startswith("construct_"):
            subject = name.split("_", 1)[1] if "_" in name else name
            return f"Constructs {subject.replace('_', ' ')}"

        if name_lower.startswith("init") or name_lower == "__init__":
            return "Initializes the instance with required configuration"

        if name_lower.startswith("save_") or name_lower.startswith("write_"):
            subject = name.split("_", 1)[1] if "_" in name else name
            return f"Persists {subject.replace('_', ' ')} to storage"

        if name_lower.startswith("load_") or name_lower.startswith("read_"):
            subject = name.split("_", 1)[1] if "_" in name else name
            return f"Loads {subject.replace('_', ' ')} from storage"

        if name_lower.startswith("convert_") or name_lower.startswith("transform_"):
            subject = name.split("_", 1)[1] if "_" in name else name
            return f"Transforms {subject.replace('_', ' ')}"

        if name_lower.startswith("send_") or name_lower.startswith("emit_"):
            subject = name.split("_", 1)[1] if "_" in name else name
            return f"Sends {subject.replace('_', ' ')}"

        if name_lower.startswith("render_") or name_lower.startswith("display_"):
            subject = name.split("_", 1)[1] if "_" in name else name
            return f"Renders {subject.replace('_', ' ')}"

        # Fallback: use the name itself
        readable = name.replace("_", " ").strip()
        return f"Handles {readable} logic"

    def _infer_class_purpose(self, name: str) -> str:
        """Infer class purpose from naming conventions."""
        name_lower = name.lower()

        if "service" in name_lower:
            return f"Service layer: orchestrates {name.replace('Service', '').strip()} business logic"
        if "controller" in name_lower:
            return f"API controller: handles HTTP requests for {name.replace('Controller', '').strip()}"
        if "repository" in name_lower:
            return f"Data access layer: manages persistence for {name.replace('Repository', '').strip()}"
        if "model" in name_lower:
            return f"Data model: represents {name.replace('Model', '').strip()} entity"
        if "handler" in name_lower:
            return f"Event/request handler for {name.replace('Handler', '').strip()} operations"
        if "factory" in name_lower:
            return f"Factory: creates instances of {name.replace('Factory', '').strip()}"
        if "builder" in name_lower:
            return f"Builder: constructs {name.replace('Builder', '').strip()} step by step"
        if "validator" in name_lower:
            return f"Validator: enforces rules for {name.replace('Validator', '').strip()}"
        if "mapper" in name_lower:
            return f"Mapper: transforms {name.replace('Mapper', '').strip()} between representations"
        if "config" in name_lower:
            return f"Configuration: defines settings for {name.replace('Config', '').strip()}"
        if "middleware" in name_lower:
            return f"Middleware: intercepts and processes requests for {name.replace('Middleware', '').strip()}"
        if "client" in name_lower:
            return f"Client: communicates with {name.replace('Client', '').strip()} external service"
        if "adapter" in name_lower:
            return f"Adapter: bridges {name.replace('Adapter', '').strip()} to the system interface"

        readable = name.replace("_", " ").strip()
        return f"Encapsulates {readable} functionality"

    def _infer_general_purpose(self, name: str, role: str) -> str:
        """Infer purpose from name and semantic role."""
        readable = name.replace("_", " ").strip()
        if role and role != "general_processing":
            role_readable = role.replace("_", " ").strip()
            return f"Handles {role_readable}: {readable}"
        return f"Implements {readable}"

    # ==========================================
    # SQL COMMENT INJECTION (REGEX FALLBACK)
    # ==========================================

    def _inject_sql_comments(self, source_file: str, output_file: str):
        """
        Fallback regex-based injection for SQL files, which don't have
        AST coverage. Parses for CREATE PROCEDURE, IF, CASE, and CURSOR,
        and injects standard comments while preserving exact lines.
        """
        with open(source_file, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()

        final_lines = []
        
        proc_re = re.compile(r'^\s*CREATE\s+(?:DEFINER\s*=\s*\S+\s+)?(?:OR\s+REPLACE\s+)?(?:PROCEDURE|FUNCTION)\s+`?([a-zA-Z0-9_]+)`?', re.IGNORECASE)
        if_re = re.compile(r'^\s*IF\s+', re.IGNORECASE)
        case_re = re.compile(r'^\s*CASE\s+', re.IGNORECASE)
        cursor_re = re.compile(r'^\s*DECLARE\s+[a-zA-Z0-9_]+\s+CURSOR\s+FOR', re.IGNORECASE)
        
        for line in lines:
            line_str = line.upper()
            indent = line[:len(line) - len(line.lstrip())]
            
            proc_match = proc_re.search(line)
            if proc_match:
                p_name = proc_match.group(1)
                final_lines.append(f"{indent}-- ==================================================================\n")
                final_lines.append(f"{indent}-- Procedure: {p_name}\n")
                final_lines.append(f"{indent}-- Purpose: Handles execution flow and data operations for {p_name}\n")
                final_lines.append(f"{indent}-- Note: This block was automatically identified by semantic analysis\n")
                final_lines.append(f"{indent}-- ==================================================================\n")
            elif if_re.search(line) and not line_str.lstrip().startswith("--"):
                final_lines.append(f"{indent}-- [Logic Block] Conditional evaluation\n")
            elif case_re.search(line) and not line_str.lstrip().startswith("--"):
                final_lines.append(f"{indent}-- [Logic Block] Case routing logic\n")
            elif cursor_re.search(line) and not line_str.lstrip().startswith("--"):
                final_lines.append(f"{indent}-- [Logic Block] Cursor declaration for row-by-row processing\n")
                
            final_lines.append(line)

        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as f:
            f.writelines(final_lines)

    # ==========================================
    # IMPORT PURPOSE INFERENCE
    # ==========================================

    _WELL_KNOWN_IMPORTS: dict = {
        # Python stdlib
        "os": "Provides tools for working with files, folders, and system settings",
        "sys": "Gives access to Python runtime settings and command-line arguments",
        "json": "Reads and writes JSON data (a common format for exchanging information)",
        "re": "Finds and manipulates text patterns (regular expressions)",
        "datetime": "Works with dates and times",
        "time": "Measures elapsed time and adds delays",
        "pathlib": "Offers a modern way to work with file and folder paths",
        "typing": "Adds type hints so code editors can catch mistakes early",
        "collections": "Provides specialized data containers (counters, ordered dicts, etc.)",
        "dataclasses": "Automatically generates boilerplate code for data-holding classes",
        "abc": "Defines abstract base classes (blueprints that other classes must follow)",
        "functools": "Supplies helper tools for working with functions (caching, decorating, etc.)",
        "itertools": "Efficient looping utilities for combining and filtering data",
        "logging": "Records messages about what the program is doing (for debugging and monitoring)",
        "subprocess": "Runs other programs or shell commands from inside Python",
        "threading": "Lets multiple tasks run at the same time inside one program",
        "uuid": "Generates unique identifiers (IDs that will never repeat)",
        "hashlib": "Creates secure fingerprints (hashes) of data for verification",
        "shutil": "Copies, moves, and deletes files and folders",
        "tempfile": "Creates temporary files and folders that clean up automatically",
        "argparse": "Parses command-line arguments so the program can accept user options",
        "ast": "Reads Python source code and turns it into a structured tree for analysis",
        "traceback": "Formats error details so developers can find where things went wrong",
        "math": "Provides mathematical functions like square root, rounding, and trigonometry",
        "io": "Handles reading and writing data streams (in-memory files, byte buffers, etc.)",
        "enum": "Defines named constants (fixed choices like status codes or categories)",
        "copy": "Creates copies of objects so the original stays unchanged",
        "glob": "Finds files matching a name pattern (e.g. all .py files in a folder)",
        "csv": "Reads and writes spreadsheet-style CSV files",
        "http": "Provides basic tools for making and handling web requests",
        "urllib": "Fetches data from URLs (web addresses)",
        "socket": "Low-level networking — sending and receiving data over the internet",
        "struct": "Converts between Python values and raw binary data",
        "contextlib": "Helpers for writing 'with' blocks (resource management)",
        "inspect": "Examines live objects and source code at runtime",
        "warnings": "Issues non-fatal alerts to developers about potential problems",
        "textwrap": "Wraps and formats text for cleaner display",
        "pprint": "Pretty-prints complex data structures for easy reading",
        # Common third-party
        "fastapi": "A modern web framework for building fast API servers",
        "flask": "A lightweight web framework for building web applications",
        "django": "A full-featured web framework for building large web applications",
        "requests": "Sends HTTP requests to web servers (downloading pages, calling APIs)",
        "numpy": "Fast math library for working with large arrays of numbers",
        "pandas": "Analyzes and manipulates tabular data (like spreadsheets)",
        "pydantic": "Validates and structures data using Python type hints",
        "sqlalchemy": "Talks to databases using Python objects instead of raw SQL",
        "pytest": "A testing framework that makes writing and running tests easy",
        "dotenv": "Loads configuration from .env files so secrets stay out of code",
        "uvicorn": "A fast web server that runs Python ASGI applications",
        "starlette": "Core toolkit for building fast async web applications",
        "jinja2": "A template engine for generating HTML or text from templates",
        "celery": "Runs background tasks asynchronously (e.g. sending emails, processing jobs)",
        "redis": "Connects to Redis — a fast in-memory database for caching",
        "boto3": "Official Python toolkit for interacting with Amazon Web Services (AWS)",
        "docker": "Controls Docker containers programmatically",
        "yaml": "Reads and writes YAML configuration files",
        "toml": "Reads and writes TOML configuration files",
        "click": "Builds command-line interfaces with minimal code",
        "rich": "Adds colors, tables, and progress bars to terminal output",
        "httpx": "Modern HTTP client supporting both sync and async requests",
        "aiohttp": "Makes asynchronous HTTP requests (non-blocking web calls)",
        "pymongo": "Connects to MongoDB databases for reading and writing data",
        "pillow": "Opens, manipulates, and saves image files",
        "matplotlib": "Creates charts, graphs, and visualizations from data",
        "scipy": "Scientific computing tools for optimization, statistics, and signal processing",
        "scikit-learn": "Machine learning library for classification, regression, and clustering",
        "tensorflow": "Deep learning framework for building and training neural networks",
        "torch": "PyTorch — deep learning framework for research and production",
        "transformers": "Pre-trained AI models for text, images, and more (by Hugging Face)",
        # JS / TS ecosystem
        "react": "UI library for building interactive user interfaces",
        "express": "Minimal web framework for building Node.js servers",
        "axios": "HTTP client for making API requests from browsers or Node.js",
        "lodash": "Utility library providing helper functions for arrays, objects, and strings",
        "moment": "Parses, validates, and formats dates and times",
        "rxjs": "Reactive programming library for handling asynchronous data streams",
        "@angular/core": "Core Angular framework for building web applications",
        "@angular/common": "Common Angular utilities (directives, pipes, HTTP helpers)",
        "@angular/router": "Angular routing module for navigating between pages",
        "@angular/forms": "Angular forms module for handling user input and validation",
        "@angular/common/http": "Angular HTTP client for making API calls",
        "vue": "Progressive JavaScript framework for building user interfaces",
        "next": "React framework for server-rendered and static web applications",
        "typescript": "Adds static type checking to JavaScript for fewer runtime errors",
        "webpack": "Bundles JavaScript modules and assets for the browser",
        "vite": "Fast build tool and dev server for modern web projects",
        "jest": "JavaScript testing framework with built-in assertions and mocking",
        "mocha": "Flexible JavaScript test framework for Node.js and browsers",
        "jszip": "Creates, reads, and edits ZIP archive files in JavaScript",
        "d3": "Data visualization library for creating interactive charts and maps",
        "three": "3D graphics library for rendering scenes in the browser",
        "socket.io": "Real-time bidirectional communication between browsers and servers",
        "mongoose": "MongoDB object modeling tool for Node.js applications",
        "sequelize": "SQL database ORM for Node.js (supports Postgres, MySQL, SQLite)",
        "prisma": "Modern database toolkit and ORM for TypeScript and Node.js",
        "graphql": "Query language for APIs — lets clients request exactly the data they need",
        "tailwindcss": "Utility-first CSS framework for rapidly building custom designs",
        "bootstrap": "Popular CSS framework for responsive, mobile-first web pages",
    }

    def _infer_import_purpose(self, name: str) -> str:
        """Return a plain-English explanation of what this import provides."""
        # Direct match
        if name in self._WELL_KNOWN_IMPORTS:
            return f"Loads the '{name}' library — {self._WELL_KNOWN_IMPORTS[name]}"

        # Try matching the top-level package (e.g. "backend.utils.foo" → "backend")
        top = name.split(".")[0] if "." in name else None
        if top and top in self._WELL_KNOWN_IMPORTS:
            return (
                f"Loads '{name}' from the '{top}' library — "
                f"{self._WELL_KNOWN_IMPORTS[top]}"
            )

        # Internal / project-local import heuristic
        if "." in name or name.startswith("backend"):
            readable = name.replace(".", " → ").replace("_", " ")
            return f"Loads an internal project module: {readable}"

        # Unknown external
        return f"Loads the '{name}' library — used by this project for additional functionality"

    # ==========================================
    # HELPER METHODS
    # ==========================================

    # ── Language-aware comment prefix ─────────────────────────
    _COMMENT_PREFIXES: dict = {
        ".py": "#", ".rb": "#", ".sh": "#", ".bash": "#",
        ".pl": "#", ".r": "#", ".R": "#",
        ".js": "//", ".jsx": "//", ".ts": "//", ".tsx": "//",
        ".java": "//", ".go": "//", ".c": "//", ".cpp": "//",
        ".cs": "//", ".swift": "//", ".kt": "//", ".rs": "//",
        ".php": "//",
    }

    def _comment_prefix(self, file_path: str) -> str:
        """Return the single-line comment prefix for a file's language."""
        ext = os.path.splitext(file_path)[1]
        return self._COMMENT_PREFIXES.get(ext, "#")



    def _extract_body(
        self,
        source_code: str,
        start_line: int,
        max_lines: int = 30,
    ) -> str:
        """Extract up to max_lines of code starting from start_line."""
        lines = source_code.splitlines()
        start = max(0, start_line - 1)
        end = min(len(lines), start + max_lines)
        return "\n".join(lines[start:end])

    def _build_kg_context(
        self,
        node,
        source_file: str,
    ) -> str:
        """Build context string from Knowledge Graph for a node."""
        if not self.kg:
            return ""

        parts = []

        # Find matching KG node by name and file
        for kg_node in self.kg.nodes.values():
            if (
                kg_node.name == node.name
                and kg_node.file_path
                and source_file.endswith(kg_node.file_path)
            ):
                if kg_node.docstring:
                    parts.append(f"Documentation: {kg_node.docstring}")
                if kg_node.business_domain:
                    parts.append(f"Business Domain: {kg_node.business_domain}")
                if kg_node.service_boundary:
                    parts.append(f"Service: {kg_node.service_boundary}")
                if kg_node.semantic_tags:
                    parts.append(f"Tags: {', '.join(kg_node.semantic_tags)}")

                # Get relationships
                for edge in self.kg.outgoing_edges(kg_node.id):
                    tgt = self.kg.nodes.get(edge.to_id)
                    if tgt:
                        parts.append(
                            f"→ {edge.relation}: {tgt.name}"
                        )
                break

        return "\n".join(parts[:10])