"""
repository_intelligence/http_endpoint_extractor.py
────────────────────────────────────────────────────────────────
Extracts HTTP API endpoints from source code using static analysis.

Supports:
  - FastAPI          (@app.get, @router.post, etc.)
  - Flask            (@app.route, @blueprint.route)
  - Express/NestJS   (app.get, @Get, @Post, etc.)
  - Spring Boot      (@GetMapping, @PostMapping, @RequestMapping)
  - Django           (urlpatterns path/re_path)

Output:
  List[EndpointNode] — each with method, path, handler, file.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

_VALID_URL_RE = re.compile(r'^/[a-zA-Z0-9_\-/{}:]+$')

def _is_valid_endpoint(path: str, handler: str) -> bool:
    """Return True only for genuine HTTP routes."""
    if not path:
        return False
    if len(path) < 2:
        return False
    if not path.startswith("/"):
        return False
    if handler in ("__init__", "__call__", "__new__", ""):
        return False

    placeholders = {"/path", "/test", "/example", "/placeholder"}
    if path.lower().rstrip("/") in placeholders:
        return False

    return True


@dataclass
class EndpointNode:
    """Represents a detected HTTP API endpoint."""
    method: str                            # GET, POST, PUT, DELETE, PATCH
    path: str                              # /api/users, /health, etc.
    handler: str = ""                      # function/method name
    handler_file: str = ""                 # file path
    request_model: Optional[str] = None    # request body type
    response_model: Optional[str] = None   # response body type
    decorators: List[str] = field(default_factory=list)
    framework: str = ""                    # fastapi, flask, express, spring, django
    line_number: int = 0


class HTTPEndpointExtractor:
    """
    Static analysis extractor for HTTP endpoints.

    Usage:
        extractor = HTTPEndpointExtractor()
        endpoints = extractor.extract_from_directory("/path/to/repo")
    """

    def __init__(self, verbose: bool = True):
        self.verbose = verbose

        # ── FastAPI patterns ─────────────────────────────────
        # @app.get("/path") or @router.post("/path", response_model=Foo)
        self._fastapi_pattern = re.compile(
            r'@\w+\.(get|post|put|delete|patch|options|head)\s*\(\s*'
            r'["\']([^"\']+)["\']'
            r'(?:.*?response_model\s*=\s*(\w+))?',
            re.IGNORECASE,
        )

        # @app.api_route("/path", methods=["GET", "POST"])
        self._fastapi_api_route = re.compile(
            r'@\w+\.api_route\s*\(\s*["\']([^"\']+)["\']'
            r'.*?methods\s*=\s*\[([^\]]+)\]',
            re.IGNORECASE,
        )

        # ── Flask patterns ───────────────────────────────────
        # @app.route("/path", methods=["GET", "POST"])
        self._flask_route = re.compile(
            r'@\w+\.route\s*\(\s*["\']([^"\']+)["\']'
            r'(?:.*?methods\s*=\s*\[([^\]]+)\])?',
            re.IGNORECASE,
        )

        # ── Express patterns ─────────────────────────────────
        # app.get("/path", handler)  or  router.post("/path", handler)
        self._express_pattern = re.compile(
            r'(?:app|router|server)\.(get|post|put|delete|patch|all)\s*\(\s*'
            r'["\'/`]([^"\'`]+)["\'/`]',
            re.IGNORECASE,
        )

        # ── NestJS patterns ──────────────────────────────────
        # @Get("/path"), @Post("/path"), @Controller("/prefix")
        self._nestjs_method = re.compile(
            r'@(Get|Post|Put|Delete|Patch|Options|Head)\s*\(\s*'
            r'(?:["\']([^"\']*)["\'])?',
        )
        self._nestjs_controller = re.compile(
            r'@Controller\s*\(\s*["\']([^"\']+)["\']',
        )

        # ── Spring Boot patterns ─────────────────────────────
        # @GetMapping("/path"), @PostMapping, @RequestMapping
        self._spring_mapping = re.compile(
            r'@(Get|Post|Put|Delete|Patch|Request)Mapping\s*\(\s*'
            r'(?:value\s*=\s*)?["\']([^"\']+)["\']'
            r'(?:.*?method\s*=\s*RequestMethod\.(\w+))?',
        )
        self._spring_rest = re.compile(
            r'@RestController',
        )

        # ── Django patterns ──────────────────────────────────
        # path("api/users/", views.user_list, name="user-list")
        self._django_path = re.compile(
            r'(?:path|re_path)\s*\(\s*["\']([^"\']+)["\']'
            r'\s*,\s*(\w[\w.]*)',
        )

        # ── Handler function detection ───────────────────────
        self._handler_def = re.compile(
            r'(?:def|async\s+def|function|async\s+function)\s+(\w+)',
        )

    def extract_from_directory(
        self, repo_path: str,
    ) -> List[EndpointNode]:
        """
        Scan a repository and extract all HTTP endpoints.

        Returns a list of EndpointNode instances.
        """
        endpoints: List[EndpointNode] = []

        for dirpath, _, filenames in os.walk(repo_path):
            # Skip common non-source dirs
            rel_dir = os.path.relpath(dirpath, repo_path)
            if any(
                skip in rel_dir
                for skip in (
                    "node_modules", "venv", ".git",
                    "__pycache__", "dist", "build",
                    ".tox", ".mypy_cache",
                )
            ):
                continue

            for fname in filenames:
                if not self._is_source_file(fname):
                    continue

                filepath = os.path.join(dirpath, fname)
                rel_path = os.path.relpath(filepath, repo_path)

                try:
                    with open(
                        filepath, "r",
                        encoding="utf-8", errors="ignore",
                    ) as f:
                        source = f.read()

                    file_endpoints = self._extract_from_source(
                        source, rel_path,
                    )
                    endpoints.extend(file_endpoints)

                except Exception:
                    pass

        if self.verbose:
            print(
                f"[http-extractor] Found {len(endpoints)} "
                f"HTTP endpoints"
            )

        return endpoints

    def _extract_from_source(
        self,
        source: str,
        file_path: str,
    ) -> List[EndpointNode]:
        """Extract endpoints from a single source file."""
        endpoints: List[EndpointNode] = []

        lines = source.split("\n")

        # Detect framework from imports
        framework = self._detect_framework(source)

        if framework == "fastapi":
            endpoints.extend(
                self._extract_fastapi(lines, file_path)
            )
        elif framework == "flask":
            endpoints.extend(
                self._extract_flask(lines, file_path)
            )
        elif framework == "express":
            endpoints.extend(
                self._extract_express(lines, file_path)
            )
        elif framework == "nestjs":
            endpoints.extend(
                self._extract_nestjs(lines, file_path)
            )
        elif framework == "spring":
            endpoints.extend(
                self._extract_spring(lines, file_path)
            )
        elif framework == "django":
            endpoints.extend(
                self._extract_django(lines, file_path)
            )
        else:
            # Try all patterns
            endpoints.extend(
                self._extract_fastapi(lines, file_path)
            )
            endpoints.extend(
                self._extract_flask(lines, file_path)
            )
            endpoints.extend(
                self._extract_express(lines, file_path)
            )
            endpoints.extend(
                self._extract_spring(lines, file_path)
            )

        valid_endpoints = []
        for ep in endpoints:
            if _is_valid_endpoint(ep.path, ep.handler):
                valid_endpoints.append(ep)

        return valid_endpoints

    def _detect_framework(self, source: str) -> str:
        """Detect which web framework is used."""
        if "from fastapi" in source or "import fastapi" in source:
            return "fastapi"
        if "from flask" in source or "import flask" in source:
            return "flask"
        if "from django" in source:
            return "django"
        if "require('express')" in source or "from 'express'" in source:
            return "express"
        if "@Controller" in source and "@Get" in source:
            return "nestjs"
        if "@RestController" in source or "@RequestMapping" in source:
            return "spring"
        return ""

    # ── FastAPI ──────────────────────────────────────────────

    def _extract_fastapi(
        self, lines: List[str], file_path: str,
    ) -> List[EndpointNode]:
        endpoints = []
        for i, line in enumerate(lines):
            m = self._fastapi_pattern.search(line)
            if m:
                method = m.group(1).upper()
                path = m.group(2)
                response_model = m.group(3)
                handler = self._find_handler_after(lines, i)
                request_model = self._find_request_model(
                    lines, i, handler,
                )

                endpoints.append(EndpointNode(
                    method=method,
                    path=path,
                    handler=handler,
                    handler_file=file_path,
                    request_model=request_model,
                    response_model=response_model,
                    framework="fastapi",
                    line_number=i + 1,
                ))

            m2 = self._fastapi_api_route.search(line)
            if m2:
                path = m2.group(1)
                methods_str = m2.group(2)
                methods = re.findall(r'["\'](\w+)["\']', methods_str)
                handler = self._find_handler_after(lines, i)

                for method in methods:
                    endpoints.append(EndpointNode(
                        method=method.upper(),
                        path=path,
                        handler=handler,
                        handler_file=file_path,
                        framework="fastapi",
                        line_number=i + 1,
                    ))

        return endpoints

    # ── Flask ────────────────────────────────────────────────

    def _extract_flask(
        self, lines: List[str], file_path: str,
    ) -> List[EndpointNode]:
        endpoints = []
        for i, line in enumerate(lines):
            m = self._flask_route.search(line)
            if m:
                path = m.group(1)
                methods_str = m.group(2)
                handler = self._find_handler_after(lines, i)

                if methods_str:
                    methods = re.findall(
                        r'["\'](\w+)["\']', methods_str,
                    )
                else:
                    methods = ["GET"]

                for method in methods:
                    endpoints.append(EndpointNode(
                        method=method.upper(),
                        path=path,
                        handler=handler,
                        handler_file=file_path,
                        framework="flask",
                        line_number=i + 1,
                    ))

        return endpoints

    # ── Express ──────────────────────────────────────────────

    def _extract_express(
        self, lines: List[str], file_path: str,
    ) -> List[EndpointNode]:
        endpoints = []
        for i, line in enumerate(lines):
            m = self._express_pattern.search(line)
            if m:
                method = m.group(1).upper()
                path = m.group(2)
                if method == "ALL":
                    method = "ALL"

                endpoints.append(EndpointNode(
                    method=method,
                    path=path,
                    handler="inline",
                    handler_file=file_path,
                    framework="express",
                    line_number=i + 1,
                ))

        return endpoints

    # ── NestJS ───────────────────────────────────────────────

    def _extract_nestjs(
        self, lines: List[str], file_path: str,
    ) -> List[EndpointNode]:
        endpoints = []
        controller_prefix = ""

        for i, line in enumerate(lines):
            # Detect controller prefix
            cm = self._nestjs_controller.search(line)
            if cm:
                controller_prefix = cm.group(1)
                if not controller_prefix.startswith("/"):
                    controller_prefix = "/" + controller_prefix

            # Detect method decorators
            mm = self._nestjs_method.search(line)
            if mm:
                method = mm.group(1).upper()
                path = mm.group(2) or ""
                full_path = controller_prefix + (
                    "/" + path if path else ""
                )
                handler = self._find_handler_after(lines, i)

                endpoints.append(EndpointNode(
                    method=method,
                    path=full_path,
                    handler=handler,
                    handler_file=file_path,
                    framework="nestjs",
                    line_number=i + 1,
                ))

        return endpoints

    # ── Spring Boot ──────────────────────────────────────────

    def _extract_spring(
        self, lines: List[str], file_path: str,
    ) -> List[EndpointNode]:
        endpoints = []
        for i, line in enumerate(lines):
            m = self._spring_mapping.search(line)
            if m:
                mapping_type = m.group(1)
                path = m.group(2)
                explicit_method = m.group(3)

                if explicit_method:
                    method = explicit_method.upper()
                elif mapping_type == "Request":
                    method = "GET"
                else:
                    method = mapping_type.upper()

                handler = self._find_handler_after(lines, i)

                endpoints.append(EndpointNode(
                    method=method,
                    path=path,
                    handler=handler,
                    handler_file=file_path,
                    framework="spring",
                    line_number=i + 1,
                ))

        return endpoints

    # ── Django ───────────────────────────────────────────────

    def _extract_django(
        self, lines: List[str], file_path: str,
    ) -> List[EndpointNode]:
        endpoints = []
        for i, line in enumerate(lines):
            m = self._django_path.search(line)
            if m:
                path = m.group(1)
                view = m.group(2)

                if not path.startswith("/"):
                    path = "/" + path

                endpoints.append(EndpointNode(
                    method="GET",
                    path=path,
                    handler=view,
                    handler_file=file_path,
                    framework="django",
                    line_number=i + 1,
                ))

        return endpoints

    # ── Helpers ──────────────────────────────────────────────

    def _find_handler_after(
        self, lines: List[str], decorator_line: int,
    ) -> str:
        """Find the function/method defined after a decorator."""
        for j in range(
            decorator_line + 1,
            min(decorator_line + 5, len(lines)),
        ):
            m = self._handler_def.search(lines[j])
            if m:
                return m.group(1)
        return ""

    def _find_request_model(
        self, lines: List[str], decorator_line: int,
        handler_name: str,
    ) -> Optional[str]:
        """Find request body type from handler signature."""
        for j in range(
            decorator_line + 1,
            min(decorator_line + 5, len(lines)),
        ):
            # Look for type-annotated body parameter
            body_match = re.search(
                r'(\w+)\s*:\s*(\w+)(?:\s*=\s*Body)?',
                lines[j],
            )
            if body_match:
                param_name = body_match.group(1)
                param_type = body_match.group(2)
                if param_name not in (
                    "self", "request", "response", "db",
                    "session", "str", "int", "float", "bool",
                ):
                    return param_type
        return None

    def _is_source_file(self, filename: str) -> bool:
        """Check if file is a source file we should scan."""
        return filename.endswith((
            ".py", ".js", ".ts", ".jsx", ".tsx",
            ".java", ".kt", ".scala",
            ".go", ".rs", ".cs",
        ))
