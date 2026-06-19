import os

from backend.universal_ast.python_normalizer import (
    PythonNormalizer
)

from backend.universal_ast.javascript_normalizer import (
    JavaScriptNormalizer
)


class UniversalASTNormalizer:

    def __init__(self):

        self.python_normalizer = (
            PythonNormalizer()
        )

        try:
            self.javascript_normalizer = (
                JavaScriptNormalizer()
            )
        except ImportError:
            self.javascript_normalizer = None

    # ==========================================
    # NORMALIZE FILE
    # ==========================================

    def normalize_file(
        self,
        file_path: str
    ):

        extension = os.path.splitext(
            file_path
        )[1]

        with open(
            file_path,
            "r",
            encoding="utf-8",
            errors="ignore"
        ) as file:

            source_code = file.read()

        # ==================================
        # PYTHON
        # ==================================

        if extension == ".py":

            return (
                self.python_normalizer.normalize(
                    source_code
                )
            )

        # ==================================
        # JAVASCRIPT / TYPESCRIPT
        # ==================================

        elif extension in [
            ".js",
            ".jsx",
            ".ts",
            ".tsx"
        ] and self.javascript_normalizer:

            return (
                self.javascript_normalizer.normalize(
                    source_code
                )
            )

        return []