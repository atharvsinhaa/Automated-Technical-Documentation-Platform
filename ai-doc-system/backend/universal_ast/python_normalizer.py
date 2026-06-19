import ast

from backend.universal_ast.universal_node import (
    UniversalNode
)


class PythonNormalizer:

    def normalize(
        self,
        source_code: str
    ):

        tree = ast.parse(source_code)

        nodes = []

        for node in ast.walk(tree):

            # =========================
            # FUNCTIONS
            # =========================

            if isinstance(node, ast.FunctionDef):

                semantic_role = (
                    self.detect_semantic_role(
                        node.name
                    )
                )

                nodes.append(

                    UniversalNode(
                        node_type="FUNCTION",
                        name=node.name,
                        language="python",
                        semantic_role=semantic_role,
                        line=node.lineno
                    )
                )

            # =========================
            # CLASSES
            # =========================

            elif isinstance(node, ast.ClassDef):

                semantic_role = (
                    self.detect_semantic_role(
                        node.name
                    )
                )

                nodes.append(

                    UniversalNode(
                        node_type="CLASS",
                        name=node.name,
                        language="python",
                        semantic_role=semantic_role,
                        line=node.lineno
                    )
                )

        return nodes

    # ==================================
    # SEMANTIC ROLE DETECTION
    # ==================================

    def detect_semantic_role(
        self,
        name: str
    ):

        lowered = name.lower()

        if "parse" in lowered:

            return "parsing"

        elif "extract" in lowered:

            return "dependency_extraction"

        elif "graph" in lowered:

            return "graph_processing"

        elif "render" in lowered:

            return "diagram_rendering"

        elif "generate" in lowered:

            return "artifact_generation"

        elif "build" in lowered:

            return "semantic_building"

        elif "detect" in lowered:

            return "technology_detection"

        elif "analyze" in lowered:

            return "semantic_analysis"

        return "general_processing"