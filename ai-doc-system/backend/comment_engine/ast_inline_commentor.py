import os

from backend.universal_ast.normalizer import (
    UniversalASTNormalizer
)


class ASTInlineCommentor:

    def __init__(self):

        self.normalizer = (
            UniversalASTNormalizer()
        )

    # ==========================================
    # MAIN COMMENT INJECTION
    # ==========================================

    def inject_comments(
        self,
        source_file: str,
        output_file: str
    ):

        # =========================
        # READ SOURCE FILE
        # =========================

        with open(
            source_file,
            "r",
            encoding="utf-8",
            errors="ignore"
        ) as file:

            source_code = file.read()

        lines = source_code.splitlines()

        # =========================
        # UNIVERSAL AST NODES
        # =========================

        universal_nodes = (
            self.normalizer.normalize_file(
                source_file
            )
        )

        inserts = []

        # =========================
        # GENERATE COMMENTS
        # =========================

        for node in universal_nodes:

            comment = (
                self.generate_semantic_comment(
                    node
                )
            )

            inserts.append(
                (
                    node.line - 1,
                    comment
                )
            )

        # =========================
        # INSERT COMMENTS
        # =========================

        for lineno, comment in sorted(
            inserts,
            reverse=True
        ):

            lines.insert(
                lineno,
                comment
            )

        final_code = "\n".join(lines)

        # =========================
        # CREATE OUTPUT DIR
        # =========================

        os.makedirs(
            os.path.dirname(output_file),
            exist_ok=True
        )

        # =========================
        # WRITE OUTPUT FILE
        # =========================

        with open(
            output_file,
            "w",
            encoding="utf-8"
        ) as file:

            file.write(final_code)

        print(
            f"[SUCCESS] Semantic comments injected: "
            f"{output_file}"
        )

    # ==========================================
    # SEMANTIC COMMENT GENERATION
    # ==========================================

    def generate_semantic_comment(
        self,
        universal_node
    ):

        role = universal_node.semantic_role

        # ==================================
        # PARSING
        # ==================================

        if role == "parsing":

            return (
                "# Parses repository source code "
                "and generates AST structures."
            )

        # ==================================
        # DEPENDENCY EXTRACTION
        # ==================================

        elif role == "dependency_extraction":

            return (
                "# Extracts semantic dependency "
                "relationships from repository code."
            )

        # ==================================
        # GRAPH PROCESSING
        # ==================================

        elif role == "graph_processing":

            return (
                "# Builds semantic graph relationships "
                "for repository intelligence."
            )

        # ==================================
        # DIAGRAM RENDERING
        # ==================================

        elif role == "diagram_rendering":

            return (
                "# Renders architecture or sequence "
                "diagram visualizations."
            )

        # ==================================
        # ARTIFACT GENERATION
        # ==================================

        elif role == "artifact_generation":

            return (
                "# Generates documentation artifacts "
                "and derived outputs."
            )

        # ==================================
        # SEMANTIC BUILDING
        # ==================================

        elif role == "semantic_building":

            return (
                "# Builds semantic intelligence "
                "and repository structures."
            )

        # ==================================
        # TECHNOLOGY DETECTION
        # ==================================

        elif role == "technology_detection":

            return (
                "# Detects repository technologies "
                "and architectural patterns."
            )

        # ==================================
        # SEMANTIC ANALYSIS
        # ==================================

        elif role == "semantic_analysis":

            return (
                "# Analyzes repository logic "
                "and semantic execution behavior."
            )

        # ==================================
        # DEFAULT
        # ==================================

        return (
            "# Handles repository processing logic."
        )