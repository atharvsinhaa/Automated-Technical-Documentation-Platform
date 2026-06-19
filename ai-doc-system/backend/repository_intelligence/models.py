from dataclasses import dataclass, field
from typing import List, Dict


@dataclass
class FrameworkInfo:
    name: str
    confidence: float


@dataclass
class EntrypointInfo:
    file_path: str
    type: str


@dataclass
class RepositoryProfile:
    repository_name: str

    languages: List[str] = field(default_factory=list)

    frameworks: List[FrameworkInfo] = field(default_factory=list)

    entrypoints: List[EntrypointInfo] = field(default_factory=list)

    databases: List[str] = field(default_factory=list)

    api_frameworks: List[str] = field(default_factory=list)

    frontend_frameworks: List[str] = field(default_factory=list)

    ml_frameworks: List[str] = field(default_factory=list)

    infrastructure: List[str] = field(default_factory=list)

    detected_patterns: List[str] = field(default_factory=list)

    repository_type: str = "Unknown"
    detected_modules: List[str] = field(default_factory=list)
    metadata: Dict = field(default_factory=dict)