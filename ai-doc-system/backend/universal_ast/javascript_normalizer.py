from backend.universal_ast.universal_node import (
    UniversalNode
)


class JavaScriptNormalizer:

    def __init__(self):
        from tree_sitter import Parser
        from tree_sitter_languages import get_language

        self.parser = Parser()

        javascript_language = get_language(
            "javascript"
        )

        self.parser.set_language(
            javascript_language
        )

    # ==========================================
    # NORMALIZE SOURCE
    # ==========================================

    def normalize(
        self,
        source_code: str
    ):

        tree = self.parser.parse(
            bytes(source_code, "utf8")
        )

        root = tree.root_node

        nodes = []

        self.walk(
            root,
            source_code,
            nodes
        )

        return nodes

    # ==========================================
    # TREE WALKER
    # ==========================================

    def walk(
        self,
        node,
        source_code,
        nodes
    ):

        # ==================================
        # FUNCTION DECLARATIONS
        # ==================================

        if node.type == "function_declaration":

            name_node = node.child_by_field_name(
                "name"
            )

            if name_node:

                function_name = (
                    source_code[
                        name_node.start_byte:
                        name_node.end_byte
                    ]
                )

                semantic_role = (
                    self.detect_semantic_role(
                        function_name
                    )
                )

                nodes.append(

                    UniversalNode(
                        node_type="FUNCTION",
                        name=function_name,
                        language="javascript",
                        semantic_role=semantic_role,
                        line=node.start_point[0] + 1
                    )
                )

        # ==================================
        # CLASS DECLARATIONS
        # ==================================

        elif node.type == "class_declaration":

            name_node = node.child_by_field_name(
                "name"
            )

            if name_node:

                class_name = (
                    source_code[
                        name_node.start_byte:
                        name_node.end_byte
                    ]
                )

                semantic_role = (
                    self.detect_semantic_role(
                        class_name
                    )
                )

                nodes.append(

                    UniversalNode(
                        node_type="CLASS",
                        name=class_name,
                        language="javascript",
                        semantic_role=semantic_role,
                        line=node.start_point[0] + 1
                    )
                )

        # ==================================
        # IMPORT STATEMENTS
        # ==================================

        elif node.type == "import_statement":
            source_node = node.child_by_field_name("source")
            if source_node:
                module_name = source_code[
                    source_node.start_byte:source_node.end_byte
                ].strip("'\"")
            else:
                module_name = source_code[
                    node.start_byte:node.end_byte
                ].strip()

            nodes.append(
                UniversalNode(
                    node_type="import",
                    name=module_name,
                    language="javascript",
                    semantic_role="dependency",
                    line=node.start_point[0] + 1,
                )
            )

        # ==================================
        # RECURSIVE WALK
        # ==================================

        for child in node.children:

            self.walk(
                child,
                source_code,
                nodes
            )

    # ==========================================
    # SEMANTIC ROLE DETECTION
    # ==========================================

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