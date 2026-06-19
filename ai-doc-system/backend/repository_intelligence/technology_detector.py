import os

from backend.repository_intelligence.constants import (
    IGNORED_DIRECTORIES,
    IGNORED_PATH_KEYWORDS
)


class TechnologyDetector:

    def should_ignore(self, path: str):

        normalized = path.lower()

        for keyword in IGNORED_PATH_KEYWORDS:
            if keyword in normalized:
                return True

        return False

    def detect_languages(self, repo_path: str):

        extensions = {}

        for root, dirs, files in os.walk(repo_path):

            dirs[:] = [
                d for d in dirs
                if d not in IGNORED_DIRECTORIES
            ]

            if self.should_ignore(root):
                continue

            for file in files:

                ext = os.path.splitext(file)[1]

                if ext:
                    extensions[ext] = extensions.get(ext, 0) + 1

        mapping = {
            ".py": "Python",
            ".js": "JavaScript",
            ".ts": "TypeScript",
            ".jsx": "React",
            ".tsx": "React",
            ".java": "Java",
            ".scala": "Scala",
            ".sql": "SQL",
        }

        languages = []

        for ext in extensions:

            if ext in mapping:
                languages.append(mapping[ext])

        return sorted(list(set(languages)))