from backend.repository_intelligence.import_analyzer import ImportAnalyzer


FRAMEWORK_IMPORT_MAP = {
    "fastapi": "FastAPI",
    "flask": "Flask",
    "django": "Django",
    "neo4j": "Neo4j",
    "torch": "PyTorch",
    "tensorflow": "TensorFlow",
    "langchain": "LangChain",
}


class FrameworkDetector:

    def __init__(self):

        self.import_analyzer = ImportAnalyzer()

    def detect(self, repo_path: str):

        detected = []

        imports = self.import_analyzer.extract_imports(repo_path)

        for imp in imports:

            if imp.lower() in FRAMEWORK_IMPORT_MAP:

                detected.append({
                    "framework": FRAMEWORK_IMPORT_MAP[imp.lower()],
                    "confidence": 0.95
                })

        return detected