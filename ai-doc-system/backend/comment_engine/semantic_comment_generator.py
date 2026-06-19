import os


class SemanticCommentGenerator:

    def generate_file_comment(
        self,
        file_path: str,
        source_code: str
    ):

        filename = os.path.basename(
            file_path
        ).lower()

        comment = []

        # MODELS
        if "model" in filename:

            comment.extend([
                "PURPOSE:",
                "Defines shared data structures and "
                "semantic models used across the system.",
                "",
                "RESPONSIBILITY:",
                "Standardizes representation of parsed "
                "repository entities and workflows.",
                "",
                "BUSINESS VALUE:",
                "Provides consistent semantic structures "
                "required for repository intelligence "
                "and documentation generation."
            ])

        # PARSER
        elif "parser" in filename:

            comment.extend([
                "PURPOSE:",
                "Parses source code into structured "
                "AST representations.",
                "",
                "RESPONSIBILITY:",
                "Transforms raw repository files into "
                "machine-understandable syntax trees.",
                "",
                "BUSINESS VALUE:",
                "Enables automated repository analysis "
                "and semantic extraction."
            ])

        # GRAPH
        elif "graph" in filename:

            comment.extend([
                "PURPOSE:",
                "Builds and manages semantic graph "
                "relationships.",
                "",
                "RESPONSIBILITY:",
                "Transforms extracted repository "
                "dependencies into graph structures.",
                "",
                "BUSINESS VALUE:",
                "Enables relationship intelligence "
                "and contextual documentation."
            ])

        # API
        elif "api" in filename:

            comment.extend([
                "PURPOSE:",
                "Handles API orchestration and "
                "external communication.",
                "",
                "RESPONSIBILITY:",
                "Coordinates request handling and "
                "service interaction.",
                "",
                "BUSINESS VALUE:",
                "Enables system integration and "
                "workflow accessibility."
            ])

        # EXTRACTOR
        elif "extract" in filename:

            comment.extend([
                "PURPOSE:",
                "Extracts semantic information from "
                "repository structures.",
                "",
                "RESPONSIBILITY:",
                "Identifies dependencies, entities, "
                "and execution relationships.",
                "",
                "BUSINESS VALUE:",
                "Supports automated intelligence "
                "generation and architecture analysis."
            ])

        # DEFAULT
        else:

            comment.extend([
                "PURPOSE:",
                "Supports repository analysis and "
                "semantic processing workflows.",
                "",
                "RESPONSIBILITY:",
                "Participates in orchestration, "
                "processing, or transformation tasks.",
                "",
                "BUSINESS VALUE:",
                "Contributes to automated "
                "documentation and repository "
                "intelligence generation."
            ])

        return comment