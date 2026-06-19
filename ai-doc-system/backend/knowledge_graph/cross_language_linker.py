"""
knowledge_graph/cross_language_linker.py
────────────────────────────────────────────────────────────────
Enterprise Cross-Language Semantic Linker.

Bridges frontend (React/JS/TS), backend (Python/Java/Go),
and API contract layers by matching:
  - Frontend fetch/axios calls → Backend API Endpoints
  - API_CALL nodes → API_ENDPOINT nodes
  - OpenAPI/Swagger contracts → implemented routes

Supports fuzzy path matching with variable normalization.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Set, Tuple

from .models import (
    KnowledgeGraph, KGNode,
    KGNodeType, KGRelationType
)


class CrossLanguageLinker:
    """Links frontend and backend via API contracts."""

    def __init__(self, verbose: bool = True):
        self.verbose = verbose
        # URL extraction patterns
        self._url_patterns = [
            re.compile(r"['\"](/api/[^'\"]+)['\"]"),         # '/api/v1/users'
            re.compile(r"['\"](/v\d+/[^'\"]+)['\"]"),        # '/v1/users'
            re.compile(r"fetch\(['\"]([^'\"]+)['\"]"),        # fetch('/api/...')
            re.compile(r"axios\.\w+\(['\"]([^'\"]+)['\"]"),   # axios.get('/api/...')
            re.compile(r"http\.\w+\(['\"]([^'\"]+)['\"]"),    # http.get('/api/...')
            re.compile(r"\$http\.\w+\(['\"]([^'\"]+)['\"]"),  # $http.get(...)
        ]

    def link(self, kg: KnowledgeGraph) -> int:
        """
        Finds API calls and links them to Backend API endpoints.
        Returns number of edges created.
        """
        added_edges = 0

        # 1. Collect all Backend API Endpoints with normalized paths
        endpoints: Dict[str, KGNode] = {}
        for node in kg.nodes_by_type(KGNodeType.API_ENDPOINT):
            path = self._normalize_route(node.name)
            if path:
                endpoints[path] = node

        if not endpoints:
            if self.verbose:
                print("[cross-lang] No API endpoints found in graph.")
            return 0

        # 2. Scan API_CALL nodes (the most direct signal)
        for node in kg.nodes_by_type(KGNodeType.API_CALL):
            path = self._normalize_route(node.name)
            if not path:
                continue
            matched = self._find_best_match(path, endpoints)
            if matched:
                # Bidirectional: CALLS_API + RETURNS_RESPONSE
                if kg.safe_add_edge(
                    node.id, matched.id, KGRelationType.CALLS_API,
                    confidence="high",
                    evidence=f"API_CALL → API_ENDPOINT path match: {path}",
                ):
                    added_edges += 1
                if kg.safe_add_edge(
                    matched.id, node.id, KGRelationType.RETURNS_RESPONSE,
                    confidence="high",
                    evidence=f"API_ENDPOINT → API_CALL response: {path}",
                ):
                    added_edges += 1

        # 3. Scan React Components and Hooks for fetch/axios patterns
        frontend_types = (KGNodeType.REACT_COMPONENT, KGNodeType.REACT_HOOK)
        for ntype in frontend_types:
            for node in kg.nodes_by_type(ntype):
                urls = self._extract_urls_from_text(node)
                for url, confidence in urls:
                    matched = self._find_best_match(url, endpoints)
                    if matched:
                        if kg.safe_add_edge(
                            node.id, matched.id, KGRelationType.CALLS_API,
                            confidence=confidence,
                            evidence=f"Frontend API call: {url}",
                        ):
                            added_edges += 1

        # 4. Scan Functions/AsyncFunctions for fetch/axios/http calls
        for node in kg.nodes.values():
            if node.node_type not in (KGNodeType.FUNCTION, KGNodeType.ASYNC_FUNCTION, KGNodeType.METHOD):
                continue
            if not node.body_preview:
                continue
            # Quick pre-filter: only process nodes with URL-like text
            bp = node.body_preview.lower()
            if not any(kw in bp for kw in ("fetch", "axios", "http", "/api/", "/v1/", "/v2/")):
                continue

            urls = self._extract_urls_from_text(node)
            for url, confidence in urls:
                matched = self._find_best_match(url, endpoints)
                if matched:
                    if kg.safe_add_edge(
                        node.id, matched.id, KGRelationType.CALLS_API,
                        confidence=confidence,
                        evidence=f"HTTP call in function: {url}",
                    ):
                        added_edges += 1

        if self.verbose:
            print(f"[cross-lang] Created {added_edges} cross-language API links.")

        return added_edges

    def _extract_urls_from_text(self, node: KGNode) -> List[Tuple[str, str]]:
        """Extract (normalized_url, confidence) pairs from a node's text."""
        results = []
        text = f"{node.body_preview or ''} {node.docstring or ''}"
        for pattern in self._url_patterns:
            for m in pattern.finditer(text):
                url = self._normalize_route(m.group(1))
                if url:
                    results.append((url, "medium"))

        # Also check for plain /api/... strings
        for m in re.finditer(r"['\"](/api/[^'\"]+)['\"]", text):
            url = self._normalize_route(m.group(1))
            if url and (url, "medium") not in results:
                results.append((url, "low"))

        return results

    def _normalize_route(self, route: str) -> str:
        """Strip HTTP methods and normalize path variables."""
        if not route:
            return ""
        # Remove HTTP method prefix
        route = re.sub(
            r'^(GET|POST|PUT|DELETE|PATCH|OPTIONS|HEAD)\s+',
            '', route, flags=re.IGNORECASE,
        )
        # Normalize variable placeholders
        route = re.sub(r'\{[^}]+\}', '{}', route)     # {id} → {}
        route = re.sub(r':[a-zA-Z0-9_]+', '{}', route) # :id → {}
        route = re.sub(r'<[^>]+>', '{}', route)         # <id> → {}
        route = re.sub(r'\$\{[^}]+\}', '{}', route)     # ${id} → {}
        # Strip query params and trailing slash
        route = route.split("?")[0].rstrip("/")
        return route.strip()

    def _find_best_match(
        self, call_path: str, endpoints: Dict[str, KGNode]
    ) -> Optional[KGNode]:
        """Find the best matching endpoint for a call path."""
        if not call_path:
            return None

        # Exact match
        if call_path in endpoints:
            return endpoints[call_path]

        # Longest prefix match
        best_match = None
        best_len = 0
        for ep_path, node in endpoints.items():
            if call_path.startswith(ep_path) and len(ep_path) > best_len:
                best_match = node
                best_len = len(ep_path)

        # Fuzzy: try matching with variable segments replaced
        if not best_match:
            call_segments = call_path.split("/")
            for ep_path, node in endpoints.items():
                ep_segments = ep_path.split("/")
                if len(call_segments) == len(ep_segments):
                    match = all(
                        cs == es or cs == "{}" or es == "{}"
                        for cs, es in zip(call_segments, ep_segments)
                    )
                    if match:
                        best_match = node
                        break

        return best_match
