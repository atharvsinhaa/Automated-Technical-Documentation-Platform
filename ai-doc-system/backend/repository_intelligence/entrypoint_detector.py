import os

from backend.repository_intelligence.constants import (
    IGNORED_DIRECTORIES,
    IGNORED_PATH_KEYWORDS
)


ENTRYPOINT_FILES = [
    "main.py",
    "app.py",
    "server.py",
    "run.py",
]


class EntrypointDetector:

    def should_ignore(self, path: str):

        normalized = path.lower()

        for keyword in IGNORED_PATH_KEYWORDS:
            if keyword in normalized:
                return True

        return False

    def detect(self, repo_path: str):

        entrypoints = []

        for root, dirs, files in os.walk(repo_path):

            dirs[:] = [
                d for d in dirs
                if d not in IGNORED_DIRECTORIES
            ]

            if self.should_ignore(root):
                continue

            for file in files:

                if file in ENTRYPOINT_FILES:

                    entrypoints.append({
                        "file_path": os.path.join(root, file),
                        "type": "application_entrypoint"
                    })

        return entrypoints