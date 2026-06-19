import os

from backend.repository_intelligence.models import (
    RepositoryProfile,
    FrameworkInfo,
    EntrypointInfo
)

from backend.repository_intelligence.framework_detector import FrameworkDetector
from backend.repository_intelligence.entrypoint_detector import EntrypointDetector
from backend.repository_intelligence.technology_detector import TechnologyDetector
from backend.repository_intelligence.frontend_detector import FrontendDetector
from backend.repository_intelligence.structure_analyzer import StructureAnalyzer


class RepositoryProfiler:

    def __init__(self):

        self.framework_detector = FrameworkDetector()

        self.entrypoint_detector = EntrypointDetector()

        self.tech_detector = TechnologyDetector()

        self.frontend_detector = FrontendDetector()

        self.structure_analyzer = StructureAnalyzer()

    def profile(self, repo_path: str):

        repo_name = os.path.basename(repo_path)

        profile = RepositoryProfile(
            repository_name=repo_name
        )

        # Languages
        profile.languages = self.tech_detector.detect_languages(repo_path)

        # Frameworks
        frameworks = self.framework_detector.detect(repo_path)

        for fw in frameworks:

            profile.frameworks.append(
                FrameworkInfo(
                    name=fw["framework"],
                    confidence=fw["confidence"]
                )
            )

        # Frontend frameworks
        frontend_frameworks = self.frontend_detector.detect(repo_path)

        for fw in frontend_frameworks:

            profile.frameworks.append(
                FrameworkInfo(
                    name=fw,
                    confidence=0.90
                )
            )

        # Entrypoints
        entrypoints = self.entrypoint_detector.detect(repo_path)

        for ep in entrypoints:

            profile.entrypoints.append(
                EntrypointInfo(
                    file_path=ep["file_path"],
                    type=ep["type"]
                )
            )

        # Structure Analysis
        profile.detected_modules = (
            self.structure_analyzer.analyze(repo_path)
        )

        # Repository Classification
        profile.repository_type = (
            self.classify_repository(profile)
        )

        return profile

    def classify_repository(self, profile):

        framework_names = [
            f.name for f in profile.frameworks
        ]

        modules = profile.detected_modules
        module_count = len(modules)

        # Full-Stack Application
        if (
            any(
                fw in framework_names
                for fw in ("React", "Vue", "Angular", "Svelte")
            )
            and any(
                fw in framework_names
                for fw in ("FastAPI", "Flask", "Express", "Django", "Spring")
            )
        ):
            return "Full-Stack Application"

        # Backend API Platform
        if any(
            fw in framework_names
            for fw in ("FastAPI", "Flask", "Express", "Django", "Spring")
        ):
            return "Backend API Platform"

        # Frontend Application
        if any(
            fw in framework_names
            for fw in ("React", "Vue", "Angular", "Svelte")
        ):
            return "Frontend Application"

        # Machine Learning Platform
        if any(
            fw in framework_names
            for fw in ("TensorFlow", "PyTorch", "Scikit-learn")
        ):
            return "Machine Learning Platform"

        # Data Processing Platform
        if any(
            fw in framework_names
            for fw in ("PySpark", "Spark", "Airflow", "dbt")
        ):
            return "Data Processing Platform"

        # Multi-module / Modular Platform
        if module_count >= 5:
            return "Modular Software Platform"

        return "Software Platform"