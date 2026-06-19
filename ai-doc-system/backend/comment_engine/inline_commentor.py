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

        lines = source_code.splitlines()

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

        for lineno, comment in sorted(
            inserts, reverse=True,
        ):
            lines.insert(lineno, comment)

        final_code = "\n".join(lines)

        # =========================
        # CREATE OUTPUT DIRECTORY
        # =========================

        os.makedirs(
            os.path.dirname(output_file),
            exist_ok=True,
        )

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
                f"# {purpose}\n"
                f"# Function: {name} (in {filename})"
            )

        elif node_type == "class":
            purpose = self._infer_class_purpose(name)
            return (
                f"# Class: {name}\n"
                f"# {purpose}\n"
                f"# Defined in: {filename}"
            )

        return f"# {name}: {self._infer_general_purpose(name, role)}"

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
    # HELPER METHODS
    # ==========================================

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