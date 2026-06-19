import os

from backend.semantic_ir.ir_builder import IRBuilder

from backend.comment_engine.ast_inline_commentor import (
    ASTInlineCommentor
)

builder = IRBuilder()

semantic_ir = builder.build("./")

commentor = ASTInlineCommentor()

for component in semantic_ir.components:

    for file_path in component.files:

        # Python only for now
        if not file_path.endswith(".py"):
            continue

        if not os.path.isfile(file_path):
            continue

        relative_path = os.path.relpath(
            file_path,
            "."
        )

        output_path = os.path.join(
            "outputs/inline_commented_repo",
            relative_path
        )

        commentor.inject_comments(
            source_file=file_path,
            output_file=output_path
        )

print(
    "\nAST inline commenting completed."
)