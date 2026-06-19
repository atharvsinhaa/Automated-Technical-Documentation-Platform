from backend.comment_engine.inline_commentor import ASTInlineCommentor


def main():

    commentor = ASTInlineCommentor()

    commentor.inject_comments(
        source_file="backend/ast_engine/core/engine.py",
        output_file=(
            "outputs/inline_commented_repo/"
            "backend/ast_engine/core/engine.py"
        )
    )

    print(
        "\n[SUCCESS] Inline comments generated."
    )


if __name__ == "__main__":
    main()