import os

from backend.repository_intelligence.constants import (
    IGNORED_DIRECTORIES,
    IGNORED_PATH_KEYWORDS
)


class FrontendDetector:

    def should_ignore(self, path: str):

        normalized = path.lower()

        for keyword in IGNORED_PATH_KEYWORDS:
            if keyword in normalized:
                return True

        return False

    def detect(self, repo_path: str):

        frameworks = []

        for root, dirs, files in os.walk(repo_path):

            dirs[:] = [
                d for d in dirs
                if d not in IGNORED_DIRECTORIES
            ]

            if self.should_ignore(root):
                continue

            for file in files:

                if not file.endswith((
                    ".js",
                    ".jsx",
                    ".ts",
                    ".tsx"
                )):
                    continue

                path = os.path.join(root, file)

                try:

                    with open(path, "r", encoding="utf-8") as f:
                        content = f.read().lower()

                    if "react" in content:
                        frameworks.append("React")

                    if "next" in content:
                        frameworks.append("Next.js")

                except Exception:
                    pass

        return list(set(frameworks))