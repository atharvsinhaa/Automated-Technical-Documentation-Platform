import os


class CommentGenerator:

    def generate_file_comment(
        self,
        file_path: str,
        component_name: str
    ):

        filename = os.path.basename(
            file_path
        )

        comment = []

        comment.append(
            f"# File: {filename}\n"
        )

        comment.append(
            "## Technical Purpose\n"
        )

        comment.append(
            f"This file belongs to the "
            f"'{component_name}' component "
            f"and contributes to the "
            f"overall repository workflow.\n"
        )

        comment.append(
            "## Developer Explanation\n"
        )

        comment.append(
            "This module contains logic "
            "required for processing, "
            "analysis, orchestration, "
            "or transformation tasks "
            "within the system.\n"
        )

        comment.append(
            "## Business Explanation\n"
        )

        comment.append(
            "From a business perspective, "
            "this file supports automated "
            "repository intelligence, "
            "documentation generation, "
            "dependency analysis, or "
            "workflow execution.\n"
        )

        comment.append(
            "## Workflow Role\n"
        )

        comment.append(
            "This file participates in "
            "the repository analysis "
            "and semantic intelligence "
            "pipeline.\n"
        )

        return "\n".join(comment)

    def save_comment(
        self,
        content: str,
        output_path: str
    ):

        os.makedirs(
            os.path.dirname(output_path),
            exist_ok=True
        )

        with open(
            output_path,
            "w",
            encoding="utf-8"
        ) as file:

            file.write(content)

        print(
            f"[SUCCESS] Comment generated: "
            f"{output_path}"
        )