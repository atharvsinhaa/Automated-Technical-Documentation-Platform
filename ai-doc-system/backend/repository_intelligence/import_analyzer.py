import ast
import os

from backend.repository_intelligence.constants import (
    IGNORED_DIRECTORIES,
    IGNORED_PATH_KEYWORDS
)


class ImportAnalyzer:

    def should_ignore(self, path: str):

        normalized = path.lower()

        for keyword in IGNORED_PATH_KEYWORDS:
            if keyword in normalized:
                return True

        return False

    def extract_imports(self, repo_path: str):

        imports = set()

        for root, dirs, files in os.walk(repo_path):

            dirs[:] = [
                d for d in dirs
                if d not in IGNORED_DIRECTORIES
            ]

            if self.should_ignore(root):
                continue

            for file in files:

                if not file.endswith(".py"):
                    continue

                path = os.path.join(root, file)

                try:

                    with open(path, "r", encoding="utf-8") as f:
                        source = f.read()

                    tree = ast.parse(source)

                    for node in ast.walk(tree):

                        if isinstance(node, ast.Import):

                            for alias in node.names:
                                imports.add(alias.name.split(".")[0])

                        elif isinstance(node, ast.ImportFrom):

                            if node.module:
                                imports.add(
                                    node.module.split(".")[0]
                                )

                except Exception:
                    pass

        return sorted(list(imports))