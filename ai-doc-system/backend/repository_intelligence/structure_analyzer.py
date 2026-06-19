"""
repository_intelligence/structure_analyzer.py
────────────────────────────────────────────────────────────────
Generic Structure Analyzer.

Detects modules by scanning top-level directory names in the
repository. No hardcoded mapping to any specific platform.
"""

import os


class StructureAnalyzer:

    def analyze(self, repo_path: str):
        """
        Detect modules from directory structure.

        Returns a list of human-readable module names
        derived from actual directory names (not hardcoded).
        """
        detected_modules = []

        # Look in common source roots
        source_roots = [
            os.path.join(repo_path, "backend"),
            os.path.join(repo_path, "src"),
            os.path.join(repo_path, "app"),
            os.path.join(repo_path, "lib"),
            repo_path,
        ]

        for root in source_roots:
            if not os.path.isdir(root):
                continue

            for entry in sorted(os.listdir(root)):
                entry_path = os.path.join(root, entry)
                if not os.path.isdir(entry_path):
                    continue
                if entry.startswith(".") or entry in (
                    "__pycache__", "node_modules", "venv",
                    "dist", "build", ".git", "egg-info",
                ):
                    continue

                # Convert directory name to readable module name
                clean_name = entry.replace("_", " ").title()
                detected_modules.append(clean_name)

            if detected_modules:
                break  # Use the first valid source root

        return list(set(detected_modules))