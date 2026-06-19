"""
repository_intelligence/architecture_pattern_recognizer.py
────────────────────────────────────────────────────────────────
Detects architecture patterns in a repository using static analysis.

Supported Patterns:
  - MVC (Model-View-Controller)
  - Layered Architecture
  - Microservices
  - Event-Driven Architecture
  - ETL Pipeline
  - CQRS (Command Query Responsibility Segregation)
  - SPA (Single Page Application)

Each pattern returns a confidence score (0.0 — 1.0).
The highest-scoring pattern is the primary classification.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple


@dataclass
class PatternScore:
    """A detected architecture pattern with confidence."""
    pattern: str
    confidence: float
    evidence: List[str] = field(default_factory=list)


class ArchitecturePatternRecognizer:
    """
    Static analysis recognizer for architecture patterns.

    Uses directory structure, file naming conventions, import
    patterns, and decorator/annotation detection.

    Usage:
        recognizer = ArchitecturePatternRecognizer()
        scores = recognizer.analyze("/path/to/repo")
        primary = recognizer.primary_pattern(scores)
    """

    def __init__(self, verbose: bool = True):
        self.verbose = verbose

    def analyze(
        self, repo_path: str,
    ) -> List[PatternScore]:
        """
        Analyze a repository and score all architecture patterns.

        Returns a list of PatternScore sorted by confidence (desc).
        """
        # Collect signals
        dirs = self._collect_dirs(repo_path)
        files = self._collect_files(repo_path)
        imports = self._collect_imports(repo_path, files)

        scores: List[PatternScore] = []
        scores.append(self._score_mvc(dirs, files, imports))
        scores.append(self._score_layered(dirs, files, imports))
        scores.append(self._score_microservices(dirs, files, imports))
        scores.append(self._score_event_driven(dirs, files, imports))
        scores.append(self._score_etl(dirs, files, imports))
        scores.append(self._score_cqrs(dirs, files, imports))
        scores.append(self._score_spa(dirs, files, imports))

        # Sort by confidence
        scores.sort(key=lambda s: -s.confidence)

        if self.verbose:
            print("[arch-recognizer] Pattern scores:")
            for s in scores:
                if s.confidence > 0:
                    print(f"  {s.pattern}: {s.confidence:.2f}")

        return scores

    def primary_pattern(
        self, scores: List[PatternScore],
    ) -> Optional[str]:
        """Return the highest-confidence pattern."""
        if scores and scores[0].confidence >= 0.2:
            return scores[0].pattern
        return None

    def analyze_from_kg(self, kg) -> List[PatternScore]:
        """
        Analyze architecture patterns from a Knowledge Graph.

        Uses node types, edge types, and service clusters
        instead of filesystem scanning.
        """
        scores: List[PatternScore] = []

        # Count relevant node types
        type_counts: Dict[str, int] = {}
        for node in kg.nodes.values():
            t = node.node_type
            type_counts[t] = type_counts.get(t, 0) + 1

        edge_types: Dict[str, int] = {}
        for edge in kg.edges:
            t = edge.relation
            edge_types[t] = edge_types.get(t, 0) + 1

        n_services = len(kg.service_clusters)
        n_controllers = type_counts.get("CONTROLLER", 0)
        n_repositories = type_counts.get("REPOSITORY", 0)
        n_services_nodes = type_counts.get("SERVICE", 0)
        n_react = type_counts.get("REACT_COMPONENT", 0)
        n_api = type_counts.get("API_ENDPOINT", 0)
        n_sql = type_counts.get("SQL_TABLE", 0)
        n_spark = type_counts.get("SPARK_JOB", 0)
        n_event_bus = type_counts.get("EVENT_BUS", 0)
        n_dataframe = type_counts.get("DATAFRAME", 0)
        n_layers = type_counts.get("DOMAIN_LAYER", 0)
        n_publish = edge_types.get("PUBLISHES_TO", 0) + edge_types.get("PRODUCES_EVENT", 0)
        n_subscribe = edge_types.get("SUBSCRIBES_FROM", 0) + edge_types.get("CONSUMES_EVENT", 0)

        # MVC
        mvc_conf = 0.0
        mvc_evidence = []
        if n_controllers > 0:
            mvc_conf += 0.3
            mvc_evidence.append(f"{n_controllers} controller(s)")
        if n_services_nodes > 0:
            mvc_conf += 0.2
        if n_repositories > 0:
            mvc_conf += 0.2
            mvc_evidence.append(f"{n_repositories} repository/ies")
        if n_sql > 0:
            mvc_conf += 0.1
        scores.append(PatternScore("MVC", min(1.0, mvc_conf), mvc_evidence))

        # Layered
        layered_conf = 0.0
        layered_evidence = []
        if n_layers > 0:
            layered_conf += 0.4
            layered_evidence.append(f"{n_layers} domain layer(s)")
        if n_controllers > 0 and n_services_nodes > 0 and n_repositories > 0:
            layered_conf += 0.3
            layered_evidence.append("Controller-Service-Repository stack")
        scores.append(PatternScore("Layered Architecture", min(1.0, layered_conf), layered_evidence))

        # Microservices
        micro_conf = 0.0
        micro_evidence = []
        if n_services > 3:
            micro_conf += 0.5
            micro_evidence.append(f"{n_services} service clusters")
        elif n_services > 1:
            micro_conf += 0.3
        if n_api > 3:
            micro_conf += 0.2
        if n_publish > 0 or n_subscribe > 0:
            micro_conf += 0.2
        scores.append(PatternScore("Microservices", min(1.0, micro_conf), micro_evidence))

        # Event-Driven
        event_conf = 0.0
        event_evidence = []
        if n_event_bus > 0:
            event_conf += 0.4
            event_evidence.append(f"{n_event_bus} event bus(es)")
        if n_publish > 0:
            event_conf += 0.3
            event_evidence.append(f"{n_publish} publish edge(s)")
        if n_subscribe > 0:
            event_conf += 0.2
        scores.append(PatternScore("Event-Driven", min(1.0, event_conf), event_evidence))

        # ETL
        etl_conf = 0.0
        etl_evidence = []
        if n_spark > 0:
            etl_conf += 0.4
            etl_evidence.append(f"{n_spark} Spark job(s)")
        if n_dataframe > 0:
            etl_conf += 0.3
            etl_evidence.append(f"{n_dataframe} DataFrame(s)")
        scores.append(PatternScore("ETL Pipeline", min(1.0, etl_conf), etl_evidence))

        # CQRS
        cqrs_conf = 0.0
        cqrs_evidence = []
        # CQRS is harder to detect from KG alone
        if n_event_bus > 0 and n_repositories > 0:
            cqrs_conf += 0.3
            cqrs_evidence.append("Event bus + repositories")
        scores.append(PatternScore("CQRS", min(1.0, cqrs_conf), cqrs_evidence))

        # SPA
        spa_conf = 0.0
        spa_evidence = []
        if n_react > 3:
            spa_conf += 0.5
            spa_evidence.append(f"{n_react} React component(s)")
        if n_api > 0 and n_react > 0:
            spa_conf += 0.2
        scores.append(PatternScore("SPA", min(1.0, spa_conf), spa_evidence))

        scores.sort(key=lambda s: -s.confidence)

        if self.verbose:
            print("[arch-recognizer] KG-based pattern scores:")
            for s in scores:
                if s.confidence > 0:
                    print(f"  {s.pattern}: {s.confidence:.2f}")

        return scores

    # ══════════════════════════════════════════════════════════
    #  FILESYSTEM-BASED SCORING
    # ══════════════════════════════════════════════════════════

    def _score_mvc(
        self, dirs: Set[str], files: List[str], imports: Set[str],
    ) -> PatternScore:
        conf = 0.0
        evidence = []

        # MVC directory markers
        mvc_dirs = {"controllers", "views", "models", "templates"}
        hits = dirs & mvc_dirs
        if len(hits) >= 2:
            conf += 0.4
            evidence.append(f"Directories: {', '.join(hits)}")

        # File naming: *_controller.*, *_view.*, *_model.*
        ctrl_files = [f for f in files if "controller" in f.lower()]
        view_files = [f for f in files if "view" in f.lower()]
        if ctrl_files:
            conf += 0.2
            evidence.append(f"{len(ctrl_files)} controller file(s)")
        if view_files:
            conf += 0.1

        # Framework imports
        if "django" in imports or "rails" in imports:
            conf += 0.2
            evidence.append("MVC framework detected")

        return PatternScore("MVC", min(1.0, conf), evidence)

    def _score_layered(
        self, dirs: Set[str], files: List[str], imports: Set[str],
    ) -> PatternScore:
        conf = 0.0
        evidence = []

        layer_dirs = {
            "presentation", "application", "domain",
            "infrastructure", "persistence", "service",
            "repository", "api", "core",
        }
        hits = dirs & layer_dirs
        if len(hits) >= 3:
            conf += 0.5
            evidence.append(f"Layer directories: {', '.join(hits)}")
        elif len(hits) >= 2:
            conf += 0.3

        # Service/Repository pattern
        svc_files = [f for f in files if "service" in f.lower()]
        repo_files = [f for f in files if "repository" in f.lower()]
        if svc_files and repo_files:
            conf += 0.2
            evidence.append("Service + Repository layers")

        return PatternScore("Layered Architecture", min(1.0, conf), evidence)

    def _score_microservices(
        self, dirs: Set[str], files: List[str], imports: Set[str],
    ) -> PatternScore:
        conf = 0.0
        evidence = []

        # Docker / K8s signals
        docker_files = [
            f for f in files
            if "dockerfile" in f.lower()
            or "docker-compose" in f.lower()
        ]
        k8s_files = [
            f for f in files
            if any(kw in f.lower() for kw in (
                "deployment.yaml", "service.yaml", "helm",
                "k8s", "kubernetes",
            ))
        ]

        if docker_files:
            conf += 0.2
            evidence.append(f"{len(docker_files)} Docker file(s)")
        if k8s_files:
            conf += 0.3
            evidence.append(f"{len(k8s_files)} K8s config(s)")

        # Multiple service directories
        potential_services = dirs & {
            "gateway", "auth", "user", "payment",
            "notification", "order", "inventory",
            "api-gateway", "service-a", "service-b",
        }
        if len(potential_services) >= 2:
            conf += 0.3

        # Proto / gRPC
        proto_files = [f for f in files if f.endswith(".proto")]
        if proto_files:
            conf += 0.2
            evidence.append("gRPC proto files")

        return PatternScore("Microservices", min(1.0, conf), evidence)

    def _score_event_driven(
        self, dirs: Set[str], files: List[str], imports: Set[str],
    ) -> PatternScore:
        conf = 0.0
        evidence = []

        event_imports = {"kafka", "rabbitmq", "celery", "nats", "redis", "eventbridge"}
        hits = imports & event_imports
        if hits:
            conf += 0.4
            evidence.append(f"Event imports: {', '.join(hits)}")

        event_files = [
            f for f in files
            if any(kw in f.lower() for kw in (
                "event", "handler", "consumer", "producer",
                "subscriber", "publisher", "listener",
            ))
        ]
        if event_files:
            conf += 0.3
            evidence.append(f"{len(event_files)} event-related file(s)")

        return PatternScore("Event-Driven", min(1.0, conf), evidence)

    def _score_etl(
        self, dirs: Set[str], files: List[str], imports: Set[str],
    ) -> PatternScore:
        conf = 0.0
        evidence = []

        etl_imports = {"pyspark", "airflow", "luigi", "dbt", "pandas", "polars"}
        hits = imports & etl_imports
        if hits:
            conf += 0.4
            evidence.append(f"ETL imports: {', '.join(hits)}")

        pipeline_dirs = dirs & {"pipelines", "etl", "dags", "transformations"}
        if pipeline_dirs:
            conf += 0.3
            evidence.append(f"Pipeline directories: {', '.join(pipeline_dirs)}")

        return PatternScore("ETL Pipeline", min(1.0, conf), evidence)

    def _score_cqrs(
        self, dirs: Set[str], files: List[str], imports: Set[str],
    ) -> PatternScore:
        conf = 0.0
        evidence = []

        cqrs_dirs = dirs & {"commands", "queries", "handlers", "read_models", "write_models"}
        if len(cqrs_dirs) >= 2:
            conf += 0.5
            evidence.append(f"CQRS directories: {', '.join(cqrs_dirs)}")

        cqrs_files = [
            f for f in files
            if any(kw in f.lower() for kw in ("command", "query", "handler"))
        ]
        if len(cqrs_files) >= 3:
            conf += 0.3
            evidence.append(f"{len(cqrs_files)} CQRS file(s)")

        return PatternScore("CQRS", min(1.0, conf), evidence)

    def _score_spa(
        self, dirs: Set[str], files: List[str], imports: Set[str],
    ) -> PatternScore:
        conf = 0.0
        evidence = []

        spa_imports = {"react", "vue", "angular", "svelte", "next", "nuxt"}
        hits = imports & spa_imports
        if hits:
            conf += 0.4
            evidence.append(f"SPA frameworks: {', '.join(hits)}")

        component_files = [
            f for f in files
            if f.endswith((".jsx", ".tsx", ".vue", ".svelte"))
        ]
        if component_files:
            conf += 0.3
            evidence.append(f"{len(component_files)} component file(s)")

        if "components" in dirs:
            conf += 0.1

        return PatternScore("SPA", min(1.0, conf), evidence)

    # ══════════════════════════════════════════════════════════
    #  SIGNAL COLLECTORS
    # ══════════════════════════════════════════════════════════

    def _collect_dirs(self, repo_path: str) -> Set[str]:
        """Collect all directory names (lowercase)."""
        dirs = set()
        for entry in os.listdir(repo_path):
            if os.path.isdir(os.path.join(repo_path, entry)):
                if not entry.startswith("."):
                    dirs.add(entry.lower())

        # Recurse one level
        for entry in dirs.copy():
            subpath = os.path.join(repo_path, entry)
            if os.path.isdir(subpath):
                for sub in os.listdir(subpath):
                    if os.path.isdir(os.path.join(subpath, sub)):
                        if not sub.startswith("."):
                            dirs.add(sub.lower())
        return dirs

    def _collect_files(self, repo_path: str) -> List[str]:
        """Collect all file basenames."""
        files = []
        for dirpath, _, filenames in os.walk(repo_path):
            rel = os.path.relpath(dirpath, repo_path)
            if any(
                skip in rel
                for skip in (
                    "node_modules", "venv", ".git",
                    "__pycache__", "dist",
                )
            ):
                continue
            for f in filenames:
                files.append(f)
        return files

    def _collect_imports(
        self, repo_path: str, files: List[str],
    ) -> Set[str]:
        """Collect top-level import module names."""
        imports = set()
        limit = 100  # Only scan first 100 files

        count = 0
        for dirpath, _, filenames in os.walk(repo_path):
            rel = os.path.relpath(dirpath, repo_path)
            if any(
                skip in rel
                for skip in (
                    "node_modules", "venv", ".git",
                    "__pycache__",
                )
            ):
                continue
            for fname in filenames:
                if count >= limit:
                    break
                if not fname.endswith((".py", ".js", ".ts")):
                    continue
                count += 1
                try:
                    fpath = os.path.join(dirpath, fname)
                    with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                        for line in f:
                            # Python: from X import ... / import X
                            m = re.match(
                                r'(?:from|import)\s+(\w+)', line,
                            )
                            if m:
                                imports.add(m.group(1).lower())
                            # JS: require("X") / from "X"
                            m2 = re.search(
                                r'(?:require|from)\s*\(?["\'](\w+)',
                                line,
                            )
                            if m2:
                                imports.add(m2.group(1).lower())
                except Exception:
                    pass

        return imports
